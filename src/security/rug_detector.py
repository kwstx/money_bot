import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from src.security.schemas import (
    ContractScanResult,
    OwnershipEvaluation,
    HoneypotSimulationResult,
    LPLockDetails,
    HolderConcentration,
    RugRiskReport,
)

logger = logging.getLogger(__name__)


class RugDetector:
    """
    Rug Pull Detection Engine and Automated Execution Gatekeeper.
    Combines contract permissions, LP control, unlock timing, holder concentration,
    developer behavior, treasury movements, transaction anomalies, and liquidity changes.
    Escalates risk immediately upon detecting sudden LP removal, privileged contract changes,
    developer dumps, or coordinated distributions, blocking automated execution workflows.
    """

    def evaluate_rug_risk(
        self,
        token_address: str,
        chain: str,
        scan_result: Optional[ContractScanResult] = None,
        ownership_eval: Optional[OwnershipEvaluation] = None,
        honeypot_res: Optional[HoneypotSimulationResult] = None,
        lp_details: Optional[LPLockDetails] = None,
        concentration: Optional[HolderConcentration] = None,
        dev_activity: Optional[Dict[str, Any]] = None,
        recent_txs: Optional[List[Dict[str, Any]]] = None,
        override_signals: Optional[Dict[str, Any]] = None
    ) -> RugRiskReport:
        """
        Evaluates rug pull probability by integrating contract permissions, LP liquidity locks,
        holder concentration, dev wallet activities, and real-time transaction anomalies.
        """
        logger.info(f"Evaluating rug risk for token {token_address} on chain {chain}")

        dev_activity = dev_activity or {}
        recent_txs = recent_txs or []
        override_signals = override_signals or {}

        # 1. Critical Anomalies / Real-time Threat Escalations
        sudden_lp_removal = bool(
            dev_activity.get("lp_removed") or
            override_signals.get("sudden_lp_removal_detected") or
            self._detect_lp_removal_event(recent_txs)
        )

        privileged_contract_change = bool(
            dev_activity.get("admin_changed") or
            override_signals.get("privileged_contract_change_detected") or
            self._detect_privileged_change_event(recent_txs)
        )

        developer_sell = bool(
            dev_activity.get("dev_sold") or
            override_signals.get("developer_sell_detected") or
            self._detect_dev_sell_event(recent_txs)
        )

        coordinated_distribution = bool(
            dev_activity.get("sybil_distribution") or
            override_signals.get("coordinated_distribution_detected") or
            self._detect_coordinated_distribution(recent_txs)
        )

        # 2. Risk Sub-scores Computation
        permissions_risk = self._compute_permissions_risk(scan_result)
        ownership_risk = self._compute_ownership_risk(ownership_eval)
        honeypot_risk = honeypot_res.overall_honeypot_risk_score if honeypot_res else 0.0
        lp_risk = self._compute_lp_risk(lp_details)
        concentration_risk = self._compute_concentration_risk(concentration)
        dev_behavior_risk = self._compute_dev_behavior_risk(dev_activity)

        risk_breakdown = {
            "permissions_risk": permissions_risk,
            "ownership_risk": ownership_risk,
            "honeypot_risk": honeypot_risk,
            "lp_risk": lp_risk,
            "concentration_risk": concentration_risk,
            "dev_behavior_risk": dev_behavior_risk
        }

        # Weighted aggregate base risk score
        weighted_score = (
            permissions_risk * 0.20 +
            ownership_risk * 0.15 +
            honeypot_risk * 0.25 +
            lp_risk * 0.20 +
            concentration_risk * 0.10 +
            dev_behavior_risk * 0.10
        )

        blocking_reasons = []
        block_execution = False

        # 3. Trigger Immediate Risk Escalation & Block Execution
        if sudden_lp_removal:
            block_execution = True
            blocking_reasons.append("CRITICAL THREAT: Sudden LP Removal Event detected.")

        if privileged_contract_change:
            block_execution = True
            blocking_reasons.append("CRITICAL THREAT: Privileged contract logic or fee modification detected.")

        if developer_sell:
            block_execution = True
            blocking_reasons.append("CRITICAL THREAT: Developer/Deployer dumped supply into liquidity pool.")

        if coordinated_distribution:
            block_execution = True
            blocking_reasons.append("CRITICAL THREAT: Coordinated supply distribution to sybil wallet cluster detected.")

        if honeypot_res and (honeypot_res.is_honeypot or honeypot_res.simulation_failed):
            block_execution = True
            blocking_reasons.append(f"CRITICAL THREAT: Honeypot or simulation failure: {honeypot_res.honeypot_reason}")

        if ownership_eval and ownership_eval.is_fake_renouncement:
            block_execution = True
            blocking_reasons.append("HIGH THREAT: Bypassed/Fake ownership renouncement detected.")

        if lp_details and not lp_details.is_lp_locked and lp_details.lock_percentage < 20.0:
            blocking_reasons.append("HIGH THREAT: Liquidity is unlocked or lock percentage is below 20%.")
            if weighted_score > 60.0:
                block_execution = True

        if block_execution:
            rug_risk_score = max(95.0, weighted_score)
            risk_level = "CRITICAL"
        else:
            rug_risk_score = min(100.0, weighted_score)
            if rug_risk_score >= 75.0:
                risk_level = "CRITICAL"
                block_execution = True
                blocking_reasons.append("Composite rug risk score exceeded CRITICAL threshold (75.0+).")
            elif rug_risk_score >= 50.0:
                risk_level = "HIGH"
            elif rug_risk_score >= 25.0:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"

        return RugRiskReport(
            token_address=token_address,
            chain=chain,
            rug_risk_score=round(rug_risk_score, 2),
            risk_level=risk_level,
            sudden_lp_removal_detected=sudden_lp_removal,
            privileged_contract_change_detected=privileged_contract_change,
            developer_sell_detected=developer_sell,
            coordinated_distribution_detected=coordinated_distribution,
            block_execution=block_execution,
            execution_blocking_reasons=blocking_reasons,
            risk_breakdown=risk_breakdown
        )

    def _compute_permissions_risk(self, scan_result: Optional[ContractScanResult]) -> float:
        if not scan_result:
            return 20.0
        p = scan_result.permissions
        score = 0.0
        if p.can_mint:
            score += 35.0
        if p.can_modify_balances:
            score += 40.0
        if p.can_blacklist or p.can_freeze:
            score += 20.0
        if p.can_alter_fees:
            score += 15.0
        if p.can_upgrade_logic:
            score += 20.0
        return min(100.0, score)

    def _compute_ownership_risk(self, ownership_eval: Optional[OwnershipEvaluation]) -> float:
        if not ownership_eval:
            return 20.0
        if ownership_eval.is_fake_renouncement:
            return 90.0
        if ownership_eval.governance_type == "EOA":
            return 50.0
        if ownership_eval.governance_type == "MULTISIG_GNOSIS":
            return 20.0
        if ownership_eval.governance_type == "TIMELOCK_CONTROLLER":
            return 10.0
        if ownership_eval.governance_type == "RENOUNCED":
            return 0.0
        return 30.0

    def _compute_lp_risk(self, lp_details: Optional[LPLockDetails]) -> float:
        if not lp_details:
            return 50.0 # Unknown LP status
        if not lp_details.is_lp_locked:
            return 95.0
        if lp_details.lock_percentage < 50.0:
            return 70.0
        if lp_details.lock_duration_remaining_seconds and lp_details.lock_duration_remaining_seconds < 86400 * 3:
            return 85.0 # Unlock in under 3 days
        return max(0.0, 100.0 - lp_details.lock_percentage)

    def _compute_concentration_risk(self, concentration: Optional[HolderConcentration]) -> float:
        if not concentration:
            return 20.0
        score = 0.0
        if concentration.top10_percentage > 70.0:
            score += 50.0
        elif concentration.top10_percentage > 40.0:
            score += 25.0

        if concentration.dev_wallet_percentage > 20.0:
            score += 45.0
        elif concentration.dev_wallet_percentage > 5.0:
            score += 20.0

        return min(100.0, score)

    def _compute_dev_behavior_risk(self, dev_activity: Dict[str, Any]) -> float:
        score = 0.0
        if dev_activity.get("interacted_with_mixer"):
            score += 40.0
        if dev_activity.get("funded_by_cex_fresh"):
            score += 15.0
        if dev_activity.get("recent_transfers_to_cex"):
            score += 30.0
        return min(100.0, score)

    def _detect_lp_removal_event(self, recent_txs: List[Dict[str, Any]]) -> bool:
        for tx in recent_txs:
            if tx.get("event") in ("RemoveLiquidity", "RemoveLiquidityETH", "BurnLP") or tx.get("method") == "removeLiquidity":
                return True
        return False

    def _detect_privileged_change_event(self, recent_txs: List[Dict[str, Any]]) -> bool:
        for tx in recent_txs:
            if tx.get("event") in ("FeeUpdated", "ImplementationUpgraded", "OwnershipTransferred", "TradingPaused"):
                return True
        return False

    def _detect_dev_sell_event(self, recent_txs: List[Dict[str, Any]]) -> bool:
        for tx in recent_txs:
            if tx.get("is_dev_wallet") and tx.get("type") == "sell":
                return True
        return False

    def _detect_coordinated_distribution(self, recent_txs: List[Dict[str, Any]]) -> bool:
        for tx in recent_txs:
            if tx.get("is_sybil_distribution") or tx.get("event") == "BatchTransfer":
                return True
        return False

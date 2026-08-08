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
    ComprehensiveSecurityAssessment,
)
from src.security.contract_scanner import ContractScanner
from src.security.ownership_system import OwnershipSystem
from src.security.honeypot_engine import HoneypotEngine
from src.security.rug_detector import RugDetector

logger = logging.getLogger(__name__)


class SectionSevenSecurityEngine:
    """
    Unified Orchestrator for Section 7:
    Contract Security, Ownership, Permissions, Honeypots, and Rug Detection.
    
    Integrates:
    1. Contract Scanner & Administrative Permission Analyzer
    2. Ownership & Governance System (Renouncement, Proxy Upgradeability, & Fake Renouncement Detection)
    3. Honeypot Engine (Multivariant Simulation, Dynamic/Wallet Taxes, & Simulation Failure Escalation)
    4. Rug Detector & Real-time Execution Gatekeeper
    """

    def __init__(
        self,
        scanner: Optional[ContractScanner] = None,
        ownership_system: Optional[OwnershipSystem] = None,
        honeypot_engine: Optional[HoneypotEngine] = None,
        rug_detector: Optional[RugDetector] = None
    ):
        self.scanner = scanner or ContractScanner()
        self.ownership_system = ownership_system or OwnershipSystem()
        self.honeypot_engine = honeypot_engine or HoneypotEngine()
        self.rug_detector = rug_detector or RugDetector()

    def scan_contract(
        self,
        token_address: str,
        chain: str,
        bytecode: Optional[str] = None,
        source_code: Optional[str] = None,
        abi: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ContractScanResult:
        """Scans contract bytecode, ABI, verified source code, proxy relations, and permissions."""
        return self.scanner.scan_contract(
            token_address=token_address,
            chain=chain,
            bytecode=bytecode,
            source_code=source_code,
            abi=abi,
            metadata=metadata
        )

    def evaluate_ownership(
        self,
        token_address: str,
        chain: str,
        scan_result: Optional[ContractScanResult] = None,
        contract_code: Optional[str] = None,
        tx_history: Optional[List[Dict[str, Any]]] = None,
        override_metadata: Optional[Dict[str, Any]] = None
    ) -> OwnershipEvaluation:
        """Evaluates owner status, renouncement validity, proxy upgradeability, and backdoor risks."""
        return self.ownership_system.analyze_ownership(
            token_address=token_address,
            chain=chain,
            scan_result=scan_result,
            contract_code=contract_code,
            tx_history=tx_history,
            override_metadata=override_metadata
        )

    def simulate_honeypot(
        self,
        token_address: str,
        chain: str,
        pool_liquidity_usd: Optional[float] = None,
        advertised_buy_tax: Optional[float] = None,
        advertised_sell_tax: Optional[float] = None,
        observed_transactions: Optional[List[Dict[str, Any]]] = None,
        simulation_override: Optional[Dict[str, Any]] = None
    ) -> HoneypotSimulationResult:
        """Simulates buys/sells across wallet personas, estimates taxes, and detects honeypots."""
        return self.honeypot_engine.simulate_honeypot(
            token_address=token_address,
            chain=chain,
            pool_liquidity_usd=pool_liquidity_usd,
            advertised_buy_tax=advertised_buy_tax,
            advertised_sell_tax=advertised_sell_tax,
            observed_transactions=observed_transactions,
            simulation_override=simulation_override
        )

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
        """Calculates composite rug risk and triggers automated execution gatekeeper decisions."""
        return self.rug_detector.evaluate_rug_risk(
            token_address=token_address,
            chain=chain,
            scan_result=scan_result,
            ownership_eval=ownership_eval,
            honeypot_res=honeypot_res,
            lp_details=lp_details,
            concentration=concentration,
            dev_activity=dev_activity,
            recent_txs=recent_txs,
            override_signals=override_signals
        )

    def run_comprehensive_security_assessment(
        self,
        token_address: str,
        chain: str,
        bytecode: Optional[str] = None,
        source_code: Optional[str] = None,
        abi: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tx_history: Optional[List[Dict[str, Any]]] = None,
        observed_transactions: Optional[List[Dict[str, Any]]] = None,
        lp_details: Optional[LPLockDetails] = None,
        concentration: Optional[HolderConcentration] = None,
        dev_activity: Optional[Dict[str, Any]] = None,
        recent_txs: Optional[List[Dict[str, Any]]] = None,
        simulation_override: Optional[Dict[str, Any]] = None,
        override_signals: Optional[Dict[str, Any]] = None
    ) -> ComprehensiveSecurityAssessment:
        """Runs complete end-to-end Section 7 Contract Security & Risk Analysis."""
        scan_res = self.scan_contract(
            token_address=token_address,
            chain=chain,
            bytecode=bytecode,
            source_code=source_code,
            abi=abi,
            metadata=metadata
        )

        ownership_res = self.evaluate_ownership(
            token_address=token_address,
            chain=chain,
            scan_result=scan_res,
            contract_code=source_code,
            tx_history=tx_history,
            override_metadata=metadata
        )

        honeypot_res = self.simulate_honeypot(
            token_address=token_address,
            chain=chain,
            pool_liquidity_usd=metadata.get("pool_liquidity_usd") if metadata else None,
            advertised_buy_tax=metadata.get("buy_tax") if metadata else None,
            advertised_sell_tax=metadata.get("sell_tax") if metadata else None,
            observed_transactions=observed_transactions,
            simulation_override=simulation_override
        )

        rug_res = self.evaluate_rug_risk(
            token_address=token_address,
            chain=chain,
            scan_result=scan_res,
            ownership_eval=ownership_res,
            honeypot_res=honeypot_res,
            lp_details=lp_details,
            concentration=concentration,
            dev_activity=dev_activity,
            recent_txs=recent_txs,
            override_signals=override_signals
        )

        is_safe = not rug_res.block_execution and rug_res.rug_risk_score < 50.0 and not honeypot_res.is_honeypot
        summary = (
            f"Risk Level: {rug_res.risk_level} (Score: {rug_res.rug_risk_score}/100). "
            f"Honeypot: {'YES' if honeypot_res.is_honeypot else 'NO'}. "
            f"Execution Blocked: {'YES' if rug_res.block_execution else 'NO'}."
        )

        return ComprehensiveSecurityAssessment(
            token_address=token_address,
            chain=chain,
            contract_scan=scan_res,
            ownership_eval=ownership_res,
            honeypot_res=honeypot_res,
            rug_report=rug_res,
            is_safe_for_trading=is_safe,
            summary=summary
        )

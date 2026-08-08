import logging
import math
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from src.intelligence.schemas import DecodedTransaction
from src.intelligence.wallet.schemas import WalletProfile
from src.intelligence.wallet.probabilistic_graph import ProbabilisticWalletGraphEngine
from src.intelligence.wallet.manipulation_schemas import (
    ManipulationPattern,
    TokenManipulationReport,
    DowngradeSignal
)

logger = logging.getLogger(__name__)

class InsiderAndManipulationEngine:
    """
    Identifies manipulation and insider risk patterns across on-chain activity:
    - Suspicious concentration & related-wallet clusters
    - Rapid funding chains
    - Coordinated launches & sniper groups
    - Bundled purchases (atomic/MEV/Jito bundles)
    - Artificial holder creation (sybil holder distribution)
    - Wash trading
    - Synchronized exits
    
    Generates structured DowngradeSignals feeding Security and Opportunity scoring systems
    so tokens with impressive price growth but suspicious ownership are downgraded immediately.
    """
    def __init__(self, high_concentration_threshold: float = 0.35):
        self.high_concentration_threshold = high_concentration_threshold

    def analyze_token_manipulation(
        self,
        token_address: str,
        chain: str,
        holder_profiles: List[WalletProfile],
        graph_engine: Optional[ProbabilisticWalletGraphEngine] = None,
        recent_transactions: Optional[List[DecodedTransaction]] = None,
        launch_timestamp: Optional[datetime] = None
    ) -> TokenManipulationReport:
        """
        Executes comprehensive manipulation and insider ownership analysis on a token.
        """
        tok = token_address.lower()
        now = datetime.now(timezone.utc)
        recent_txs = recent_transactions or []
        detected_patterns: List[ManipulationPattern] = []

        # 1. Suspicious Concentration & Related-Wallet Clusters
        total_cluster_supply_pct = 0.0
        top_cluster_sizes = []
        if graph_engine and holder_profiles:
            # Map wallet addresses to token balances
            balances = {p.address.lower(): p.positions.get(tok).current_balance if tok in p.positions else 0.0 for p in holder_profiles}
            total_held = sum(balances.values())
            
            # Find related clusters via probabilistic graph
            cluster_sets: List[Set[str]] = []
            visited = set()

            for p in holder_profiles:
                addr = p.address.lower()
                if addr in visited:
                    continue
                
                # Retrieve probabilistic relationships
                rels = graph_engine.get_all_relationships_for_wallet(addr)
                cluster = {addr}
                visited.add(addr)
                
                for r in rels:
                    if r.probability >= 0.60:
                        peer = r.target_address if r.source_address == addr else r.source_address
                        cluster.add(peer)
                        visited.add(peer)
                
                if len(cluster) > 1:
                    cluster_sets.append(cluster)

            for c in cluster_sets:
                top_cluster_sizes.append(len(c))
                cluster_bal = sum(balances.get(w, 0.0) for w in c)
                if total_held > 0:
                    conc_ratio = cluster_bal / total_held
                    total_cluster_supply_pct += conc_ratio
                    if conc_ratio >= 0.20:
                        detected_patterns.append(ManipulationPattern(
                            pattern_type="INSIDER_CLUSTER",
                            severity="HIGH" if conc_ratio >= 0.35 else "MEDIUM",
                            confidence=0.90,
                            participating_wallets=list(c),
                            description=f"Related wallet cluster controls {conc_ratio*100:.1f}% of tracked token supply",
                            details={"cluster_size": len(c), "concentration_ratio": round(conc_ratio, 4)}
                        ))

        # 2. Coordinated Launches & Sniper Groups
        if launch_timestamp and recent_txs:
            snipers = []
            for tx in recent_txs:
                if tx.action_type in ["SWAP", "MINT"] and tx.timestamp:
                    seconds_from_launch = (tx.timestamp - launch_timestamp).total_seconds()
                    if 0 <= seconds_from_launch <= 30.0:  # within 30s of launch
                        snipers.append(tx.sender.lower())
            
            if len(snipers) >= 3:
                detected_patterns.append(ManipulationPattern(
                    pattern_type="SNIPER_GROUP",
                    severity="HIGH",
                    confidence=0.95,
                    participating_wallets=list(set(snipers)),
                    description=f"{len(snipers)} wallets executed purchases within 30s of token deployment",
                    details={"sniper_count": len(snipers)}
                ))

        # 3. Bundled Purchases (MEV / Atomic Bundles)
        if recent_txs:
            timestamp_groups = defaultdict(list)
            for tx in recent_txs:
                if tx.action_type == "SWAP" and tx.timestamp:
                    ts_key = tx.timestamp.isoformat()
                    timestamp_groups[ts_key].append(tx)
            
            for ts_str, tx_list in timestamp_groups.items():
                if len(tx_list) >= 3:
                    senders = [tx.sender.lower() for tx in tx_list]
                    detected_patterns.append(ManipulationPattern(
                        pattern_type="BUNDLED_PURCHASE",
                        severity="MEDIUM",
                        confidence=0.85,
                        participating_wallets=list(set(senders)),
                        description=f"Atomic bundle execution detected: {len(tx_list)} buy transactions in exact same block/timestamp",
                        details={"timestamp": ts_str, "bundle_size": len(tx_list)}
                    ))
                    break

        # 4. Rapid Funding Chains
        if holder_profiles:
            funding_chains = []
            for p in holder_profiles:
                if p.funding_sources and tok in p.positions:
                    first_buy = p.positions[tok].first_buy_time
                    if first_buy:
                        for fs in p.funding_sources:
                            time_diff = (first_buy - fs.timestamp).total_seconds()
                            if 0 <= time_diff <= 300.0:  # funded < 5 mins prior to first buy
                                funding_chains.append(p.address.lower())

            if len(funding_chains) >= 2:
                detected_patterns.append(ManipulationPattern(
                    pattern_type="RAPID_FUNDING_CHAIN",
                    severity="HIGH",
                    confidence=0.90,
                    participating_wallets=list(set(funding_chains)),
                    description=f"Rapid pass-through funding detected for {len(funding_chains)} wallets within 5 mins of trading",
                    details={"wallet_count": len(funding_chains)}
                ))

        # 5. Artificial Holder Creation (Sybil Holder Dusting)
        if holder_profiles:
            dust_wallets = []
            for p in holder_profiles:
                # If wallet has 1 trade, < 2 transactions total, and tiny balance
                pos = p.positions.get(tok)
                if pos and pos.trades_count == 1 and p.behavior.swap_count <= 2:
                    dust_wallets.append(p.address.lower())

            if len(holder_profiles) >= 10 and (len(dust_wallets) / len(holder_profiles)) >= 0.50:
                detected_patterns.append(ManipulationPattern(
                    pattern_type="ARTIFICIAL_HOLDERS",
                    severity="MEDIUM",
                    confidence=0.80,
                    participating_wallets=dust_wallets[:10],  # sample
                    description=f"High proportion of single-trade artificial wallets ({len(dust_wallets)}/{len(holder_profiles)})",
                    details={"dust_wallet_count": len(dust_wallets), "total_holders": len(holder_profiles)}
                ))

        # 6. Wash Trading Detection (Self-swaps or reciprocal transfers)
        if recent_txs:
            trade_pairs = defaultdict(int)
            for tx in recent_txs:
                if tx.sender and tx.receiver:
                    pair = tuple(sorted([tx.sender.lower(), tx.receiver.lower()]))
                    trade_pairs[pair] += 1
            
            wash_pairs = [pair for pair, count in trade_pairs.items() if count >= 4]
            if wash_pairs:
                flat_wallets = list({w for p in wash_pairs for w in p})
                detected_patterns.append(ManipulationPattern(
                    pattern_type="WASH_TRADING",
                    severity="HIGH",
                    confidence=0.92,
                    participating_wallets=flat_wallets,
                    description=f"Wash trading circular transaction pattern detected between {len(wash_pairs)} wallet pair(s)",
                    details={"wash_pairs_count": len(wash_pairs)}
                ))

        # Calculate Overall Manipulation Score (0 - 100)
        base_score = 0.0
        for p in detected_patterns:
            if p.severity == "HIGH":
                base_score += 30.0 * p.confidence
            elif p.severity == "MEDIUM":
                base_score += 15.0 * p.confidence
            else:
                base_score += 5.0 * p.confidence

        overall_score = round(min(100.0, base_score), 2)
        insider_ratio = round(min(1.0, total_cluster_supply_pct), 4)

        return TokenManipulationReport(
            token_address=tok,
            chain=chain,
            overall_manipulation_score=overall_score,
            insider_concentration_ratio=insider_ratio,
            detected_patterns=detected_patterns,
            top_cluster_sizes=top_cluster_sizes,
            assessed_at=now
        )

    def generate_score_downgrade_signals(self, report: TokenManipulationReport) -> DowngradeSignal:
        """
        Feeds both Security & Opportunity scoring engines to IMMEDIATELY downgrade tokens
        with impressive price growth but suspicious ownership or manipulation patterns.
        """
        score = report.overall_manipulation_score
        insider_ratio = report.insider_concentration_ratio

        # Determine risk multiplier and penalty points
        if score >= 60.0 or insider_ratio >= 0.40:
            security_multiplier = 3.0  # 3x risk increase
            opportunity_penalty = 50.0 # -50 pts from opportunity score
            reason = f"CRITICAL: Heavy manipulation ({score}/100) and insider concentration ({insider_ratio*100:.1f}%)"
            downgrade = True
        elif score >= 30.0 or insider_ratio >= 0.20:
            security_multiplier = 1.8  # 1.8x risk increase
            opportunity_penalty = 25.0 # -25 pts
            reason = f"WARNING: Moderate manipulation patterns detected ({score}/100)"
            downgrade = True
        else:
            security_multiplier = 1.0
            opportunity_penalty = 0.0
            reason = "Organic ownership distribution; no significant manipulation detected."
            downgrade = False

        return DowngradeSignal(
            token_address=report.token_address,
            security_risk_multiplier=security_multiplier,
            opportunity_penalty_points=opportunity_penalty,
            reason=reason,
            manipulation_score=score,
            downgrade_recommended=downgrade,
            timestamp=datetime.now(timezone.utc)
        )

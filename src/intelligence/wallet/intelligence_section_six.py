import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone

from src.intelligence.schemas import DecodedTransaction
from src.intelligence.wallet.schemas import WalletProfile
from src.intelligence.wallet.probabilistic_graph import ProbabilisticWalletGraphEngine
from src.intelligence.wallet.smart_money import SmartMoneyPredictiveEngine
from src.intelligence.wallet.whale import WhaleMarketImpactEngine
from src.intelligence.wallet.manipulation import InsiderAndManipulationEngine
from src.intelligence.wallet.manipulation_schemas import (
    SmartMoneyEvaluation,
    WhaleMarketImpact,
    TokenManipulationReport,
    DowngradeSignal,
    ProbabilisticRelationship
)

logger = logging.getLogger(__name__)

class SectionSixIntelligenceEngine:
    """
    Unified Orchestrator for Section 6:
    Smart Money, Whale, Insider, Exchange, and Manipulation Intelligence.
    
    Brings together:
    1. Smart Money Predictive Skill vs Luck Engine
    2. Whale Executable Liquidity & Market Impact Engine
    3. Insider & Manipulation Detection Engine (with Security & Opportunity Downgrade Feeder)
    4. Probabilistic Graph Engine (Explicit Evidence-Backed Inference Limitation Modeling)
    """
    def __init__(
        self,
        smart_money_engine: Optional[SmartMoneyPredictiveEngine] = None,
        whale_engine: Optional[WhaleMarketImpactEngine] = None,
        manipulation_engine: Optional[InsiderAndManipulationEngine] = None,
        probabilistic_graph: Optional[ProbabilisticWalletGraphEngine] = None
    ):
        self.smart_money_engine = smart_money_engine or SmartMoneyPredictiveEngine()
        self.whale_engine = whale_engine or WhaleMarketImpactEngine()
        self.manipulation_engine = manipulation_engine or InsiderAndManipulationEngine()
        self.probabilistic_graph = probabilistic_graph or ProbabilisticWalletGraphEngine()

    def evaluate_smart_money(
        self,
        profile: WalletProfile,
        token_histories: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> SmartMoneyEvaluation:
        """Evaluates true Smart Money predictive skill vs luck against baseline cohorts."""
        return self.smart_money_engine.evaluate_predictive_skill(profile, token_histories)

    def analyze_whale_impact(
        self,
        wallet_address: str,
        token_address: str,
        token_balance: float,
        pool_liquidity_usd: float,
        token_price_usd: float,
        total_supply: float = 1_000_000.0,
        circulating_supply: Optional[float] = None
    ) -> WhaleMarketImpact:
        """Calculates Whale Executable Liquidity Impact and potential sell pressure."""
        return self.whale_engine.analyze_whale_position(
            wallet_address=wallet_address,
            token_address=token_address,
            token_balance=token_balance,
            pool_liquidity_usd=pool_liquidity_usd,
            token_price_usd=token_price_usd,
            total_supply=total_supply,
            circulating_supply=circulating_supply
        )

    def analyze_token_manipulation(
        self,
        token_address: str,
        chain: str,
        holder_profiles: List[WalletProfile],
        recent_transactions: Optional[List[DecodedTransaction]] = None,
        launch_timestamp: Optional[datetime] = None
    ) -> Tuple[TokenManipulationReport, DowngradeSignal]:
        """
        Analyzes manipulation patterns (snipers, MEV bundles, rapid funding, sybil holders, wash trading)
        and generates security/opportunity downgrade signals.
        """
        report = self.manipulation_engine.analyze_token_manipulation(
            token_address=token_address,
            chain=chain,
            holder_profiles=holder_profiles,
            graph_engine=self.probabilistic_graph,
            recent_transactions=recent_transactions,
            launch_timestamp=launch_timestamp
        )
        downgrade = self.manipulation_engine.generate_score_downgrade_signals(report)
        return report, downgrade

    def record_probabilistic_evidence(
        self,
        source: str,
        target: str,
        rel_type: str,
        evidence_type: str,
        weight: float,
        details: Optional[Dict[str, Any]] = None
    ) -> ProbabilisticRelationship:
        """Records evidence and updates probabilistic relationship model."""
        self.probabilistic_graph.add_evidence(
            source=source,
            target=target,
            rel_type=rel_type,
            evidence_type=evidence_type,
            weight=weight,
            details=details
        )
        return self.probabilistic_graph.evaluate_relationship(source, target, rel_type)

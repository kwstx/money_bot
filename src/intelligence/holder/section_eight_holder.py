import logging
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timezone

from src.intelligence.holder.schemas import (
    TokenTransferEvent,
    HistoricalOwnershipSnapshot,
    HolderVelocityAndRetention,
    OwnershipDistributionMetrics,
    HolderQualityMetrics,
    LiquidityOwnershipHealthView,
    SectionEightAnalysisReport,
    HolderCategory
)
from src.intelligence.holder.tracker import HolderTracker
from src.intelligence.holder.distribution import (
    HolderCategorizationEngine,
    OwnershipDistributionAnalyzer
)
from src.intelligence.holder.quality import HolderQualityEngine
from src.intelligence.holder.liquidity_ownership import LiquidityOwnershipHealthEngine

logger = logging.getLogger(__name__)


class SectionEightHolderIntelligenceEngine:
    """
    Unified Orchestrator for Section 8:
    Holder, Ownership, Distribution, and Liquidity Quality Intelligence.

    Integrates:
    1. Holder Balance Tracker & Snapshot Engine (Requirement 1)
    2. Wallet Categorization & Ownership Distribution Analyzer (Requirement 2)
    3. Holder Quality & Growth Trajectory Evaluator (Requirement 3)
    4. Integrated Liquidity & Ownership Market Health Engine (Requirement 4)
    """
    def __init__(
        self,
        token_address: str,
        initial_total_supply: float = 1_000_000_000.0,
        known_pools: Optional[Set[str]] = None,
        known_exchanges: Optional[Set[str]] = None,
        known_staking: Optional[Set[str]] = None,
        known_bridges: Optional[Set[str]] = None,
        known_treasury: Optional[Set[str]] = None,
        developer_addresses: Optional[Set[str]] = None,
        insider_addresses: Optional[Set[str]] = None,
        smart_money_addresses: Optional[Set[str]] = None
    ):
        self.token_address = token_address
        self.tracker = HolderTracker(
            token_address=token_address,
            initial_total_supply=initial_total_supply
        )
        self.categorizer = HolderCategorizationEngine(
            known_pools=known_pools,
            known_exchanges=known_exchanges,
            known_staking=known_staking,
            known_bridges=known_bridges,
            known_treasury=known_treasury,
            developer_addresses=developer_addresses,
            insider_addresses=insider_addresses,
            smart_money_addresses=smart_money_addresses
        )
        self.distribution_analyzer = OwnershipDistributionAnalyzer(categorizer=self.categorizer)
        self.quality_engine = HolderQualityEngine()
        self.health_engine = LiquidityOwnershipHealthEngine()

    def process_event(self, event: TokenTransferEvent) -> None:
        """Processes a token event (transfer, mint, burn, bridge, LP, contract) to update state."""
        self.tracker.process_event(event)

    def process_transfer_event(self, event: TokenTransferEvent) -> None:
        """Processes a token event (transfer, mint, burn, bridge, LP, contract) to update state."""
        self.process_event(event)

    def process_batch_events(self, events: List[TokenTransferEvent]) -> None:
        """Processes a list of events in batch."""
        for ev in events:
            self.process_event(ev)

    def mark_technical_account(self, address: str, category: HolderCategory) -> None:
        """Explicitly registers a technical wallet account (pool, exchange, burn, bridge, staking, treasury)."""
        self.tracker.mark_technical_account(address, category)

    def evaluate_token_holder_and_liquidity_quality(
        self,
        pool_liquidity_usd: float,
        token_price_usd: float,
        lp_locked_pct: float = 0.0,
        lp_lock_duration_days: float = 0.0,
        depth_1pct_usd: Optional[float] = None,
        depth_2pct_usd: Optional[float] = None,
        depth_5pct_usd: Optional[float] = None,
        current_time: Optional[datetime] = None
    ) -> SectionEightAnalysisReport:
        """
        Executes full Section 8 pipeline and generates unified analysis report.
        """
        now = current_time or datetime.now(timezone.utc)

        # 1. Take Snapshot & calculate velocity/retention
        snapshot = self.tracker.take_snapshot(timestamp=now)
        velocity_retention = self.tracker.calculate_velocity_and_retention(
            window_hours=24,
            current_time=now
        )

        # 2. Analyze Ownership Distribution
        distribution = self.distribution_analyzer.analyze_distribution(
            token_address=self.token_address,
            wallet_states=self.tracker.balances,
            total_supply=self.tracker.total_supply,
            current_time=now
        )

        # 3. Evaluate Holder Growth Quality & Trajectory
        quality = self.quality_engine.evaluate_quality(
            token_address=self.token_address,
            velocity_retention=velocity_retention,
            distribution_metrics=distribution,
            recent_events=self.tracker.event_log[-500:] if self.tracker.event_log else []
        )

        # 4. Evaluate Liquidity & Ownership Market Health View
        market_health = self.health_engine.evaluate_market_health(
            token_address=self.token_address,
            pool_liquidity_usd=pool_liquidity_usd,
            token_price_usd=token_price_usd,
            snapshot=snapshot,
            distribution=distribution,
            lp_locked_pct=lp_locked_pct,
            lp_lock_duration_days=lp_lock_duration_days,
            depth_1pct_usd=depth_1pct_usd,
            depth_2pct_usd=depth_2pct_usd,
            depth_5pct_usd=depth_5pct_usd
        )

        # 5. Composite Section 8 Score
        overall_score = (
            0.30 * quality.holder_quality_score +
            0.30 * market_health.overall_market_health_score +
            0.20 * distribution.wallet_diversity_index +
            0.20 * velocity_retention.retention_rate_pct
        )
        overall_score = float(max(0.0, min(100.0, overall_score)))

        return SectionEightAnalysisReport(
            token_address=self.token_address,
            timestamp=now,
            latest_snapshot=snapshot,
            velocity_retention=velocity_retention,
            distribution_metrics=distribution,
            quality_metrics=quality,
            market_health_view=market_health,
            overall_section_eight_score=overall_score
        )

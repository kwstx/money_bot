import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
import uuid

from ..discovery.schemas import (
    LaunchMetrics,
    MilestoneEvent,
    MilestoneType,
    UnifiedChainEvent,
    EventType,
)
from ..publisher import publisher

logger = logging.getLogger(__name__)

class NewLaunchDetector:
    """
    New Launch Detector.
    Tracks launch metrics, detects milestone events, and publishes alerts.
    """

    def __init__(self, liquidity_increase_threshold: float = 1.5, whale_buy_usd_threshold: float = 5000.0):
        self.metrics_store: Dict[str, LaunchMetrics] = {}
        self.milestones_history: Dict[str, List[MilestoneEvent]] = {}
        self.liquidity_increase_threshold = liquidity_increase_threshold
        self.whale_buy_usd_threshold = whale_buy_usd_threshold

    def register_launch(self, token_address: str, chain: str, deployment_time: Optional[datetime] = None) -> LaunchMetrics:
        key = f"{chain}:{token_address.lower()}"
        now = datetime.now(timezone.utc)
        start_time = deployment_time or now

        metrics = LaunchMetrics(
            token_address=token_address,
            chain=chain,
            launch_time=start_time,
            launch_age_seconds=0.0,
            time_to_liquidity_seconds=0.0,
            initial_liquidity_usd=0.0,
            current_liquidity_usd=0.0,
            initial_volume_usd=0.0,
            holder_count=0,
            first_buyers=[],
            top10_holder_concentration_pct=0.0,
            buy_count=0,
            sell_count=0,
            buy_sell_ratio=1.0,
            buy_velocity_per_min=0.0,
            bot_transaction_ratio=0.0,
            contract_risk_score=0.0,
            updated_at=now
        )
        self.metrics_store[key] = metrics
        self.milestones_history[key] = []
        return metrics

    async def update_liquidity(self, token_address: str, chain: str, liquidity_usd: float, timestamp: Optional[datetime] = None) -> Optional[MilestoneEvent]:
        key = f"{chain}:{token_address.lower()}"
        metrics = self.metrics_store.get(key)
        if not metrics:
            metrics = self.register_launch(token_address, chain, timestamp)

        now = timestamp or datetime.now(timezone.utc)
        metrics.launch_age_seconds = (now - metrics.launch_time).total_seconds()

        milestone_event = None
        if metrics.initial_liquidity_usd == 0.0 and liquidity_usd > 0.0:
            metrics.initial_liquidity_usd = liquidity_usd
            metrics.current_liquidity_usd = liquidity_usd
            metrics.time_to_liquidity_seconds = metrics.launch_age_seconds
        else:
            prev_liquidity = metrics.current_liquidity_usd
            metrics.current_liquidity_usd = liquidity_usd

            # Check for SIGNIFICANT_LIQUIDITY_INCREASE milestone
            if prev_liquidity > 0 and (liquidity_usd / prev_liquidity) >= self.liquidity_increase_threshold:
                milestone_event = MilestoneEvent(
                    milestone=MilestoneType.SIGNIFICANT_LIQUIDITY_INCREASE,
                    token_address=token_address,
                    chain=chain,
                    timestamp=now,
                    description=f"Liquidity increased from ${prev_liquidity:,.2f} to ${liquidity_usd:,.2f}",
                    value=liquidity_usd,
                    details={"prev_liquidity": prev_liquidity, "new_liquidity": liquidity_usd}
                )

        metrics.updated_at = now
        if milestone_event:
            await self._record_and_publish_milestone(key, milestone_event)
        return milestone_event

    async def record_swap(
        self,
        token_address: str,
        chain: str,
        buyer_address: str,
        is_buy: bool,
        amount_usd: float,
        is_bot: bool = False,
        timestamp: Optional[datetime] = None
    ) -> List[MilestoneEvent]:
        key = f"{chain}:{token_address.lower()}"
        metrics = self.metrics_store.get(key)
        if not metrics:
            metrics = self.register_launch(token_address, chain, timestamp)

        now = timestamp or datetime.now(timezone.utc)
        metrics.launch_age_seconds = (now - metrics.launch_time).total_seconds()
        metrics.initial_volume_usd += amount_usd

        triggered_milestones: List[MilestoneEvent] = []

        if is_buy:
            metrics.buy_count += 1
            if buyer_address not in metrics.first_buyers:
                metrics.first_buyers.append(buyer_address)
                metrics.holder_count = len(metrics.first_buyers)

            # FIRST_BUY milestone
            if metrics.buy_count == 1:
                first_buy = MilestoneEvent(
                    milestone=MilestoneType.FIRST_BUY,
                    token_address=token_address,
                    chain=chain,
                    timestamp=now,
                    description=f"First buy executed by {buyer_address[:8]}... for ${amount_usd:,.2f}",
                    value=amount_usd,
                    details={"buyer": buyer_address}
                )
                triggered_milestones.append(first_buy)

            # FIRST_100_WALLETS milestone
            if len(metrics.first_buyers) == 100:
                h100 = MilestoneEvent(
                    milestone=MilestoneType.FIRST_100_WALLETS,
                    token_address=token_address,
                    chain=chain,
                    timestamp=now,
                    description="Token reached first 100 unique holder wallets",
                    value=100.0,
                    details={"unique_wallets": 100}
                )
                triggered_milestones.append(h100)

            # WHALE_ENTRY milestone
            if amount_usd >= self.whale_buy_usd_threshold:
                whale = MilestoneEvent(
                    milestone=MilestoneType.WHALE_ENTRY,
                    token_address=token_address,
                    chain=chain,
                    timestamp=now,
                    description=f"Whale buy detected: ${amount_usd:,.2f} by {buyer_address[:8]}...",
                    value=amount_usd,
                    details={"buyer": buyer_address, "buy_usd": amount_usd}
                )
                triggered_milestones.append(whale)

        else:
            metrics.sell_count += 1

        # Buy/Sell Ratio & Velocity calculation
        total_tx = metrics.buy_count + metrics.sell_count
        metrics.buy_sell_ratio = metrics.buy_count / max(metrics.sell_count, 1)
        
        minutes = max(metrics.launch_age_seconds / 60.0, 1.0)
        metrics.buy_velocity_per_min = metrics.buy_count / minutes

        if is_bot:
            bot_txs = int(metrics.bot_transaction_ratio * (total_tx - 1)) + 1
            metrics.bot_transaction_ratio = bot_txs / total_tx

        # RAPID_VOLUME_ACCELERATION milestone
        if metrics.buy_velocity_per_min > 20 and total_tx >= 15:
            existing_milestones = [m.milestone for m in self.milestones_history.get(key, [])]
            if MilestoneType.RAPID_VOLUME_ACCELERATION not in existing_milestones:
                rapid = MilestoneEvent(
                    milestone=MilestoneType.RAPID_VOLUME_ACCELERATION,
                    token_address=token_address,
                    chain=chain,
                    timestamp=now,
                    description=f"Rapid volume acceleration: {metrics.buy_velocity_per_min:.1f} buys/min",
                    value=metrics.buy_velocity_per_min,
                    details={"buy_velocity": metrics.buy_velocity_per_min, "volume_usd": metrics.initial_volume_usd}
                )
                triggered_milestones.append(rapid)

        metrics.updated_at = now

        for milestone in triggered_milestones:
            await self._record_and_publish_milestone(key, milestone)

        return triggered_milestones

    async def _record_and_publish_milestone(self, key: str, milestone: MilestoneEvent) -> None:
        self.milestones_history.setdefault(key, []).append(milestone)
        logger.info(f"[LaunchDetector] Milestone triggered for {key}: {milestone.milestone.value} - {milestone.description}")
        
        # Publish event to Kafka/Redis if publisher connected
        if publisher.kafka:
            try:
                await publisher.publish({
                    "event_type": "LAUNCH_MILESTONE",
                    "milestone": milestone.model_dump(mode="json")
                })
            except Exception as e:
                logger.error(f"[LaunchDetector] Failed to publish milestone: {e}")

new_launch_detector = NewLaunchDetector()

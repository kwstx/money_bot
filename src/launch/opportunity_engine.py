import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .detector import new_launch_detector as global_launch_detector, NewLaunchDetector
from ..discovery.schemas import LaunchMetrics, MilestoneEvent, MilestoneType

logger = logging.getLogger(__name__)

class OpportunityEngine:
    """
    Opportunity Engine.
    Filters and prioritizes genuinely early opportunities from launch metrics and milestones.
    Prevents treating every new contract as investable.
    """

    def __init__(self, min_liquidity_usd: float = 1000.0, max_bot_ratio: float = 0.8, max_risk_score: float = 0.6):
        self.min_liquidity_usd = min_liquidity_usd
        self.max_bot_ratio = max_bot_ratio
        self.max_risk_score = max_risk_score
        self.prioritized_opportunities: Dict[str, Dict[str, Any]] = {}

    def evaluate_opportunity(self, token_address: str, chain: str, detector: Optional[NewLaunchDetector] = None) -> Dict[str, Any]:
        key = f"{chain}:{token_address.lower()}"
        target_detector = detector or global_launch_detector
        metrics = target_detector.metrics_store.get(key)

        if not metrics:
            return {
                "is_prioritized": False,
                "priority_score": 0.0,
                "rejection_reasons": ["No launch metrics registered"],
                "token_address": token_address,
                "chain": chain
            }

        rejection_reasons = []

        # Liquidity Check
        if metrics.current_liquidity_usd < self.min_liquidity_usd:
            rejection_reasons.append(f"Insufficient liquidity (${metrics.current_liquidity_usd:,.2f} < ${self.min_liquidity_usd:,.2f})")

        # Bot activity check
        if metrics.bot_transaction_ratio > self.max_bot_ratio:
            rejection_reasons.append(f"Excessive bot transaction ratio ({metrics.bot_transaction_ratio:.2f} > {self.max_bot_ratio:.2f})")

        # Risk Score Check
        if metrics.contract_risk_score > self.max_risk_score:
            rejection_reasons.append(f"High contract risk score ({metrics.contract_risk_score:.2f} > {self.max_risk_score:.2f})")

        # Calculate Priority Score (0.0 to 100.0)
        priority_score = 0.0
        if not rejection_reasons:
            # Factor 1: Liquidity depth score (up to 30 pts)
            liq_score = min(metrics.current_liquidity_usd / 50000.0 * 30.0, 30.0)
            
            # Factor 2: Volume acceleration & velocity (up to 30 pts)
            vel_score = min(metrics.buy_velocity_per_min / 30.0 * 30.0, 30.0)

            # Factor 3: Milestone progression (up to 20 pts)
            milestones = target_detector.milestones_history.get(key, [])
            milestone_types = {m.milestone for m in milestones}
            milestone_score = 0.0
            if MilestoneType.FIRST_BUY in milestone_types:
                milestone_score += 5.0
            if MilestoneType.WHALE_ENTRY in milestone_types:
                milestone_score += 5.0
            if MilestoneType.RAPID_VOLUME_ACCELERATION in milestone_types:
                milestone_score += 5.0
            if MilestoneType.FIRST_100_WALLETS in milestone_types:
                milestone_score += 5.0

            # Factor 4: Organic buy ratio (up to 20 pts)
            buy_ratio_score = min(metrics.buy_sell_ratio / 3.0 * 20.0, 20.0)

            priority_score = round(liq_score + vel_score + milestone_score + buy_ratio_score, 2)

        is_prioritized = len(rejection_reasons) == 0 and priority_score >= 25.0

        eval_result = {
            "token_address": token_address,
            "chain": chain,
            "is_prioritized": is_prioritized,
            "priority_score": priority_score,
            "rejection_reasons": rejection_reasons,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics.model_dump(mode="json")
        }

        if is_prioritized:
            self.prioritized_opportunities[key] = eval_result
            logger.info(f"[OpportunityEngine] PRIORITIZED OPPORTUNITY: {key} with score {priority_score}/100")

        return eval_result

    def get_top_opportunities(self, limit: int = 10) -> List[Dict[str, Any]]:
        sorted_opps = sorted(
            self.prioritized_opportunities.values(),
            key=lambda x: x.get("priority_score", 0.0),
            reverse=True
        )
        return sorted_opps[:limit]

opportunity_engine = OpportunityEngine()

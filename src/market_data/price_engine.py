import logging
import math
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple, Optional
from .schemas import PriceObservation, ReconciledPrice

logger = logging.getLogger(__name__)

class PriceEngine:
    """
    Market-Data Price Engine.
    Reconciles price across multiple data sources, filters stale/contradictory observations,
    evaluates pool consistency, trade recency, liquidity, and abnormal price spikes,
    and produces confidence scores and provenance records.
    """

    def __init__(
        self,
        max_staleness_seconds: float = 120.0,
        max_deviation_threshold: float = 0.25,  # 25% max allowed divergence from median
        min_reliable_sources: int = 1,
        min_liquidity_usd: float = 500.0,
        abnormal_movement_pct: float = 0.50,   # 50% jump/crash flagging threshold
    ):
        self.max_staleness_seconds = max_staleness_seconds
        self.max_deviation_threshold = max_deviation_threshold
        self.min_reliable_sources = min_reliable_sources
        self.min_liquidity_usd = min_liquidity_usd
        self.abnormal_movement_pct = abnormal_movement_pct
        self.price_history: Dict[str, List[ReconciledPrice]] = {}

    def reconcile_price(
        self,
        token_address: str,
        chain: str,
        observations: List[PriceObservation],
        last_trade_timestamp: Optional[datetime] = None,
    ) -> ReconciledPrice:
        now = datetime.now(timezone.utc)
        key = f"{chain}:{token_address.lower()}"

        if not observations:
            return ReconciledPrice(
                token_address=token_address,
                chain=chain,
                price_usd=0.0,
                confidence_score=0.0,
                is_reliable=False,
                provider_count=0,
                rejected_sources=[],
                rejection_reasons=["No price observations provided"],
            )

        rejected_sources: List[str] = []
        rejection_reasons: List[str] = []
        valid_observations: List[PriceObservation] = []

        # 1. Staleness check
        for obs in observations:
            age = (now - obs.timestamp).total_seconds()
            if age > self.max_staleness_seconds:
                rejected_sources.append(obs.source_id)
                rejection_reasons.append(f"Source {obs.source_id} stale by {age:.1f}s")
            elif obs.price_usd <= 0.0:
                rejected_sources.append(obs.source_id)
                rejection_reasons.append(f"Source {obs.source_id} non-positive price: {obs.price_usd}")
            else:
                valid_observations.append(obs)

        if not valid_observations:
            return ReconciledPrice(
                token_address=token_address,
                chain=chain,
                price_usd=0.0,
                confidence_score=0.0,
                is_reliable=False,
                provider_count=0,
                rejected_sources=rejected_sources,
                rejection_reasons=rejection_reasons or ["All observations rejected"],
            )

        # 2. Contradictory Observation Rejection (Median-based outlier detection)
        prices = [obs.price_usd for obs in valid_observations]
        prices_sorted = sorted(prices)
        mid = len(prices_sorted) // 2
        median_price = prices_sorted[mid] if len(prices_sorted) % 2 != 0 else (prices_sorted[mid - 1] + prices_sorted[mid]) / 2.0

        non_outlier_observations: List[PriceObservation] = []
        for obs in valid_observations:
            dev = abs(obs.price_usd - median_price) / median_price if median_price > 0 else 1.0
            if len(valid_observations) >= 3 and dev > self.max_deviation_threshold:
                rejected_sources.append(obs.source_id)
                rejection_reasons.append(
                    f"Source {obs.source_id} price ${obs.price_usd:.6f} deviates {dev*100:.1f}% from median ${median_price:.6f}"
                )
            else:
                non_outlier_observations.append(obs)

        if not non_outlier_observations:
            non_outlier_observations = valid_observations

        # 3. Weighted Price Reconciliation (Liquidity + Source Weight + Recency Weight)
        total_weight = 0.0
        weighted_price_sum = 0.0
        max_pool_liquidity = 0.0

        for obs in non_outlier_observations:
            age = max(0.0, (now - obs.timestamp).total_seconds())
            recency_decay = math.exp(-age / 300.0)  # Exponential decay over 5 minutes
            liquidity_weight = math.log10(max(1.0, obs.liquidity_usd)) + 1.0
            combined_weight = obs.weight * liquidity_weight * recency_decay

            weighted_price_sum += obs.price_usd * combined_weight
            total_weight += combined_weight
            if obs.liquidity_usd > max_pool_liquidity:
                max_pool_liquidity = obs.liquidity_usd

        reconciled_price = weighted_price_sum / total_weight if total_weight > 0 else median_price

        # 4. Calculate Max Deviation among accepted sources
        acc_prices = [obs.price_usd for obs in non_outlier_observations]
        min_acc, max_acc = min(acc_prices), max(acc_prices)
        deviation_pct = (max_acc - min_acc) / min_acc if min_acc > 0 else 0.0

        # 5. Evaluate Recency & Abnormal Price Movements
        trade_recency_score = 1.0
        if last_trade_timestamp:
            trade_age = (now - last_trade_timestamp).total_seconds()
            if trade_age > 1800:  # Older than 30 mins
                trade_recency_score = 0.3
                rejection_reasons.append(f"Trade recency low ({trade_age/60:.1f} mins since last trade)")
            elif trade_age > 300:
                trade_recency_score = 0.7

        # Check historic price jump / crash
        history = self.price_history.get(key, [])
        abnormal_movement = False
        if history:
            prev_price = history[-1].price_usd
            if prev_price > 0:
                price_change = abs(reconciled_price - prev_price) / prev_price
                if price_change >= self.abnormal_movement_pct:
                    abnormal_movement = True
                    rejection_reasons.append(
                        f"Abnormal price shift detected: {price_change*100:.1f}% change from previous ${prev_price:.6f}"
                    )

        # 6. Confidence Score Calculation
        # Components:
        # - Source multiplicity (30%)
        # - Pool liquidity level (30%)
        # - Source agreement / low deviation (20%)
        # - Recency & abnormal movement (20%)
        multiplicity_score = min(1.0, len(non_outlier_observations) / 3.0)
        liquidity_score = min(1.0, max_pool_liquidity / 10000.0) if max_pool_liquidity > 0 else 0.1
        agreement_score = max(0.0, 1.0 - (deviation_pct / self.max_deviation_threshold)) if self.max_deviation_threshold > 0 else 1.0
        recency_and_stability = trade_recency_score * (0.4 if abnormal_movement else 1.0)

        confidence_score = (
            0.30 * multiplicity_score +
            0.30 * liquidity_score +
            0.20 * agreement_score +
            0.20 * recency_and_stability
        )
        confidence_score = max(0.0, min(1.0, confidence_score))

        # Reliability decision
        is_reliable = (
            confidence_score >= 0.40 and
            max_pool_liquidity >= self.min_liquidity_usd and
            len(non_outlier_observations) >= self.min_reliable_sources and
            not abnormal_movement
        )

        if not is_reliable and not rejection_reasons:
            rejection_reasons.append("Confidence score below reliability threshold or low liquidity")

        result = ReconciledPrice(
            token_address=token_address,
            chain=chain,
            price_usd=round(reconciled_price, 8),
            confidence_score=round(confidence_score, 4),
            is_reliable=is_reliable,
            provider_count=len(non_outlier_observations),
            rejected_sources=rejected_sources,
            deviation_pct=round(deviation_pct, 4),
            provenance=observations,
            last_trade_timestamp=last_trade_timestamp or now,
            rejection_reasons=rejection_reasons,
            updated_at=now,
        )

        # Update history
        if key not in self.price_history:
            self.price_history[key] = []
        self.price_history[key].append(result)
        if len(self.price_history[key]) > 100:
            self.price_history[key] = self.price_history[key][-100:]

        return result

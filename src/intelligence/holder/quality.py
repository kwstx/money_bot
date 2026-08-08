import logging
import math
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone

from src.intelligence.holder.schemas import (
    GrowthTrajectoryPattern,
    HolderQualityMetrics,
    HolderVelocityAndRetention,
    OwnershipDistributionMetrics,
    TokenTransferEvent
)

logger = logging.getLogger(__name__)

# Benchmark reference vectors for historical token trajectories:
# [growth_velocity, retention_pct, churn_pct, sybil_score, gini_trend (-1=declining, +1=increasing), diversity_index]
BENCHMARK_TRAJECTORIES = {
    GrowthTrajectoryPattern.ORGANIC_ACCUMULATION: {
        "vector": [0.60, 0.85, 0.10, 0.10, -0.30, 0.80],
        "description": "Sustained organic holder growth with high retention and expanding distribution."
    },
    GrowthTrajectoryPattern.BOT_AIRDROP_CHURN: {
        "vector": [0.95, 0.15, 0.80, 0.85, 0.20, 0.40],
        "description": "Rapid bot/airdrop holder spike followed by extreme immediate churn."
    },
    GrowthTrajectoryPattern.PUMP_AND_DUMP: {
        "vector": [0.90, 0.25, 0.70, 0.60, 0.80, 0.25],
        "description": "Aggressive promotional growth accompanied by heavy insider dump and crashing retention."
    },
    GrowthTrajectoryPattern.SLOW_BLEED: {
        "vector": [0.05, 0.30, 0.50, 0.20, 0.50, 0.30],
        "description": "Stagnant new holder rate with steady user erosion and rising inactivity."
    },
    GrowthTrajectoryPattern.INSTITUTIONAL_HOLD: {
        "vector": [0.20, 0.90, 0.05, 0.05, 0.40, 0.50],
        "description": "High concentration in long-term conviction holders with minimal churn."
    },
    GrowthTrajectoryPattern.STAGNANT: {
        "vector": [0.0, 0.40, 0.20, 0.10, 0.0, 0.20],
        "description": "Inactive or dead token state with minimal transaction activity."
    }
}


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculates cosine similarity between two float vectors (0.0 to 1.0)."""
    if len(vec1) != len(vec2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 <= 1e-9 or norm2 <= 1e-9:
        return 0.0
    sim = dot_product / (norm1 * norm2)
    return float(max(0.0, min(1.0, sim)))


class HolderQualityEngine:
    """
    Evaluates holder growth durability and matches evolution against historical token trajectories.
    Distinguishes organic growth from bot churn, sybil coordination, or artificial distribution.
    """
    def __init__(self):
        pass

    def evaluate_quality(
        self,
        token_address: str,
        velocity_retention: HolderVelocityAndRetention,
        distribution_metrics: OwnershipDistributionMetrics,
        recent_events: Optional[List[TokenTransferEvent]] = None
    ) -> HolderQualityMetrics:
        """Evaluates holder durability, sybil coordination, organic score, and historical trajectory match."""
        # 1. Churn Rate calculation
        new_holders = velocity_retention.new_holder_count
        exits = velocity_retention.holder_exits_count
        churn_rate = (exits / float(new_holders) * 100.0) if new_holders > 0 else (50.0 if exits > 0 else 0.0)
        churn_rate = min(100.0, churn_rate)

        # 2. Retention estimate (7d / 30d)
        retention_24h = velocity_retention.retention_rate_pct
        retention_7d = max(0.0, retention_24h * 0.90)  # slightly decay or use historical snapshot if available
        retention_30d = max(0.0, retention_24h * 0.75)

        # 3. Sybil Coordination Score: check for suspicious identical amounts or rapid sequential wallet distributions
        sybil_score = self._detect_sybil_coordination(recent_events or [])

        # 4. Organic Growth Score
        diversity = distribution_metrics.wallet_diversity_index
        organic_score = (
            0.35 * velocity_retention.retention_rate_pct +
            0.35 * diversity +
            0.30 * (100.0 - sybil_score) -
            0.25 * churn_rate
        )
        organic_score = float(max(0.0, min(100.0, organic_score)))

        # 5. Trajectory matching
        classification, sim_scores = self._classify_trajectory(
            velocity_retention=velocity_retention,
            distribution_metrics=distribution_metrics,
            churn_rate_pct=churn_rate,
            sybil_score=sybil_score
        )

        # 6. Composite Holder Quality Score
        quality_score = (
            0.35 * organic_score +
            0.30 * retention_24h +
            0.20 * (100.0 - sybil_score) +
            0.15 * (100.0 - churn_rate)
        )
        quality_score = float(max(0.0, min(100.0, quality_score)))

        return HolderQualityMetrics(
            token_address=token_address,
            churn_rate_24h_pct=float(churn_rate),
            retention_rate_7d_pct=float(retention_7d),
            retention_rate_30d_pct=float(retention_30d),
            sybil_coordination_score=float(sybil_score),
            organic_growth_score=float(organic_score),
            trajectory_classification=classification,
            trajectory_similarity_scores=sim_scores,
            holder_quality_score=float(quality_score)
        )

    def _detect_sybil_coordination(self, events: List[TokenTransferEvent]) -> float:
        """
        Detects coordinated bot / dusting / sybil transfers (identical amounts, single sender, rapid cluster).
        Returns a score from 0.0 (fully organic) to 100.0 (highly coordinated sybil).
        """
        if not events or len(events) < 5:
            return 0.0

        # Frequency of identical transfer amounts
        amount_counts: Dict[float, int] = {}
        sender_distribution_counts: Dict[str, int] = {}

        for ev in events:
            amt = round(ev.amount, 4)
            if amt > 0:
                amount_counts[amt] = amount_counts.get(amt, 0) + 1
            snd = ev.sender.lower()
            sender_distribution_counts[snd] = sender_distribution_counts.get(snd, 0) + 1

        total_ev = len(events)
        max_same_amount = max(amount_counts.values()) if amount_counts else 0
        same_amount_ratio = max_same_amount / total_ev

        max_from_single_sender = max(sender_distribution_counts.values()) if sender_distribution_counts else 0
        sender_ratio = max_from_single_sender / total_ev

        # High ratio of identical amounts or single distributor indicates sybil/airdrop botting
        sybil_score = (0.5 * same_amount_ratio + 0.5 * sender_ratio) * 100.0
        return float(max(0.0, min(100.0, sybil_score)))

    def _classify_trajectory(
        self,
        velocity_retention: HolderVelocityAndRetention,
        distribution_metrics: OwnershipDistributionMetrics,
        churn_rate_pct: float,
        sybil_score: float
    ) -> Tuple[GrowthTrajectoryPattern, Dict[str, float]]:
        """Classifies token trajectory against historical benchmarks using vector similarity."""
        # Normalize current state vector:
        # [growth_velocity, retention_ratio, churn_ratio, sybil_ratio, gini_trend, diversity_ratio]
        velocity_norm = min(1.0, velocity_retention.new_holder_rate / 50.0)
        retention_ratio = min(1.0, velocity_retention.retention_rate_pct / 100.0)
        churn_ratio = min(1.0, churn_rate_pct / 100.0)
        sybil_ratio = min(1.0, sybil_score / 100.0)
        gini_trend = min(1.0, max(-1.0, velocity_retention.concentration_delta_top10 / 10.0))
        diversity_ratio = min(1.0, distribution_metrics.wallet_diversity_index / 100.0)

        current_vector = [
            velocity_norm,
            retention_ratio,
            churn_ratio,
            sybil_ratio,
            gini_trend,
            diversity_ratio
        ]

        sim_scores: Dict[str, float] = {}
        best_match = GrowthTrajectoryPattern.STAGNANT
        best_sim = -1.0

        for pattern, config in BENCHMARK_TRAJECTORIES.items():
            bench_vec = config["vector"]
            sim = cosine_similarity(current_vector, bench_vec)
            sim_scores[pattern.value] = round(sim, 4)
            if sim > best_sim:
                best_sim = sim
                best_match = pattern

        return best_match, sim_scores

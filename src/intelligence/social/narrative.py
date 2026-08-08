import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import math

from src.intelligence.social.schemas import (
    NarrativeAnalysis,
    NarrativeLifecycle,
    TrendMetrics,
    ViralDynamics,
    NarrativePrediction,
    SocialSignal
)

logger = logging.getLogger(__name__)

class NarrativeDynamicsEngine:
    """
    Analyzes narratives, trends, attention, and viral dynamics.
    Identifies narrative lifecycles, trend acceleration, and predicts entry/exit risks based on attention-price mismatches.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        # Thresholds for heuristics
        self.viral_threshold = self.config.get("viral_threshold", 2.5) # multiplier of normal growth
        self.bot_coordination_threshold = self.config.get("bot_coordination_threshold", 0.7)
        
    def detect_narrative(self, narrative_id: str, concepts: List[str], signals: List[SocialSignal], market_activity: Dict[str, Any]) -> NarrativeAnalysis:
        """
        Identifies clusters of related concepts across social conversations, news, etc.
        Determines the narrative's lifecycle phase.
        """
        # In a real implementation, this would use NLP clustering (e.g., HDBSCAN on embeddings) 
        # to group concepts and tokens dynamically. For now, we evaluate the provided concepts.
        
        related_tokens = set()
        for signal in signals:
            related_tokens.update(signal.tokens_referenced)
            
        # Heuristics for lifecycle phase based on signal volume over time and market activity
        volume_momentum = self._calculate_momentum([s.timestamp for s in signals])
        market_momentum = market_activity.get("volume_momentum", 0.0)
        
        phase = NarrativeLifecycle.UNKNOWN
        confidence = 0.0
        rotating_into = None
        
        if volume_momentum > 2.0 and market_momentum < 1.5:
            phase = NarrativeLifecycle.EMERGING
            confidence = 0.8
        elif volume_momentum > 3.0 and market_momentum > 2.0:
            phase = NarrativeLifecycle.ACCELERATING
            confidence = 0.9
        elif volume_momentum > 1.0 and market_momentum > 3.0:
            phase = NarrativeLifecycle.MATURE
            confidence = 0.7
        elif volume_momentum < 0.5 and market_momentum > 1.0:
            phase = NarrativeLifecycle.SATURATED
            confidence = 0.8
        elif volume_momentum < -0.5:
            phase = NarrativeLifecycle.DECLINING
            confidence = 0.75
            
        # Detect rotation if declining but a subset of concepts are accelerating under a new narrative
        # (Mock logic for rotation detection)
        if phase in (NarrativeLifecycle.SATURATED, NarrativeLifecycle.DECLINING):
            if "ai" in concepts and "agents" in concepts:
                rotating_into = "autonomous_agents"
        
        return NarrativeAnalysis(
            narrative_id=narrative_id,
            related_concepts=concepts,
            associated_tokens=list(related_tokens),
            current_phase=phase,
            phase_confidence=confidence,
            rotating_into=rotating_into
        )

    def measure_trend(self, target_id: str, signals: List[SocialSignal], search_data: Dict[str, Any]) -> TrendMetrics:
        """
        Measures changes in attention, engagement, unique participants, and cross-platform propagation.
        """
        if not signals:
            return TrendMetrics(target_id=target_id)
            
        unique_authors = len(set(s.author_id for s in signals))
        platforms = len(set(s.source_platform for s in signals))
        
        total_engagement = sum(sum(s.engagement_metrics.values()) for s in signals)
        
        # Calculate acceleration (mocked as simple ratio for demonstration)
        # In production, this would compare t(now) - t(-1h) vs t(-1h) - t(-2h)
        engagement_accel = (total_engagement / max(1, len(signals))) * 0.1 
        participants_growth = (unique_authors / max(1, len(signals))) * 1.5
        
        cross_platform = min(1.0, platforms / 5.0) # Assume 5 major platforms
        
        search_momentum = search_data.get("trend_slope", 0.0)
        
        return TrendMetrics(
            target_id=target_id,
            attention_score=min(100.0, len(signals) * 0.5 + search_data.get("volume", 0) * 0.1),
            engagement_acceleration=engagement_accel,
            unique_participants_growth=participants_growth,
            search_interest_momentum=search_momentum,
            cross_platform_propagation=cross_platform
        )

    def analyze_viral_dynamics(self, target_id: str, trend: TrendMetrics, signals: List[SocialSignal]) -> ViralDynamics:
        """
        Identifies unusually rapid expansion and separates organic diffusion from coordinated campaigns.
        """
        # Velocity is high if engagement and participants are growing rapidly across platforms
        velocity = (trend.engagement_acceleration + trend.unique_participants_growth) * trend.cross_platform_propagation
        
        is_viral = velocity > self.viral_threshold
        
        # Coordinated campaign heuristics:
        # - High volume but low unique participants (sybil)
        # - High engagement but low cross-platform spread (isolated bot farm)
        # - Exact same content posted across multiple accounts
        
        unique_content_ratio = len(set(s.content for s in signals)) / max(1, len(signals))
        participant_ratio = min(1.0, trend.unique_participants_growth / max(0.1, trend.engagement_acceleration))
        
        coordination_risk = 1.0 - (unique_content_ratio * 0.7 + participant_ratio * 0.3)
        organic_score = 1.0 - coordination_risk
        
        return ViralDynamics(
            target_id=target_id,
            is_viral=is_viral,
            viral_velocity=min(1.0, velocity / 10.0), # normalized
            organic_diffusion_score=organic_score,
            coordinated_campaign_risk=coordination_risk
        )
        
    def predict_narrative(self, target_id: str, narrative: NarrativeAnalysis, trend: TrendMetrics, price_data: Dict[str, Any]) -> NarrativePrediction:
        """
        Compares current conditions with historical lifecycles.
        Detects attention-price mismatches and late-hype conditions for entry/exit timing.
        """
        price_momentum = price_data.get("price_momentum", 0.0)
        price_expansion = price_data.get("price_expansion_7d", 0.0) # e.g., 2.0 = 200% up
        
        attention_accel = trend.engagement_acceleration + trend.search_interest_momentum
        
        # Attention-price mismatch: Social attention accelerating, but price hasn't moved much yet
        mismatch = (attention_accel > 1.5) and (price_expansion < 0.2)
        
        # Late-hype condition: Price has expanded dramatically, but attention growth is slowing or saturated
        late_hype = (price_expansion > 1.5) and (
            narrative.current_phase in (NarrativeLifecycle.SATURATED, NarrativeLifecycle.DECLINING) or 
            attention_accel < 0.0
        )
        
        # Entry timing signal: Strong when emerging/accelerating with a mismatch
        entry_signal = 0.0
        if mismatch and narrative.current_phase in (NarrativeLifecycle.EMERGING, NarrativeLifecycle.ACCELERATING):
            entry_signal = min(1.0, attention_accel * 0.4)
            
        # Exit risk signal: Strong when mature/saturated or in late-hype condition
        exit_signal = 0.0
        if late_hype:
            exit_signal = min(1.0, price_expansion * 0.3 + (1.0 - max(0, attention_accel)))
        elif narrative.current_phase == NarrativeLifecycle.ROTATING:
            exit_signal = 0.8
            
        return NarrativePrediction(
            target_id=target_id,
            attention_price_mismatch=mismatch,
            late_hype_condition=late_hype,
            historical_similarity=0.75, # Mock: would compare shape of curves with DTW
            entry_timing_signal=entry_signal,
            exit_risk_signal=exit_signal
        )

    def _calculate_momentum(self, timestamps: List[datetime]) -> float:
        """Helper to calculate momentum from a series of timestamps."""
        if len(timestamps) < 2:
            return 0.0
            
        # Mock calculation: more recent timestamps = higher momentum
        now = datetime.now(timezone.utc)
        recent_count = sum(1 for t in timestamps if (now - t).total_seconds() < 3600)
        older_count = sum(1 for t in timestamps if 3600 <= (now - t).total_seconds() < 7200)
        
        if older_count == 0:
            return float(recent_count)
        return (recent_count - older_count) / older_count

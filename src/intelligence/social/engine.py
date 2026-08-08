import logging
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import re

from .schemas import (
    SocialSignal,
    CommunityMetrics,
    InfluencerProfile,
    OffChainCatalyst,
    SocialIntelligenceResult
)

logger = logging.getLogger(__name__)

class SocialIntelligenceEngine:
    """
    Engine for processing social signals, community metrics, influencer profiles,
    and identifying off-chain catalysts.
    """
    
    def __init__(self):
        # In a real system, these would connect to databases/message buses
        self.influencer_profiles: Dict[str, InfluencerProfile] = {}
        self.community_history: Dict[str, List[CommunityMetrics]] = {}
        self.active_catalysts: Dict[str, OffChainCatalyst] = {}
        self.token_social_results: Dict[str, SocialIntelligenceResult] = {}
        
    def process_social_signal(self, raw_data: Dict[str, Any]) -> Optional[SocialSignal]:
        """
        Ingests and normalizes a public signal from X, Telegram, Discord, etc.
        """
        try:
            # Extract basic info
            platform = raw_data.get("platform", "UNKNOWN")
            source_id = raw_data.get("id", str(uuid.uuid4()))
            author_id = raw_data.get("author_id", "UNKNOWN_AUTHOR")
            content = raw_data.get("content", "")
            
            # Simple cashtag/token extraction regex
            cashtags = re.findall(r'\$([A-Za-z0-9]+)', content)
            
            # Mock extraction logic for projects/links
            links = raw_data.get("links", [])
            engagement = raw_data.get("engagement", {})
            
            signal = SocialSignal(
                source_platform=platform,
                source_id=source_id,
                author_id=author_id,
                author_username=raw_data.get("author_username"),
                content=content,
                engagement_metrics=engagement,
                links_included=links,
                tokens_referenced=cashtags,
                timestamp=datetime.now(timezone.utc)
            )
            
            self._update_influencer_stats_from_signal(signal)
            self._detect_catalyst_from_signal(signal)
            
            return signal
        except Exception as e:
            logger.error(f"Failed to process social signal: {e}")
            return None

    def _update_influencer_stats_from_signal(self, signal: SocialSignal):
        """Update influencer profile based on new activity."""
        if signal.author_username and signal.author_username in self.influencer_profiles:
            # Update engagement, tracking, etc. (Mock implementation)
            profile = self.influencer_profiles[signal.author_username]
            if signal.tokens_referenced:
                for token in signal.tokens_referenced:
                    profile.past_endorsements.append({
                        "token": token,
                        "timestamp": signal.timestamp.isoformat(),
                        "engagement_at_time": sum(signal.engagement_metrics.values())
                    })
    
    def _detect_catalyst_from_signal(self, signal: SocialSignal):
        """Monitor for unexpected endorsements, rumors, etc."""
        content_lower = signal.content.lower()
        
        # Simple heuristic for exchange listing
        if "binance" in content_lower and ("listing" in content_lower or "list" in content_lower):
            catalyst_id = f"listing_rumor_{uuid.uuid4().hex[:8]}"
            catalyst = OffChainCatalyst(
                event_id=catalyst_id,
                event_type="EXCHANGE_LISTING",
                description=f"Exchange listing rumor detected from {signal.source_platform}",
                target_token=signal.tokens_referenced[0] if signal.tokens_referenced else None,
                credibility_score=0.3, # low until corroborated
                uncertainty_level="HIGH",
                market_impact_potential=0.8,
                sources=[signal.source_id]
            )
            self.active_catalysts[catalyst_id] = catalyst

    def analyze_community(self, project_id: str, historical_signals: List[SocialSignal]) -> CommunityMetrics:
        """
        Measure growth, retention, bot probability, etc.
        Distinguish genuine vs automated activity.
        """
        # Mock analysis logic
        total_signals = len(historical_signals)
        unique_authors = len(set(s.author_id for s in historical_signals))
        
        if total_signals == 0:
            return CommunityMetrics(project_id=project_id)
            
        # If high volume but low unique authors, high bot probability or spam
        bot_prob = 0.0
        if unique_authors / total_signals < 0.1:
            bot_prob = 0.8
            
        engagement_quality = 0.5
        if bot_prob < 0.3 and total_signals > 100:
            engagement_quality = 0.8
            
        metrics = CommunityMetrics(
            project_id=project_id,
            active_participants_count=unique_authors,
            bot_probability_score=bot_prob,
            engagement_quality=engagement_quality,
            overall_health_score=engagement_quality * (1.0 - bot_prob)
        )
        
        if project_id not in self.community_history:
            self.community_history[project_id] = []
        self.community_history[project_id].append(metrics)
        
        return metrics

    def evaluate_influencer(self, profile: InfluencerProfile) -> InfluencerProfile:
        """
        Evaluate past endorsements and update ROI and estimated influence.
        """
        # In a real system, this would query market data for tokens in `past_endorsements`
        # and calculate actual ROI post-mention.
        # Mock calculation:
        successful_calls = 0
        total_calls = len(profile.past_endorsements)
        
        if total_calls > 0:
            # Randomize or use external data, here we mock a basic positive ROI
            profile.historical_roi = 1.5 # 50% avg return
            profile.estimated_influence = 0.7 if profile.audience_quality_score > 0.6 else 0.3
        
        self.influencer_profiles[profile.username] = profile
        return profile

    def register_influencer(self, profile: InfluencerProfile):
        """Add a known influencer to track."""
        self.influencer_profiles[profile.username] = profile

    def get_social_intelligence(self, target_id: str) -> SocialIntelligenceResult:
        """
        Aggregate all social layers for a token or project.
        """
        # Get active catalysts for this target
        target_catalysts = [
            cat for cat in self.active_catalysts.values() 
            if cat.target_token == target_id or cat.target_project == target_id
        ]
        
        # Get community metrics (latest)
        latest_metrics = None
        if target_id in self.community_history and self.community_history[target_id]:
            latest_metrics = self.community_history[target_id][-1]
            
        # Find recent influencer mentions
        influencer_mentions = []
        for inf in self.influencer_profiles.values():
            for end in inf.past_endorsements:
                if end.get("token") == target_id:
                    influencer_mentions.append({
                        "influencer": inf.username,
                        "timestamp": end.get("timestamp"),
                        "estimated_influence": inf.estimated_influence
                    })
                    
        # Calculate scores
        base_sentiment = 0.0
        if latest_metrics:
            base_sentiment = (latest_metrics.overall_health_score * 2.0) - 1.0
            
        # Generate actionable signals
        actionable_signals = []
        for cat in target_catalysts:
            if cat.market_impact_potential > 0.7 and cat.credibility_score > 0.5:
                actionable_signals.append({
                    "type": "HIGH_IMPACT_CATALYST",
                    "description": cat.description,
                    "catalyst_id": cat.event_id
                })
                
        result = SocialIntelligenceResult(
            target_id=target_id,
            community_metrics=latest_metrics,
            active_catalysts=target_catalysts,
            influencer_mentions=influencer_mentions,
            social_sentiment_score=base_sentiment,
            actionable_signals=actionable_signals
        )
        
        self.token_social_results[target_id] = result
        return result

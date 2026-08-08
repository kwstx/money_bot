from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

class SocialSignal(BaseModel):
    """Raw or normalized social signal ingested from various platforms."""
    source_platform: str = Field(..., description="Platform like X, Telegram, Discord, Reddit, Farcaster, Lens, etc.")
    source_id: str = Field(..., description="Unique identifier of the post/message on the platform")
    author_id: str = Field(..., description="Identifier of the author/account")
    author_username: Optional[str] = Field(default=None)
    content: str = Field(..., description="Text content of the signal")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    engagement_metrics: Dict[str, int] = Field(default_factory=dict, description="Likes, retweets, replies, views, etc.")
    links_included: List[str] = Field(default_factory=list)
    tokens_referenced: List[str] = Field(default_factory=list, description="Extracted cashtags or token addresses")
    projects_referenced: List[str] = Field(default_factory=list, description="Identified project names or domains")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class CommunityMetrics(BaseModel):
    """Metrics assessing the health and quality of a project's community."""
    project_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    growth_velocity: float = Field(default=0.0, description="Rate of new member acquisition")
    retention_rate: float = Field(default=0.0, description="Percentage of members remaining active over time")
    engagement_quality: float = Field(default=0.0, description="Score based on substance of participation vs just volume (0.0 to 1.0)")
    active_participants_count: int = Field(default=0, description="Number of unique active participants in the window")
    recurring_contributors_count: int = Field(default=0, description="Number of members who participate regularly")
    
    bot_probability_score: float = Field(default=0.0, description="Estimated probability of automated/sybil activity (0.0 to 1.0)")
    coordinated_activity_score: float = Field(default=0.0, description="Score detecting inorganic coordinated posting (0.0 to 1.0)")
    community_overlap: Dict[str, float] = Field(default_factory=dict, description="Overlap percentage with other known communities")
    
    overall_health_score: float = Field(default=0.0, description="Aggregated community quality score (0.0 to 1.0)")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class InfluencerProfile(BaseModel):
    """Profile and historical track record of an influencer."""
    influencer_id: str
    platform: str
    username: str
    
    audience_quality_score: float = Field(default=0.0, description="Estimated percentage of real, engaged followers (0.0 to 1.0)")
    historical_roi: float = Field(default=0.0, description="Average market performance of previously mentioned tokens")
    mention_timing_score: float = Field(default=0.0, description="Score evaluating if they buy before mentioning (0.0 to 1.0)")
    
    relationship_network: List[str] = Field(default_factory=list, description="IDs of other frequently interacting influencers")
    estimated_influence: float = Field(default=0.0, description="True market impact capability (0.0 to 1.0)")
    
    past_endorsements: List[Dict[str, Any]] = Field(default_factory=list, description="History of token calls and outcomes")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class OffChainCatalyst(BaseModel):
    """Event or rumor that could move the market but isn't visible on-chain."""
    event_id: str = Field(..., description="Unique ID for the catalyst")
    event_type: str = Field(..., description="Type of event: EXCHANGE_LISTING, VIRAL_POST, MAJOR_NEWS, UNEXPECTED_ENDORSEMENT")
    target_token: Optional[str] = Field(default=None)
    target_project: Optional[str] = Field(default=None)
    
    description: str = Field(..., description="Summary of the catalyst")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    credibility_score: float = Field(default=0.0, description="Estimated likelihood the event is true/significant (0.0 to 1.0)")
    uncertainty_level: str = Field(default="HIGH", description="LOW, MEDIUM, HIGH uncertainty")
    market_impact_potential: float = Field(default=0.0, description="Estimated price/volume impact potential (0.0 to 1.0)")
    
    sources: List[str] = Field(default_factory=list, description="URLs or signal IDs that corroborate the event")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SocialIntelligenceResult(BaseModel):
    """Aggregated social intelligence for a specific token or project."""
    target_id: str = Field(..., description="Token address or project ID")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    community_metrics: Optional[CommunityMetrics] = Field(default=None)
    active_catalysts: List[OffChainCatalyst] = Field(default_factory=list)
    influencer_mentions: List[Dict[str, Any]] = Field(default_factory=list, description="Recent mentions by profiled influencers")
    
    social_sentiment_score: float = Field(default=0.0, description="Aggregated sentiment (-1.0 to 1.0)")
    hype_momentum: float = Field(default=0.0, description="Rate of change in social volume and engagement")
    
    actionable_signals: List[Dict[str, Any]] = Field(default_factory=list, description="Derived triggers for the trading engine")
    metadata: Dict[str, Any] = Field(default_factory=dict)

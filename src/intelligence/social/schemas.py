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
    
    # Community Authenticity Metrics
    organic_discussion_score: float = Field(default=0.0, description="Score for natural vs forced/shilled conversation (0.0 to 1.0)")
    independent_content_volume: float = Field(default=0.0, description="Volume of user-generated content not from core team")
    meaningful_interaction_score: float = Field(default=0.0, description="Depth of conversation vs shallow spam (0.0 to 1.0)")
    diversity_score: float = Field(default=0.0, description="Diversity of participants, demographics or client usage (0.0 to 1.0)")
    
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

class MemeIntelligence(BaseModel):
    """Analysis of the cultural concept behind a token."""
    target_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    recognizability_score: float = Field(default=0.0, description="How well known the underlying meme/concept is (0.0 to 1.0)")
    emotional_resonance: float = Field(default=0.0, description="Ability to trigger emotion (humor, nostalgia, greed) (0.0 to 1.0)")
    uniqueness_score: float = Field(default=0.0, description="How distinct the meme is from existing metas (0.0 to 1.0)")
    adaptability_score: float = Field(default=0.0, description="How easily the meme can be remixed or adapted (0.0 to 1.0)")
    mainstream_potential: float = Field(default=0.0, description="Capability of spreading beyond crypto audience (0.0 to 1.0)")
    remix_volume: int = Field(default=0, description="Count of distinct variations/artworks seen")
    
    overall_meme_score: float = Field(default=0.0, description="Aggregated meme strength (0.0 to 1.0)")

class BrandAnalysis(BaseModel):
    """Evaluation of the project's brand identity and consistency."""
    target_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    brand_recognition: float = Field(default=0.0, description="How recognizable the visual/textual brand is (0.0 to 1.0)")
    visual_consistency: float = Field(default=0.0, description="Consistency across different platforms/materials (0.0 to 1.0)")
    copycat_risk: float = Field(default=0.0, description="Risk that the brand is easily copied or already a derivative (0.0 to 1.0)")
    community_identity_strength: float = Field(default=0.0, description="How strongly the community identifies with the brand (0.0 to 1.0)")
    
    overall_brand_score: float = Field(default=0.0, description="Aggregated brand strength (0.0 to 1.0)")

class MemeLifespanPrediction(BaseModel):
    """Probabilistic prediction of meme lifecycle phase."""
    target_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    current_phase: str = Field(default="UNKNOWN", description="ACCELERATING, PEAKING, SATURATING, DECAYING, UNKNOWN")
    phase_confidence: float = Field(default=0.0, description="Confidence in current phase (0.0 to 1.0)")
    
    estimated_time_to_peak_hours: Optional[float] = Field(default=None)
    historical_cycle_similarity_score: float = Field(default=0.0, description="Similarity to known historical hype cycles (0.0 to 1.0)")

class SocialIntelligenceResult(BaseModel):
    """Aggregated social intelligence for a specific token or project."""
    target_id: str = Field(..., description="Token address or project ID")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    community_metrics: Optional[CommunityMetrics] = Field(default=None)
    meme_intelligence: Optional[MemeIntelligence] = Field(default=None)
    brand_analysis: Optional[BrandAnalysis] = Field(default=None)
    lifespan_prediction: Optional[MemeLifespanPrediction] = Field(default=None)
    
    active_catalysts: List[OffChainCatalyst] = Field(default_factory=list)
    influencer_mentions: List[Dict[str, Any]] = Field(default_factory=list, description="Recent mentions by profiled influencers")
    
    social_sentiment_score: float = Field(default=0.0, description="Aggregated sentiment (-1.0 to 1.0)")
    hype_momentum: float = Field(default=0.0, description="Rate of change in social volume and engagement")
    
    actionable_signals: List[Dict[str, Any]] = Field(default_factory=list, description="Derived triggers for the trading engine")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class NarrativeLifecycle(str):
    EMERGING = "EMERGING"
    ACCELERATING = "ACCELERATING"
    MATURE = "MATURE"
    SATURATED = "SATURATED"
    ROTATING = "ROTATING"
    DECLINING = "DECLINING"
    UNKNOWN = "UNKNOWN"

class NarrativeAnalysis(BaseModel):
    """Detection and lifecycle analysis of a broader narrative or theme."""
    narrative_id: str = Field(..., description="Unique ID for the narrative theme")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    related_concepts: List[str] = Field(default_factory=list, description="Keywords, tags, or concepts in this cluster")
    associated_tokens: List[str] = Field(default_factory=list, description="Tokens strongly correlated with this narrative")
    
    current_phase: str = Field(default=NarrativeLifecycle.UNKNOWN, description="Current lifecycle phase")
    phase_confidence: float = Field(default=0.0, description="Confidence in the detected phase (0.0 to 1.0)")
    
    rotating_into: Optional[str] = Field(default=None, description="If rotating, the narrative it is transitioning into")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TrendMetrics(BaseModel):
    """Measurements of attention, engagement, and unique participants for a trend."""
    target_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    attention_score: float = Field(default=0.0, description="Overall volume of mentions/views")
    engagement_acceleration: float = Field(default=0.0, description="Rate of change of active engagement")
    unique_participants_growth: float = Field(default=0.0, description="Rate of new unique actors joining")
    search_interest_momentum: float = Field(default=0.0, description="Trend in external search or query volume")
    cross_platform_propagation: float = Field(default=0.0, description="Degree to which it is spreading across different platforms")

class ViralDynamics(BaseModel):
    """Analysis of viral growth and separation from coordinated campaigns."""
    target_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    is_viral: bool = Field(default=False, description="Is it experiencing unusually rapid expansion?")
    viral_velocity: float = Field(default=0.0, description="Speed of expansion (0.0 to 1.0)")
    organic_diffusion_score: float = Field(default=0.0, description="Probability that growth is organic vs coordinated (0.0 to 1.0)")
    coordinated_campaign_risk: float = Field(default=0.0, description="Risk that it's a sybil/bot driven campaign (0.0 to 1.0)")

class NarrativePrediction(BaseModel):
    """Predictive signals comparing narrative vs price."""
    target_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    attention_price_mismatch: bool = Field(default=False, description="Social attention accelerating before price")
    late_hype_condition: bool = Field(default=False, description="Price expanded but attention slowing")
    
    historical_similarity: float = Field(default=0.0, description="Similarity to past narrative lifecycles")
    entry_timing_signal: float = Field(default=0.0, description="Signal strength for early entry (0.0 to 1.0)")
    exit_risk_signal: float = Field(default=0.0, description="Risk signal for late exit (0.0 to 1.0)")

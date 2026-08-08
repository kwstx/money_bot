from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone

class EvidenceItem(BaseModel):
    """Specific empirical evidence item supporting a probabilistic relationship or label."""
    evidence_type: str = Field(..., description="Classification of evidence (e.g. COMMON_FUNDING, CO_TRADING, MEV_BUNDLE)")
    weight: float = Field(..., ge=0.0, le=1.0, description="Base weight of this evidence type")
    observation_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decay_factor: float = Field(default=0.95, ge=0.0, le=1.0, description="Half-life or decay multiplier over time")
    details: Dict[str, Any] = Field(default_factory=dict, description="Contextual details (tx hashes, time diffs, volumes)")

class ProbabilisticRelationship(BaseModel):
    """Models wallet relationships as evidence-backed probabilities rather than rigid identities."""
    source_address: str
    target_address: str
    relationship_type: str  # FUNDED, CLUSTER_PEER, CO_TRADER, INSIDER_CLUSTER, WASH_PAIR, SNIPER_GROUP
    probability: float = Field(..., ge=0.0, le=1.0, description="Estimated posterior probability of relationship")
    confidence_interval: Tuple[float, float] = Field(..., description="(lower_bound, upper_bound) 95% confidence interval")
    evidence_chain: List[EvidenceItem] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    disclaimer: str = Field(
        default="Probabilistic on-chain inference. Not a verified real-world identity association.",
        description="Disclaimer for AI layers to prevent false accusations"
    )

class SkillVsLuckResult(BaseModel):
    """Statistical hypothesis testing result comparing a wallet against random early buyers & ordinary whales."""
    wallet_address: str
    p_value: float = Field(..., description="p-value testing hypothesis that performance > random early buyers")
    z_score: float = Field(..., description="Standardized z-score against cohort mean")
    skill_over_luck_index: float = Field(..., ge=0.0, le=100.0, description="0-100 score indicating statistical skill confidence")
    is_statistically_significant: bool = Field(..., description="True if p_value < 0.05 and z_score > 1.96")
    cohort_comparison: Dict[str, Any] = Field(default_factory=dict, description="Summary stats against Random Early Buyers & Whales")

class SmartMoneyEvaluation(BaseModel):
    """Evaluation of smart-money predictive capability across multiple regimes and risk metrics."""
    wallet_address: str
    is_smart_money: bool
    predictive_score: float = Field(..., ge=0.0, le=100.0)
    early_accumulation_ratio: float = Field(..., description="Ratio of positions accumulated prior to measurable price expansion")
    catastrophic_avoidance_score: float = Field(..., ge=0.0, le=100.0, description="Ability to avoid >70% loss rugpulls/collapses")
    multi_regime_consistency: Dict[str, float] = Field(default_factory=dict, description="Performance across BULL, BEAR, and VOLATILE regimes")
    skill_vs_luck: SkillVsLuckResult
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SellPressureMetrics(BaseModel):
    """Liquidation impact metrics when selling portions of a position into available liquidity."""
    holding_tokens: float
    holding_usd: float
    liquidation_percentage: float  # e.g. 0.25 (25%)
    liquidated_usd: float
    pool_liquidity_usd: float
    estimated_price_impact_percent: float = Field(..., description="Estimated slippage/price collapse percentage if liquidated")
    sell_pressure_index: float = Field(..., ge=0.0, le=100.0, description="0-100 risk rating of liquidation severity")

class WhaleMarketImpact(BaseModel):
    """Market impact metrics for a whale position considering executable liquidity, not just size."""
    wallet_address: str
    token_address: str
    token_balance: float
    holding_usd: float
    supply_percentage: float = Field(..., description="% of total or circulating token supply controlled")
    executable_liquidity_share: float = Field(..., description="Ratio of position USD size to total pool liquidity USD")
    sell_pressure_10pct: SellPressureMetrics
    sell_pressure_25pct: SellPressureMetrics
    sell_pressure_50pct: SellPressureMetrics
    sell_pressure_100pct: SellPressureMetrics
    concentration_rank: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW market impact risk rating")
    accumulation_rate_24h: float = Field(default=0.0, description="Percent change in balance over last 24h")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CoordinatedWhaleAlert(BaseModel):
    """Alert triggered when multiple whale wallets engage in synchronized accumulation or distribution."""
    token_address: str
    participating_whales: List[str]
    total_coordinated_usd: float
    action_type: str  # ACCUMULATION, DISTRIBUTION, SYNCHRONIZED_EXIT
    confidence: float
    window_seconds: float
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ManipulationPattern(BaseModel):
    """Individual detected manipulation pattern."""
    pattern_type: str  # SNIPER_GROUP, BUNDLED_PURCHASE, RAPID_FUNDING_CHAIN, ARTIFICIAL_HOLDERS, WASH_TRADING, SYNCHRONIZED_EXITS
    severity: str  # HIGH, MEDIUM, LOW
    confidence: float = Field(..., ge=0.0, le=1.0)
    participating_wallets: List[str]
    description: str
    details: Dict[str, Any] = Field(default_factory=dict)

class TokenManipulationReport(BaseModel):
    """Full manipulation and insider ownership risk assessment for a token."""
    token_address: str
    chain: str
    overall_manipulation_score: float = Field(..., ge=0.0, le=100.0, description="0 = Organic, 100 = Heavily Manipulated")
    insider_concentration_ratio: float = Field(..., description="% of token supply held by linked insider clusters")
    detected_patterns: List[ManipulationPattern] = Field(default_factory=list)
    top_cluster_sizes: List[int] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DowngradeSignal(BaseModel):
    """Feeds both Security and Opportunity scoring systems to penalize suspicious tokens."""
    token_address: str
    security_risk_multiplier: float = Field(..., ge=1.0, description="Multiplier for security risk score (>=1.0)")
    opportunity_penalty_points: float = Field(..., ge=0.0, le=100.0, description="Points subtracted from opportunity score")
    reason: str
    manipulation_score: float
    downgrade_recommended: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

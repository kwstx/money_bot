from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from enum import Enum

class TokenTransferEventType(str, Enum):
    TRANSFER = "TRANSFER"
    MINT = "MINT"
    BURN = "BURN"
    BRIDGE_IN = "BRIDGE_IN"
    BRIDGE_OUT = "BRIDGE_OUT"
    LIQUIDITY_ADD = "LIQUIDITY_ADD"
    LIQUIDITY_REMOVE = "LIQUIDITY_REMOVE"
    CONTRACT_EXECUTION = "CONTRACT_EXECUTION"

class HolderCategory(str, Enum):
    POOL = "POOL"
    EXCHANGE = "EXCHANGE"
    BURN = "BURN"
    STAKING = "STAKING"
    BRIDGE = "BRIDGE"
    TREASURY = "TREASURY"
    INSIDER = "INSIDER"
    DEVELOPER = "DEVELOPER"
    SMART_MONEY = "SMART_MONEY"
    WHALE = "WHALE"
    RETAIL = "RETAIL"
    TECHNICAL_OTHER = "TECHNICAL_OTHER"

class GrowthTrajectoryPattern(str, Enum):
    ORGANIC_ACCUMULATION = "ORGANIC_ACCUMULATION"
    BOT_AIRDROP_CHURN = "BOT_AIRDROP_CHURN"
    PUMP_AND_DUMP = "PUMP_AND_DUMP"
    SLOW_BLEED = "SLOW_BLEED"
    INSTITUTIONAL_HOLD = "INSTITUTIONAL_HOLD"
    STAGNANT = "STAGNANT"

class TokenTransferEvent(BaseModel):
    event_id: str = Field(..., description="Unique event identifier or transaction hash")
    token_address: str = Field(..., description="Token contract address")
    tx_hash: str = Field(..., description="Transaction hash")
    block_number: Optional[int] = Field(default=None)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sender: str = Field(..., description="Sender wallet or contract address")
    receiver: str = Field(..., description="Receiver wallet or contract address")
    amount: float = Field(..., description="Amount of tokens transferred")
    event_type: TokenTransferEventType = Field(default=TokenTransferEventType.TRANSFER)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class WalletOwnershipState(BaseModel):
    address: str
    token_address: str
    balance: float = Field(default=0.0)
    percent_of_supply: float = Field(default=0.0)
    first_seen_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_transfers_count: int = Field(default=0)
    category: HolderCategory = Field(default=HolderCategory.RETAIL)
    is_technical_account: bool = Field(default=False)
    is_contract: bool = Field(default=False)

class HistoricalOwnershipSnapshot(BaseModel):
    snapshot_id: str
    token_address: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_supply: float
    circulating_supply: float
    total_holders_count: int
    economically_meaningful_holders_count: int
    top_10_concentration_pct: float
    top_20_concentration_pct: float
    top_50_concentration_pct: float
    gini_coefficient: float
    average_balance: float
    median_balance: float
    percentile_balances: Dict[str, float] = Field(
        default_factory=lambda: {"p10": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.0, "p99": 0.0}
    )
    technical_accounts_supply_pct: float = Field(default=0.0)

class HolderVelocityAndRetention(BaseModel):
    token_address: str
    time_window_hours: int = 24
    new_holder_count: int = 0
    new_holder_rate: float = 0.0  # new holders per hour
    holder_exits_count: int = 0   # holders dropping to zero balance
    retention_rate_pct: float = 0.0 # percentage retained over window
    net_holder_growth: int = 0
    concentration_delta_top10: float = 0.0  # change in top 10 % share over window
    ownership_velocity: float = 0.0  # rate of supply redistribution

class OwnershipDistributionMetrics(BaseModel):
    token_address: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    insider_concentration_pct: float = 0.0
    developer_concentration_pct: float = 0.0
    smart_money_participation_pct: float = 0.0
    smart_money_holder_count: int = 0
    whale_concentration_pct: float = 0.0
    whale_holder_count: int = 0
    retail_participation_pct: float = 0.0
    retail_holder_count: int = 0
    technical_accounts_supply_pct: float = 0.0
    wallet_diversity_index: float = 0.0  # 0 to 100 (entropy-based)
    inactive_holder_share_pct: float = 0.0  # % supply in dormant wallets (>30 days)
    economically_meaningful_holders_count: int = 0
    technical_accounts_count: int = 0

class HolderQualityMetrics(BaseModel):
    token_address: str
    churn_rate_24h_pct: float = 0.0
    retention_rate_7d_pct: float = 0.0
    retention_rate_30d_pct: float = 0.0
    sybil_coordination_score: float = 0.0  # 0 to 100 (high = suspected artificial/bot sybil)
    organic_growth_score: float = 0.0     # 0 to 100
    trajectory_classification: GrowthTrajectoryPattern = GrowthTrajectoryPattern.STAGNANT
    trajectory_similarity_scores: Dict[str, float] = Field(default_factory=dict)
    holder_quality_score: float = 0.0     # composite score 0 to 100

class LiquidityOwnershipHealthView(BaseModel):
    token_address: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    holder_concentration_risk_score: float = 0.0  # 0 to 100
    executable_depth_usd_1pct: float = 0.0
    executable_depth_usd_2pct: float = 0.0
    executable_depth_usd_5pct: float = 0.0
    slippage_buy_5k_pct: float = 0.0
    slippage_sell_5k_pct: float = 0.0
    slippage_sell_25k_pct: float = 0.0
    lp_stability_score: float = 0.0             # 0 to 100
    lp_lock_pct: float = 0.0
    seller_pressure_risk_ratio: float = 0.0      # ratio of sellable whale/insider holdings to 2% depth
    exit_feasibility_index: float = 0.0          # 0 to 100 (ease of exiting without crash)
    overall_market_health_score: float = 0.0     # 0 to 100
    risk_warnings: List[str] = Field(default_factory=list)

class SectionEightAnalysisReport(BaseModel):
    token_address: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    latest_snapshot: HistoricalOwnershipSnapshot
    velocity_retention: HolderVelocityAndRetention
    distribution_metrics: OwnershipDistributionMetrics
    quality_metrics: HolderQualityMetrics
    market_health_view: LiquidityOwnershipHealthView
    overall_section_eight_score: float = Field(..., description="Overall composite Section 8 score (0-100)")

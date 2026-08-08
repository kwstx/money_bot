from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import uuid


class PriceObservation(BaseModel):
    """Raw price observation from a specific provider or DEX pool."""
    source_id: str = Field(..., description="Provider or DEX identifier (e.g., UniswapV3, Pyth, Chainlink, DexScreener)")
    price_usd: float = Field(..., description="Observed price in USD")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of observation")
    pool_address: Optional[str] = Field(default=None, description="Pool contract address if DEX")
    liquidity_usd: float = Field(default=0.0, description="Available pool liquidity in USD")
    volume_24h_usd: float = Field(default=0.0, description="24h volume for the pool/source")
    weight: float = Field(default=1.0, description="Source reliability weight (0.0 to 1.0)")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReconciledPrice(BaseModel):
    """Consolidated and reconciled price output with confidence and provenance."""
    token_address: str
    chain: str
    price_usd: float = Field(..., description="Reconciled price in USD")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score of the price")
    is_reliable: bool = Field(default=True, description="Whether price meets reliability criteria for decision-making")
    provider_count: int = Field(..., description="Number of valid data sources contributing")
    rejected_sources: List[str] = Field(default_factory=list, description="Sources rejected due to staleness or outlier status")
    deviation_pct: float = Field(default=0.0, description="Max deviation among valid sources")
    provenance: List[PriceObservation] = Field(default_factory=list, description="Sources used to calculate price")
    last_trade_timestamp: Optional[datetime] = Field(default=None, description="Recency of last executed trade")
    rejection_reasons: List[str] = Field(default_factory=list, description="Reasons if price was rejected or marked unreliable")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LiquidityPoolState(BaseModel):
    """Detailed state of a liquidity pool."""
    pool_address: str
    dex_name: str
    token0_address: str
    token1_address: str
    reserve0: float = Field(default=0.0)
    reserve1: float = Field(default=0.0)
    total_liquidity_usd: float = Field(default=0.0)
    fee_tier_pct: float = Field(default=0.3)
    lp_distribution: Dict[str, float] = Field(default_factory=dict, description="LP wallet address -> pool ownership share (0.0 to 1.0)")
    is_locked: bool = Field(default=False)
    lock_expiry: Optional[datetime] = Field(default=None)
    unlock_schedule: List[Dict[str, Any]] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LiquidityRiskEvent(BaseModel):
    """Event emitted when liquidity risk threshold is breached."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    token_address: str
    chain: str
    risk_type: str = Field(..., description="SHARP_LIQUIDITY_DROP, HIGH_LP_CONCENTRATION, DRAIN_RISK")
    severity: str = Field(..., description="INFO, WARNING, CRITICAL")
    current_liquidity_usd: float
    previous_liquidity_usd: Optional[float] = None
    max_executable_exit_usd: float
    top_lp_concentration_pct: float
    description: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = Field(default_factory=dict)


class LiquidityAnalysis(BaseModel):
    """Engine analysis output for token liquidity."""
    token_address: str
    chain: str
    total_liquidity_usd: float = Field(default=0.0)
    depth_1pct_usd: float = Field(default=0.0, description="Liquidity available within 1% price impact")
    depth_2pct_usd: float = Field(default=0.0, description="Liquidity available within 2% price impact")
    depth_5pct_usd: float = Field(default=0.0, description="Liquidity available within 5% price impact")
    max_realistic_exit_usd: float = Field(default=0.0, description="Capital that can exit before exceeding 2% impact")
    max_realistic_entry_usd: float = Field(default=0.0, description="Capital that can enter before exceeding 2% impact")
    top3_lp_concentration_pct: float = Field(default=0.0, description="Percentage of total LP held by top 3 LPs")
    herfindahl_index: float = Field(default=0.0, description="LP concentration Herfindahl index (0 to 1)")
    is_liquidity_locked: bool = Field(default=False)
    liquidity_drop_24h_pct: float = Field(default=0.0)
    drain_risk_detected: bool = Field(default=False)
    risk_level: str = Field(default="LOW", description="LOW, MEDIUM, HIGH, CRITICAL")
    active_pools: List[LiquidityPoolState] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TradeObservation(BaseModel):
    """Single trade transaction observation."""
    tx_hash: str
    token_address: str
    chain: str
    trader_address: str
    is_buy: bool
    amount_tokens: float
    amount_usd: float
    price_usd: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    block_number: Optional[int] = None
    gas_price_gwei: Optional[float] = None
    is_smart_money: bool = Field(default=False)
    is_whale: bool = Field(default=False)
    is_developer: bool = Field(default=False)


class VolumeAnalysis(BaseModel):
    """Volume engine breakdown and anomaly detection."""
    token_address: str
    chain: str
    raw_volume_24h_usd: float = Field(default=0.0)
    organic_volume_24h_usd: float = Field(default=0.0)
    suspicious_volume_24h_usd: float = Field(default=0.0)
    smart_money_volume_24h_usd: float = Field(default=0.0)
    whale_volume_24h_usd: float = Field(default=0.0)
    retail_volume_24h_usd: float = Field(default=0.0)
    developer_volume_24h_usd: float = Field(default=0.0)
    
    # Acceleration metrics across time windows
    acceleration_5m: float = Field(default=1.0, description="Volume growth ratio 5m vs baseline")
    acceleration_15m: float = Field(default=1.0, description="Volume growth ratio 15m vs baseline")
    acceleration_1h: float = Field(default=1.0, description="Volume growth ratio 1h vs baseline")
    acceleration_24h: float = Field(default=1.0, description="Volume growth ratio 24h vs baseline")

    # Manipulation flags
    wash_trading_score: float = Field(default=0.0, ge=0.0, le=1.0)
    repetitive_trade_score: float = Field(default=0.0, ge=0.0, le=1.0)
    synchronized_tx_score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_artificial_burst: bool = Field(default=False)
    detected_anomalies: List[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SupplyBreakdown(BaseModel):
    """Comprehensive token supply categories."""
    total_supply: float = Field(default=0.0)
    circulating_supply: float = Field(default=0.0)
    burned_supply: float = Field(default=0.0)
    locked_supply: float = Field(default=0.0)
    treasury_supply: float = Field(default=0.0)
    exchange_balances: float = Field(default=0.0)
    other_non_circulating: float = Field(default=0.0)


class SupplyEvent(BaseModel):
    """Event recording material changes in token supply."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    token_address: str
    chain: str
    event_type: str = Field(..., description="MINT, BURN, UNLOCK, TREASURY_RELEASE, MIGRATION")
    amount: float = Field(..., description="Number of tokens minted/burned/unlocked")
    pct_of_total_supply: float = Field(default=0.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tx_hash: Optional[str] = None
    description: str = Field(default="")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ValuationAnalysis(BaseModel):
    """Valuation Engine intelligence output."""
    token_address: str
    chain: str
    price_usd: float = Field(default=0.0)
    market_cap_usd: float = Field(default=0.0, description="Circulating Supply * Price")
    fdv_usd: float = Field(default=0.0, description="Total Supply * Price")
    supply: SupplyBreakdown = Field(default_factory=SupplyBreakdown)
    effective_market_cap_ratio: float = Field(default=0.0, description="Market Cap / Liquidity Ratio")
    valuation_confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    circulating_supply_assumptions: List[str] = Field(default_factory=list)
    recent_supply_events: List[SupplyEvent] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

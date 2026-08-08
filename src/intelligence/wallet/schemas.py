from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

class Position(BaseModel):
    """Tracks token balances, transaction metrics, realized and unrealized ROI/P&L."""
    token_address: str
    symbol: Optional[str] = None
    total_bought_tokens: float = 0.0
    total_bought_usd: float = 0.0
    total_sold_tokens: float = 0.0
    total_sold_usd: float = 0.0
    current_balance: float = 0.0
    average_buy_price: float = 0.0
    
    realized_pnl_usd: float = 0.0
    realized_roi: float = 0.0
    unrealized_pnl_usd: float = 0.0
    unrealized_roi: float = 0.0
    
    first_buy_time: Optional[datetime] = None
    last_trade_time: Optional[datetime] = None
    trades_count: int = 0
    holding_periods: List[float] = Field(default_factory=list, description="Durations (in seconds) of completed holding cycles")

class FundingSource(BaseModel):
    """Represents a tracer link showing how a wallet was funded."""
    sender_address: str
    token_address: str = "native"
    amount: float
    amount_usd: float = 0.0
    timestamp: datetime
    tx_hash: str

class CounterpartySummary(BaseModel):
    """Aggregates interactions with another wallet address."""
    address: str
    incoming_count: int = 0
    outgoing_count: int = 0
    total_volume_usd: float = 0.0
    last_interaction_time: datetime

class BehavioralPatterns(BaseModel):
    """Tracks trading frequencies, active hours, and transaction types."""
    trade_velocity_24h: float = 0.0
    swap_count: int = 0
    transfer_count: int = 0
    liquidity_ops_count: int = 0
    active_hours: List[int] = Field(default_factory=lambda: [0]*24, description="Count of transactions per hour (0-23)")
    contracts_deployed_count: int = 0
    average_holding_period_seconds: float = 0.0

class WalletScore(BaseModel):
    """Multi-dimensional wallet rating engine state."""
    score: float = 50.0
    early_entry_score: float = 50.0
    consistency_score: float = 50.0
    risk_adjusted_profit_score: float = 50.0
    holding_discipline_score: float = 50.0
    exit_timing_score: float = 50.0
    regime_scores: Dict[str, float] = Field(default_factory=dict, description="Regime name -> score mapping")
    min_trades_satisfied: bool = False
    total_trades: int = 0
    last_updated: datetime

class ReputationLabel(BaseModel):
    """Dynamic, reversible category label with evidence tracing."""
    label: str  # SMART_MONEY, WHALE, RETAIL, DEVELOPER, INSIDER_CANDIDATE, EXCHANGE, MARKET_MAKER, LIQUIDITY_PROVIDER, TREASURY, BOT, UNKNOWN
    confidence: float = 1.0  # 0.0 to 1.0
    evidence: List[str] = Field(default_factory=list)
    assigned_at: datetime

from src.schemas import CanonicalIdentity

class WalletProfile(CanonicalIdentity):
    """Unified profile representing all tracked states of a wallet."""
    address: str
    chain: str
    
    positions: Dict[str, Position] = Field(default_factory=dict)
    funding_sources: List[FundingSource] = Field(default_factory=list)
    top_counterparties: Dict[str, CounterpartySummary] = Field(default_factory=dict)
    behavior: BehavioralPatterns = Field(default_factory=BehavioralPatterns)
    score: WalletScore = Field(default_factory=lambda: WalletScore(last_updated=datetime.now(timezone.utc)))
    reputation_labels: List[ReputationLabel] = Field(default_factory=list)
    is_followed: bool = False
    
    metadata: Dict[str, Any] = Field(default_factory=dict)

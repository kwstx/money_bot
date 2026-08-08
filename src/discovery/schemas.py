from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid

class MilestoneType(str, Enum):
    FIRST_BUY = "FIRST_BUY"
    FIRST_100_WALLETS = "FIRST_100_WALLETS"
    SIGNIFICANT_LIQUIDITY_INCREASE = "SIGNIFICANT_LIQUIDITY_INCREASE"
    WHALE_ENTRY = "WHALE_ENTRY"
    RAPID_VOLUME_ACCELERATION = "RAPID_VOLUME_ACCELERATION"

class EventType(str, Enum):
    NEW_TOKEN = "NEW_TOKEN"
    PAIR_CREATED = "PAIR_CREATED"
    LIQUIDITY_ADDED = "LIQUIDITY_ADDED"
    SWAP_EXECUTED = "SWAP_EXECUTED"
    TRADING_ACTIVATED = "TRADING_ACTIVATED"
    BRIDGE_TRANSFER = "BRIDGE_TRANSFER"

class TokenDeploymentMetadata(BaseModel):
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain identifier")
    deployer_address: Optional[str] = Field(default=None, description="Deployer wallet address")
    creation_tx_hash: Optional[str] = Field(default=None, description="Contract deployment transaction hash")
    block_number: Optional[int] = Field(default=None, description="Deployment block number")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    initial_supply: Optional[float] = Field(default=None, description="Initial total supply")
    bytecode_hash: Optional[str] = Field(default=None, description="Bytecode hash if EVM")
    is_verified_source: bool = Field(default=False, description="Whether source code is verified")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class PoolRecord(BaseModel):
    pool_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pool_address: str = Field(..., description="Liquidity pool address")
    chain: str = Field(..., description="Blockchain identifier")
    dex_name: str = Field(..., description="DEX protocol name (e.g. UniswapV2, Raydium, PumpFun)")
    factory_address: Optional[str] = Field(default=None, description="DEX factory address")
    token0_address: str = Field(..., description="Address of token 0")
    token1_address: str = Field(..., description="Address of token 1")
    target_token_address: str = Field(..., description="Address of target token being tracked")
    quote_token_address: str = Field(..., description="Quote token address (e.g. WETH, SOL, USDC)")
    initial_reserve0: float = Field(default=0.0)
    initial_reserve1: float = Field(default=0.0)
    initial_liquidity_usd: float = Field(default=0.0)
    creation_tx_hash: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

class LaunchMetrics(BaseModel):
    token_address: str
    chain: str
    launch_time: datetime
    launch_age_seconds: float = Field(default=0.0)
    time_to_liquidity_seconds: float = Field(default=0.0)
    initial_liquidity_usd: float = Field(default=0.0)
    current_liquidity_usd: float = Field(default=0.0)
    initial_volume_usd: float = Field(default=0.0)
    holder_count: int = Field(default=0)
    first_buyers: List[str] = Field(default_factory=list)
    top10_holder_concentration_pct: float = Field(default=0.0)
    buy_count: int = Field(default=0)
    sell_count: int = Field(default=0)
    buy_sell_ratio: float = Field(default=1.0)
    buy_velocity_per_min: float = Field(default=0.0)
    bot_transaction_ratio: float = Field(default=0.0)
    contract_risk_score: float = Field(default=0.0, description="0.0 = low risk, 1.0 = extreme risk")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MilestoneEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    milestone: MilestoneType
    token_address: str
    chain: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    description: str
    value: float = Field(default=0.0)
    details: Dict[str, Any] = Field(default_factory=dict)

class UnifiedChainEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    chain: str
    block_number: Optional[int] = Field(default=None)
    tx_hash: Optional[str] = Field(default=None)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    token_address: Optional[str] = Field(default=None)
    pool_address: Optional[str] = Field(default=None)
    wallet_address: Optional[str] = Field(default=None)
    payload: Dict[str, Any] = Field(default_factory=dict)

class CrossChainTokenRepresentation(BaseModel):
    chain: str
    token_address: str
    pool_address: Optional[str] = None
    is_canonical: bool = False
    is_wrapped: bool = False
    bridge_protocol: Optional[str] = None
    liquidity_usd: float = 0.0
    volume_24h_usd: float = 0.0
    holder_count: int = 0

class CrossChainAssetGroup(BaseModel):
    group_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    asset_name: str
    canonical_symbol: str
    representations: List[CrossChainTokenRepresentation] = Field(default_factory=list)
    bridges: List[Dict[str, Any]] = Field(default_factory=list)
    total_aggregated_liquidity_usd: float = Field(default=0.0)
    total_aggregated_volume_24h_usd: float = Field(default=0.0)
    total_deduplicated_holders: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ConfidenceAssessment(BaseModel):
    token_address: str
    chain: str
    discovery_confidence: float = Field(..., ge=0.0, le=1.0, description="Authenticity of token discovery event")
    investment_confidence: float = Field(..., ge=0.0, le=1.0, description="Conviction score based on risk & metrics")
    discovery_factors: Dict[str, float] = Field(default_factory=dict)
    investment_factors: Dict[str, float] = Field(default_factory=dict)
    rapid_security_passed: bool = Field(default=False)
    rapid_liquidity_passed: bool = Field(default=False)
    trade_eligible: bool = Field(default=False)
    rejection_reasons: List[str] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

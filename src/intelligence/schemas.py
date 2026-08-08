from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import uuid

class AssetTransfer(BaseModel):
    """Represents a transfer of an asset (native or token) within a transaction."""
    token_address: str = Field(..., description="Contract address of the token (or 'native')")
    symbol: Optional[str] = Field(default=None)
    amount: float = Field(..., description="Amount of tokens/assets transferred")
    amount_usd: float = Field(default=0.0, description="Approximate USD value of the transfer")

class DecodedTransaction(BaseModel):
    """Decoded representation of a raw blockchain transaction."""
    tx_hash: str = Field(..., description="Transaction hash or signature")
    chain: str = Field(..., description="Blockchain network (e.g. ethereum, solana)")
    block_number: Optional[int] = Field(default=None)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Action classification: TRANSFER, SWAP, LIQUIDITY_ADD, LIQUIDITY_REMOVE, APPROVAL, MINT, BURN, STAKING, GOVERNANCE, TREASURY, CONTRACT_ADMIN, BRIDGE
    action_type: str = Field(..., description="Decoded activity classification")
    
    sender: str = Field(..., description="Address that initiated or signed the transaction")
    receiver: Optional[str] = Field(default=None, description="Direct recipient of the transaction")
    contract_address: Optional[str] = Field(default=None, description="Interacted contract address if applicable")
    
    assets_involved: List[AssetTransfer] = Field(default_factory=list, description="Assets transferred or swapped")
    economic_value_usd: float = Field(default=0.0, description="Total estimated economic value of the transaction in USD")
    status: str = Field(default="SUCCESS", description="SUCCESS or FAILED")
    
    liquidity_context: Dict[str, Any] = Field(default_factory=dict, description="Context about associated liquidity pools if applicable")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional logs, raw traces, or chain-specific data")

class BuySellIntelligence(BaseModel):
    """Market purchase or sale intelligence extracted from decoded transactions."""
    tx_hash: str
    chain: str
    timestamp: datetime
    token_address: str
    trader_address: str
    
    direction: str = Field(..., description="BUY, SELL, or UNKNOWN")
    amount_tokens: float = Field(..., description="Amount of the token traded")
    amount_usd: float = Field(..., description="Estimated USD value of the trade")
    price_usd: float = Field(..., description="Approximate execution price per token in USD")
    
    liquidity_usd_at_execution: float = Field(default=0.0, description="Available pool liquidity in USD at execution")
    mcap_usd_at_execution: float = Field(default=0.0, description="Market capitalization of the token at execution")
    
    size_relative_to_liquidity: float = Field(default=0.0, description="USD size relative to pool liquidity (ratio)")
    size_relative_to_mcap: float = Field(default=0.0, description="USD size relative to token market cap (ratio)")
    
    # Wallet classification tags: RETAIL, WHALE, SMART_MONEY, DEVELOPER, CONTRACT, NEW_WALLET
    wallet_classification: List[str] = Field(default_factory=list, description="Classifications for the trader's wallet")
    
    sequence_id: Optional[str] = Field(default=None, description="Associated sequence or campaign identifier if detected")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class FlowIntelligence(BaseModel):
    """Continuous flow analytics and sequence detection outcomes."""
    token_address: str
    chain: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    window_size_seconds: int = Field(default=300, description="Time window in seconds for flow calculations")
    
    buy_volume_usd: float = Field(default=0.0)
    sell_volume_usd: float = Field(default=0.0)
    buy_sell_imbalance: float = Field(default=0.0, description="Ratio of buy/sell pressure between -1.0 and 1.0")
    
    # Classification frequency e.g. {"small": 10, "medium": 5, "large": 2, "whale": 0}
    trade_size_distribution: Dict[str, int] = Field(default_factory=dict)
    transaction_velocity: float = Field(default=0.0, description="Transactions per minute")
    
    # ACCUMULATION, DISTRIBUTION, NEUTRAL
    accumulation_status: str = Field(default="NEUTRAL")
    
    whale_pressure: float = Field(default=0.0, description="Whale net flow in USD (positive represents buying)")
    smart_money_pressure: float = Field(default=0.0, description="Smart money net flow in USD")
    
    participation_change: float = Field(default=0.0, description="Percent change in unique active wallets vs previous window")
    active_wallets_count: int = Field(default=0)
    
    detected_sequences: List[Dict[str, Any]] = Field(default_factory=list, description="Identified multi-transaction sequences in window")
    metadata: Dict[str, Any] = Field(default_factory=dict)

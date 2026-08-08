from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid

class AdministrativePermissions(BaseModel):
    """Permissions matrix for privileged contract actors."""
    can_mint: bool = Field(default=False, description="Ability to mint new tokens and dilute supply")
    can_freeze: bool = Field(default=False, description="Ability to freeze accounts or pause transfers")
    can_blacklist: bool = Field(default=False, description="Ability to blacklist specific addresses from trading")
    can_alter_fees: bool = Field(default=False, description="Ability to change buy/sell/transfer tax rates")
    can_restrict_trading: bool = Field(default=False, description="Ability to set max transaction size, max wallet limit, or trading pause")
    can_modify_balances: bool = Field(default=False, description="Ability to directly mutate user balances or force transfers")
    can_upgrade_logic: bool = Field(default=False, description="Ability to replace contract implementation code via proxy")
    can_change_ownership: bool = Field(default=False, description="Ability to transfer administrative ownership or roles")
    can_pause_trading: bool = Field(default=False, description="Ability to pause or disable trading for all users")
    can_withdraw_contract_funds: bool = Field(default=False, description="Ability to drain ETH/tokens from contract treasury")
    other_dangerous_capabilities: List[str] = Field(default_factory=list, description="List of custom dangerous functions detected")


class ProxyMetadata(BaseModel):
    """Metadata regarding contract proxy and upgradeability implementation."""
    is_proxy: bool = Field(default=False, description="Whether the contract is a proxy wrapper")
    proxy_type: Optional[str] = Field(default=None, description="Proxy standard (e.g. EIP-1967, EIP-1822 UUPS, EIP-897, Beacon, Transparent, Custom)")
    implementation_address: Optional[str] = Field(default=None, description="Current underlying implementation logic contract address")
    admin_address: Optional[str] = Field(default=None, description="Proxy admin address capable of upgrading logic")
    beacon_address: Optional[str] = Field(default=None, description="Beacon contract address if BeaconProxy")


class DeploymentMetadata(BaseModel):
    """Metadata regarding token deployment history."""
    deployer_address: str = Field(..., description="Wallet address that deployed the contract")
    deployment_tx_hash: Optional[str] = Field(default=None, description="Deployment transaction hash")
    deployment_block: Optional[int] = Field(default=None, description="Block number when deployed")
    deployment_timestamp: Optional[datetime] = Field(default=None, description="Timestamp of contract deployment")
    initial_supply: Optional[float] = Field(default=None, description="Initial token supply at deployment")


class ContractScanResult(BaseModel):
    """Result of smart contract bytecode, ABI, source code, and permission scanning."""
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain network name")
    bytecode_hash: Optional[str] = Field(default=None, description="SHA256 / Keccak hash of deployed bytecode")
    is_verified: bool = Field(default=False, description="Whether source code is verified on block explorer")
    source_code_snippet: Optional[str] = Field(default=None, description="Truncated source code or key snippets")
    abi_methods: List[str] = Field(default_factory=list, description="List of detected function signatures")
    deployment_metadata: DeploymentMetadata
    proxy_info: ProxyMetadata
    permissions: AdministrativePermissions
    risk_flags: List[str] = Field(default_factory=list, description="High priority warning flags from contract scanner")


class OwnershipLog(BaseModel):
    """Historical record of ownership transfer event."""
    tx_hash: str = Field(..., description="Transaction hash of ownership change")
    previous_owner: str = Field(..., description="Previous owner address")
    new_owner: str = Field(..., description="New owner address")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OwnershipEvaluation(BaseModel):
    """Evaluation of ownership, renouncement, multisig governance, and backdoor risks."""
    token_address: str = Field(..., description="Token contract address")
    current_owner: str = Field(..., description="Current owner address or contract")
    is_renounced: bool = Field(default=False, description="Whether primary owner is zero address or dead address")
    renouncement_address: Optional[str] = Field(default=None, description="Address owner was set to (e.g. 0x0 or 0xdead)")
    is_fake_renouncement: bool = Field(default=False, description="Whether apparent renouncement is bypassed by hidden admin mechanisms")
    fake_renouncement_reasons: List[str] = Field(default_factory=list, description="List of detected bypass backdoors")
    governance_type: str = Field(default="EOA", description="Governance classification: EOA, MULTISIG_GNOSIS, TIMELOCK_CONTROLLER, GOVERNANCE_DAO, RENOUNCED")
    privileged_roles: Dict[str, List[str]] = Field(default_factory=dict, description="Map of role names to assigned addresses")
    historical_changes: List[OwnershipLog] = Field(default_factory=list, description="History of ownership modifications")
    upgradeability_risk: str = Field(default="NONE", description="Upgradeability risk rating: NONE, LOW, MEDIUM, HIGH, CRITICAL")
    upgradeability_details: Dict[str, Any] = Field(default_factory=dict, description="Detailed upgradeability risk factors")


class TaxEstimate(BaseModel):
    """Estimated transaction tax rates."""
    buy_tax_percent: float = Field(default=0.0, description="Estimated Buy tax percentage (0.0 to 100.0)")
    sell_tax_percent: float = Field(default=0.0, description="Estimated Sell tax percentage (0.0 to 100.0)")
    transfer_tax_percent: float = Field(default=0.0, description="Estimated Transfer tax percentage (0.0 to 100.0)")
    expected_vs_simulated_buy_diff: float = Field(default=0.0, description="Difference between advertised and simulated buy tax")
    expected_vs_simulated_sell_diff: float = Field(default=0.0, description="Difference between advertised and simulated sell tax")


class TradeSimulation(BaseModel):
    """Individual trade simulation run for a specific test wallet archetype."""
    wallet_type: str = Field(..., description="Persona: STANDARD_EOA, FRESH_WALLET, WHALE_WALLET, CONTRACT")
    buy_success: bool = Field(default=True, description="Whether buy simulation succeeded without revert")
    sell_success: bool = Field(default=True, description="Whether sell simulation succeeded without revert")
    transfer_success: bool = Field(default=True, description="Whether wallet-to-wallet transfer succeeded")
    buy_revert_reason: Optional[str] = Field(default=None, description="Revert reason if buy failed")
    sell_revert_reason: Optional[str] = Field(default=None, description="Revert reason if sell failed")
    transfer_revert_reason: Optional[str] = Field(default=None, description="Revert reason if transfer failed")
    gas_used_buy: int = Field(default=150000, description="Gas consumed during buy simulation")
    gas_used_sell: int = Field(default=150000, description="Gas consumed during sell simulation")
    tax_estimate: TaxEstimate = Field(default_factory=TaxEstimate)


class HoneypotSimulationResult(BaseModel):
    """Comprehensive honeypot and trade simulation result."""
    token_address: str = Field(..., description="Token contract address")
    is_honeypot: bool = Field(default=False, description="Whether token is classified as a honeypot")
    honeypot_reason: Optional[str] = Field(default=None, description="Primary reason for honeypot classification")
    simulation_failed: bool = Field(default=False, description="Whether technical simulation execution failed")
    simulation_failure_as_risk: bool = Field(default=True, description="Treating simulation failure as explicit security risk signal")
    simulations_by_wallet: List[TradeSimulation] = Field(default_factory=list)
    is_dynamic_tax: bool = Field(default=False, description="Whether buy/sell taxes change dynamically over time or per tx")
    is_wallet_specific_tax: bool = Field(default=False, description="Whether taxes differ based on wallet age, type, or whitelist")
    observed_market_tax_discrepancy: bool = Field(default=False, description="Discrepancy between simulated and DEX observed taxes")
    observed_buy_tax_avg: Optional[float] = Field(default=None, description="Average buy tax observed in DEX market trades")
    observed_sell_tax_avg: Optional[float] = Field(default=None, description="Average sell tax observed in DEX market trades")
    max_tx_amount: Optional[float] = Field(default=None, description="Detected maximum transaction limit in tokens")
    max_wallet_amount: Optional[float] = Field(default=None, description="Detected maximum wallet balance limit in tokens")
    anti_whale_active: bool = Field(default=False, description="Whether anti-whale or cooldown timers are active")
    overall_honeypot_risk_score: float = Field(default=0.0, description="Honeypot risk score from 0.0 (safe) to 100.0 (honeypot)")


class LPLockDetails(BaseModel):
    """Liquidity Pool lock and unlock metadata."""
    is_lp_locked: bool = Field(default=False, description="Whether LP tokens are locked or burned")
    lock_percentage: float = Field(default=0.0, description="Percentage of total LP tokens locked (0.0 to 100.0)")
    unlock_timestamp: Optional[datetime] = Field(default=None, description="Timestamp when LP lock expires")
    lock_duration_remaining_seconds: Optional[float] = Field(default=None, description="Remaining seconds until LP unlock")
    lock_provider: Optional[str] = Field(default=None, description="Lock service (e.g. UNCX, PinkSale, TeamFinance, DeadAddress)")


class HolderConcentration(BaseModel):
    """Token holder distribution & concentration metrics."""
    top10_percentage: float = Field(default=0.0, description="Total supply held by top 10 holders excluding DEX pair")
    dev_wallet_percentage: float = Field(default=0.0, description="Total supply held by deployer/dev wallets")
    insider_wallets_percentage: float = Field(default=0.0, description="Total supply held by identified insider clusters")
    liquidity_pair_percentage: float = Field(default=0.0, description="Total supply held in main DEX liquidity pool")


class RugRiskReport(BaseModel):
    """Unified Rug Pull Risk Assessment and Execution Gatekeeper Decision."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain network name")
    rug_risk_score: float = Field(..., description="Overall rug risk score from 0.0 (safe) to 100.0 (extreme rug risk)")
    risk_level: str = Field(..., description="Risk level: LOW, MEDIUM, HIGH, CRITICAL")
    sudden_lp_removal_detected: bool = Field(default=False, description="Sudden LP withdrawal or liquidity drain detected")
    privileged_contract_change_detected: bool = Field(default=False, description="Malicious administrative contract change detected")
    developer_sell_detected: bool = Field(default=False, description="Deployer/Developer dumping tokens into LP")
    coordinated_distribution_detected: bool = Field(default=False, description="Coordinated distribution event to sybil wallets detected")
    block_execution: bool = Field(default=False, description="Gatekeeper decision: whether to immediately block automated trading")
    execution_blocking_reasons: List[str] = Field(default_factory=list, description="Detailed list of conditions triggering execution block")
    risk_breakdown: Dict[str, float] = Field(default_factory=dict, description="Risk sub-scores for individual components")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ComprehensiveSecurityAssessment(BaseModel):
    """Combined output of all Section 7 Security Systems."""
    token_address: str
    chain: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    contract_scan: ContractScanResult
    ownership_eval: OwnershipEvaluation
    honeypot_res: HoneypotSimulationResult
    rug_report: RugRiskReport
    is_safe_for_trading: bool
    summary: str

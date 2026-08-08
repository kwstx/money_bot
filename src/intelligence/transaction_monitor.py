import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from src.intelligence.schemas import DecodedTransaction, AssetTransfer

logger = logging.getLogger(__name__)

# Standard ERC20/Uniswap event topic signatures
TOPIC_TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
TOPIC_APPROVAL = "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925"
TOPIC_SWAP_V2 = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"
TOPIC_SWAP_V3 = "0xc42079f94a6350d7e6235f29174924f928a50122e379a9a8839104b8975835e"
TOPIC_MINT_V2 = "0x4c209b533d6575124f5911409617c10b48aa02167ec35f12e8c10d4090aae40f"
TOPIC_BURN_V2 = "0xdccd412f0b7c2a27a252a38b1f55a4df523b3ef"

class TransactionMonitor:
    """
    Transaction Monitor.
    Decodes raw blockchain transactions (from EVM and Solana structures) into structured,
    understandable actions with asset details, economic values, and context.
    """

    def __init__(self, treasury_addresses: Optional[List[str]] = None):
        # Configured treasury or multisig addresses to detect treasury operations
        self.treasury_addresses = {addr.lower() for addr in (treasury_addresses or [])}

    def decode(self, raw_tx: Dict[str, Any]) -> DecodedTransaction:
        """
        Decodes a raw transaction structure into a structured DecodedTransaction.
        Supports EVM transaction logs, transaction inputs, and Solana signature/instruction info.
        """
        try:
            # 1. Basic properties extraction
            tx_hash = raw_tx.get("tx_hash") or raw_tx.get("hash") or raw_tx.get("signature") or raw_tx.get("id") or "0xunknown"
            chain = raw_tx.get("chain") or raw_tx.get("blockchain_id") or "ethereum"
            block_number = raw_tx.get("block_number") or raw_tx.get("blockNumber")
            
            # Timestamp parsing
            timestamp = raw_tx.get("timestamp")
            if not timestamp:
                dt = datetime.now(timezone.utc)
            elif isinstance(timestamp, (int, float)):
                # Handle unix timestamp
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            elif isinstance(timestamp, str):
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    dt = datetime.now(timezone.utc)
            else:
                dt = datetime.now(timezone.utc)
                
            sender = raw_tx.get("sender") or raw_tx.get("from") or raw_tx.get("signer") or raw_tx.get("from_address") or "0xunknown"
            receiver = raw_tx.get("receiver") or raw_tx.get("to") or raw_tx.get("to_address")
            contract_address = raw_tx.get("contract_address") or raw_tx.get("interacted_contract")
            
            # Status extraction
            status_val = raw_tx.get("status")
            status = "SUCCESS"
            if status_val is not None:
                if str(status_val).lower() in ["failed", "fail", "error", "0", "false"]:
                    status = "FAILED"
                    
            # 2. Extract assets involved
            assets_involved = []
            raw_assets = raw_tx.get("assets_involved") or raw_tx.get("transfers") or []
            for asset in raw_assets:
                if isinstance(asset, dict):
                    assets_involved.append(
                        AssetTransfer(
                            token_address=asset.get("token_address") or asset.get("address") or "native",
                            symbol=asset.get("symbol"),
                            amount=float(asset.get("amount") or 0.0),
                            amount_usd=float(asset.get("amount_usd") or 0.0)
                        )
                    )
            
            # If no assets parsed but we have native transfer value
            native_value = raw_tx.get("value") or raw_tx.get("amount")
            if native_value and not assets_involved:
                try:
                    amount = float(native_value)
                    if amount > 0:
                        assets_involved.append(
                            AssetTransfer(
                                token_address="native",
                                symbol="ETH" if "solana" not in chain.lower() else "SOL",
                                amount=amount,
                                amount_usd=float(raw_tx.get("value_usd") or raw_tx.get("amount_usd") or 0.0)
                            )
                        )
                except ValueError:
                    pass

            economic_value_usd = float(raw_tx.get("economic_value_usd") or raw_tx.get("value_usd") or sum(a.amount_usd for a in assets_involved))
            
            # 3. Classify transaction action type
            action_type = "TRANSFER"
            liquidity_context = {}
            metadata = raw_tx.get("metadata") or {}
            
            # Heuristics based on logs and topics
            logs = raw_tx.get("logs") or []
            input_data = str(raw_tx.get("input") or raw_tx.get("data") or "").lower()
            
            # Extract topics for EVM
            topics = []
            for log in logs:
                if isinstance(log, dict) and "topics" in log:
                    topics.extend(log["topics"])
            
            # Check Gnosis Safe/multisig patterns or configured treasuries for treasury movement
            is_treasury = False
            if sender.lower() in self.treasury_addresses or (receiver and receiver.lower() in self.treasury_addresses):
                is_treasury = True
            elif "multisig" in sender.lower() or (receiver and "multisig" in receiver.lower()):
                is_treasury = True
                
            # Classify action type based on properties/topics/input
            if is_treasury:
                action_type = "TREASURY"
            elif any(topic == TOPIC_SWAP_V2 or topic == TOPIC_SWAP_V3 for topic in topics) or "swap" in input_data:
                action_type = "SWAP"
            elif any(topic == TOPIC_MINT_V2 for topic in topics) or "addliquidity" in input_data.replace("_", ""):
                action_type = "LIQUIDITY_ADD"
            elif any(topic == TOPIC_BURN_V2 for topic in topics) or "removeliquidity" in input_data.replace("_", ""):
                action_type = "LIQUIDITY_REMOVE"
            elif any(topic == TOPIC_APPROVAL for topic in topics) or input_data.startswith("0x095ea7b3"): # approve(address,uint256)
                action_type = "APPROVAL"
            elif "mint" in input_data:
                # Differentiate between ERC20 Mint and general mint
                action_type = "MINT"
            elif "burn" in input_data:
                action_type = "BURN"
            elif any(k in input_data for k in ["stake", "unstake", "deposit", "withdraw", "claim"]) and "staking" in input_data:
                action_type = "STAKING"
            elif any(k in input_data for k in ["propose", "vote", "castvote", "delegate", "governance"]):
                action_type = "GOVERNANCE"
            elif any(k in input_data for k in ["renounceownership", "transferownership", "setfee", "upgradeto", "initialize", "pause", "unpause", "0x71505871", "0xf2fde38b"]):
                action_type = "CONTRACT_ADMIN"
            elif any(k in input_data for k in ["bridge", "teleport", "crosschain", "wormhole", "axelar"]):
                action_type = "BRIDGE"
            # Fallbacks based on category fields
            elif raw_tx.get("action") or raw_tx.get("action_type") or raw_tx.get("event_category"):
                act = str(raw_tx.get("action") or raw_tx.get("action_type") or raw_tx.get("event_category")).upper()
                if act in ["TRANSFER", "SWAP", "LIQUIDITY_ADD", "LIQUIDITY_REMOVE", "APPROVAL", "MINT", "BURN", "STAKING", "GOVERNANCE", "TREASURY", "CONTRACT_ADMIN", "BRIDGE"]:
                    action_type = act
                elif "swap" in act.lower():
                    action_type = "SWAP"
                elif "liquidity" in act.lower():
                    action_type = "LIQUIDITY_ADD" if "add" in act.lower() else "LIQUIDITY_REMOVE"
                elif "bridge" in act.lower():
                    action_type = "BRIDGE"
                    
            # Populate liquidity context if swap or liquidity operation
            if action_type in ["SWAP", "LIQUIDITY_ADD", "LIQUIDITY_REMOVE"]:
                liquidity_context = {
                    "pool_address": raw_tx.get("pool_address") or contract_address,
                    "dex_name": raw_tx.get("dex_name") or raw_tx.get("dex") or "UnknownDEX",
                    "reserve0": raw_tx.get("reserve0"),
                    "reserve1": raw_tx.get("reserve1")
                }

            return DecodedTransaction(
                tx_hash=tx_hash,
                chain=chain,
                block_number=block_number,
                timestamp=dt,
                action_type=action_type,
                sender=sender,
                receiver=receiver,
                contract_address=contract_address,
                assets_involved=assets_involved,
                economic_value_usd=economic_value_usd,
                status=status,
                liquidity_context=liquidity_context,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Failed to decode transaction: {e}")
            raise

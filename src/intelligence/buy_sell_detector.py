import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone
from src.intelligence.schemas import DecodedTransaction, BuySellIntelligence

logger = logging.getLogger(__name__)

class BuySellDetector:
    """
    Buy and Sell Detector.
    Identifies actual market purchases and sales from transactions, determines pricing,
    measures sizes relative to pool liquidity/mcap, classifies trader wallets, and identifies
    coordination/sequence indicators.
    """

    def __init__(
        self,
        whale_threshold_usd: float = 10000.0,
        retail_threshold_usd: float = 500.0,
        smart_money_addresses: Optional[List[str]] = None,
        new_wallet_age_threshold_sec: float = 3600.0, # 1 hour
    ):
        self.whale_threshold_usd = whale_threshold_usd
        self.retail_threshold_usd = retail_threshold_usd
        self.smart_money_addresses = {addr.lower() for addr in (smart_money_addresses or [])}
        self.new_wallet_age_threshold_sec = new_wallet_age_threshold_sec
        # Temporary memory cache of newly funded wallets to identify sequences
        # wallet_address -> funding_source_address
        self.funded_wallets: Dict[str, str] = {}

    def register_funding(self, wallet_address: str, funding_source: str) -> None:
        """Helper to register that a wallet was funded by a specific source address."""
        self.funded_wallets[wallet_address.lower()] = funding_source.lower()

    def detect(
        self,
        decoded_tx: DecodedTransaction,
        token_address: str,
        current_price_usd: float = 0.0,
        total_liquidity_usd: float = 0.0,
        market_cap_usd: float = 0.0,
        developer_address: Optional[str] = None,
        is_smart_money_override: bool = False,
    ) -> Optional[BuySellIntelligence]:
        """
        Detects buy or sell market intelligence from a decoded transaction.
        Returns BuySellIntelligence if a trade is identified, or None otherwise.
        """
        token_address_lower = token_address.lower()
        trader_address = decoded_tx.sender
        
        # 1. Identify if transaction contains a swap/trade of target token
        # We look for a Swap action, or a Transfer involving a pool contract
        is_trade = False
        direction = "UNKNOWN"
        amount_tokens = 0.0
        amount_usd = 0.0
        
        # Check action type
        if decoded_tx.action_type == "SWAP":
            is_trade = True
        
        # Look for target token transfers in assets_involved
        token_transfer = None
        base_transfer = None # Native or stablecoin used to buy/sell
        
        for asset in decoded_tx.assets_involved:
            if asset.token_address.lower() == token_address_lower:
                token_transfer = asset
            elif asset.token_address.lower() in ["native", "usdc", "usdt", "dai", "weth", "wsol"]:
                base_transfer = asset
                
        if token_transfer:
            is_trade = True
            amount_tokens = token_transfer.amount
            amount_usd = token_transfer.amount_usd
            
            # If swap, direction is determined by flow of target token:
            # - If target token is incoming (positive amount or flow indicates receipt):
            # - Let's look at receiver or logs. Or if we know the trader is decoded_tx.sender,
            #   and we receive it, it's a BUY.
            #   Let's check if the raw transaction explicitly specifies is_buy or if receiver matches trader.
            is_buy = decoded_tx.metadata.get("is_buy")
            if is_buy is not None:
                direction = "BUY" if is_buy else "SELL"
            else:
                # Heuristics:
                # If we have base_transfer, did we send base and receive token?
                # If receiver is trader_address, it means trader is getting the token -> BUY.
                # If receiver is a pool/contract, and sender is trader, trader is sending token -> SELL.
                # Let's inspect logs or metadata or default to sender/receiver flow.
                if decoded_tx.receiver and decoded_tx.receiver.lower() == trader_address.lower():
                    direction = "BUY"
                elif decoded_tx.receiver and decoded_tx.receiver.lower() == token_address_lower:
                    direction = "SELL"
                else:
                    # Let's look at transaction structure. If sender sends base asset, it's BUY.
                    # If sender sends token_address, it's SELL.
                    if decoded_tx.sender.lower() == trader_address.lower():
                        # Standard trade path
                        # If base asset USD value is greater than zero and token is transferred to sender
                        direction = "BUY" # Default to buy if not clearly sell
                        # Check metadata for direction
                        if "sell" in decoded_tx.metadata.get("action_type", "").lower() or "sell" in decoded_tx.metadata.get("event_type", "").lower():
                            direction = "SELL"
                        elif "buy" in decoded_tx.metadata.get("action_type", "").lower() or "buy" in decoded_tx.metadata.get("event_type", "").lower():
                            direction = "BUY"
                        elif base_transfer and base_transfer.amount_usd > 0:
                            # Swap base for token = BUY. Swap token for base = SELL.
                            # Usually, if we transfer token out to a contract and get base in, it's a SELL.
                            pass

        if not is_trade:
            return None

        # Determine price
        if amount_tokens > 0:
            price_usd = amount_usd / amount_tokens
        else:
            price_usd = current_price_usd
            
        if price_usd <= 0:
            price_usd = current_price_usd

        # Calculate relative sizes
        size_relative_to_liquidity = (amount_usd / total_liquidity_usd) if total_liquidity_usd > 0 else 0.0
        size_relative_to_mcap = (amount_usd / market_cap_usd) if market_cap_usd > 0 else 0.0

        # 2. Wallet Classification
        wallet_classification = []
        
        # RETAIL vs WHALE
        if amount_usd >= self.whale_threshold_usd:
            wallet_classification.append("WHALE")
        elif amount_usd <= self.retail_threshold_usd:
            wallet_classification.append("RETAIL")
            
        # SMART_MONEY
        if is_smart_money_override or trader_address.lower() in self.smart_money_addresses:
            wallet_classification.append("SMART_MONEY")
            
        # DEVELOPER
        if developer_address and trader_address.lower() == developer_address.lower():
            wallet_classification.append("DEVELOPER")
            
        # CONTRACT
        # Check if address starts with contract characteristics or is flagged in metadata
        if decoded_tx.metadata.get("is_contract") or decoded_tx.contract_address == trader_address:
            wallet_classification.append("CONTRACT")
            
        # NEW_WALLET
        # If we have tracked funding source for this wallet, it is flagged as a funded/linked wallet,
        # which is a strong indicator of a new or staged wallet.
        funding_source = self.funded_wallets.get(trader_address.lower())
        if funding_source or decoded_tx.metadata.get("is_new_wallet"):
            wallet_classification.append("NEW_WALLET")
            if funding_source and "SMART_MONEY" not in wallet_classification:
                wallet_classification.append("SMART_MONEY")
            
        # If empty, default to standard user
        if not wallet_classification:
            wallet_classification.append("RETAIL")

        # 3. Determine if part of a sequence / campaign
        sequence_id = None
        if funding_source:
            # Group by funding source to identify staged accumulation campaigns
            sequence_id = f"campaign_funded_by_{funding_source[:10]}"
        elif "campaign" in decoded_tx.metadata:
            sequence_id = decoded_tx.metadata["campaign"]

        return BuySellIntelligence(
            tx_hash=decoded_tx.tx_hash,
            chain=decoded_tx.chain,
            timestamp=decoded_tx.timestamp,
            token_address=token_address,
            trader_address=trader_address,
            direction=direction,
            amount_tokens=amount_tokens,
            amount_usd=amount_usd,
            price_usd=price_usd,
            liquidity_usd_at_execution=total_liquidity_usd,
            mcap_usd_at_execution=market_cap_usd,
            size_relative_to_liquidity=size_relative_to_liquidity,
            size_relative_to_mcap=size_relative_to_mcap,
            wallet_classification=wallet_classification,
            sequence_id=sequence_id,
            metadata=decoded_tx.metadata
        )

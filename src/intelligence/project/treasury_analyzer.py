from typing import List, Dict, Any
from datetime import datetime, timezone
from .schemas import TreasuryState

class TreasuryAnalyzer:
    """Analyzes treasury wallet movements and assesses associated risks."""
    
    def __init__(self, treasury_wallets: List[str]):
        self.treasury_wallets = treasury_wallets
        
    def _is_exchange_address(self, address: str) -> bool:
        """Mock method: determines if an address belongs to a known CEX."""
        # In a real implementation, this would query a known address database
        return "exchange" in address.lower() or "binance" in address.lower() or "coinbase" in address.lower()
        
    def _is_dex_liquidity_pool(self, address: str) -> bool:
        """Mock method: determines if an address is a DEX pair/pool."""
        return "pool" in address.lower() or "pair" in address.lower()
        
    def analyze_transactions(self, transactions: List[Dict[str, Any]]) -> TreasuryState:
        """
        Analyzes a batch of transactions involving treasury wallets.
        Identifies inflows, outflows, CEX transfers, and liquidity interactions.
        """
        total_inflows = 0.0
        total_outflows = 0.0
        exchange_transfers = 0.0
        liquidity_interactions = 0.0
        unexplained_movements = 0.0
        
        for tx in transactions:
            sender = tx.get("sender", "")
            receiver = tx.get("receiver", "")
            amount_usd = tx.get("amount_usd", 0.0)
            justification = tx.get("justification", "")
            
            is_outflow = sender in self.treasury_wallets
            is_inflow = receiver in self.treasury_wallets
            
            if is_outflow:
                total_outflows += amount_usd
                
                if self._is_exchange_address(receiver):
                    exchange_transfers += amount_usd
                elif self._is_dex_liquidity_pool(receiver):
                    liquidity_interactions += amount_usd
                elif not justification:
                    # If it's not a known contract and has no public justification
                    unexplained_movements += amount_usd
                    
            elif is_inflow:
                total_inflows += amount_usd
                
                if self._is_dex_liquidity_pool(sender):
                    # Pulling liquidity
                    liquidity_interactions += amount_usd
                    
        # Determine risk level based on unexplained movements relative to total outflows
        risk_level = "LOW"
        if total_outflows > 0:
            unexplained_ratio = unexplained_movements / total_outflows
            if unexplained_ratio > 0.5 or exchange_transfers > total_outflows * 0.4:
                risk_level = "HIGH"
            elif unexplained_ratio > 0.2:
                risk_level = "MEDIUM"
                
        return TreasuryState(
            treasury_wallets=self.treasury_wallets,
            timestamp=datetime.now(timezone.utc),
            inflows_24h_usd=total_inflows,
            outflows_24h_usd=total_outflows,
            exchange_transfers_usd=exchange_transfers,
            liquidity_interactions_usd=liquidity_interactions,
            unexplained_movements_usd=unexplained_movements,
            risk_level=risk_level
        )

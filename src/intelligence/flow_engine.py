import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from src.intelligence.schemas import DecodedTransaction, BuySellIntelligence, FlowIntelligence

logger = logging.getLogger(__name__)

class FlowEngine:
    """
    Market Flow Intelligence Engine.
    Continuously tracks rolling windows of transactions to calculate imbalance, velocity,
    distribution, and pressure metrics, and runs sequence detection to connect multiple
    transactions into campaigns (funding, staged accumulation, dump/distribution).
    """

    def __init__(self, window_size_seconds: int = 300):
        self.window_size_seconds = window_size_seconds
        
        # History caches (retained for 24 hours for memory efficiency)
        self.trade_history: Dict[str, List[BuySellIntelligence]] = defaultdict(list)
        # funding_transfers: sender -> list of (receiver, amount, timestamp)
        self.funding_transfers: List[DecodedTransaction] = []
        # liquidity_removals: token_address -> list of liquidity removal events
        self.liquidity_events: Dict[str, List[DecodedTransaction]] = defaultdict(list)
        
        # Keep track of active wallets count in previous windows for velocity/participation change
        # token_key -> list of (window_end_time, active_wallets_count)
        self.participation_history: Dict[str, List[Tuple[datetime, int]]] = defaultdict(list)

    def record_decoded_transaction(self, tx: DecodedTransaction) -> None:
        """Records general transactions (transfers, liquidity) to aid sequence detection."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)
        
        # Record funding transfers (native asset transfers that could fund new wallets)
        # Usually from a source to a receiver where value > 0
        if tx.action_type == "TRANSFER":
            has_native = any(a.token_address == "native" for a in tx.assets_involved)
            if has_native or tx.economic_value_usd > 0:
                self.funding_transfers.append(tx)
                
        # Record liquidity events
        if tx.action_type in ["LIQUIDITY_ADD", "LIQUIDITY_REMOVE"]:
            for asset in tx.assets_involved:
                if asset.token_address != "native":
                    key = f"{tx.chain}:{asset.token_address.lower()}"
                    self.liquidity_events[key].append(tx)
                    
        # Evict old items
        self.funding_transfers = [t for t in self.funding_transfers if t.timestamp >= cutoff]
        for k in list(self.liquidity_events.keys()):
            self.liquidity_events[k] = [t for t in self.liquidity_events[k] if t.timestamp >= cutoff]

    def record_trade(self, trade: BuySellIntelligence) -> None:
        """Records buy/sell trade intelligence."""
        key = f"{trade.chain}:{trade.token_address.lower()}"
        self.trade_history[key].append(trade)
        
        # Evict old trades
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)
        self.trade_history[key] = [t for t in self.trade_history[key] if t.timestamp >= cutoff]

    def _detect_sequences(
        self,
        token_address: str,
        chain: str,
        trades: List[BuySellIntelligence],
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Runs sequence analysis algorithms to connect transactions:
        1. Wallet Funding -> Purchase
        2. Staged Accumulation across multiple wallets
        3. Liquidity Withdrawal -> Distribution (selloff)
        """
        detected = []
        token_key = f"{chain}:{token_address.lower()}"
        
        # 1. Detect Wallet Funding -> Purchase
        # Find native funding events that occurred up to 30 mins before any buy trade in the window
        buyer_wallets = {t.trader_address.lower() for t in trades if t.direction == "BUY"}
        
        funding_links: Dict[str, Tuple[str, float, datetime]] = {} # wallet -> (funding_source, amount, time)
        for tx in self.funding_transfers:
            if tx.receiver and tx.receiver.lower() in buyer_wallets:
                # Find matching native transfer
                for asset in tx.assets_involved:
                    if asset.token_address == "native":
                        funding_links[tx.receiver.lower()] = (tx.sender.lower(), asset.amount, tx.timestamp)

        # Connect funding to trade
        for trade in trades:
            if trade.direction == "BUY" and trade.trader_address.lower() in funding_links:
                f_source, f_amount, f_time = funding_links[trade.trader_address.lower()]
                time_diff = (trade.timestamp - f_time).total_seconds()
                if 0 <= time_diff <= 1800: # funded within 30 minutes before buying
                    seq = {
                        "type": "wallet_funding_purchase",
                        "funding_wallet": f_source,
                        "buying_wallet": trade.trader_address,
                        "token_address": token_address,
                        "funding_amount_native": f_amount,
                        "trade_amount_usd": trade.amount_usd,
                        "delay_seconds": int(time_diff),
                        "timestamp": trade.timestamp.isoformat()
                    }
                    detected.append(seq)

        # 2. Detect Staged Accumulation Campaigns
        # Multiple buyer wallets funded by the SAME source wallet buying in the same window
        funded_buyers = defaultdict(list) # source_wallet -> list of trades
        for trade in trades:
            if trade.direction == "BUY" and trade.trader_address.lower() in funding_links:
                f_source, _, _ = funding_links[trade.trader_address.lower()]
                funded_buyers[f_source].append(trade)

        for source, linked_trades in funded_buyers.items():
            unique_buyers = {t.trader_address for t in linked_trades}
            if len(unique_buyers) >= 2: # At least 2 wallets funded by same source
                total_campaign_usd = sum(t.amount_usd for t in linked_trades)
                seq = {
                    "type": "staged_accumulation",
                    "funding_wallet": source,
                    "buying_wallets": list(unique_buyers),
                    "token_address": token_address,
                    "total_amount_usd": round(total_campaign_usd, 2),
                    "trades_count": len(linked_trades),
                    "timestamp": end_time.isoformat()
                }
                detected.append(seq)

        # 3. Liquidity Withdrawal -> Distribution (Rug pull sequence)
        # Check if a LIQUIDITY_REMOVE occurred recently, and then subsequent sells by related wallets
        removals = self.liquidity_events.get(token_key, [])
        active_removals = [r for r in removals if r.action_type == "LIQUIDITY_REMOVE" and (end_time - r.timestamp).total_seconds() <= 1800] # within 30 mins
        
        if active_removals:
            # We have a liquidity withdrawal. Now check if there are sells in this window
            sells = [t for t in trades if t.direction == "SELL"]
            if sells:
                sell_vol = sum(s.amount_usd for s in sells)
                sellers = {s.trader_address for s in sells}
                # Check if sellers include the developer/LP remover, or are connected to the remover
                removers = {r.sender for r in active_removals}
                
                seq = {
                    "type": "liquidity_withdrawal_distribution",
                    "removers": list(removers),
                    "selling_wallets": list(sellers),
                    "sell_volume_usd": round(sell_vol, 2),
                    "token_address": token_address,
                    "pool_address": active_removals[0].liquidity_context.get("pool_address"),
                    "timestamp": end_time.isoformat()
                }
                detected.append(seq)

        return detected

    def calculate_flow_metrics(
        self,
        token_address: str,
        chain: str,
        window_seconds: Optional[int] = None
    ) -> FlowIntelligence:
        """
        Calculates flow analytics (buy/sell imbalance, trade distributions, pressures, velocities)
        over the specified rolling window, and connects transactions into sequences.
        """
        win_size = window_seconds or self.window_size_seconds
        token_key = f"{chain}:{token_address.lower()}"
        all_trades = self.trade_history.get(token_key, [])
        
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(seconds=win_size)
        
        # Filter trades within the window
        trades_in_window = [t for t in all_trades if start_time <= t.timestamp <= end_time]
        
        if not trades_in_window:
            return FlowIntelligence(
                token_address=token_address,
                chain=chain,
                timestamp=end_time,
                window_size_seconds=win_size,
                active_wallets_count=0
            )

        # Run sequence detectors first to identify coordinated campaigns
        detected_seqs = self._detect_sequences(token_address, chain, trades_in_window, start_time, end_time)
        
        # Build set of coordinated wallet addresses
        coordinated_wallets = set()
        for seq in detected_seqs:
            if "buying_wallets" in seq:
                for w in seq["buying_wallets"]:
                    coordinated_wallets.add(w.lower())
            if "buying_wallet" in seq:
                coordinated_wallets.add(seq["buying_wallet"].lower())
            if "selling_wallets" in seq:
                for w in seq["selling_wallets"]:
                    coordinated_wallets.add(w.lower())

        # 1. Volume and Imbalance Calculations
        buy_vol = 0.0
        sell_vol = 0.0
        active_wallets = set()
        
        whale_buy_vol = 0.0
        whale_sell_vol = 0.0
        sm_buy_vol = 0.0
        sm_sell_vol = 0.0
        
        # Trade size distribution categories
        distribution = {"small": 0, "medium": 0, "large": 0, "whale": 0}
        
        for t in trades_in_window:
            trader_lower = t.trader_address.lower()
            active_wallets.add(trader_lower)
            
            is_smart_money = "SMART_MONEY" in t.wallet_classification or trader_lower in coordinated_wallets
            is_whale = "WHALE" in t.wallet_classification
            
            # Bucketing
            if t.amount_usd < 500:
                distribution["small"] += 1
            elif t.amount_usd < 2000:
                distribution["medium"] += 1
            elif t.amount_usd < 10000:
                distribution["large"] += 1
            else:
                distribution["whale"] += 1

            if t.direction == "BUY":
                buy_vol += t.amount_usd
                if is_whale:
                    whale_buy_vol += t.amount_usd
                if is_smart_money:
                    sm_buy_vol += t.amount_usd
            elif t.direction == "SELL":
                sell_vol += t.amount_usd
                if is_whale:
                    whale_sell_vol += t.amount_usd
                if is_smart_money:
                    sm_sell_vol += t.amount_usd

        total_vol = buy_vol + sell_vol
        buy_sell_imbalance = (buy_vol - sell_vol) / total_vol if total_vol > 0 else 0.0
        
        # Pressure Metrics
        whale_pressure = whale_buy_vol - whale_sell_vol
        smart_money_pressure = sm_buy_vol - sm_sell_vol
        
        # Accumulation / Distribution state classification
        accumulation_status = "NEUTRAL"
        if buy_sell_imbalance > 0.25 and (whale_pressure > 0 or smart_money_pressure > 0):
            accumulation_status = "ACCUMULATION"
        elif buy_sell_imbalance < -0.25 and (whale_pressure < 0 or smart_money_pressure < 0):
            accumulation_status = "DISTRIBUTION"

        # Velocity (trades per minute)
        velocity = len(trades_in_window) / (win_size / 60.0)

        # 2. Participation Changes
        # Find active wallets count in previous window to calculate changes
        prev_start = start_time - timedelta(seconds=win_size)
        prev_trades = [t for t in all_trades if prev_start <= t.timestamp < start_time]
        prev_wallets_count = len({t.trader_address.lower() for t in prev_trades})
        
        current_wallets_count = len(active_wallets)
        
        if prev_wallets_count > 0:
            participation_change = (current_wallets_count - prev_wallets_count) / prev_wallets_count
        else:
            participation_change = 0.0

        return FlowIntelligence(
            token_address=token_address,
            chain=chain,
            timestamp=end_time,
            window_size_seconds=win_size,
            buy_volume_usd=round(buy_vol, 2),
            sell_volume_usd=round(sell_vol, 2),
            buy_sell_imbalance=round(buy_sell_imbalance, 4),
            trade_size_distribution=distribution,
            transaction_velocity=round(velocity, 2),
            accumulation_status=accumulation_status,
            whale_pressure=round(whale_pressure, 2),
            smart_money_pressure=round(smart_money_pressure, 2),
            participation_change=round(participation_change, 4),
            active_wallets_count=current_wallets_count,
            detected_sequences=detected_seqs,
            metadata={
                "total_trades": len(trades_in_window),
                "whale_buy_vol": whale_buy_vol,
                "whale_sell_vol": whale_sell_vol,
                "sm_buy_vol": sm_buy_vol,
                "sm_sell_vol": sm_sell_vol
            }
        )

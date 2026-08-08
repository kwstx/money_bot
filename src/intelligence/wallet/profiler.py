import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone, timedelta
from src.intelligence.schemas import DecodedTransaction, BuySellIntelligence
from src.intelligence.wallet.schemas import (
    WalletProfile,
    Position,
    FundingSource,
    CounterpartySummary,
    BehavioralPatterns
)

logger = logging.getLogger(__name__)

class WalletProfiler:
    """
    Tracks and maintains individual wallet profiles, including positions, realized/unrealized
    performance, funding sources, counterparties, holding periods, and behavioral analytics.
    """
    def __init__(self, followed_addresses: Optional[List[str]] = None):
        self.followed_wallets = {addr.lower() for addr in (followed_addresses or [])}

    def follow_wallet(self, address: str) -> None:
        """Designate a wallet address for followed-wallet monitoring."""
        self.followed_wallets.add(address.lower())

    def unfollow_wallet(self, address: str) -> None:
        """Remove a wallet address from monitoring."""
        self.followed_wallets.discard(address.lower())

    def is_followed(self, address: str) -> bool:
        """Check if the address is on the monitoring list."""
        return address.lower() in self.followed_wallets

    def create_profile(self, address: str, chain: str) -> WalletProfile:
        """Create a new blank profile for a wallet address."""
        is_followed = self.is_followed(address)
        addr_lower = address.lower()
        return WalletProfile(
            canonical_id=f"profile_{addr_lower}",
            address=addr_lower,
            chain=chain,
            is_followed=is_followed,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

    def record_trade(self, profile: WalletProfile, trade: BuySellIntelligence, current_price_usd: float = 0.0) -> None:
        """
        Updates token position based on a buy/sell trade.
        Calculates cost basis, realized performance, holding periods, and updates timestamps.
        """
        token_addr = trade.token_address.lower()
        
        # Get or create position
        if token_addr not in profile.positions:
            profile.positions[token_addr] = Position(token_address=token_addr)
            
        pos = profile.positions[token_addr]
        pos.trades_count += 1
        pos.last_trade_time = trade.timestamp

        # Add to history timestamps in metadata for velocity tracking
        if "trade_timestamps" not in profile.metadata:
            profile.metadata["trade_timestamps"] = []
        profile.metadata["trade_timestamps"].append(trade.timestamp.isoformat())

        if trade.direction == "BUY":
            if pos.first_buy_time is None:
                pos.first_buy_time = trade.timestamp
            
            # Calculate cost basis (average buy price)
            new_total_tokens = pos.total_bought_tokens + trade.amount_tokens
            new_total_usd = pos.total_bought_usd + trade.amount_usd
            if new_total_tokens > 0:
                pos.average_buy_price = new_total_usd / new_total_tokens
                
            pos.total_bought_tokens = new_total_tokens
            pos.total_bought_usd = new_total_usd
            pos.current_balance += trade.amount_tokens

        elif trade.direction == "SELL":
            # Realized PNL calculations based on average buy price cost basis
            cost_basis_sold = pos.average_buy_price * trade.amount_tokens
            realized_pnl = trade.amount_usd - cost_basis_sold
            pos.realized_pnl_usd += realized_pnl
            
            pos.total_sold_tokens += trade.amount_tokens
            pos.total_sold_usd += trade.amount_usd
            
            if pos.total_bought_usd > 0:
                pos.realized_roi = pos.realized_pnl_usd / pos.total_bought_usd
            else:
                pos.realized_roi = 0.0
                
            pos.current_balance = max(0.0, pos.current_balance - trade.amount_tokens)

            # Check if holding cycle completed
            if pos.current_balance < 1e-6: # fully exited position
                if pos.first_buy_time is not None:
                    duration = (trade.timestamp - pos.first_buy_time).total_seconds()
                    pos.holding_periods.append(duration)
                    pos.first_buy_time = None  # reset for next cycle

        # Update unrealized performance
        price = current_price_usd if current_price_usd > 0 else trade.price_usd
        if pos.current_balance > 0 and price > 0:
            current_val = pos.current_balance * price
            cost_basis = pos.current_balance * pos.average_buy_price
            pos.unrealized_pnl_usd = current_val - cost_basis
            if cost_basis > 0:
                pos.unrealized_roi = pos.unrealized_pnl_usd / cost_basis
            else:
                pos.unrealized_roi = 0.0
        else:
            pos.unrealized_pnl_usd = 0.0
            pos.unrealized_roi = 0.0

        # Update profile update timestamp
        profile.updated_at = datetime.now(timezone.utc)
        
        # Refresh behavioral holding metrics
        self._refresh_behavioral_metrics(profile)

    def record_transaction(self, profile: WalletProfile, tx: DecodedTransaction) -> None:
        """
        Record basic transaction details to maintain:
        - Funding sources (first incoming native asset transfer)
        - Counterparty maps (frequency, volume)
        - Behavioral patterns (velocity, transaction types, active hours)
        """
        tx_sender = tx.sender.lower()
        tx_receiver = tx.receiver.lower() if tx.receiver else None
        my_address = profile.address.lower()

        # Update active hours (0-23)
        hour = tx.timestamp.hour
        profile.behavior.active_hours[hour] += 1

        # Classify transaction action
        if tx.action_type == "SWAP":
            profile.behavior.swap_count += 1
        elif tx.action_type == "TRANSFER":
            profile.behavior.transfer_count += 1
        elif tx.action_type in ["LIQUIDITY_ADD", "LIQUIDITY_REMOVE"]:
            profile.behavior.liquidity_ops_count += 1
        elif tx.action_type == "CONTRACT_ADMIN" or (tx_receiver is None and tx.contract_address is not None):
            profile.behavior.contracts_deployed_count += 1

        # Tracing Funding Source (first native inflow)
        if not profile.funding_sources and tx_receiver == my_address:
            # Check if transaction contains a transfer of native asset
            for asset in tx.assets_involved:
                if asset.token_address == "native" and asset.amount > 0:
                    profile.funding_sources.append(
                        FundingSource(
                            sender_address=tx_sender,
                            token_address="native",
                            amount=asset.amount,
                            amount_usd=asset.amount_usd,
                            timestamp=tx.timestamp,
                            tx_hash=tx.tx_hash
                        )
                    )
                    break

        # Maintain counterparties
        other_party = None
        is_incoming = False
        if tx_sender != my_address:
            other_party = tx_sender
            is_incoming = True
        elif tx_receiver and tx_receiver != my_address:
            other_party = tx_receiver
            is_incoming = False

        if other_party and other_party != "0xunknown":
            if other_party not in profile.top_counterparties:
                profile.top_counterparties[other_party] = CounterpartySummary(
                    address=other_party,
                    last_interaction_time=tx.timestamp
                )
            
            c_summary = profile.top_counterparties[other_party]
            if is_incoming:
                c_summary.incoming_count += 1
            else:
                c_summary.outgoing_count += 1
                
            c_summary.total_volume_usd += tx.economic_value_usd
            c_summary.last_interaction_time = max(c_summary.last_interaction_time, tx.timestamp)

        # Update profile update timestamp
        profile.updated_at = datetime.now(timezone.utc)
        
        # Refresh behavioral metrics
        self._refresh_behavioral_metrics(profile)

    def _refresh_behavioral_metrics(self, profile: WalletProfile) -> None:
        """Internal helper to recompute aggregated stats on profile."""
        now = datetime.now(timezone.utc)
        
        # 1. Average Holding Period
        all_durations = []
        for pos in profile.positions.values():
            all_durations.extend(pos.holding_periods)
            # Add duration of currently active cycle if it started a while ago
            if pos.first_buy_time is not None:
                all_durations.append((now - pos.first_buy_time).total_seconds())

        if all_durations:
            profile.behavior.average_holding_period_seconds = sum(all_durations) / len(all_durations)
        else:
            profile.behavior.average_holding_period_seconds = 0.0

        # 2. Trade velocity (last 24 hours trades)
        timestamps_str = profile.metadata.get("trade_timestamps", [])
        valid_ts = []
        for ts_str in timestamps_str:
            try:
                ts = datetime.fromisoformat(ts_str)
                if (now - ts).total_seconds() <= 86400:
                    valid_ts.append(ts_str)
            except ValueError:
                pass
        
        profile.metadata["trade_timestamps"] = valid_ts
        profile.behavior.trade_velocity_24h = len(valid_ts)

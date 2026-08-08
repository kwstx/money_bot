import logging
import math
import statistics
import uuid
from typing import Dict, List, Optional, Tuple, Set, Any
from datetime import datetime, timezone, timedelta

from src.intelligence.holder.schemas import (
    TokenTransferEvent,
    TokenTransferEventType,
    WalletOwnershipState,
    HistoricalOwnershipSnapshot,
    HolderVelocityAndRetention,
    HolderCategory
)

logger = logging.getLogger(__name__)

ZERO_ADDRESSES = {
    "0x0000000000000000000000000000000000000000",
    "0x000000000000000000000000000000000000dead",
    "0xdead000000000000000000000000000000000000",
    "11111111111111111111111111111111",
    "0x0"
}

def calculate_gini_coefficient(balances: List[float]) -> float:
    """Calculates Gini Coefficient for a list of balances (0.0 = perfect equality, 1.0 = absolute inequality)."""
    positive_balances = [b for b in balances if b > 0]
    if not positive_balances or len(positive_balances) <= 1:
        return 0.0
    sorted_b = sorted(positive_balances)
    n = len(sorted_b)
    total_sum = sum(sorted_b)
    if total_sum <= 0:
        return 0.0
    
    cumulative_indexed_sum = sum((i + 1) * val for i, val in enumerate(sorted_b))
    gini = (2.0 * cumulative_indexed_sum) / (n * total_sum) - (n + 1.0) / n
    return float(max(0.0, min(1.0, gini)))

def calculate_percentile(sorted_data: List[float], p: float) -> float:
    """Calculates percentile p (0 to 100) using linear interpolation."""
    if not sorted_data:
        return 0.0
    if len(sorted_data) == 1:
        return sorted_data[0]
    
    n = len(sorted_data)
    idx = (p / 100.0) * (n - 1)
    lower = int(math.floor(idx))
    upper = int(math.ceil(idx))
    weight = idx - lower
    
    if lower == upper:
        return sorted_data[lower]
    return sorted_data[lower] * (1.0 - weight) + sorted_data[upper] * weight


class HolderTracker:
    """
    Core state manager and snapshot engine for token holders.
    Updates wallet balances on events and maintains historical snapshot timeline.
    """
    def __init__(self, token_address: str, initial_total_supply: float = 1_000_000_000.0):
        self.token_address = token_address
        self.total_supply = initial_total_supply
        
        # Address -> WalletOwnershipState
        self.balances: Dict[str, WalletOwnershipState] = {}
        
        # Historical event log
        self.event_log: List[TokenTransferEvent] = []
        
        # Historical snapshots timeline
        self.snapshots: List[HistoricalOwnershipSnapshot] = []
        
        # Wallet creation timeline: address -> datetime
        self.wallet_first_seen: Dict[str, datetime] = {}
        self.wallet_zero_since: Dict[str, datetime] = {}
        
        # Technical account flags set manually or by classification engine
        self.technical_accounts: Set[str] = set()

    def process_event(self, event: TokenTransferEvent) -> None:
        """Updates balances after every relevant transfer, mint, burn, bridge, liquidity, or contract event."""
        if event.token_address != self.token_address:
            return
        
        sender = event.sender.lower()
        receiver = event.receiver.lower()
        amount = event.amount
        ts = event.timestamp
        
        self.event_log.append(event)
        
        # Handle Mint
        if event.event_type == TokenTransferEventType.MINT or sender in ZERO_ADDRESSES:
            self._add_balance(receiver, amount, ts)
            self.total_supply += amount
            return

        # Handle Burn
        if event.event_type == TokenTransferEventType.BURN or receiver in ZERO_ADDRESSES:
            self._deduct_balance(sender, amount, ts)
            # Reduce supply if burned to zero address
            if receiver in ZERO_ADDRESSES:
                self.total_supply = max(0.0, self.total_supply - amount)
            return

        # Standard Transfer / Bridge / Liquidity / Contract execution
        self._deduct_balance(sender, amount, ts)
        self._add_balance(receiver, amount, ts)

    def _add_balance(self, address: str, amount: float, ts: datetime) -> None:
        if address in ZERO_ADDRESSES:
            return
            
        if address not in self.balances:
            self.balances[address] = WalletOwnershipState(
                address=address,
                token_address=self.token_address,
                balance=0.0,
                first_seen_timestamp=ts,
                last_seen_timestamp=ts,
                total_transfers_count=0
            )
            self.wallet_first_seen[address] = ts
            
        state = self.balances[address]
        state.balance += amount
        state.last_seen_timestamp = ts
        state.total_transfers_count += 1
        
        if address in self.wallet_zero_since and state.balance > 0:
            del self.wallet_zero_since[address]

    def _deduct_balance(self, address: str, amount: float, ts: datetime) -> None:
        if address in ZERO_ADDRESSES or address not in self.balances:
            return
            
        state = self.balances[address]
        state.balance = max(0.0, state.balance - amount)
        state.last_seen_timestamp = ts
        state.total_transfers_count += 1
        
        if state.balance <= 1e-9:
            state.balance = 0.0
            if address not in self.wallet_zero_since:
                self.wallet_zero_since[address] = ts

    def mark_technical_account(self, address: str, category: HolderCategory) -> None:
        """Marks a wallet address as technical (pool, exchange, burn, bridge, staking, treasury)."""
        addr = address.lower()
        self.technical_accounts.add(addr)
        if addr in self.balances:
            self.balances[addr].category = category
            self.balances[addr].is_technical_account = True

    def calculate_current_metrics(self) -> Tuple[List[float], Dict[str, Any]]:
        """Calculates current positive balances, concentration, percentiles, and Gini coefficient."""
        active_balances = [
            st.balance for addr, st in self.balances.items() 
            if st.balance > 1e-9 and addr not in ZERO_ADDRESSES
        ]
        
        if not active_balances:
            return [], {
                "holder_count": 0,
                "top_10_pct": 0.0,
                "top_20_pct": 0.0,
                "top_50_pct": 0.0,
                "gini": 0.0,
                "average": 0.0,
                "median": 0.0,
                "percentiles": {"p10": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.0, "p99": 0.0}
            }
            
        sorted_balances = sorted(active_balances, reverse=True)
        total_active_supply = sum(sorted_balances)
        n = len(sorted_balances)
        
        top_10_count = max(1, math.ceil(n * 0.10)) if n >= 10 else n
        top_20_count = max(1, math.ceil(n * 0.20)) if n >= 5 else n
        top_50_count = max(1, math.ceil(n * 0.50)) if n >= 2 else n

        top_10_pct = (sum(sorted_balances[:top_10_count]) / total_active_supply * 100.0) if total_active_supply > 0 else 0.0
        top_20_pct = (sum(sorted_balances[:top_20_count]) / total_active_supply * 100.0) if total_active_supply > 0 else 0.0
        top_50_pct = (sum(sorted_balances[:top_50_count]) / total_active_supply * 100.0) if total_active_supply > 0 else 0.0

        ascending_b = list(reversed(sorted_balances))
        gini = calculate_gini_coefficient(ascending_b)
        
        avg_bal = statistics.mean(sorted_balances)
        med_bal = statistics.median(sorted_balances)
        
        p10 = calculate_percentile(ascending_b, 10.0)
        p25 = calculate_percentile(ascending_b, 25.0)
        p50 = calculate_percentile(ascending_b, 50.0)
        p75 = calculate_percentile(ascending_b, 75.0)
        p90 = calculate_percentile(ascending_b, 90.0)
        p99 = calculate_percentile(ascending_b, 99.0)

        percentiles = {
            "p10": p10, "p25": p25, "p50": p50,
            "p75": p75, "p90": p90, "p99": p99
        }

        metrics = {
            "holder_count": n,
            "top_10_pct": float(top_10_pct),
            "top_20_pct": float(top_20_pct),
            "top_50_pct": float(top_50_pct),
            "gini": float(gini),
            "average": float(avg_bal),
            "median": float(med_bal),
            "percentiles": percentiles
        }
        return sorted_balances, metrics

    def take_snapshot(self, timestamp: Optional[datetime] = None) -> HistoricalOwnershipSnapshot:
        """Takes a historical ownership snapshot and stores it in the timeline."""
        ts = timestamp or datetime.now(timezone.utc)
        sorted_balances, metrics = self.calculate_current_metrics()
        
        tech_supply = sum(
            st.balance for addr, st in self.balances.items() 
            if st.balance > 0 and (addr in self.technical_accounts or st.is_technical_account)
        )
        tech_pct = (tech_supply / self.total_supply * 100.0) if self.total_supply > 0 else 0.0
        
        econ_count = sum(
            1 for addr, st in self.balances.items()
            if st.balance > 1e-9 and addr not in self.technical_accounts and not st.is_technical_account
        )

        snapshot = HistoricalOwnershipSnapshot(
            snapshot_id=str(uuid.uuid4()),
            token_address=self.token_address,
            timestamp=ts,
            total_supply=self.total_supply,
            circulating_supply=max(0.0, self.total_supply - tech_supply),
            total_holders_count=metrics["holder_count"],
            economically_meaningful_holders_count=econ_count,
            top_10_concentration_pct=metrics["top_10_pct"],
            top_20_concentration_pct=metrics["top_20_pct"],
            top_50_concentration_pct=metrics["top_50_pct"],
            gini_coefficient=metrics["gini"],
            average_balance=metrics["average"],
            median_balance=metrics["median"],
            percentile_balances=metrics["percentiles"],
            technical_accounts_supply_pct=tech_pct
        )
        self.snapshots.append(snapshot)
        return snapshot

    def calculate_velocity_and_retention(self, window_hours: int = 24, current_time: Optional[datetime] = None) -> HolderVelocityAndRetention:
        """
        Calculates new-holder rate, holder exits, retention, concentration changes,
        and ownership velocity over specified time window.
        """
        now = current_time or datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=window_hours)
        
        # New holders in window
        new_holders = [
            addr for addr, first_ts in self.wallet_first_seen.items()
            if first_ts >= cutoff and self.balances.get(addr, WalletOwnershipState(address=addr, token_address=self.token_address)).balance > 0
        ]
        new_count = len(new_holders)
        new_rate = new_count / float(max(1, window_hours))
        
        # Holder exits in window (wallets dropping to balance zero)
        exits = [
            addr for addr, zero_ts in self.wallet_zero_since.items()
            if zero_ts >= cutoff
        ]
        exits_count = len(exits)
        
        # Retention rate: holders active at start of window who still hold tokens at end
        holders_active_at_start = [
            addr for addr, first_ts in self.wallet_first_seen.items()
            if first_ts < cutoff
        ]
        start_count = len(holders_active_at_start)
        if start_count > 0:
            retained_count = sum(
                1 for addr in holders_active_at_start
                if self.balances.get(addr, WalletOwnershipState(address=addr, token_address=self.token_address)).balance > 0
            )
            retention_rate = (retained_count / float(start_count)) * 100.0
        else:
            retention_rate = 100.0 if new_count > 0 else 0.0

        net_growth = new_count - exits_count
        
        # Concentration delta over snapshots
        conc_delta = 0.0
        if len(self.snapshots) >= 2:
            conc_delta = self.snapshots[-1].top_10_concentration_pct - self.snapshots[0].top_10_concentration_pct
            
        # Ownership velocity: total tokens transferred in window / total supply
        window_transfers_volume = sum(
            ev.amount for ev in self.event_log
            if ev.timestamp >= cutoff
        )
        ownership_velocity = (window_transfers_volume / self.total_supply) if self.total_supply > 0 else 0.0

        return HolderVelocityAndRetention(
            token_address=self.token_address,
            time_window_hours=window_hours,
            new_holder_count=new_count,
            new_holder_rate=float(new_rate),
            holder_exits_count=exits_count,
            retention_rate_pct=float(retention_rate),
            net_holder_growth=net_growth,
            concentration_delta_top10=float(conc_delta),
            ownership_velocity=float(ownership_velocity)
        )

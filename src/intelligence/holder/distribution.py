import logging
import math
from typing import Dict, List, Set, Optional, Tuple, Any
from datetime import datetime, timezone, timedelta

from src.intelligence.holder.schemas import (
    HolderCategory,
    WalletOwnershipState,
    OwnershipDistributionMetrics
)

logger = logging.getLogger(__name__)

KNOWN_BURN_ADDRESSES = {
    "0x0000000000000000000000000000000000000000",
    "0x000000000000000000000000000000000000dead",
    "0xdead000000000000000000000000000000000000",
    "11111111111111111111111111111111",
    "incinerator111111111111111111111111111111111"
}

TECHNICAL_CATEGORIES = {
    HolderCategory.POOL,
    HolderCategory.EXCHANGE,
    HolderCategory.BURN,
    HolderCategory.STAKING,
    HolderCategory.BRIDGE,
    HolderCategory.TREASURY,
    HolderCategory.TECHNICAL_OTHER
}


class HolderCategorizationEngine:
    """
    Categorizes token holder addresses into technical vs economically meaningful accounts:
    - Technical: Pools, Exchanges, Burn addresses, Staking contracts, Bridges, Treasury/Vesting.
    - Economically Meaningful: Devs, Insiders, Smart Money, Whales, Retail users.
    """
    def __init__(
        self,
        known_pools: Optional[Set[str]] = None,
        known_exchanges: Optional[Set[str]] = None,
        known_staking: Optional[Set[str]] = None,
        known_bridges: Optional[Set[str]] = None,
        known_treasury: Optional[Set[str]] = None,
        developer_addresses: Optional[Set[str]] = None,
        insider_addresses: Optional[Set[str]] = None,
        smart_money_addresses: Optional[Set[str]] = None,
        whale_threshold_pct: float = 1.0
    ):
        self.known_pools = {a.lower() for a in (known_pools or set())}
        self.known_exchanges = {a.lower() for a in (known_exchanges or set())}
        self.known_staking = {a.lower() for a in (known_staking or set())}
        self.known_bridges = {a.lower() for a in (known_bridges or set())}
        self.known_treasury = {a.lower() for a in (known_treasury or set())}
        self.developer_addresses = {a.lower() for a in (developer_addresses or set())}
        self.insider_addresses = {a.lower() for a in (insider_addresses or set())}
        self.smart_money_addresses = {a.lower() for a in (smart_money_addresses or set())}
        self.whale_threshold_pct = whale_threshold_pct

    def categorize_address(
        self,
        address: str,
        balance: float,
        total_supply: float,
        is_contract: bool = False,
        labels: Optional[List[str]] = None
    ) -> Tuple[HolderCategory, bool]:
        """
        Classifies an address into a HolderCategory and returns (category, is_technical).
        """
        addr = address.lower()
        lbls = [l.lower() for l in (labels or [])]

        # 1. Burn addresses
        if addr in KNOWN_BURN_ADDRESSES or "burn" in lbls:
            return HolderCategory.BURN, True

        # 2. DEX Pools
        if addr in self.known_pools or "pool" in lbls or "amm" in lbls or "pair" in lbls:
            return HolderCategory.POOL, True

        # 3. Exchanges
        if addr in self.known_exchanges or "exchange" in lbls or "cex" in lbls or "binance" in lbls or "coinbase" in lbls:
            return HolderCategory.EXCHANGE, True

        # 4. Bridges
        if addr in self.known_bridges or "bridge" in lbls:
            return HolderCategory.BRIDGE, True

        # 5. Staking contracts
        if addr in self.known_staking or "staking" in lbls:
            return HolderCategory.STAKING, True

        # 6. Treasury / Lockers / Vesting
        if addr in self.known_treasury or "treasury" in lbls or "vesting" in lbls or "lock" in lbls:
            return HolderCategory.TREASURY, True

        # 7. Generic contracts (technical)
        if is_contract and "eoa" not in lbls:
            return HolderCategory.TECHNICAL_OTHER, True

        # --- Economically Meaningful Accounts ---
        # 8. Developer
        if addr in self.developer_addresses or "developer" in lbls or "deployer" in lbls:
            return HolderCategory.DEVELOPER, False

        # 9. Insiders
        if addr in self.insider_addresses or "insider" in lbls or "team" in lbls:
            return HolderCategory.INSIDER, False

        # 10. Smart Money
        if addr in self.smart_money_addresses or "smart_money" in lbls:
            return HolderCategory.SMART_MONEY, False

        # 11. Whales vs Retail based on supply percentage
        pct = (balance / total_supply * 100.0) if total_supply > 0 else 0.0
        if pct >= self.whale_threshold_pct:
            return HolderCategory.WHALE, False

        return HolderCategory.RETAIL, False


class OwnershipDistributionAnalyzer:
    """
    Computes ownership distribution metrics:
    - Separates technical accounts (pools, exchanges, burn, staking, bridges, treasury).
    - Calculates insider concentration, developer concentration, smart-money participation,
      whale concentration, retail participation, wallet diversity, and inactive-holder share.
    """
    def __init__(self, categorizer: Optional[HolderCategorizationEngine] = None):
        self.categorizer = categorizer or HolderCategorizationEngine()

    def analyze_distribution(
        self,
        token_address: str,
        wallet_states: Dict[str, WalletOwnershipState],
        total_supply: float,
        current_time: Optional[datetime] = None,
        inactivity_threshold_days: int = 30
    ) -> OwnershipDistributionMetrics:
        """Analyzes token holder distribution metrics."""
        now = current_time or datetime.now(timezone.utc)
        inactivity_cutoff = now - timedelta(days=inactivity_threshold_days)

        dev_supply = 0.0
        insider_supply = 0.0
        smart_money_supply = 0.0
        smart_money_count = 0
        whale_supply = 0.0
        whale_count = 0
        retail_supply = 0.0
        retail_count = 0
        tech_supply = 0.0
        tech_count = 0

        econ_balances: List[float] = []
        inactive_econ_supply = 0.0
        econ_count = 0

        for addr, state in wallet_states.items():
            if state.balance <= 1e-9:
                continue

            category, is_tech = self.categorizer.categorize_address(
                address=addr,
                balance=state.balance,
                total_supply=total_supply,
                is_contract=state.is_contract
            )
            state.category = category
            state.is_technical_account = is_tech

            if is_tech:
                tech_supply += state.balance
                tech_count += 1
            else:
                econ_count += 1
                econ_balances.append(state.balance)

                # Track inactivity for economic holders
                if state.last_seen_timestamp < inactivity_cutoff:
                    inactive_econ_supply += state.balance

                if category == HolderCategory.DEVELOPER:
                    dev_supply += state.balance
                elif category == HolderCategory.INSIDER:
                    insider_supply += state.balance
                elif category == HolderCategory.SMART_MONEY:
                    smart_money_supply += state.balance
                    smart_money_count += 1
                elif category == HolderCategory.WHALE:
                    whale_supply += state.balance
                    whale_count += 1
                elif category == HolderCategory.RETAIL:
                    retail_supply += state.balance
                    retail_count += 1

        denom = total_supply if total_supply > 0 else 1.0

        dev_pct = (dev_supply / denom) * 100.0
        insider_pct = (insider_supply / denom) * 100.0
        smart_money_pct = (smart_money_supply / denom) * 100.0
        whale_pct = (whale_supply / denom) * 100.0
        retail_pct = (retail_supply / denom) * 100.0
        tech_pct = (tech_supply / denom) * 100.0

        # Inactive holder share relative to economic circulating supply
        econ_total_supply = sum(econ_balances)
        inactive_share_pct = (inactive_econ_supply / econ_total_supply * 100.0) if econ_total_supply > 0 else 0.0

        # Wallet Diversity Index: Normalized Inverse HHI (0 to 100)
        diversity_index = self._calculate_wallet_diversity(econ_balances)

        return OwnershipDistributionMetrics(
            token_address=token_address,
            timestamp=now,
            insider_concentration_pct=float(insider_pct),
            developer_concentration_pct=float(dev_pct),
            smart_money_participation_pct=float(smart_money_pct),
            smart_money_holder_count=smart_money_count,
            whale_concentration_pct=float(whale_pct),
            whale_holder_count=whale_count,
            retail_participation_pct=float(retail_pct),
            retail_holder_count=retail_count,
            technical_accounts_supply_pct=float(tech_pct),
            wallet_diversity_index=float(diversity_index),
            inactive_holder_share_pct=float(inactive_share_pct),
            economically_meaningful_holders_count=econ_count,
            technical_accounts_count=tech_count
        )

    def _calculate_wallet_diversity(self, balances: List[float]) -> float:
        """Calculates Wallet Diversity Index (0-100) based on Herfindahl-Hirschman Index & Shannon Entropy."""
        if not balances:
            return 0.0
        total = sum(balances)
        if total <= 0:
            return 0.0

        # HHI calculation: sum of squared market shares
        shares = [b / total for b in balances]
        hhi = sum(s * s for s in shares)  # Ranges from 1/N to 1.0

        # Shannon Entropy calculation for distribution breadth
        entropy = -sum(s * math.log2(s) for s in shares if s > 0)
        max_entropy = math.log2(len(balances)) if len(balances) > 1 else 1.0
        normalized_entropy = (entropy / max_entropy) if max_entropy > 0 else 0.0

        # Composite score combining 1 - HHI and normalized entropy
        diversity = (0.5 * (1.0 - hhi) + 0.5 * normalized_entropy) * 100.0
        return float(max(0.0, min(100.0, diversity)))

import logging
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from .schemas import LiquidityPoolState, LiquidityAnalysis, LiquidityRiskEvent

logger = logging.getLogger(__name__)

class LiquidityEngine:
    """
    Liquidity Engine.
    Tracks pool reserves, composition, LP provider behavior, additions, removals, lock status,
    unlock schedules, executable depth across slippage bands (1%, 2%, 5%), capital impact estimation,
    and emits risk events when liquidity drops, LPs concentrate, or drain risks are detected.
    """

    def __init__(
        self,
        sharp_drop_threshold_pct: float = 0.20,  # 20% drop triggers alert
        concentration_threshold_pct: float = 0.70, # Top LPs holding >70%
        impact_target_pct: float = 0.02, # 2% max acceptable exit impact
    ):
        self.sharp_drop_threshold_pct = sharp_drop_threshold_pct
        self.concentration_threshold_pct = concentration_threshold_pct
        self.impact_target_pct = impact_target_pct
        self.pools_store: Dict[str, List[LiquidityPoolState]] = {}  # token_key -> pools
        self.analysis_history: Dict[str, List[LiquidityAnalysis]] = {}

    def update_pool_state(self, token_address: str, chain: str, pool: LiquidityPoolState) -> None:
        key = f"{chain}:{token_address.lower()}"
        if key not in self.pools_store:
            self.pools_store[key] = []
        
        # Replace existing pool state or append
        existing_idx = -1
        for i, p in enumerate(self.pools_store[key]):
            if p.pool_address.lower() == pool.pool_address.lower():
                existing_idx = i
                break
        
        if existing_idx >= 0:
            self.pools_store[key][existing_idx] = pool
        else:
            self.pools_store[key].append(pool)

    def estimate_executable_depth(
        self, pools: List[LiquidityPoolState], price_usd: float
    ) -> Tuple[float, float, float, float, float]:
        """
        Calculates depth_1pct, depth_2pct, depth_5pct, max_realistic_exit, max_realistic_entry
        using constant product AMM formula dx = x * (sqrt(1/(1-impact)) - 1).
        """
        depth_1pct = 0.0
        depth_2pct = 0.0
        depth_5pct = 0.0

        for pool in pools:
            total_usd = pool.total_liquidity_usd
            if total_usd <= 0:
                continue

            # For constant product xy=k, price impact i roughly requires delta_y = pool_reserves * (sqrt(1/(1-i)) - 1)
            # USD depth for impact i is ~ total_usd * (sqrt(1 / (1 - i)) - 1) / 2
            # 1% impact => factor ~ 0.0050
            # 2% impact => factor ~ 0.0101
            # 5% impact => factor ~ 0.0259
            factor_1pct = (math.sqrt(1.0 / (1.0 - 0.01)) - 1.0) / 2.0
            factor_2pct = (math.sqrt(1.0 / (1.0 - 0.02)) - 1.0) / 2.0
            factor_5pct = (math.sqrt(1.0 / (1.0 - 0.05)) - 1.0) / 2.0

            depth_1pct += total_usd * factor_1pct
            depth_2pct += total_usd * factor_2pct
            depth_5pct += total_usd * factor_5pct

        max_realistic_exit = depth_2pct
        max_realistic_entry = depth_2pct
        return depth_1pct, depth_2pct, depth_5pct, max_realistic_exit, max_realistic_entry

    def calculate_lp_concentration(self, pools: List[LiquidityPoolState]) -> Tuple[float, float]:
        """
        Calculates top-3 LP concentration percentage and Herfindahl Index (HHI) across all active pools.
        """
        aggregated_lp_shares: Dict[str, float] = {}
        total_pool_weight = 0.0

        for pool in pools:
            pool_liq = pool.total_liquidity_usd
            total_pool_weight += pool_liq
            for wallet, share in pool.lp_distribution.items():
                w_share = share * pool_liq
                aggregated_lp_shares[wallet] = aggregated_lp_shares.get(wallet, 0.0) + w_share

        if total_pool_weight <= 0 or not aggregated_lp_shares:
            return 0.0, 0.0

        # Normalize shares
        norm_shares = [v / total_pool_weight for v in aggregated_lp_shares.values()]
        sorted_shares = sorted(norm_shares, reverse=True)
        top3_concentration = sum(sorted_shares[:3])

        # Herfindahl-Hirschman Index = sum(s_i^2)
        hhi = sum(s ** 2 for s in norm_shares)

        return round(top3_concentration, 4), round(hhi, 4)

    def analyze_liquidity(
        self,
        token_address: str,
        chain: str,
        current_price_usd: float,
        largest_holder_token_balance: float = 0.0,
    ) -> Tuple[LiquidityAnalysis, List[LiquidityRiskEvent]]:
        key = f"{chain}:{token_address.lower()}"
        pools = self.pools_store.get(key, [])
        now = datetime.now(timezone.utc)

        total_liquidity_usd = sum(p.total_liquidity_usd for p in pools)
        d1, d2, d5, max_exit, max_entry = self.estimate_executable_depth(pools, current_price_usd)
        top3_lp_pct, hhi = self.calculate_lp_concentration(pools)
        is_locked = any(p.is_locked for p in pools)

        # Check 24h liquidity drop
        history = self.analysis_history.get(key, [])
        prev_liquidity = history[-1].total_liquidity_usd if history else total_liquidity_usd
        liquidity_drop_pct = (
            (prev_liquidity - total_liquidity_usd) / prev_liquidity
            if prev_liquidity > 0 and total_liquidity_usd < prev_liquidity
            else 0.0
        )

        # Check Drain Risk: if largest holder token value > max exit capital before 5% impact
        largest_holder_value_usd = largest_holder_token_balance * current_price_usd
        drain_risk = (
            largest_holder_value_usd > d5 and largest_holder_value_usd > 0
        )

        # Determine overall Risk Level
        risk_level = "LOW"
        if liquidity_drop_pct >= self.sharp_drop_threshold_pct or drain_risk:
            risk_level = "CRITICAL"
        elif top3_lp_pct >= self.concentration_threshold_pct or hhi > 0.4:
            risk_level = "HIGH"
        elif total_liquidity_usd < 1000.0:
            risk_level = "MEDIUM"

        analysis = LiquidityAnalysis(
            token_address=token_address,
            chain=chain,
            total_liquidity_usd=round(total_liquidity_usd, 2),
            depth_1pct_usd=round(d1, 2),
            depth_2pct_usd=round(d2, 2),
            depth_5pct_usd=round(d5, 2),
            max_realistic_exit_usd=round(max_exit, 2),
            max_realistic_entry_usd=round(max_entry, 2),
            top3_lp_concentration_pct=top3_lp_pct,
            herfindahl_index=hhi,
            is_liquidity_locked=is_locked,
            liquidity_drop_24h_pct=round(liquidity_drop_pct, 4),
            drain_risk_detected=drain_risk,
            risk_level=risk_level,
            active_pools=pools,
            updated_at=now,
        )

        # Generate Risk Events if thresholds breached
        risk_events: List[LiquidityRiskEvent] = []

        if liquidity_drop_pct >= self.sharp_drop_threshold_pct:
            risk_events.append(
                LiquidityRiskEvent(
                    token_address=token_address,
                    chain=chain,
                    risk_type="SHARP_LIQUIDITY_DROP",
                    severity="CRITICAL",
                    current_liquidity_usd=total_liquidity_usd,
                    previous_liquidity_usd=prev_liquidity,
                    max_executable_exit_usd=max_exit,
                    top_lp_concentration_pct=top3_lp_pct,
                    description=f"Liquidity dropped by {liquidity_drop_pct*100:.1f}% (from ${prev_liquidity:,.2f} to ${total_liquidity_usd:,.2f})",
                    timestamp=now,
                )
            )

        if top3_lp_pct >= self.concentration_threshold_pct:
            risk_events.append(
                LiquidityRiskEvent(
                    token_address=token_address,
                    chain=chain,
                    risk_type="HIGH_LP_CONCENTRATION",
                    severity="WARNING" if risk_level != "CRITICAL" else "CRITICAL",
                    current_liquidity_usd=total_liquidity_usd,
                    max_executable_exit_usd=max_exit,
                    top_lp_concentration_pct=top3_lp_pct,
                    description=f"Top 3 LPs hold {top3_lp_pct*100:.1f}% of pool liquidity (HHI: {hhi:.2f})",
                    timestamp=now,
                )
            )

        if drain_risk:
            risk_events.append(
                LiquidityRiskEvent(
                    token_address=token_address,
                    chain=chain,
                    risk_type="DRAIN_RISK",
                    severity="CRITICAL",
                    current_liquidity_usd=total_liquidity_usd,
                    max_executable_exit_usd=max_exit,
                    top_lp_concentration_pct=top3_lp_pct,
                    description=f"Single holder (${largest_holder_value_usd:,.2f}) can completely drain available exit liquidity (${d5:,.2f})",
                    timestamp=now,
                    details={
                        "largest_holder_value_usd": largest_holder_value_usd,
                        "depth_5pct_usd": d5,
                    },
                )
            )

        # Store in history
        if key not in self.analysis_history:
            self.analysis_history[key] = []
        self.analysis_history[key].append(analysis)
        if len(self.analysis_history[key]) > 50:
            self.analysis_history[key] = self.analysis_history[key][-50:]

        return analysis, risk_events

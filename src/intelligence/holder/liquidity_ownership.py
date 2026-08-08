import logging
import math
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone

from src.intelligence.holder.schemas import (
    LiquidityOwnershipHealthView,
    OwnershipDistributionMetrics,
    HistoricalOwnershipSnapshot
)

logger = logging.getLogger(__name__)


class LiquidityOwnershipHealthEngine:
    """
    Evaluates liquidity quality together with token ownership structure.
    Addresses the scenario where a token has many holders but shallow/concentrated liquidity
    makes exiting impossible without severe price impact.
    """
    def __init__(self):
        pass

    def evaluate_market_health(
        self,
        token_address: str,
        pool_liquidity_usd: float,
        token_price_usd: float,
        snapshot: HistoricalOwnershipSnapshot,
        distribution: OwnershipDistributionMetrics,
        lp_locked_pct: float = 0.0,
        lp_lock_duration_days: float = 0.0,
        depth_1pct_usd: Optional[float] = None,
        depth_2pct_usd: Optional[float] = None,
        depth_5pct_usd: Optional[float] = None
    ) -> LiquidityOwnershipHealthView:
        """
        Combines holder concentration, executable depth, slippage, LP stability,
        and likely seller pressure into a unified market health view.
        """
        warnings: List[str] = []
        
        # 1. Executable depth calculation (using AMM approximation if not explicitly provided)
        # For x*y=k pool, depth for p% impact is ~ (p%) * Liquidity
        d1 = depth_1pct_usd if depth_1pct_usd is not None else (pool_liquidity_usd * 0.01)
        d2 = depth_2pct_usd if depth_2pct_usd is not None else (pool_liquidity_usd * 0.02)
        d5 = depth_5pct_usd if depth_5pct_usd is not None else (pool_liquidity_usd * 0.05)

        # 2. Slippage estimations
        # Slippage ~ Trade USD / (2 * Pool Liquidity USD)
        slippage_buy_5k = (5_000.0 / (2.0 * pool_liquidity_usd) * 100.0) if pool_liquidity_usd > 0 else 100.0
        slippage_sell_5k = (5_000.0 / (2.0 * pool_liquidity_usd) * 100.0) if pool_liquidity_usd > 0 else 100.0
        slippage_sell_25k = (25_000.0 / (2.0 * pool_liquidity_usd) * 100.0) if pool_liquidity_usd > 0 else 100.0

        slippage_buy_5k = float(min(100.0, max(0.0, slippage_buy_5k)))
        slippage_sell_5k = float(min(100.0, max(0.0, slippage_sell_5k)))
        slippage_sell_25k = float(min(100.0, max(0.0, slippage_sell_25k)))

        # 3. LP Stability Score (0 to 100)
        # High score for locked LP, long lock duration, and reasonable pool size
        lock_score = min(100.0, lp_locked_pct)
        duration_score = min(100.0, (lp_lock_duration_days / 365.0) * 100.0)
        mcap_usd = snapshot.total_supply * token_price_usd
        liquidity_to_mcap_ratio = (pool_liquidity_usd / mcap_usd * 100.0) if mcap_usd > 0 else 0.0
        ratio_score = min(100.0, liquidity_to_mcap_ratio * 5.0)  # 20% liq ratio gives 100 score

        lp_stability_score = (0.50 * lock_score + 0.30 * duration_score + 0.20 * ratio_score)
        lp_stability_score = float(max(0.0, min(100.0, lp_stability_score)))

        if lp_locked_pct < 50.0:
            warnings.append(f"Low LP lock percentage: {lp_locked_pct:.1f}% locked.")
        if liquidity_to_mcap_ratio < 5.0:
            warnings.append(f"Shallow liquidity relative to market cap ({liquidity_to_mcap_ratio:.1f}% liq/mcap).")

        # 4. Likely Seller Pressure Risk Ratio
        # Total sellable holdings of top insiders & whales in USD
        insider_whale_supply_pct = distribution.insider_concentration_pct + distribution.whale_concentration_pct + distribution.developer_concentration_pct
        insider_whale_usd = (insider_whale_supply_pct / 100.0) * mcap_usd
        
        # Seller pressure risk ratio = insider/whale holdings in USD / 2% depth USD
        seller_pressure_ratio = (insider_whale_usd / d2) if d2 > 0 else 999.0
        seller_pressure_ratio = float(min(999.0, max(0.0, seller_pressure_ratio)))

        if seller_pressure_ratio > 10.0:
            warnings.append(f"Critical seller pressure risk ratio ({seller_pressure_ratio:.1f}x): Top holders exceed 2% pool depth by >10x.")

        # 5. Holder Concentration Risk Score (0 to 100)
        top10_econ_share = snapshot.top_10_concentration_pct
        conc_risk_score = min(100.0, top10_econ_share * 1.2)
        if top10_econ_share > 50.0:
            warnings.append(f"High top-10 concentration ({top10_econ_share:.1f}% of supply).")

        # 6. Exit Feasibility Index (0 to 100)
        # Evaluates how safely holders can exit based on slippage and depth vs whale positions
        slippage_penalty = min(50.0, slippage_sell_5k * 2.5)
        depth_safety = min(50.0, (d2 / 50_000.0) * 50.0) if d2 > 0 else 0.0
        pressure_penalty = min(40.0, seller_pressure_ratio * 2.0)
        
        exit_feasibility = 100.0 - slippage_penalty - pressure_penalty + (depth_safety * 0.4)
        exit_feasibility = float(max(0.0, min(100.0, exit_feasibility)))

        if exit_feasibility < 30.0:
            warnings.append("Illiquid exit risk: High slippage or shallow depth makes holder exits dangerous.")

        # 7. Overall Market Health Score (0 to 100)
        overall_score = (
            0.35 * exit_feasibility +
            0.25 * lp_stability_score +
            0.20 * (100.0 - conc_risk_score) +
            0.20 * max(0.0, 100.0 - (seller_pressure_ratio * 5.0))
        )
        overall_score = float(max(0.0, min(100.0, overall_score)))

        return LiquidityOwnershipHealthView(
            token_address=token_address,
            timestamp=datetime.now(timezone.utc),
            holder_concentration_risk_score=float(conc_risk_score),
            executable_depth_usd_1pct=float(d1),
            executable_depth_usd_2pct=float(d2),
            executable_depth_usd_5pct=float(d5),
            slippage_buy_5k_pct=float(slippage_buy_5k),
            slippage_sell_5k_pct=float(slippage_sell_5k),
            slippage_sell_25k_pct=float(slippage_sell_25k),
            lp_stability_score=float(lp_stability_score),
            lp_lock_pct=float(lp_locked_pct),
            seller_pressure_risk_ratio=float(seller_pressure_ratio),
            exit_feasibility_index=float(exit_feasibility),
            overall_market_health_score=float(overall_score),
            risk_warnings=warnings
        )

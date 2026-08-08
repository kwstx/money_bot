import logging
import math
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from src.intelligence.wallet.schemas import WalletProfile
from src.intelligence.wallet.manipulation_schemas import (
    SellPressureMetrics,
    WhaleMarketImpact,
    CoordinatedWhaleAlert
)

logger = logging.getLogger(__name__)

class WhaleMarketImpactEngine:
    """
    Evaluates whale position risk based on EXECUTABLE LIQUIDITY IMPACT rather than simple raw wallet balance.
    Calculates potential sell pressure price impact, supply concentration, accumulation rates, and coordinated whale behavior.
    """
    def __init__(self, slippage_multiplier: float = 1.5):
        self.slippage_multiplier = slippage_multiplier

    def calculate_sell_pressure_impact(
        self,
        holding_tokens: float,
        token_price_usd: float,
        pool_liquidity_usd: float,
        liquidation_percentage: float = 0.25
    ) -> SellPressureMetrics:
        """
        Calculates price impact % and sell pressure severity index for dumping N% of a holding into pool liquidity.
        Uses constant-product AMM slippage curve: Impact % = Liquidated_USD / (Pool_USD + Liquidated_USD)
        """
        liq_pct = max(0.01, min(1.0, liquidation_percentage))
        total_holding_usd = holding_tokens * token_price_usd
        liquidated_usd = total_holding_usd * liq_pct
        pool_usd = max(1.0, pool_liquidity_usd)

        # AMM Price Impact model with slippage multiplier
        raw_impact = liquidated_usd / (pool_usd + liquidated_usd)
        price_impact_pct = round(min(100.0, raw_impact * 100.0 * self.slippage_multiplier), 2)

        # Sell Pressure Index (0 - 100 rating)
        # 10% impact -> 40 score; 25% impact -> 70 score; >50% impact -> 100 score
        sell_pressure_index = round(min(100.0, 50.0 + 50.0 * math.tanh(price_impact_pct / 20.0)), 2)

        return SellPressureMetrics(
            holding_tokens=holding_tokens,
            holding_usd=round(total_holding_usd, 2),
            liquidation_percentage=liq_pct,
            liquidated_usd=round(liquidated_usd, 2),
            pool_liquidity_usd=round(pool_usd, 2),
            estimated_price_impact_percent=price_impact_pct,
            sell_pressure_index=sell_pressure_index
        )

    def analyze_whale_position(
        self,
        wallet_address: str,
        token_address: str,
        token_balance: float,
        pool_liquidity_usd: float,
        token_price_usd: float,
        total_supply: float = 1_000_000.0,
        circulating_supply: Optional[float] = None,
        balance_24h_ago: Optional[float] = None
    ) -> WhaleMarketImpact:
        """
        Generates comprehensive WhaleMarketImpact metrics for a position.
        Crucially differentiates tiny % of liquid supply vs large % of executable liquidity.
        """
        now = datetime.now(timezone.utc)
        holding_usd = token_balance * token_price_usd
        circ_supply = circulating_supply or total_supply
        
        # 1. Supply Percentage vs Executable Liquidity Share
        supply_pct = round((token_balance / max(1.0, circ_supply)) * 100.0, 4)
        executable_liq_share = round(holding_usd / max(1.0, pool_liquidity_usd), 4)

        # 2. Sell Pressure at different liquidation tiers
        sp_10 = self.calculate_sell_pressure_impact(token_balance, token_price_usd, pool_liquidity_usd, 0.10)
        sp_25 = self.calculate_sell_pressure_impact(token_balance, token_price_usd, pool_liquidity_usd, 0.25)
        sp_50 = self.calculate_sell_pressure_impact(token_balance, token_price_usd, pool_liquidity_usd, 0.50)
        sp_100 = self.calculate_sell_pressure_impact(token_balance, token_price_usd, pool_liquidity_usd, 1.00)

        # 3. Market Impact Risk Classification based on EXECUTABLE LIQUIDITY SHARE
        if executable_liq_share >= 0.50 or sp_25.estimated_price_impact_percent >= 30.0:
            rank = "CRITICAL"
        elif executable_liq_share >= 0.20 or sp_25.estimated_price_impact_percent >= 15.0:
            rank = "HIGH"
        elif executable_liq_share >= 0.05 or sp_25.estimated_price_impact_percent >= 5.0:
            rank = "MEDIUM"
        else:
            rank = "LOW"

        # 4. Accumulation Rate 24h
        accum_rate = 0.0
        if balance_24h_ago is not None and balance_24h_ago > 0:
            accum_rate = round(((token_balance - balance_24h_ago) / balance_24h_ago) * 100.0, 2)

        return WhaleMarketImpact(
            wallet_address=wallet_address.lower(),
            token_address=token_address.lower(),
            token_balance=token_balance,
            holding_usd=round(holding_usd, 2),
            supply_percentage=supply_pct,
            executable_liquidity_share=executable_liq_share,
            sell_pressure_10pct=sp_10,
            sell_pressure_25pct=sp_25,
            sell_pressure_50pct=sp_50,
            sell_pressure_100pct=sp_100,
            concentration_rank=rank,
            accumulation_rate_24h=accum_rate,
            updated_at=now
        )

    def detect_coordinated_whale_behavior(
        self,
        whale_profiles: List[WalletProfile],
        token_address: str,
        window_seconds: float = 300.0
    ) -> Optional[CoordinatedWhaleAlert]:
        """
        Detects synchronized buying or selling across multiple whale addresses within window_seconds.
        """
        tok = token_address.lower()
        now = datetime.now(timezone.utc)
        
        participating_buys = []
        participating_sells = []
        total_buy_usd = 0.0
        total_sell_usd = 0.0

        for p in whale_profiles:
            pos = p.positions.get(tok)
            if not pos or not pos.last_trade_time:
                continue
            
            time_diff = (now - pos.last_trade_time).total_seconds()
            if time_diff <= window_seconds:
                # Check if net accumulation or distribution
                if pos.current_balance > 0 and pos.total_bought_usd > pos.total_sold_usd:
                    participating_buys.append(p.address.lower())
                    total_buy_usd += pos.total_bought_usd
                elif pos.total_sold_usd > 0:
                    participating_sells.append(p.address.lower())
                    total_sell_usd += pos.total_sold_usd

        if len(participating_buys) >= 2:
            return CoordinatedWhaleAlert(
                token_address=tok,
                participating_whales=participating_buys,
                total_coordinated_usd=round(total_buy_usd, 2),
                action_type="ACCUMULATION",
                confidence=min(0.95, 0.70 + 0.10 * len(participating_buys)),
                window_seconds=window_seconds,
                detected_at=now
            )
        elif len(participating_sells) >= 2:
            return CoordinatedWhaleAlert(
                token_address=tok,
                participating_whales=participating_sells,
                total_coordinated_usd=round(total_sell_usd, 2),
                action_type="DISTRIBUTION",
                confidence=min(0.95, 0.70 + 0.10 * len(participating_sells)),
                window_seconds=window_seconds,
                detected_at=now
            )

        return None

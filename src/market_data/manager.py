import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone

from .schemas import (
    PriceObservation,
    ReconciledPrice,
    LiquidityPoolState,
    LiquidityAnalysis,
    LiquidityRiskEvent,
    TradeObservation,
    VolumeAnalysis,
    SupplyBreakdown,
    SupplyEvent,
    ValuationAnalysis,
)
from .price_engine import PriceEngine
from .liquidity_engine import LiquidityEngine
from .volume_engine import VolumeEngine
from .valuation_engine import ValuationEngine
from ..publisher import publisher

logger = logging.getLogger(__name__)

class MarketIntelligenceManager:
    """
    Unified Market Intelligence Manager.
    Coordinates PriceEngine, LiquidityEngine, VolumeEngine, and ValuationEngine.
    """

    def __init__(self):
        self.price_engine = PriceEngine()
        self.liquidity_engine = LiquidityEngine()
        self.volume_engine = VolumeEngine()
        self.valuation_engine = ValuationEngine()

    async def ingest_price_observations(
        self,
        token_address: str,
        chain: str,
        observations: List[PriceObservation],
        last_trade_timestamp: Optional[datetime] = None,
    ) -> ReconciledPrice:
        reconciled = self.price_engine.reconcile_price(
            token_address=token_address,
            chain=chain,
            observations=observations,
            last_trade_timestamp=last_trade_timestamp,
        )

        # Trigger valuation update with new reconciled price
        liquidity_analysis, _ = self.liquidity_engine.analyze_liquidity(token_address, chain, reconciled.price_usd)
        self.valuation_engine.calculate_valuation(
            token_address=token_address,
            chain=chain,
            price_usd=reconciled.price_usd,
            total_liquidity_usd=liquidity_analysis.total_liquidity_usd,
        )

        return reconciled

    def update_liquidity_pool(self, token_address: str, chain: str, pool: LiquidityPoolState) -> None:
        self.liquidity_engine.update_pool_state(token_address, chain, pool)

    async def evaluate_liquidity(
        self,
        token_address: str,
        chain: str,
        price_usd: float,
        largest_holder_token_balance: float = 0.0,
    ) -> Tuple[LiquidityAnalysis, List[LiquidityRiskEvent]]:
        analysis, risk_events = self.liquidity_engine.analyze_liquidity(
            token_address=token_address,
            chain=chain,
            current_price_usd=price_usd,
            largest_holder_token_balance=largest_holder_token_balance,
        )

        # Emit immediate events to risk layer / publisher if kafka connected
        for event in risk_events:
            logger.warning(f"[Liquidity Risk Event Emitted] {event.risk_type} for {token_address}: {event.description}")
            if publisher.kafka:
                try:
                    await publisher.publish(
                        {
                            "source_app_id": "market_data_engine",
                            "event_category": "liquidity_risk",
                            "referenced_token_address": token_address,
                            "blockchain_id": chain,
                            "raw_payload": event.model_dump(mode="json"),
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to publish liquidity risk event: {e}")

        return analysis, risk_events

    async def record_trade(self, trade: TradeObservation) -> VolumeAnalysis:
        self.volume_engine.record_trade(trade)
        volume_analysis = self.volume_engine.analyze_volume(trade.token_address, trade.chain)

        if volume_analysis.is_artificial_burst or volume_analysis.wash_trading_score > 0.35:
            logger.warning(f"[Volume Manipulation Alert] Token {trade.token_address} anomalies: {volume_analysis.detected_anomalies}")

        return volume_analysis

    def set_supply_breakdown(self, token_address: str, chain: str, supply: SupplyBreakdown) -> None:
        self.valuation_engine.set_supply_breakdown(token_address, chain, supply)

    async def record_supply_event(self, token_address: str, chain: str, event: SupplyEvent) -> ValuationAnalysis:
        valuation = self.valuation_engine.record_supply_event(token_address, chain, event)
        logger.info(f"[Supply Event Recorded] Token {token_address} {event.event_type} {event.amount} tokens")
        return valuation

    def get_full_token_intelligence(
        self, token_address: str, chain: str, price_observations: Optional[List[PriceObservation]] = None
    ) -> Dict[str, Any]:
        key = f"{chain}:{token_address.lower()}"

        # 1. Price
        if price_observations:
            reconciled_price = self.price_engine.reconcile_price(token_address, chain, price_observations)
        else:
            prev_prices = self.price_engine.price_history.get(key, [])
            reconciled_price = prev_prices[-1] if prev_prices else None

        current_price = reconciled_price.price_usd if reconciled_price else 0.0

        # 2. Liquidity
        liquidity_analysis, _ = self.liquidity_engine.analyze_liquidity(token_address, chain, current_price)

        # 3. Volume
        volume_analysis = self.volume_engine.analyze_volume(token_address, chain)

        # 4. Valuation
        valuation_analysis = self.valuation_engine.calculate_valuation(
            token_address, chain, current_price, total_liquidity_usd=liquidity_analysis.total_liquidity_usd
        )

        return {
            "token_address": token_address,
            "chain": chain,
            "price": reconciled_price.model_dump(mode="json") if reconciled_price else None,
            "liquidity": liquidity_analysis.model_dump(mode="json"),
            "volume": volume_analysis.model_dump(mode="json"),
            "valuation": valuation_analysis.model_dump(mode="json"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


market_intelligence_manager = MarketIntelligenceManager()

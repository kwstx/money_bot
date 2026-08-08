import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from .base import Workflow
from ..schemas import CanonicalNotificationEvent
from ..market_data import (
    MarketIntelligenceManager,
    market_intelligence_manager,
    PriceObservation,
    LiquidityPoolState,
    TradeObservation,
    SupplyEvent,
    SupplyBreakdown,
)

logger = logging.getLogger(__name__)

class MarketWorkflow(Workflow):
    """
    Market Intelligence Workflow.
    Receives incoming market/swap/liquidity/token canonical events, passes them to
    MarketIntelligenceManager, and updates price, volume, liquidity, and valuation state.
    """

    def __init__(self, manager: Optional[MarketIntelligenceManager] = None):
        self.manager = manager or market_intelligence_manager

    @property
    def name(self) -> str:
        return "Market"

    async def process(self, event: CanonicalNotificationEvent) -> None:
        logger.info(f"[{self.name}] Processing event {event.event_id} (category: {event.event_category})")

        payload = event.raw_payload or {}
        token_address = event.referenced_token_address or payload.get("token_address") or payload.get("mint")
        chain = event.blockchain_id or payload.get("chain") or "ethereum"

        if not token_address:
            logger.debug(f"[{self.name}] Event {event.event_id} has no referenced token address. Skipping.")
            return

        # 1. Process Price Observations if present in payload
        if "price_observations" in payload or "price_usd" in payload:
            raw_obs_list = payload.get("price_observations", [])
            observations = []
            if raw_obs_list:
                for item in raw_obs_list:
                    observations.append(PriceObservation(**item))
            elif "price_usd" in payload:
                observations.append(
                    PriceObservation(
                        source_id=event.source_app_id or "event_payload",
                        price_usd=float(payload["price_usd"]),
                        liquidity_usd=float(payload.get("liquidity_usd", 0.0)),
                    )
                )

            if observations:
                reconciled = await self.manager.ingest_price_observations(
                    token_address=token_address,
                    chain=chain,
                    observations=observations,
                )
                logger.info(f"[{self.name}] Reconciled Price for {token_address}: ${reconciled.price_usd} (Reliable: {reconciled.is_reliable}, Conf: {reconciled.confidence_score})")

        # 2. Process Pool / Liquidity State if present
        if "liquidity_pool" in payload or "pool_address" in payload:
            pool_data = payload.get("liquidity_pool") or payload
            if "pool_address" in pool_data and "token0_address" in pool_data:
                pool_state = LiquidityPoolState(
                    pool_address=pool_data["pool_address"],
                    dex_name=pool_data.get("dex_name", "UnknownDEX"),
                    token0_address=pool_data["token0_address"],
                    token1_address=pool_data["token1_address"],
                    reserve0=float(pool_data.get("reserve0", 0.0)),
                    reserve1=float(pool_data.get("reserve1", 0.0)),
                    total_liquidity_usd=float(pool_data.get("total_liquidity_usd", 0.0)),
                    lp_distribution=pool_data.get("lp_distribution", {}),
                    is_locked=bool(pool_data.get("is_locked", False)),
                )
                self.manager.update_liquidity_pool(token_address, chain, pool_state)

                current_price = payload.get("price_usd", 0.0)
                largest_holder_bal = float(payload.get("largest_holder_balance", 0.0))
                analysis, risk_events = await self.manager.evaluate_liquidity(
                    token_address, chain, current_price, largest_holder_bal
                )
                logger.info(f"[{self.name}] Evaluated Liquidity for {token_address}: ${analysis.total_liquidity_usd} (Risk Level: {analysis.risk_level})")

        # 3. Process Trade Observations if present
        if "trade" in payload or "trader_address" in payload:
            trade_data = payload.get("trade") or payload
            if "trader_address" in trade_data and "amount_usd" in trade_data:
                trade_obs = TradeObservation(
                    tx_hash=trade_data.get("tx_hash", f"tx_{event.event_id}"),
                    token_address=token_address,
                    chain=chain,
                    trader_address=trade_data["trader_address"],
                    is_buy=bool(trade_data.get("is_buy", True)),
                    amount_tokens=float(trade_data.get("amount_tokens", 0.0)),
                    amount_usd=float(trade_data["amount_usd"]),
                    price_usd=float(trade_data.get("price_usd", 0.0)),
                    is_smart_money=bool(trade_data.get("is_smart_money", False)),
                    is_whale=bool(trade_data.get("is_whale", False)),
                    is_developer=bool(trade_data.get("is_developer", False)),
                )
                vol_analysis = await self.manager.record_trade(trade_obs)
                logger.info(f"[{self.name}] Updated Volume for {token_address}: 24h Raw ${vol_analysis.raw_volume_24h_usd} (Organic: ${vol_analysis.organic_volume_24h_usd})")

        # 4. Process Supply Event if present
        if "supply_event" in payload or ("event_type" in payload and payload["event_type"] in ["MINT", "BURN", "UNLOCK", "TREASURY_RELEASE", "MIGRATION"]):
            se_data = payload.get("supply_event") or payload
            supply_event = SupplyEvent(
                token_address=token_address,
                chain=chain,
                event_type=se_data["event_type"],
                amount=float(se_data["amount"]),
                description=se_data.get("description", ""),
            )
            valuation = await self.manager.record_supply_event(token_address, chain, supply_event)
            logger.info(f"[{self.name}] Processed Supply Event for {token_address}: Market Cap ${valuation.market_cap_usd:,.2f}, FDV ${valuation.fdv_usd:,.2f}")

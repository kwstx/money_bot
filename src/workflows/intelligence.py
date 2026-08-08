import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from .base import Workflow
from ..schemas import CanonicalNotificationEvent
from ..market_data import market_intelligence_manager
from ..publisher import publisher

from src.intelligence.transaction_monitor import TransactionMonitor
from src.intelligence.buy_sell_detector import BuySellDetector
from src.intelligence.flow_engine import FlowEngine
from src.intelligence.schemas import DecodedTransaction

logger = logging.getLogger(__name__)

class IntelligenceWorkflow(Workflow):
    """
    Unified Transaction, Buy/Sell, and Flow Intelligence Workflow.
    Decodes incoming raw transactions, identifies purchases/sales,
    calculates rolling market-flow dynamics, and alerts on coordinated campaigns.
    """

    def __init__(
        self,
        monitor: Optional[TransactionMonitor] = None,
        detector: Optional[BuySellDetector] = None,
        flow_engine: Optional[FlowEngine] = None
    ):
        self.monitor = monitor or TransactionMonitor()
        self.detector = detector or BuySellDetector()
        self.flow_engine = flow_engine or FlowEngine()

    @property
    def name(self) -> str:
        return "Intelligence"

    async def process(self, event: CanonicalNotificationEvent) -> None:
        """
        Processes incoming canonical events to extract transaction, trade,
        and market-flow intelligence.
        """
        logger.info(f"[{self.name}] Processing event {event.event_id} (Category: {event.event_category})")
        
        payload = event.raw_payload or {}
        
        # We need a transaction hash/payload to decode
        has_tx_info = any(k in payload for k in ["tx_hash", "hash", "signature", "id", "input", "logs"])
        if not has_tx_info and event.event_category not in ["swap", "wallet", "transaction", "liquidity"]:
            logger.debug(f"[{self.name}] Event {event.event_id} has no transaction details. Skipping.")
            return

        # 1. Decode raw transaction
        try:
            # Construct a raw tx dict from event metadata if needed
            raw_tx = dict(payload)
            if "tx_hash" not in raw_tx:
                raw_tx["tx_hash"] = event.notification_id or f"tx_{event.event_id}"
            if "chain" not in raw_tx:
                raw_tx["chain"] = event.blockchain_id or "ethereum"
            if "timestamp" not in raw_tx:
                raw_tx["timestamp"] = event.timestamp
            if "sender" not in raw_tx:
                raw_tx["sender"] = event.referenced_wallet_address or payload.get("trader_address") or "0xunknown"
            if "receiver" not in raw_tx:
                raw_tx["receiver"] = payload.get("to_address") or payload.get("receiver")
            if "value" not in raw_tx and "amount_usd" in payload:
                raw_tx["value_usd"] = payload.get("amount_usd")
                
            decoded_tx = self.monitor.decode(raw_tx)
            logger.info(f"[{self.name}] Decoded TX {decoded_tx.tx_hash}: Action={decoded_tx.action_type}, Value=${decoded_tx.economic_value_usd:.2f}")
        except Exception as e:
            logger.error(f"[{self.name}] Failed to decode transaction for event {event.event_id}: {e}")
            return

        # Record decoded tx (transfers, liquidity) in flow engine to assist sequence trackers
        self.flow_engine.record_decoded_transaction(decoded_tx)

        # 2. Extract referenced token and market context
        token_address = event.referenced_token_address or payload.get("token_address") or payload.get("mint")
        if not token_address:
            # Try to find target token address from assets involved (excluding native/stables)
            for asset in decoded_tx.assets_involved:
                if asset.token_address.lower() not in ["native", "usdc", "usdt", "dai", "weth", "wsol"]:
                    token_address = asset.token_address
                    break

        if not token_address:
            logger.debug(f"[{self.name}] Could not determine target token address for transaction {decoded_tx.tx_hash}. Skipping trade detection.")
            return

        chain = decoded_tx.chain
        
        # Query market intelligence manager for pool details (price, liquidity, mcap)
        price_usd = 0.0
        total_liquidity_usd = 0.0
        market_cap_usd = 0.0
        developer_address = None
        
        try:
            m_intel = market_intelligence_manager.get_full_token_intelligence(token_address, chain)
            if m_intel:
                price_usd = float(m_intel.get("price", {}).get("price_usd") or 0.0)
                total_liquidity_usd = float(m_intel.get("liquidity", {}).get("total_liquidity_usd") or 0.0)
                market_cap_usd = float(m_intel.get("valuation", {}).get("market_cap_usd") or 0.0)
        except Exception as e:
            logger.debug(f"[{self.name}] Failed to fetch market context from MarketIntelligenceManager: {e}")

        # Also register funding if the decoded transaction is a native asset transfer
        # (to help track wallet funding -> buy trade sequences)
        if decoded_tx.action_type == "TRANSFER":
            for asset in decoded_tx.assets_involved:
                if asset.token_address == "native" and decoded_tx.receiver:
                    self.detector.register_funding(decoded_tx.receiver, decoded_tx.sender)

        # 3. Detect Buy/Sell Trade Intelligence
        is_smart_money = bool(payload.get("is_smart_money", False) or "SMART_MONEY" in payload.get("wallet_classification", []))
        trade_intel = self.detector.detect(
            decoded_tx=decoded_tx,
            token_address=token_address,
            current_price_usd=price_usd,
            total_liquidity_usd=total_liquidity_usd,
            market_cap_usd=market_cap_usd,
            developer_address=developer_address,
            is_smart_money_override=is_smart_money
        )

        if trade_intel:
            logger.info(
                f"[{self.name}] Detected Trade: {trade_intel.direction} {trade_intel.amount_tokens:.2f} tokens "
                f"(${trade_intel.amount_usd:.2f}) at ${trade_intel.price_usd:.4f}. Wallets={trade_intel.wallet_classification}"
            )
            
            # Record trade in flow engine
            self.flow_engine.record_trade(trade_intel)
            
            # Publish trade intelligence event downstream
            if publisher.kafka:
                try:
                    await publisher.publish(
                        {
                            "source_app_id": "intelligence_engine",
                            "event_category": "trade_intelligence",
                            "referenced_token_address": token_address,
                            "blockchain_id": chain,
                            "raw_payload": trade_intel.model_dump(mode="json"),
                        }
                    )
                except Exception as e:
                    logger.error(f"[{self.name}] Failed to publish trade intelligence event: {e}")

            # 4. Calculate continuous market flow metrics
            flow_intel = self.flow_engine.calculate_flow_metrics(token_address, chain)
            logger.info(
                f"[{self.name}] Flow metrics for {token_address}: Imbalance={flow_intel.buy_sell_imbalance:.4f}, "
                f"Accumulation={flow_intel.accumulation_status}, NetWhalePressure=${flow_intel.whale_pressure:,.2f}, "
                f"Velocity={flow_intel.transaction_velocity:.2f} tx/min, SeqsCount={len(flow_intel.detected_sequences)}"
            )
            
            # Alert/Log on detected sequences (staged accumulation, rug risk, etc.)
            for seq in flow_intel.detected_sequences:
                logger.warning(f"[Flow Sequence Warning] Detected {seq['type']} sequence: {seq}")
                if publisher.kafka:
                    try:
                        await publisher.publish(
                            {
                                "source_app_id": "intelligence_engine",
                                "event_category": f"sequence_{seq['type']}",
                                "referenced_token_address": token_address,
                                "blockchain_id": chain,
                                "raw_payload": seq,
                            }
                        )
                    except Exception as e:
                        logger.error(f"[{self.name}] Failed to publish sequence event: {e}")
                        
            # Publish flow metrics downstream
            if publisher.kafka:
                try:
                    await publisher.publish(
                        {
                            "source_app_id": "intelligence_engine",
                            "event_category": "flow_intelligence",
                            "referenced_token_address": token_address,
                            "blockchain_id": chain,
                            "raw_payload": flow_intel.model_dump(mode="json"),
                        }
                    )
                except Exception as e:
                    logger.error(f"[{self.name}] Failed to publish flow metrics: {e}")

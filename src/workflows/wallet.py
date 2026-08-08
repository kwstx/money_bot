import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select

from .base import Workflow
from ..schemas import CanonicalNotificationEvent
from ..storage.implementations import postgres_store, DBIdentity, graph_store
from ..publisher import publisher
from ..market_data import market_intelligence_manager

from src.intelligence.transaction_monitor import TransactionMonitor
from src.intelligence.buy_sell_detector import BuySellDetector
from src.intelligence.wallet import (
    WalletProfile,
    WalletProfiler,
    WalletScoringEngine,
    WalletClusteringEngine,
    WalletGraphEngine,
    WalletReputationEngine
)

logger = logging.getLogger(__name__)

class WalletWorkflow(Workflow):
    """
    Upgraded Wallet Workflow.
    Maintains wallet history/positions, runs multi-dimensional scoring,
    updates reputation labels, links wallets in a graph, and alerts on followed wallets.
    """
    def __init__(
        self,
        profiler: Optional[WalletProfiler] = None,
        scoring_engine: Optional[WalletScoringEngine] = None,
        clustering_engine: Optional[WalletClusteringEngine] = None,
        graph_engine: Optional[WalletGraphEngine] = None,
        reputation_engine: Optional[WalletReputationEngine] = None,
        monitor: Optional[TransactionMonitor] = None,
        detector: Optional[BuySellDetector] = None
    ):
        self.profiler = profiler or WalletProfiler()
        self.scoring_engine = scoring_engine or WalletScoringEngine()
        self.clustering_engine = clustering_engine or WalletClusteringEngine()
        self.graph_engine = graph_engine or WalletGraphEngine()
        self.reputation_engine = reputation_engine or WalletReputationEngine()
        
        self.monitor = monitor or TransactionMonitor()
        self.detector = detector or BuySellDetector()

    @property
    def name(self) -> str:
        return "Wallet"

    async def get_wallet_profile(self, address: str) -> Optional[WalletProfile]:
        """Loads and parses a WalletProfile directly from DBIdentity mapping."""
        async with postgres_store.async_session() as session:
            stmt = select(DBIdentity).where(DBIdentity.canonical_id == f"profile_{address.lower()}")
            result = await session.execute(stmt)
            db_entity = result.scalar_one_or_none()
            if db_entity:
                return WalletProfile(**db_entity.data)
            return None

    async def load_all_profiles(self) -> List[WalletProfile]:
        """Loads all profiles currently in the database to run global clustering."""
        async with postgres_store.async_session() as session:
            stmt = select(DBIdentity).where(DBIdentity.identity_type == "WalletProfile")
            result = await session.execute(stmt)
            entities = result.scalars().all()
            return [WalletProfile(**entity.data) for entity in entities]

    async def process(self, event: CanonicalNotificationEvent) -> None:
        if not event.referenced_wallet_address:
            logger.debug(f"[{self.name}] Event {event.event_id} has no referenced wallet address. Skipping.")
            return

        address = event.referenced_wallet_address.lower()
        chain = event.blockchain_id or "ethereum"
        logger.info(f"[{self.name}] Tracking wallet activity for {address} on {chain}")

        # 1. Retrieve or create profile
        profile = await self.get_wallet_profile(address)
        if not profile:
            logger.info(f"[{self.name}] Discovered new wallet: {address}")
            profile = self.profiler.create_profile(address, chain)

        # Update followed state in case it changed in the registry
        profile.is_followed = self.profiler.is_followed(address)

        # 2. Decode transaction details if present in raw payload
        payload = event.raw_payload or {}
        has_tx_info = any(k in payload for k in ["tx_hash", "hash", "signature", "id", "input", "logs"])
        
        decoded_tx = None
        if has_tx_info:
            try:
                raw_tx = dict(payload)
                if "tx_hash" not in raw_tx:
                    raw_tx["tx_hash"] = event.notification_id or f"tx_{event.event_id}"
                if "chain" not in raw_tx:
                    raw_tx["chain"] = chain
                if "timestamp" not in raw_tx:
                    raw_tx["timestamp"] = event.timestamp
                if "sender" not in raw_tx:
                    raw_tx["sender"] = address
                
                decoded_tx = self.monitor.decode(raw_tx)
                # Record transaction patterns
                self.profiler.record_transaction(profile, decoded_tx)
            except Exception as e:
                logger.error(f"[{self.name}] Failed to decode transaction for profile update: {e}")

        # 3. Detect trades if transaction represents a swap
        token_address = event.referenced_token_address or payload.get("token_address")
        if decoded_tx and token_address:
            # Query market parameters to calculate relative metrics and update cost basis
            price_usd = 0.0
            try:
                m_intel = market_intelligence_manager.get_full_token_intelligence(token_address, chain)
                if m_intel:
                    price_usd = float(m_intel.get("price", {}).get("price_usd") or 0.0)
            except Exception as e:
                logger.debug(f"[{self.name}] Failed to fetch price context from MarketIntelligenceManager: {e}")

            trade = self.detector.detect(
                decoded_tx=decoded_tx,
                token_address=token_address,
                current_price_usd=price_usd
            )
            
            if trade:
                self.profiler.record_trade(profile, trade, price_usd)

        # 4. Evaluate Scoring & Decay
        # Look up token launches & peak prices from metadata if available (to pass to scoring engine)
        token_launches = {}
        token_peak_prices = {}
        for pos_addr, pos in profile.positions.items():
            # Estimate peak price as max sold price or current price
            token_peak_prices[pos_addr] = max(
                pos.average_buy_price * 2.0, # fallback estimate
                pos.total_sold_usd / pos.total_sold_tokens if pos.total_sold_tokens > 0 else 0.0
            )

        self.scoring_engine.calculate_and_update_score(
            profile=profile,
            token_launches=token_launches,
            token_peak_prices=token_peak_prices
        )

        # 5. Graph Updates & Traversals
        node_type = "WALLET"
        # Determine node type based on reputation/labels
        reputation_strs = [l.label for l in profile.reputation_labels]
        if "DEVELOPER" in reputation_strs:
            node_type = "DEVELOPER"
        elif "EXCHANGE" in reputation_strs:
            node_type = "EXCHANGE"

        self.graph_engine.add_node(profile.address, node_type, {
            "score": profile.score.score,
            "reputation_labels": reputation_strs
        })

        # Add funding links
        for f in profile.funding_sources:
            self.graph_engine.add_relationship(
                source=f.sender_address,
                target=profile.address,
                rel_type="FUNDED",
                confidence=0.99,
                properties={"tx_hash": f.tx_hash, "amount": f.amount, "timestamp": f.timestamp.isoformat()}
            )
            await graph_store.add_relationship(
                source_id=f.sender_address,
                target_id=profile.address,
                rel_type="FUNDED",
                properties={"confidence": 0.99, "tx_hash": f.tx_hash}
            )

        # Add counterparty links
        for c in profile.top_counterparties.values():
            self.graph_engine.add_relationship(
                source=profile.address,
                target=c.address,
                rel_type="COUNTERPARTY",
                confidence=0.80 if c.incoming_count + c.outgoing_count >= 5 else 0.50,
                properties={"volume_usd": c.total_volume_usd, "count": c.incoming_count + c.outgoing_count}
            )
            await graph_store.add_relationship(
                source_id=profile.address,
                target_id=c.address,
                rel_type="COUNTERPARTY",
                properties={"confidence": 0.80 if c.incoming_count + c.outgoing_count >= 5 else 0.50}
            )

        # 6. Evaluate Reputation & Dynamic Labels
        old_labels = {l.label for l in profile.reputation_labels}
        self.reputation_engine.evaluate_reputation(profile, self.graph_engine)
        new_labels = {l.label for l in profile.reputation_labels}

        # 7. Run Co-trading Clustering across all wallets
        all_profiles = await self.load_all_profiles()
        # Add current profile in case it hasn't been saved yet
        if not any(p.address.lower() == profile.address.lower() for p in all_profiles):
            all_profiles.append(profile)

        relationships = self.clustering_engine.detect_relationships(all_profiles)
        for r in relationships:
            if r["relation_type"] == "synchronized_trade":
                self.graph_engine.add_relationship(
                    source=r["wallet_a"],
                    target=r["wallet_b"],
                    rel_type="CO_TRADER",
                    confidence=r["confidence"],
                    properties=r["details"]
                )
                await graph_store.add_relationship(
                    source_id=r["wallet_a"],
                    target_id=r["wallet_b"],
                    rel_type="CO_TRADER",
                    properties={"confidence": r["confidence"]}
                )

        # 8. Persist updated profile
        await postgres_store.upsert_entity(profile)

        # 9. Alerting for followed wallets or reputation changes
        label_change = old_labels != new_labels
        if profile.is_followed or label_change:
            alert_payload = {
                "source_app_id": "wallet_intelligence_workflow",
                "event_category": "wallet_alert",
                "referenced_wallet_address": profile.address,
                "raw_payload": {
                    "address": profile.address,
                    "is_followed": profile.is_followed,
                    "reputation_labels": [l.model_dump(mode="json") for l in profile.reputation_labels],
                    "score": profile.score.model_dump(mode="json"),
                    "label_change": label_change,
                    "previous_labels": list(old_labels),
                    "current_labels": list(new_labels)
                }
            }
            logger.warning(f"[{self.name}] Alert triggered for wallet {profile.address}! Labels: {list(new_labels)}")
            if publisher.kafka:
                try:
                    await publisher.publish(alert_payload)
                except Exception as e:
                    logger.error(f"[{self.name}] Failed to publish wallet alert: {e}")

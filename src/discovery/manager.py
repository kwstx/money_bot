import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime, timezone

from .schemas import (
    UnifiedChainEvent,
    EventType,
    TokenDeploymentMetadata,
    PoolRecord,
)
from ..schemas import TokenIdentity
from ..storage.implementations import postgres_store

logger = logging.getLogger(__name__)

class TokenDiscoveryManager:
    """
    Token Discovery System.
    Continuously ingests unified chain events, creates token & pool records,
    captures deployment metadata, and launches parallel analysis tasks.
    """

    def __init__(self):
        self.known_tokens: Dict[str, TokenIdentity] = {}
        self.pools: Dict[str, List[PoolRecord]] = {}
        self.deployment_metadata: Dict[str, TokenDeploymentMetadata] = {}
        self._analysis_subscribers: List[Callable[[str, str], Awaitable[None]]] = []

    def register_analysis_subscriber(self, subscriber: Callable[[str, str], Awaitable[None]]):
        """
        Register a subscriber callback that is invoked when a new token is discovered.
        Callback signature: async def subscriber(token_address: str, chain: str) -> None
        """
        self._analysis_subscribers.append(subscriber)

    async def process_event(self, event: UnifiedChainEvent) -> Optional[TokenIdentity]:
        """
        Main ingress handler for raw/unified chain events.
        """
        if event.event_type == EventType.NEW_TOKEN or event.event_type == EventType.PAIR_CREATED:
            return await self._handle_token_discovery(event)
        elif event.event_type == EventType.LIQUIDITY_ADDED:
            await self._handle_liquidity_added(event)
        elif event.event_type == EventType.SWAP_EXECUTED:
            await self._handle_swap_executed(event)
        elif event.event_type == EventType.TRADING_ACTIVATED:
            await self._handle_trading_activated(event)
        return None

    async def _handle_token_discovery(self, event: UnifiedChainEvent) -> TokenIdentity:
        token_address = event.token_address or event.payload.get("token_address")
        chain = event.chain

        if not token_address:
            logger.warning(f"[Discovery] Discovery event missing token address: {event}")
            raise ValueError("Token address missing in discovery event")

        composite_key = f"{chain}:{token_address.lower()}"

        # In-memory check first
        if composite_key in self.known_tokens:
            logger.debug(f"[Discovery] Token {composite_key} already known in memory.")
            return self.known_tokens[composite_key]

        # DB check with graceful fallback
        try:
            existing_identity = await postgres_store.get_entity(composite_key)
            if existing_identity and isinstance(existing_identity, TokenIdentity):
                self.known_tokens[composite_key] = existing_identity
                return existing_identity
        except Exception as err:
            logger.debug(f"[Discovery] Operational store offline or error ({err}); relying on in-memory store.")

        # Create deployment metadata
        metadata = TokenDeploymentMetadata(
            token_address=token_address,
            chain=chain,
            deployer_address=event.wallet_address or event.payload.get("deployer"),
            creation_tx_hash=event.tx_hash,
            block_number=event.block_number,
            timestamp=event.timestamp,
            initial_supply=event.payload.get("initial_supply"),
            bytecode_hash=event.payload.get("bytecode_hash"),
            is_verified_source=event.payload.get("is_verified", False),
            metadata=event.payload
        )
        self.deployment_metadata[composite_key] = metadata

        # Create canonical token record
        token_record = TokenIdentity(
            canonical_id=composite_key,
            address=token_address,
            chain=chain,
            symbol=event.payload.get("symbol", "UNKNOWN"),
            name=event.payload.get("name", "Unknown Token"),
            decimals=event.payload.get("decimals", 18),
            metadata={
                "deployer": metadata.deployer_address,
                "creation_tx_hash": metadata.creation_tx_hash,
                "block_number": metadata.block_number,
                "deployment_timestamp": metadata.timestamp.isoformat(),
                "discovered_at": datetime.now(timezone.utc).isoformat()
            }
        )

        try:
            await postgres_store.upsert_entity(token_record)
        except Exception as err:
            logger.debug(f"[Discovery] Could not upsert entity to postgres_store ({err}); stored in memory.")

        self.known_tokens[composite_key] = token_record

        # If pair/pool address present, record pool details
        pool_address = event.pool_address or event.payload.get("pool_address")
        if pool_address:
            pool = PoolRecord(
                pool_address=pool_address,
                chain=chain,
                dex_name=event.payload.get("dex_name", "UnknownDEX"),
                factory_address=event.payload.get("factory_address"),
                token0_address=event.payload.get("token0", token_address),
                token1_address=event.payload.get("token1", "NATIVE"),
                target_token_address=token_address,
                quote_token_address=event.payload.get("quote_token", "NATIVE"),
                initial_reserve0=float(event.payload.get("reserve0", 0.0)),
                initial_reserve1=float(event.payload.get("reserve1", 0.0)),
                initial_liquidity_usd=float(event.payload.get("initial_liquidity_usd", 0.0)),
                creation_tx_hash=event.tx_hash,
                created_at=event.timestamp
            )
            self.pools.setdefault(composite_key, []).append(pool)

        logger.info(f"[Discovery] Discovered new token {token_record.symbol} ({composite_key}) on {chain}")

        # Trigger Parallel Analysis Workflow immediately
        await self._trigger_parallel_analysis(token_address, chain)

        return token_record

    async def _handle_liquidity_added(self, event: UnifiedChainEvent) -> None:
        token_address = event.token_address or event.payload.get("token_address")
        if not token_address:
            return
        composite_key = f"{event.chain}:{token_address.lower()}"
        logger.info(f"[Discovery] Liquidity added for token {composite_key}: {event.payload.get('amount_usd', 0.0)} USD")

    async def _handle_swap_executed(self, event: UnifiedChainEvent) -> None:
        token_address = event.token_address or event.payload.get("token_address")
        if not token_address:
            return
        composite_key = f"{event.chain}:{token_address.lower()}"
        logger.debug(f"[Discovery] First swap executed for token {composite_key}")

    async def _handle_trading_activated(self, event: UnifiedChainEvent) -> None:
        token_address = event.token_address or event.payload.get("token_address")
        if not token_address:
            return
        composite_key = f"{event.chain}:{token_address.lower()}"
        logger.info(f"[Discovery] Trading activated for token {composite_key}")

    async def _trigger_parallel_analysis(self, token_address: str, chain: str) -> None:
        """
        Executes parallel security check, risk assessment, and launch analysis tasks.
        """
        logger.info(f"[Discovery] Launching parallel analysis tasks for {chain}:{token_address}")
        
        tasks = []
        for subscriber in self._analysis_subscribers:
            tasks.append(asyncio.create_task(subscriber(token_address, chain)))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for idx, res in enumerate(results):
                if isinstance(res, Exception):
                    logger.error(f"[Discovery] Parallel analysis task {idx} failed for {token_address}: {res}")

token_discovery_manager = TokenDiscoveryManager()

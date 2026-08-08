from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging

from .base import ChainAdapter
from ...discovery.schemas import UnifiedChainEvent, EventType

logger = logging.getLogger(__name__)

# Uniswap V2 PairCreated topic signature
UNISWAP_V2_PAIR_CREATED = "0x0d364807468ba37c76757150ace64230137d16f175a3d080a3778f2d1e2e92c6"

class EVMChainAdapter(ChainAdapter):
    """
    Chain Adapter for EVM-compatible networks (Ethereum, Base, Arbitrum, BSC).
    """

    def __init__(self, chain_name: str = "ethereum", confirmations: int = 12):
        self._chain_id = chain_name.lower()
        self._confirmations = confirmations

    @property
    def chain_id(self) -> str:
        return self._chain_id

    @property
    def required_confirmations(self) -> int:
        return self._confirmations

    def normalize_address(self, address: str) -> str:
        if not address:
            return ""
        return address.lower().strip()

    def parse_transaction(self, raw_tx: Dict[str, Any]) -> List[UnifiedChainEvent]:
        events = []
        tx_hash = raw_tx.get("hash")
        block_number = raw_tx.get("blockNumber")
        to_address = self.normalize_address(raw_tx.get("to", ""))
        from_address = self.normalize_address(raw_tx.get("from", ""))

        # Check for contract creation (to is None or empty)
        if not to_address or raw_tx.get("creates"):
            token_address = self.normalize_address(raw_tx.get("creates", raw_tx.get("contractAddress", "")))
            if token_address:
                events.append(
                    UnifiedChainEvent(
                        event_type=EventType.NEW_TOKEN,
                        chain=self.chain_id,
                        block_number=block_number,
                        tx_hash=tx_hash,
                        token_address=token_address,
                        wallet_address=from_address,
                        payload={
                            "deployer": from_address,
                            "bytecode_hash": raw_tx.get("input", "")[:66],
                            "value": raw_tx.get("value", 0)
                        }
                    )
                )

        return events

    def parse_log_event(self, raw_log: Dict[str, Any]) -> Optional[UnifiedChainEvent]:
        topics = raw_log.get("topics", [])
        topic0 = topics[0].lower() if topics and isinstance(topics[0], str) else ""
        tx_hash = raw_log.get("transactionHash")
        block_number = raw_log.get("blockNumber")
        event_name = raw_log.get("event", "")

        # Uniswap V2 / V3 PairCreated Event Log
        if topic0 == UNISWAP_V2_PAIR_CREATED or event_name == "PairCreated":
            token0 = raw_log.get("token0") or (topics[1] if len(topics) > 1 else None)
            token1 = raw_log.get("token1") or (topics[2] if len(topics) > 2 else None)
            pair_address = raw_log.get("pair") or raw_log.get("address")

            return UnifiedChainEvent(
                event_type=EventType.PAIR_CREATED,
                chain=self.chain_id,
                block_number=block_number,
                tx_hash=tx_hash,
                token_address=self.normalize_address(token0 or ""),
                pool_address=self.normalize_address(pair_address or ""),
                payload={
                    "token0": self.normalize_address(token0 or ""),
                    "token1": self.normalize_address(token1 or ""),
                    "pool_address": self.normalize_address(pair_address or ""),
                    "factory_address": self.normalize_address(raw_log.get("address", "")),
                    "dex_name": raw_log.get("dex_name", "UniswapV2")
                }
            )

        return None

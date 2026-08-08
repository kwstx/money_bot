from typing import Dict, Any, List, Optional
import logging

from .base import ChainAdapter
from ...discovery.schemas import UnifiedChainEvent, EventType

logger = logging.getLogger(__name__)

class SolanaChainAdapter(ChainAdapter):
    """
    Chain Adapter for Solana blockchain (SPL Tokens, Raydium, PumpFun).
    """

    def __init__(self, confirmations: int = 1):
        self._chain_id = "solana"
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
        return address.strip()

    def parse_transaction(self, raw_tx: Dict[str, Any]) -> List[UnifiedChainEvent]:
        events = []
        signature = raw_tx.get("signature") or raw_tx.get("tx_hash")
        slot = raw_tx.get("slot") or raw_tx.get("block_number")
        payer = self.normalize_address(raw_tx.get("payer", raw_tx.get("feePayer", "")))

        # Detect InitializeMint or PumpFun Token Creation
        if raw_tx.get("instruction") == "InitializeMint" or raw_tx.get("is_token_creation"):
            token_address = self.normalize_address(raw_tx.get("mint", raw_tx.get("token_address", "")))
            if token_address:
                events.append(
                    UnifiedChainEvent(
                        event_type=EventType.NEW_TOKEN,
                        chain=self.chain_id,
                        block_number=slot,
                        tx_hash=signature,
                        token_address=token_address,
                        wallet_address=payer,
                        payload={
                            "deployer": payer,
                            "decimals": raw_tx.get("decimals", 9),
                            "mint_authority": raw_tx.get("mintAuthority"),
                            "freeze_authority": raw_tx.get("freezeAuthority"),
                            "symbol": raw_tx.get("symbol", "UNKNOWN"),
                            "name": raw_tx.get("name", "Solana Token")
                        }
                    )
                )

        return events

    def parse_log_event(self, raw_log: Dict[str, Any]) -> Optional[UnifiedChainEvent]:
        event_name = raw_log.get("event") or raw_log.get("type")
        signature = raw_log.get("signature")
        slot = raw_log.get("slot")

        if event_name in ("InitializePool", "RaydiumPoolCreated", "PumpFunPoolCreated"):
            token_address = self.normalize_address(raw_log.get("mint", raw_log.get("token_address", "")))
            pool_address = self.normalize_address(raw_log.get("pool_address", raw_log.get("pair", "")))

            return UnifiedChainEvent(
                event_type=EventType.PAIR_CREATED,
                chain=self.chain_id,
                block_number=slot,
                tx_hash=signature,
                token_address=token_address,
                pool_address=pool_address,
                payload={
                    "token0": token_address,
                    "token1": self.normalize_address(raw_log.get("quote_mint", "So11111111111111111111111111111111111111112")),
                    "pool_address": pool_address,
                    "dex_name": raw_log.get("dex_name", "Raydium"),
                    "initial_liquidity_usd": float(raw_log.get("initial_liquidity_usd", 0.0))
                }
            )

        return None

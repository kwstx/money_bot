import logging
from .base import Workflow
from ..schemas import CanonicalNotificationEvent

logger = logging.getLogger(__name__)

class DiscoveryWorkflow(Workflow):
    @property
    def name(self) -> str:
        return "Discovery"

    async def process(self, event: CanonicalNotificationEvent) -> None:
        if not event.referenced_token_address:
            return
            
        logger.info(f"[{self.name}] Processing token discovery for {event.referenced_token_address}")
        
        from ..storage.implementations import postgres_store
        from ..schemas import TokenIdentity
        
        # Check if token is already known
        token = await postgres_store.get_entity(event.referenced_token_address)
        if not token:
            logger.info(f"[{self.name}] Brand new token discovered! Triggering deep discovery for {event.referenced_token_address}")
            # Here we would normally call out to RPC nodes, DexScreener, etc. to get decimals/symbol
            new_token = TokenIdentity(
                canonical_id=event.referenced_token_address,
                address=event.referenced_token_address,
                chain=event.blockchain_id or "solana",
                symbol="UNKNOWN",
                metadata={"discovered_from": event.source_app_id}
            )
            await postgres_store.upsert_entity(new_token)
        else:
            logger.debug(f"[{self.name}] Token {event.referenced_token_address} is already known.")

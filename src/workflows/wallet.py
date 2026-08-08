import logging
from .base import Workflow
from ..schemas import CanonicalNotificationEvent, WalletIdentity
from ..storage.implementations import postgres_store

logger = logging.getLogger(__name__)

class WalletWorkflow(Workflow):
    @property
    def name(self) -> str:
        return "Wallet"

    async def process(self, event: CanonicalNotificationEvent) -> None:
        if not event.referenced_wallet_address:
            return
            
        logger.info(f"[{self.name}] Tracking wallet activity for {event.referenced_wallet_address}")
        
        # In a real scenario, we might check the database if this wallet is new
        existing_wallet = await postgres_store.get_entity(event.referenced_wallet_address)
        if not existing_wallet:
            logger.info(f"[{self.name}] Discovered new wallet: {event.referenced_wallet_address}")
            new_wallet = WalletIdentity(
                canonical_id=event.referenced_wallet_address,
                address=event.referenced_wallet_address,
                chain=event.blockchain_id or "ethereum"
            )
            await postgres_store.upsert_entity(new_wallet)

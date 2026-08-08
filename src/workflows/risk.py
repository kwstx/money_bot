import logging
from .base import Workflow
from ..schemas import CanonicalNotificationEvent

logger = logging.getLogger(__name__)

class RiskWorkflow(Workflow):
    @property
    def name(self) -> str:
        return "Risk"

    async def process(self, event: CanonicalNotificationEvent) -> None:
        if not event.referenced_token_address and not event.referenced_wallet_address:
            return
            
        logger.info(f"[{self.name}] Assessing risk for event {event.event_id}")
        
        from ..storage.implementations import postgres_store
        
        # If this is a token event, maybe we flag high risk for unverified tokens
        if event.referenced_token_address:
            token = await postgres_store.get_entity(event.referenced_token_address)
            if token and token.metadata.get("discovered_from") == "untrusted_source":
                logger.warning(f"[{self.name}] High risk token detected: {event.referenced_token_address}")
        
        # If this is a wallet event, check for known bad actors
        if event.referenced_wallet_address:
            wallet = await postgres_store.get_entity(event.referenced_wallet_address)
            # Add risk flags if necessary
            if wallet and getattr(wallet, 'risk_score', 0) > 80.0:
                logger.warning(f"[{self.name}] High risk wallet interacted: {event.referenced_wallet_address}")

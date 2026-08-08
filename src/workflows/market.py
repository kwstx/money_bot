import logging
from .base import Workflow
from ..schemas import CanonicalNotificationEvent

logger = logging.getLogger(__name__)

class MarketWorkflow(Workflow):
    @property
    def name(self) -> str:
        return "Market"

    async def process(self, event: CanonicalNotificationEvent) -> None:
        logger.info(f"[{self.name}] Processing event {event.event_id}")
        # Logic for processing price action, volume, or liquidity changes
        pass

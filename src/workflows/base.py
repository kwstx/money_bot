import logging
from abc import ABC, abstractmethod
from ..schemas import CanonicalNotificationEvent

logger = logging.getLogger(__name__)

class Workflow(ABC):
    """Base class for downstream intelligence workflows."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the workflow."""
        pass

    @abstractmethod
    async def process(self, event: CanonicalNotificationEvent) -> None:
        """Process the canonical event and apply workflow logic."""
        pass

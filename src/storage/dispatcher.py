import logging
from typing import List
from ..schemas import CanonicalNotificationEvent
from .interfaces import EventStore, OperationalStore, TimeSeriesStore, GraphStore, FeatureStore

logger = logging.getLogger(__name__)

class StorageDispatcher:
    """
    Responsible for projecting a CanonicalNotificationEvent into 
    the various specialized data stores.
    """
    def __init__(
        self,
        event_store: EventStore = None,
        operational_store: OperationalStore = None,
        time_series_store: TimeSeriesStore = None,
        graph_store: GraphStore = None,
        feature_store: FeatureStore = None
    ):
        self.event_store = event_store
        self.operational_store = operational_store
        self.time_series_store = time_series_store
        self.graph_store = graph_store
        self.feature_store = feature_store

    async def dispatch_event(self, event: CanonicalNotificationEvent):
        """Dispatches an event to all configured stores."""
        logger.info(f"Dispatching event {event.event_id} to storage layers.")
        
        # 1. Always append to Immutable Event Store first
        if self.event_store:
            await self.event_store.append(event)
            
        # 2. Extract entities and update Operational Store
        # (Mock logic: in reality, you'd parse event.entities)
        if self.operational_store:
            logger.debug("Updating Operational Store")
            
        # 3. If there is price/volume/latency data, send to Time-Series
        if self.time_series_store:
            logger.debug("Updating Time-Series Store")
            
        # 4. If relationships exist (e.g. Wallet -> Token), send to Graph
        if self.graph_store:
            logger.debug("Updating Graph Store")
            
        # 5. Recompute and push ML features if applicable
        if self.feature_store:
            logger.debug("Updating Feature Store")

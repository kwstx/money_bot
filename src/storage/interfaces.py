from abc import ABC, abstractmethod
from typing import Dict, Any, List
from ..schemas import CanonicalIdentity, CanonicalNotificationEvent

class EventStore(ABC):
    """Immutable append-only log of all events."""
    @abstractmethod
    async def append(self, event: CanonicalNotificationEvent) -> None:
        pass
    
    @abstractmethod
    async def get_history(self, entity_id: str) -> List[CanonicalNotificationEvent]:
        pass

class OperationalStore(ABC):
    """Derived current state database (e.g. PostgreSQL)."""
    @abstractmethod
    async def upsert_entity(self, entity: CanonicalIdentity) -> None:
        pass
        
    @abstractmethod
    async def get_entity(self, canonical_id: str) -> CanonicalIdentity | None:
        pass

class TimeSeriesStore(ABC):
    """Optimized for metrics, prices, and high-frequency data (e.g. InfluxDB)."""
    @abstractmethod
    async def insert_point(self, measurement: str, tags: Dict[str, str], fields: Dict[str, Any], timestamp: str) -> None:
        pass

class GraphStore(ABC):
    """Optimized for entity relationships (e.g. Neo4j)."""
    @abstractmethod
    async def add_relationship(self, source_id: str, target_id: str, rel_type: str, properties: Dict[str, Any]) -> None:
        pass

class FeatureStore(ABC):
    """Optimized for serving ML model features."""
    @abstractmethod
    async def update_features(self, entity_id: str, features: Dict[str, float]) -> None:
        pass

import json
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, mapped_column, Mapped
from sqlalchemy import String, JSON, DateTime, select
from datetime import datetime, timezone
import logging

from .interfaces import EventStore, OperationalStore, TimeSeriesStore, GraphStore, FeatureStore
from ..schemas import CanonicalIdentity, CanonicalNotificationEvent
from ..config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

class DBEvent(Base):
    __tablename__ = "events"
    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    entity_id: Mapped[str] = mapped_column(String, index=True, nullable=True) # E.g., Token address
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict] = mapped_column(JSON)

class DBIdentity(Base):
    __tablename__ = "identities"
    canonical_id: Mapped[str] = mapped_column(String, primary_key=True)
    identity_type: Mapped[str] = mapped_column(String, index=True) # Token, Wallet, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data: Mapped[dict] = mapped_column(JSON) # The actual identity schema

class PostgresStore(EventStore, OperationalStore):
    """
    Combined implementation for Operational DB and Event Store using PostgreSQL.
    """
    def __init__(self):
        self.engine = create_async_engine(settings.postgres_url, echo=False)
        self.async_session = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("PostgreSQL tables initialized.")

    async def append(self, event: CanonicalNotificationEvent) -> None:
        """Immutable append-only log of events."""
        async with self.async_session() as session:
            async with session.begin():
                db_event = DBEvent(
                    event_id=event.event_id,
                    entity_id=event.referenced_token_address or event.referenced_wallet_address,
                    timestamp=event.timestamp,
                    payload=event.model_dump(mode="json")
                )
                session.add(db_event)
        logger.debug(f"Event {event.event_id} appended to store.")

    async def get_history(self, entity_id: str) -> List[CanonicalNotificationEvent]:
        """Time-travel / Event sourcing reconstruction."""
        async with self.async_session() as session:
            stmt = select(DBEvent).where(DBEvent.entity_id == entity_id).order_by(DBEvent.timestamp)
            result = await session.execute(stmt)
            events = result.scalars().all()
            return [CanonicalNotificationEvent(**event.payload) for event in events]

    async def upsert_entity(self, entity: CanonicalIdentity) -> None:
        """Upsert canonical entity state."""
        async with self.async_session() as session:
            async with session.begin():
                stmt = select(DBIdentity).where(DBIdentity.canonical_id == entity.canonical_id)
                result = await session.execute(stmt)
                db_entity = result.scalar_one_or_none()
                
                if db_entity:
                    db_entity.updated_at = entity.updated_at
                    db_entity.data = entity.model_dump(mode="json")
                else:
                    db_entity = DBIdentity(
                        canonical_id=entity.canonical_id,
                        identity_type=entity.__class__.__name__,
                        created_at=entity.created_at,
                        updated_at=entity.updated_at,
                        data=entity.model_dump(mode="json")
                    )
                    session.add(db_entity)
        logger.debug(f"Entity {entity.canonical_id} upserted.")

    async def get_entity(self, canonical_id: str) -> CanonicalIdentity | None:
        async with self.async_session() as session:
            stmt = select(DBIdentity).where(DBIdentity.canonical_id == canonical_id)
            result = await session.execute(stmt)
            db_entity = result.scalar_one_or_none()
            if db_entity:
                # Need to convert back to specific subclass based on identity_type
                # For simplicity, returning a raw BaseModel or passing to a factory would be better,
                # but we'll return the base class for the interface for now.
                return CanonicalIdentity(**db_entity.data)
            return None

# For the sake of this implementation, we will use mock/stub stores for TimeSeries and Graph 
# to focus on the core Postgres Operational Store + Kafka bus architecture requested.

class MockTimeSeriesStore(TimeSeriesStore):
    async def insert_point(self, measurement: str, tags: Dict[str, str], fields: Dict[str, Any], timestamp: str) -> None:
        logger.debug(f"TS Point inserted: {measurement} {tags}")

class MockGraphStore(GraphStore):
    async def add_relationship(self, source_id: str, target_id: str, rel_type: str, properties: Dict[str, Any]) -> None:
        logger.debug(f"Graph relationship added: {source_id} -[{rel_type}]-> {target_id}")

class MockFeatureStore(FeatureStore):
    async def update_features(self, entity_id: str, features: Dict[str, float]) -> None:
        logger.debug(f"Features updated for {entity_id}: {features}")

postgres_store = PostgresStore()
ts_store = MockTimeSeriesStore()
graph_store = MockGraphStore()
feature_store = MockFeatureStore()

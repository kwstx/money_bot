import json
import logging
from aiokafka import AIOKafkaProducer
from ..config import settings
from ..schemas import CanonicalNotificationEvent

logger = logging.getLogger(__name__)

class DurableProducer:
    """
    A durable Kafka producer to publish canonical events into the message bus.
    Ensures message delivery.
    """
    def __init__(self):
        self.producer: AIOKafkaProducer | None = None
        self._connected = False

    async def connect(self):
        if self._connected:
            return
        self.producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            acks="all",  # Highest durability
            enable_idempotence=True # Idempotent producer
        )
        await self.producer.start()
        self._connected = True
        logger.info(f"DurableProducer connected to Kafka at {settings.kafka_bootstrap_servers}")

    async def disconnect(self):
        if self.producer and self._connected:
            await self.producer.stop()
            self._connected = False
            logger.info("DurableProducer disconnected.")

    async def publish_canonical_event(self, event: CanonicalNotificationEvent):
        """Publish a normalized canonical event to the main events topic."""
        if not self._connected or not self.producer:
            await self.connect()
            
        topic = settings.events_topic
        payload = event.model_dump(mode="json")
        try:
            # We use event_id as the Kafka key to guarantee ordering for the same event if it's updated
            key = event.event_id.encode('utf-8')
            await self.producer.send_and_wait(topic, value=payload, key=key)
            logger.debug(f"Published canonical event {event.event_id} to {topic}")
        except Exception as e:
            logger.error(f"Failed to publish event {event.event_id}: {e}")
            raise

producer = DurableProducer()

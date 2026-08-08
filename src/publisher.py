import json
import logging
import asyncio
from redis.asyncio import Redis
from aiokafka import AIOKafkaProducer
from .config import settings
from .telemetry import TelemetryTracker

logger = logging.getLogger(__name__)

class EventPublisher:
    def __init__(self):
        self.redis: Redis | None = None
        self.kafka: AIOKafkaProducer | None = None

    async def connect(self):
        """Establish connections to Redis (cache) and Kafka (durable broker)."""
        try:
            # Connect to Redis for deduplication caching
            self.redis = Redis.from_url(settings.redis_url, decode_responses=True)
            await self.redis.ping()
            logger.info(f"Connected to Redis at {settings.redis_url}")

            # Connect to Kafka for durable messaging
            self.kafka = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            await self.kafka.start()
            logger.info(f"Connected to Kafka broker at {settings.kafka_bootstrap_servers}")

        except Exception as e:
            logger.error(f"Failed to connect to messaging brokers: {e}")
            raise

    async def disconnect(self):
        """Close connections to brokers."""
        if self.kafka:
            await self.kafka.stop()
            logger.info("Disconnected from Kafka")
        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis")

    async def publish_raw(self, payload: dict, fingerprint: str, tracker: TelemetryTracker = None):
        """Publish a raw notification payload to the immutable log."""
        if not self.kafka:
            raise RuntimeError("Kafka connection is not established")
        
        try:
            message = {
                "fingerprint": fingerprint,
                "payload": payload
            }
            if tracker and tracker.receipt_time:
                message["receipt_time"] = str(tracker.receipt_time)
                
            future = await self.kafka.send(settings.raw_events_topic, message)
            logger.debug(f"Published raw event to Kafka topic '{settings.raw_events_topic}'.")
            return future
        except Exception as e:
            logger.error(f"Failed to publish raw event: {e}")
            raise

    async def publish(self, event: dict, tracker: TelemetryTracker = None):
        """Publish a canonical notification event to the durable broker."""
        if not self.kafka:
            raise RuntimeError("Kafka connection is not established")
        
        try:
            if tracker:
                tracker.record_pre_queue()
                event["telemetry"] = tracker.to_dict()
            
            future = await self.kafka.send(settings.events_topic, event)
            
            if tracker:
                tracker.record_post_queue()

            logger.debug(f"Published canonical event to Kafka topic '{settings.events_topic}'.")
            return future
        except Exception as e:
            logger.error(f"Failed to publish canonical event: {e}")
            raise

publisher = EventPublisher()


import json
import logging
from redis.asyncio import Redis
from .config import settings
from .telemetry import TelemetryTracker

logger = logging.getLogger(__name__)

class EventPublisher:
    def __init__(self):
        self.redis: Redis | None = None

    async def connect(self):
        """Establish connection to the Redis message broker."""
        try:
            self.redis = Redis.from_url(settings.redis_url, decode_responses=True)
            # Test connection
            await self.redis.ping()
            logger.info(f"Connected to Redis message broker at {settings.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        """Close connection to the Redis message broker."""
        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis message broker")

    async def publish_raw(self, payload: dict, fingerprint: str, tracker: TelemetryTracker = None):
        """Publish a raw notification payload to the immutable log."""
        if not self.redis:
            raise RuntimeError("Redis connection is not established")
        
        try:
            import asyncio
            payload_str = await asyncio.to_thread(json.dumps, payload)
            
            message = {
                "fingerprint": fingerprint,
                "payload": payload_str
            }
            if tracker and tracker.receipt_time:
                message["receipt_time"] = str(tracker.receipt_time)
                
            message_id = await self.redis.xadd(settings.raw_events_topic, message)
            logger.debug(f"Published raw event to stream '{settings.raw_events_topic}'. Message ID: {message_id}")
            return message_id
        except Exception as e:
            logger.error(f"Failed to publish raw event: {e}")
            raise

    async def publish(self, event: dict, tracker: TelemetryTracker = None):
        """Publish a canonical notification event to the durable broker."""
        if not self.redis:
            raise RuntimeError("Redis connection is not established")
        
        try:
            if tracker:
                tracker.record_pre_queue()
                event["telemetry"] = tracker.to_dict()
            import asyncio
            
            # Using Redis Streams (XADD) for persistence and durability, enabling multiple consumers.
            payload_str = await asyncio.to_thread(json.dumps, event)
            message = {"payload": payload_str}
            message_id = await self.redis.xadd(settings.events_topic, message)
            
            if tracker:
                tracker.record_post_queue()

            logger.debug(f"Published event to stream '{settings.events_topic}'. Message ID: {message_id}")
            return message_id
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            raise

publisher = EventPublisher()

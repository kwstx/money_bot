import json
import logging
from redis.asyncio import Redis
from .config import settings

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

    async def publish(self, event: dict):
        """Publish a normalized event to the broker."""
        if not self.redis:
            raise RuntimeError("Redis connection is not established")
        
        try:
            message = json.dumps(event)
            # Using Redis Pub/Sub here. Alternatively, Redis Streams (XADD) could be used for persistence.
            # Using Pub/Sub for simplicity as requested "publish notification events to a message broker".
            receivers = await self.redis.publish(settings.events_topic, message)
            logger.debug(f"Published event to topic '{settings.events_topic}'. Receivers: {receivers}")
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            raise

publisher = EventPublisher()

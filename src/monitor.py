import asyncio
import logging
from datetime import datetime, timezone
import time
from typing import Dict, Any, List

from .config import settings
from .publisher import publisher

logger = logging.getLogger(__name__)

class HealthMonitor:
    def __init__(self):
        self.last_notification_received_at: float = time.time()
        self.total_notifications_received: int = 0
        self.recovery_attempts_count: int = 0
        self._is_running: bool = False
        self._task: asyncio.Task | None = None
        
        self.redis_status = "unknown"
        self.rate_status = "healthy"

    def record_notification(self):
        """Record that a notification was successfully received."""
        self.last_notification_received_at = time.time()
        self.total_notifications_received += 1
        self.rate_status = "healthy"
        
    def check_quarantine(self, payload: dict) -> bool:
        """
        Quarantine suspicious data before it hits the canonical bus.
        Returns True if the payload should be quarantined (dropped/flagged).
        """
        confidence = payload.get("confidence", 1.0)
        if confidence < 0.3:
            logger.warning("Quarantining event due to extreme low confidence.")
            return True
            
        # Example: if multiple providers are specified but they disagree wildly on price
        providers = payload.get("metadata", {}).get("providers", [])
        if len(providers) > 1 and payload.get("price_variance_pct", 0) > 20.0:
            logger.warning("Quarantining event due to provider disagreement on price (>20% variance).")
            return True
            
        return False

    async def _check_redis_connectivity(self) -> bool:
        """Verify that Redis is connected and writable."""
        if not publisher.redis:
            logger.warning("Redis client is not initialized.")
            return False
        
        try:
            # Check ping
            await publisher.redis.ping()
            
            # Check heartbeat write
            timestamp_str = str(time.time())
            await publisher.redis.set(settings.health_redis_check_key, timestamp_str, ex=60)
            val = await publisher.redis.get(settings.health_redis_check_key)
            
            if val != timestamp_str:
                logger.error("Redis heartbeat write verification failed.")
                return False
                
            self.redis_status = "healthy"
            return True
        except Exception as e:
            logger.error(f"Redis connectivity check failed: {e}")
            self.redis_status = "disconnected"
            return False

    async def _check_kafka_connectivity(self) -> bool:
        """Verify that Kafka is connected."""
        if getattr(publisher, "kafka", None) is None:
            logger.warning("Kafka producer is not initialized.")
            return False
            
        try:
            # Check cluster metadata as a basic ping
            await publisher.kafka.client.check_version()
            return True
        except Exception as e:
            logger.error(f"Kafka connectivity check failed: {e}")
            return False

    async def _monitor_loop(self):
        """Background loop to monitor health continuously."""
        logger.info("Health monitor loop started.")
        while self._is_running:
            try:
                # 1. Verify queue and storage connectivity
                redis_healthy = await self._check_redis_connectivity()
                kafka_healthy = await self._check_kafka_connectivity()
                
                if not redis_healthy or not kafka_healthy:
                    logger.warning("Queue connectivity compromised. Attempting self-recovery...")
                    self.recovery_attempts_count += 1
                    try:
                        # Attempt to disconnect and reconnect
                        await publisher.disconnect()
                        await publisher.connect()
                        logger.info("Self-recovery successful: Reconnected to Redis.")
                    except Exception as e:
                        logger.error(f"Self-recovery failed: {e}")

                # 2. Monitor notification rates
                time_since_last = time.time() - self.last_notification_received_at
                if time_since_last > settings.notification_rate_threshold_seconds:
                    if self.rate_status != "degraded":
                        logger.warning(
                            f"Notification rate dropped. No notifications in {time_since_last:.1f}s "
                            f"(Threshold: {settings.notification_rate_threshold_seconds}s)"
                        )
                        self.rate_status = "degraded"
                else:
                    self.rate_status = "healthy"
                    
            except asyncio.CancelledError:
                logger.info("Health monitor loop cancelled.")
                break
            except Exception as e:
                logger.error(f"Unexpected error in health monitor loop: {e}")
                
            await asyncio.sleep(settings.health_check_interval_seconds)

    async def start(self):
        """Start the background monitoring loop."""
        if self._is_running:
            return
            
        self._is_running = True
        self.last_notification_received_at = time.time()  # Reset on start
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("HealthMonitor started.")

    async def stop(self):
        """Stop the background monitoring loop."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("HealthMonitor stopped.")

    def get_status(self) -> Dict[str, Any]:
        """Return a snapshot of the current health status."""
        now_ts = time.time()
        time_since_last = now_ts - self.last_notification_received_at
        
        return {
            "status": "healthy" if (self.redis_status == "healthy" and self.rate_status == "healthy") else "degraded",
            "queue_status": self.redis_status,
            "rate_status": self.rate_status,
            "metrics": {
                "total_notifications_received": self.total_notifications_received,
                "seconds_since_last_notification": round(time_since_last, 2),
                "recovery_attempts_count": self.recovery_attempts_count
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

monitor = HealthMonitor()

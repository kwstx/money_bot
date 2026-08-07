import asyncio
import logging
from typing import List

from .publisher import publisher
from .adapters.base import IngestionAdapter
from .deduplicator import Deduplicator

logger = logging.getLogger(__name__)

class CoreListener:
    """
    The CoreListener orchestrates the lifecycle of all ingestion adapters
    and manages the connection to the publisher.
    """

    def __init__(self):
        self.adapters: List[IngestionAdapter] = []
        self._tasks: List[asyncio.Task] = []
        self.deduplicator = Deduplicator(redis_client=publisher.redis)

    def register_adapter(self, adapter: IngestionAdapter):
        """
        Register a new ingestion adapter.
        """
        self.adapters.append(adapter)
        logger.info(f"Registered adapter: {adapter.__class__.__name__}")

    async def handle_notification(self, payload: dict) -> None:
        """
        Callback provided to adapters to handle an incoming notification.
        Checks for duplicates before pushing data to the publisher (e.g., Redis).
        """
        # Deduplication check
        fingerprint = self.deduplicator.compute_fingerprint(payload)
        is_duplicate = await self.deduplicator.is_duplicate_and_store(fingerprint)
        
        if is_duplicate:
            logger.info(f"Duplicate notification detected (fingerprint: {fingerprint}). Discarding.")
            return

        await publisher.publish(payload)

    async def start(self):
        """
        Start the publisher and all registered adapters concurrently.
        """
        logger.info("Starting CoreListener...")
        await publisher.connect()
        
        # Inject the connected Redis client into the deduplicator
        self.deduplicator.redis = publisher.redis

        # Start all adapters as background tasks
        for adapter in self.adapters:
            task = asyncio.create_task(adapter.start())
            self._tasks.append(task)

        # Wait for all adapters (e.g. uvicorn server running forever)
        if self._tasks:
            await asyncio.gather(*self._tasks)

    async def stop(self):
        """
        Stop all registered adapters and disconnect the publisher.
        """
        logger.info("Stopping CoreListener...")
        for adapter in self.adapters:
            await adapter.stop()
        
        # Cancel any tasks that didn't stop gracefully
        for task in self._tasks:
            if not task.done():
                task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)
        await publisher.disconnect()
        logger.info("CoreListener stopped.")

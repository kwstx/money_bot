import asyncio
import logging
import uuid
import time
from datetime import datetime, timezone
import json

from src.config import settings
from src.schemas import CanonicalNotificationEvent
from src.bus.producer import producer
from src.workflows.router import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def simulate_end_to_end():
    logger.info("Initializing Postgres Store...")
    from src.storage.implementations import postgres_store
    await postgres_store.init_db()

    logger.info("Starting DurableProducer...")
    await producer.connect()

    # 1. Create a dummy canonical event (simulating ingestion)
    token_address = "0x" + "a" * 40
    wallet_address = "0x" + "b" * 40

    event = CanonicalNotificationEvent(
        source_app_id="dexscreener",
        event_category="new_pool",
        referenced_token_address=token_address,
        referenced_wallet_address=wallet_address,
        blockchain_id="ethereum",
        raw_payload={"type": "pool_created", "price": 0.0001},
        confidence_level=0.9
    )

    # 2. Append event to Event Store
    logger.info("Appending event to immutable Event Store...")
    await postgres_store.append(event)

    # 3. Publish to message bus
    logger.info("Publishing event to Message Bus...")
    await producer.publish_canonical_event(event)

    # 4. Simulate the Consumer receiving the event and passing it to the Router
    logger.info("Simulating Router dispatching the event to all Workflows...")
    await router.route_event(event.model_dump(mode="json"))

    # 5. Verify the state in the Operational Database
    logger.info("Verifying Operational Store state...")
    token_entity = await postgres_store.get_entity(token_address)
    wallet_entity = await postgres_store.get_entity(wallet_address)

    logger.info(f"Token Entity Found: {token_entity is not None}")
    if token_entity:
        logger.info(f"Token Data: {json.dumps(token_entity.model_dump(mode='json'), indent=2)}")

    logger.info(f"Wallet Entity Found: {wallet_entity is not None}")
    if wallet_entity:
         logger.info(f"Wallet Data: {json.dumps(wallet_entity.model_dump(mode='json'), indent=2)}")

    await producer.disconnect()
    logger.info("End-to-End Simulation Complete.")

if __name__ == "__main__":
    asyncio.run(simulate_end_to_end())

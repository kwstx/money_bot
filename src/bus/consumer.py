import json
import logging
import asyncio
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from typing import Callable, Awaitable
from ..config import settings

logger = logging.getLogger(__name__)

class DurableConsumer:
    """
    A base asynchronous consumer that connects to Kafka,
    reads messages, checkpoints offsets (at-least-once),
    and routes failed messages to a dead-letter topic.
    """
    def __init__(self, topic: str, group_id: str, handler: Callable[[dict], Awaitable[None]]):
        self.topic = topic
        self.group_id = group_id
        self.handler = handler
        self.consumer: AIOKafkaConsumer | None = None
        self.producer: AIOKafkaProducer | None = None  # for DLQ
        self.dlq_topic = f"{self.topic}.dlq"
        self._running = False

    async def start(self):
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=self.group_id,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            enable_auto_commit=False,  # We manually commit after successful processing
            auto_offset_reset="earliest"
        )
        
        # Producer for Dead Letter Queue
        self.producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

        await self.consumer.start()
        await self.producer.start()
        self._running = True
        logger.info(f"Started DurableConsumer for topic {self.topic} (group: {self.group_id})")

        # Start consuming loop in background
        asyncio.create_task(self._consume_loop())

    async def _consume_loop(self):
        try:
            async for msg in self.consumer:
                if not self._running:
                    break
                
                payload = msg.value
                max_retries = 3
                retry_count = 0
                delay = 1.0
                
                while retry_count <= max_retries:
                    try:
                        # Process the message
                        await self.handler(payload)
                        # Commit offset ONLY if handler succeeds
                        await self.consumer.commit()
                        break # Success
                    except Exception as e:
                        retry_count += 1
                        if retry_count > max_retries:
                            logger.error(f"Error processing message from {self.topic} after {max_retries} retries: {e}. Routing to DLQ.")
                            # Route to DLQ
                            await self.route_to_dlq(payload, str(e))
                            # Still commit so we don't get stuck in a poison pill loop
                            await self.consumer.commit()
                            break
                        else:
                            logger.warning(f"Error processing message. Retrying {retry_count}/{max_retries} in {delay}s: {e}")
                            await asyncio.sleep(delay)
                            delay *= 2 # Exponential backoff

        except Exception as e:
            logger.error(f"Consumer loop error: {e}")
        finally:
            self._running = False

    async def route_to_dlq(self, payload: dict, error_reason: str):
        """Send failed message to Dead Letter Queue for later replay."""
        dlq_payload = {
            "original_payload": payload,
            "error_reason": error_reason
        }
        await self.producer.send(self.dlq_topic, dlq_payload)

    async def stop(self):
        self._running = False
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        logger.info(f"Stopped DurableConsumer for topic {self.topic}")

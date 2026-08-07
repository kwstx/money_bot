import asyncio
import logging
import signal
import sys

from src.config import settings
from src.core import CoreListener
from src.adapters.webhook import WebhookAdapter

import logging.handlers
import queue

# Setup basic logging to a queue for non-blocking asynchronous logging
log_queue = queue.Queue(-1)
queue_handler = logging.handlers.QueueHandler(log_queue)

# Standard stream handler that does the actual formatting and writing
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

queue_listener = logging.handlers.QueueListener(log_queue, stream_handler)
queue_listener.start()

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(queue_handler)

logger = logging.getLogger(__name__)

async def main():
    listener = CoreListener()
    
    # Initialize the webhook adapter with the listener's callback
    webhook_adapter = WebhookAdapter(
        publish_callback=listener.handle_notification,
        host=settings.api_host,
        port=settings.api_port
    )
    
    # Register adapters
    listener.register_adapter(webhook_adapter)
    
    # Setup graceful shutdown handlers
    def handle_sigterm():
        logger.info("Received termination signal")
        asyncio.create_task(listener.stop())

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_sigterm)
        except NotImplementedError:
            # Signal handlers might not be fully supported on Windows Event Loops
            pass

    try:
        await listener.start()
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt")
    finally:
        await listener.stop()
        queue_listener.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program exiting")

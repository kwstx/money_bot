import asyncio
import logging
import uvicorn
from datetime import datetime, timezone
from fastapi import FastAPI, APIRouter, HTTPException
from typing import Callable, Awaitable, Any

from .base import IngestionAdapter
from ..schemas import RawNotification
from ..config import settings

logger = logging.getLogger(__name__)

class WebhookAdapter(IngestionAdapter):
    """
    Ingestion adapter that listens for webhooks via a FastAPI server.
    """

    def __init__(self, publish_callback: Callable[[dict], Awaitable[Any]], host: str = settings.api_host, port: int = settings.api_port):
        super().__init__(publish_callback)
        self.host = host
        self.port = port
        self.server = None
        self.app = self._create_app()

    def _create_app(self) -> FastAPI:
        app = FastAPI(title="Webhook Adapter", version="1.0.0")
        router = APIRouter()

        @router.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        @router.post("/webhooks/fomo", status_code=202)
        async def ingest_webhook(notification: RawNotification):
            try:
                # Use the provided callback to publish the event
                await self.publish_callback(notification.model_dump(mode="json"))
                return {"status": "accepted"}
            except Exception as e:
                logger.error(f"Failed to ingest notification via webhook: {e}")
                raise HTTPException(status_code=500, detail="Failed to ingest notification")

        app.include_router(router)
        return app

    async def start(self) -> None:
        logger.info(f"Starting WebhookAdapter on {self.host}:{self.port}")
        
        config = uvicorn.Config(
            app=self.app, 
            host=self.host, 
            port=self.port,
            log_level="info",
            # Disable uvloop/httptools overriding if needed, but defaults are usually fine
        )
        self.server = uvicorn.Server(config)
        
        # Start the uvicorn server in the current asyncio loop
        await self.server.serve()

    async def stop(self) -> None:
        if self.server:
            logger.info("Stopping WebhookAdapter...")
            # uvicorn.Server has a should_exit flag to gracefully shut down
            self.server.should_exit = True

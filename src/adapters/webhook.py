import asyncio
import logging
import uvicorn
from datetime import datetime, timezone
from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends
from prometheus_client import make_asgi_app
from typing import Callable, Awaitable, Any

from .base import IngestionAdapter
from ..schemas import RawNotification
from ..config import settings
from ..telemetry import TelemetryTracker
from ..monitor import monitor

logger = logging.getLogger(__name__)

async def limit_payload_size(request: Request):
    """Enforce maximum body size to protect against DoS attacks."""
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.max_payload_size_bytes:
                raise HTTPException(status_code=413, detail="Payload Too Large")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length Header")
    
    # Read stream up to limit to catch spoofed or missing Content-Length headers
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > settings.max_payload_size_bytes:
            raise HTTPException(status_code=413, detail="Payload Too Large")
            
    # Reset request receive function so the body can be read again downstream
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
    request._receive = receive

async def verify_api_key(request: Request):
    """Enforce API Key token authentication if configured."""
    if settings.auth_token:
        token = request.headers.get(settings.auth_header_name)
        if not token or token != settings.auth_token:
            raise HTTPException(status_code=401, detail="Unauthorized")

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
        
        # Mount Prometheus metrics endpoint
        metrics_app = make_asgi_app()
        app.mount("/metrics", metrics_app)

        router = APIRouter()

        @router.get("/health")
        async def health_check():
            status_data = monitor.get_status()
            
            # Use appropriate HTTP status codes based on health
            if status_data.get("status") == "healthy":
                return status_data
            else:
                # If degraded, we return 503 so load balancers know to potentially route elsewhere or alert
                # Or just return 200 with degraded status if we prefer not to take the service out of rotation
                # Since we want to expose degraded status, 200 is acceptable or a custom code. We'll stick to 200.
                return status_data

        @router.post("/webhooks/fomo", status_code=202, dependencies=[Depends(limit_payload_size), Depends(verify_api_key)])
        async def ingest_webhook(notification: RawNotification):
            tracker = TelemetryTracker()
            tracker.record_receipt()
            try:
                # Attach telemetry metadata
                notification.telemetry = tracker.to_dict()
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

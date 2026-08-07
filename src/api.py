import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any
import time

from .publisher import publisher
from .schemas import RawNotification

router = APIRouter()

class HealthCheck(BaseModel):
    status: str
    timestamp: str

@router.get("/health", response_model=HealthCheck)
async def health_check():
    """
    Small internal API endpoint to verify service health.
    """
    return HealthCheck(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat()
    )

@router.post("/webhooks/fomo", status_code=202)
async def ingest_webhook(notification: RawNotification):
    """
    The primary ingestion endpoint for the FOMO application.
    Immediately publishes the raw notification to a durable queue 
    (Redis Streams) before any additional processing occurs.
    This prevents data loss and enables horizontal scaling of consumers.
    """
    try:
        # Directly publish the raw payload to the message broker
        await publisher.publish(notification.model_dump(mode="json"))
        return {"status": "accepted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to ingest notification")

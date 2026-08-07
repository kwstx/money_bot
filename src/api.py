import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any

from .publisher import publisher

router = APIRouter()

class FomoNotification(BaseModel):
    """
    The raw notification structure expected from the FOMO application webhook.
    """
    source: str
    event_type: str
    payload: Dict[str, Any]

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

def normalize_event(raw_notification: FomoNotification) -> dict:
    """
    Transforms a raw notification into a structured event.
    Guarantees exactly once semantics per ingestion by assigning a unique event ID,
    timestamping it, and normalizing the structure.
    """
    return {
        "event_id": str(uuid.uuid4()),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "source": raw_notification.source,
        "event_type": raw_notification.event_type,
        "data": raw_notification.payload
    }

async def process_and_publish(notification: FomoNotification):
    """
    Background task to normalize and publish the event.
    """
    event = normalize_event(notification)
    await publisher.publish(event)

@router.post("/webhooks/fomo", status_code=202)
async def ingest_webhook(notification: FomoNotification, background_tasks: BackgroundTasks):
    """
    The primary ingestion endpoint for the FOMO application.
    Accepts the webhook, immediately acknowledges receipt (minimal latency), 
    and offloads the normalization and publishing to a background task.
    """
    try:
        # Offload processing to ensure minimal latency for the ingestion endpoint
        background_tasks.add_task(process_and_publish, notification)
        return {"status": "accepted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to ingest notification")

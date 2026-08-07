from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid

class RawNotification(BaseModel):
    """Raw incoming notification payload."""
    source: str
    event_type: str
    payload: Dict[str, Any]
    telemetry: Dict[str, Any] = Field(default_factory=dict, description="Telemetry tracking timestamps")

class CanonicalNotificationEvent(BaseModel):
    """
    Canonical notification event schema.
    Every notification should be represented using this structure regardless of origin.
    """
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Globally unique event identifier")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Event timestamp")
    
    source_app_id: str = Field(..., description="Source application identifier")
    notification_id: Optional[str] = Field(default=None, description="Notification identifier if available")
    
    title: Optional[str] = Field(default=None, description="Notification title")
    body: Optional[str] = Field(default=None, description="Notification body")
    event_category: str = Field(default="generic", description="High-level classification category (e.g., wallet, token, swap)")
    
    sender_metadata: Dict[str, Any] = Field(default_factory=dict, description="Sender metadata")
    referenced_wallet_address: Optional[str] = Field(default=None, description="Referenced wallet address")
    referenced_token_address: Optional[str] = Field(default=None, description="Referenced token address")
    blockchain_id: Optional[str] = Field(default=None, description="Blockchain identifier")
    
    confidence_level: Optional[float] = Field(default=None, description="Confidence level of the parsed data")
    processing_status: str = Field(default="ingested", description="Processing status")
    
    raw_payload: Dict[str, Any] = Field(..., description="Keeping the raw payload ensures future parsers can reprocess historical events")
    parsing_version: str = Field(default="1.0.0", description="Parsing version")
    ingestion_latency_ms: Optional[float] = Field(default=None, description="Ingestion latency in milliseconds")
    telemetry: Dict[str, Any] = Field(default_factory=dict, description="Telemetry tracking timestamps")

import re
import html
from pydantic import BaseModel, Field, model_validator
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid

def sanitize_text(text: str) -> str:
    """Strips HTML tags and escapes special characters to prevent injection."""
    if not isinstance(text, str):
        return text
    # Strip HTML tags
    cleaned = re.sub(r"<[a-zA-Z/][^>]*>", "", text)
    # Normalize/escape HTML special characters
    cleaned = html.escape(html.unescape(cleaned))
    return cleaned

def sanitize_value(val: Any) -> Any:
    """Recursively sanitizes string values in dicts, lists, and strings."""
    if isinstance(val, str):
        return sanitize_text(val)
    elif isinstance(val, dict):
        return {k: sanitize_value(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [sanitize_value(item) for item in val]
    return val

class RawNotification(BaseModel):
    """Raw incoming notification payload."""
    source: str = Field(..., min_length=1, max_length=256)
    event_type: str = Field(..., min_length=1, max_length=256)
    payload: Dict[str, Any]
    telemetry: Dict[str, Any] = Field(default_factory=dict, description="Telemetry tracking timestamps")

    @model_validator(mode="after")
    def sanitize_fields(self) -> "RawNotification":
        self.source = sanitize_text(self.source)
        self.event_type = sanitize_text(self.event_type)
        self.payload = sanitize_value(self.payload)
        return self


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


class ExtractedEntity(BaseModel):
    """Represents a discrete entity extracted from a notification."""
    entity_type: str = Field(..., description="Type of entity (e.g., wallet, token, contract, url, amount)")
    value: str = Field(..., description="The extracted string value")
    context: str = Field(default="", description="Surrounding text or context where it was found")
    confidence: float = Field(default=1.0, description="Confidence score of this extraction (0.0 to 1.0)")
    is_valid: bool = Field(default=True, description="Whether the entity passed structural/existence validation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional enriched data (e.g., blockchain_id, chain_name, token_symbol)")


class EntityRelationship(BaseModel):
    """Represents a directed relationship between two entities."""
    subject: str = Field(..., description="The subject of the action (e.g., a wallet address)")
    subject_type: str = Field(..., description="The type of the subject (e.g., 'wallet')")
    action: str = Field(..., description="The action performed (e.g., 'buy', 'sell', 'transfer')")
    object_target: str = Field(..., description="The object of the action (e.g., a token address)")
    object_type: str = Field(..., description="The type of the object (e.g., 'token')")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context about the relationship")


class ParsedIntelligenceEvent(BaseModel):
    """The serialized output of the Notification Parser pipeline."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Globally unique parsed event identifier")
    original_event_id: str = Field(..., description="The ID of the canonical event this was parsed from")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of parsing completion")
    
    normalized_text: str = Field(..., description="The cleaned, normalized version of the notification body")
    entities: list[ExtractedEntity] = Field(default_factory=list, description="All entities extracted during the pipeline")
    relationships: list[EntityRelationship] = Field(default_factory=list, description="Explicit relationships between entities")
    
    primary_category: str = Field(default="unknown", description="The overall determined category of the notification")
    overall_confidence: float = Field(default=0.0, description="Overall confidence score for the parsing result (0.0 to 1.0)")
    
    parser_version: str = Field(default="1.0.0", description="The version of the parser logic used")
    enrichment_data: Dict[str, Any] = Field(default_factory=dict, description="Additional context fetched or inferred during enrichment")
    telemetry: Dict[str, Any] = Field(default_factory=dict, description="Telemetry tracking timestamps")

class CanonicalIdentity(BaseModel):
    """Base class for all canonical entities in the platform."""
    canonical_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Globally unique canonical identifier")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = Field(default="1.0.0")

class TokenIdentity(CanonicalIdentity):
    """Canonical representation of a Token."""
    address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain network (e.g., ethereum, solana)")
    symbol: Optional[str] = Field(default=None)
    name: Optional[str] = Field(default=None)
    decimals: Optional[int] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class WalletIdentity(CanonicalIdentity):
    """Canonical representation of a Wallet."""
    address: str = Field(..., description="Wallet address")
    chain: str = Field(..., description="Blockchain network")
    wallet_type: str = Field(default="eoa", description="e.g., eoa, smart_contract, exchange")
    risk_score: Optional[float] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TransactionIdentity(CanonicalIdentity):
    """Canonical representation of a Transaction."""
    tx_hash: str = Field(..., description="Transaction hash")
    chain: str = Field(..., description="Blockchain network")
    block_number: Optional[int] = Field(default=None)
    timestamp: Optional[datetime] = Field(default=None)
    from_address: Optional[str] = Field(default=None)
    to_address: Optional[str] = Field(default=None)
    value: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class NarrativeIdentity(CanonicalIdentity):
    """Canonical representation of a Market Narrative."""
    name: str = Field(..., description="Narrative name (e.g., ai_tokens, memecoins)")
    description: Optional[str] = Field(default=None)
    sentiment_score: Optional[float] = Field(default=None)
    related_tokens: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

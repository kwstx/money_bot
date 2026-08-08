import uuid
from datetime import datetime, timezone
from typing import Optional

from src.schemas import CanonicalNotificationEvent, ParsedIntelligenceEvent, ExtractedEntity
from src.parser import stages

class NotificationParser:
    """
    The Notification Parser is the second stage of the ingestion pipeline.
    It executes a canonical, deterministic 7-stage pipeline to convert 
    CanonicalNotificationEvents into ParsedIntelligenceEvents.
    """
    
    def __init__(self):
        # We could inject dependencies here if needed (e.g. database connections for enrichment)
        pass
        
    def parse(self, event: CanonicalNotificationEvent) -> ParsedIntelligenceEvent:
        """Executes the canonical parsing pipeline."""
        
        # Combine title and body for parsing
        raw_text = f"{event.title or ''} {event.body or ''}".strip()
        if not raw_text and event.raw_payload:
            # Fallback to stringified payload if there's no title/body
            raw_text = str(event.raw_payload)
            
        # Stage 1: Normalization
        normalized_text = stages.normalize(raw_text)
        
        # Stage 2: Preprocessing
        preprocessed_text = stages.preprocess(normalized_text)
        
        # Stage 3: Entity Extraction
        raw_entities = stages.extract_entities(preprocessed_text)
        
        # Stage 4: Validation
        valid_entities = stages.validate_entities(raw_entities)
        
        # Stage 5: Enrichment
        enriched_entities = stages.enrich_entities(valid_entities)
        
        # Stage 6: Confidence Scoring
        confidence = stages.score_confidence(enriched_entities, preprocessed_text)
        
        # Stage 7: Serialization
        return self._serialize(event, preprocessed_text, enriched_entities, confidence)
        
    def _serialize(self, 
                   original_event: CanonicalNotificationEvent, 
                   normalized_text: str, 
                   entities_data: list[dict], 
                   confidence: float) -> ParsedIntelligenceEvent:
        """Stage 7: Serializes the parsed data into a ParsedIntelligenceEvent."""
        
        # Convert dicts back to ExtractedEntity models
        pydantic_entities = [
            ExtractedEntity(
                entity_type=ent["entity_type"],
                value=ent["value"],
                context=ent.get("context", ""),
                confidence=ent.get("confidence", 1.0),
                metadata=ent.get("metadata", {})
            ) for ent in entities_data
        ]
        
        # Determine primary category based on extracted entities or fallback to original
        primary_category = original_event.event_category
        entity_types = {e["entity_type"] for e in entities_data}
        if "wallet" in entity_types and "amount" in entity_types:
            primary_category = "transaction"
        elif "token" in entity_types:
            primary_category = "token_alert"
            
        return ParsedIntelligenceEvent(
            event_id=str(uuid.uuid4()),
            original_event_id=original_event.event_id,
            timestamp=datetime.now(timezone.utc),
            normalized_text=normalized_text,
            entities=pydantic_entities,
            primary_category=primary_category,
            overall_confidence=confidence,
            enrichment_data={},
            telemetry=original_event.telemetry  # carry over telemetry
        )

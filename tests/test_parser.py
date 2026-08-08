import pytest
from src.schemas import CanonicalNotificationEvent
from src.parser.stages import (
    normalize, preprocess, extract_entities, validate_entities,
    enrich_entities, score_confidence
)
from src.parser.pipeline import NotificationParser

def test_normalize_stage():
    """Test stage 1: Normalization."""
    raw = "Hello   \u200bWorld!  "
    assert normalize(raw) == "Hello World!"
    assert normalize("") == ""

def test_preprocess_stage():
    """Test stage 2: Preprocessing."""
    # Currently just returns the text
    assert preprocess("Hello World") == "Hello World"

def test_extract_entities_stage():
    """Test stage 3: Entity Extraction."""
    text = "Check out $PEPE on https://etherscan.io ! Send 1.5 ETH to 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
    entities = extract_entities(text)
    
    assert len(entities) == 4
    types = [e["entity_type"] for e in entities]
    assert "token" in types
    assert "url" in types
    assert "amount" in types
    assert "wallet" in types
    
    # Check specific extractions
    for e in entities:
        if e["entity_type"] == "wallet":
            assert e["value"] == "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
        elif e["entity_type"] == "amount":
            assert e["value"] == "1.5"
            assert e["metadata"]["currency"] == "ETH"
        elif e["entity_type"] == "token":
            assert e["value"] == "PEPE"

def test_validate_and_enrich_stages():
    """Test stages 4 & 5: Validation and Enrichment."""
    text = "See https://etherscan.io/address/0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
    entities = extract_entities(text)
    
    valid = validate_entities(entities)
    assert len(valid) == len(entities)
    
    enriched = enrich_entities(valid)
    # Check if URL was enriched
    url_ent = next(e for e in enriched if e["entity_type"] == "url")
    assert url_ent["metadata"].get("is_explorer") is True

def test_score_confidence_stage():
    """Test stage 6: Confidence Scoring."""
    assert score_confidence([], "Just some text") == 0.1
    # with one entity
    assert score_confidence([{"entity_type": "url"}], "Check https://google.com") > 0.4

def test_pipeline_integration():
    """Test the full NotificationParser pipeline."""
    parser = NotificationParser()
    
    event = CanonicalNotificationEvent(
        source_app_id="test_app",
        title="Whale Alert",
        body="Whale transferred 500 SOL to 9v9CwkB4pE6tNZb9TjT78qF1U32S9vXm6vK5rS98QxW1",
        event_category="generic",
        raw_payload={"raw": "test"}
    )
    
    parsed = parser.parse(event)
    
    assert parsed.original_event_id == event.event_id
    assert "Whale transferred 500 SOL" in parsed.normalized_text
    
    assert len(parsed.entities) == 2
    
    entity_types = {e.entity_type for e in parsed.entities}
    assert "amount" in entity_types
    assert "wallet" in entity_types
    
    assert parsed.primary_category == "transaction"
    assert parsed.overall_confidence > 0.5

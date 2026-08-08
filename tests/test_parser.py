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
    
    assert len(entities) == 5
    types = [e["entity_type"] for e in entities]
    assert "token" in types
    assert "url" in types
    assert "amount" in types
    assert "wallet" in types
    assert "blockchain" in types
    
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
    
    enriched, relationships = enrich_entities(valid)
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
    
    assert len(parsed.entities) == 4
    
    entity_types = {e.entity_type for e in parsed.entities}
    assert "amount" in entity_types
    assert "wallet" in entity_types
    assert "action" in entity_types
    assert "blockchain" in entity_types
    
    assert parsed.primary_category == "transaction"
    assert parsed.overall_confidence > 0.5
    assert parsed.parser_version == "1.0.0"

def test_parser_version_and_entity_confidence():
    """Test that extracted entities receive correct certainty-based confidence scores and parser version is recorded."""
    parser = NotificationParser()
    
    # 1. Test Semantic Extractor confidence variations
    text = "whale bought contract verified rug"
    event = CanonicalNotificationEvent(
        source_app_id="test_app",
        body=text,
        raw_payload={"raw": text}
    )
    parsed = parser.parse(event)
    
    # Verify parser version
    assert parsed.parser_version == "1.0.0"
    
    # Find semantic events and verify confidence mapping
    semantic_ents = {e.value: e.confidence for e in parsed.entities if e.entity_type == "semantic_event"}
    assert semantic_ents["SWAP_BUY"] == 0.65          # Moderately descriptive
    assert semantic_ents["CONTRACT_VERIFIED"] == 0.75 # Highly specific/unambiguous
    assert semantic_ents["LIQUIDITY_REMOVE"] == 0.50  # Slang/highly ambiguous
    
    # 2. Test Validation and Confidence adjustment
    # Valid Solana wallet (passes base58 length validation) -> confidence boosted to 0.95
    # Invalid Solana wallet -> confidence dropped to 0.1
    # Invalid EVM address (bad checksum mixed casing) -> confidence dropped to 0.1
    sol_valid = "9v9CwkB4pE6tNZb9TjT78qF1U32S9vXm6vK5rS98QxW1"
    sol_invalid = "0000000000000000000000000000000"  # Invalid characters/length
    evm_invalid = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA9604a" # Last char lowercase instead of uppercase checksum
    
    text_validation = f"Valid Solana: {sol_valid}, Invalid Solana: {sol_invalid}, Invalid EVM: {evm_invalid}"
    event_val = CanonicalNotificationEvent(
        source_app_id="test_app",
        body=text_validation,
        raw_payload={"raw": text_validation}
    )
    parsed_val = parser.parse(event_val)
    
    # Verify wallets confidence
    wallets = {e.value: e for e in parsed_val.entities if e.entity_type == "wallet"}
    
    assert wallets[sol_valid].is_valid is True
    assert wallets[sol_valid].confidence == 0.95
    
    assert wallets[sol_invalid].is_valid is False
    assert wallets[sol_invalid].confidence == 0.1
    
    assert wallets[evm_invalid].is_valid is False
    assert wallets[evm_invalid].confidence == 0.1


import pytest
from datetime import datetime, timezone
from src.intelligence.research.schemas import AggregatedIntelligence
from src.intelligence.research.engine import AIResearchEngine

@pytest.fixture
def engine():
    return AIResearchEngine()

@pytest.fixture
def sample_intelligence():
    return AggregatedIntelligence(
        token_address="0xMockTokenAddress123",
        chain="ethereum",
        security_metrics={"is_verified": True, "mint_enabled": False},
        liquidity_metrics={"pool_size_usd": 500000, "locked_percentage": 100},
        ownership_metrics={"top_10_percent": 15},
        smart_money_metrics={"net_inflow_24h": 50000},
        social_traction={"twitter_sentiment": "positive", "mentions_24h": 1200}
    )

def test_generate_thesis(engine, sample_intelligence):
    thesis = engine.generate_thesis(sample_intelligence)
    
    assert thesis.token_address == "0xMockTokenAddress123"
    assert thesis.overall_conviction == 0.85
    assert thesis.recommended_action == "STRONG BUY"
    
    # Check that observed facts parsed correctly from mock
    assert "Liquidity is $500k" in thesis.observed_facts.liquidity_state
    
    # Check that validation criteria parsed
    assert "Dev wallet movement" in thesis.validation.invalidating_signals

def test_detect_thesis_change(engine, sample_intelligence):
    # First, generate a thesis so there's a baseline
    engine.generate_thesis(sample_intelligence)
    
    # Simulate an update (e.g., later in the day)
    updated_intelligence = sample_intelligence.model_copy(update={
        "liquidity_metrics": {"pool_size_usd": 1000, "locked_percentage": 0} # Massive drain
    })
    
    change_result = engine.detect_thesis_change(updated_intelligence)
    
    assert change_result is not None
    assert change_result.is_material_change is True
    assert change_result.requires_new_thesis is True
    assert "liquidity" in change_result.affected_areas

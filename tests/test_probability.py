import pytest
from datetime import datetime, timezone, timedelta
from src.intelligence.probability import (
    ProbabilityEngine, 
    Evidence, 
    ExpectedValueConfig
)

def test_initial_estimate():
    engine = ProbabilityEngine()
    estimate = engine.generate_initial_estimate()
    
    assert estimate.rug_probability == 0.8
    assert estimate.growth_probability == 0.15
    assert estimate.winner_probability == 0.05
    assert estimate.confidence_level == 0.1

def test_bayesian_update_positive_evidence():
    engine = ProbabilityEngine()
    estimate = engine.generate_initial_estimate()
    
    evidence = Evidence(
        category="smart_money",
        signal_strength=0.8,
        description="Smart money accumulating"
    )
    
    updated = engine.apply_evidence(estimate, evidence)
    
    # Positive signal should reduce rug probability and increase growth/winner
    assert updated.rug_probability < 0.8
    assert updated.growth_probability > 0.15
    assert updated.winner_probability > 0.05
    assert updated.confidence_level > 0.1
    
    assert len(updated.recent_updates) == 3
    assert any(u.direction == "negative" and u.previous_probability == 0.8 for u in updated.recent_updates)

def test_historical_boundary():
    engine = ProbabilityEngine()
    estimate = engine.generate_initial_estimate()
    
    # Evidence from the future should be ignored
    future_time = datetime.now(timezone.utc) + timedelta(days=1)
    evidence = Evidence(
        category="liquidity_increase",
        signal_strength=1.0,
        description="Liquidity increased",
        timestamp=future_time
    )
    
    updated = engine.apply_evidence(estimate, evidence)
    
    # Should not have changed
    assert updated.rug_probability == 0.8
    assert len(updated.recent_updates) == 0

def test_expected_value_calculation():
    engine = ProbabilityEngine()
    
    config = ExpectedValueConfig(
        target_multiple=2.0,
        probability_of_target=0.3,
        downside_probability=0.5,
        downside_loss_pct=1.0,
        liquidity_available=10000.0,
        execution_cost_pct=0.02, # 2% slip/fees
        time_horizon_days=7,
        position_size=100.0
    )
    
    result = engine.calculate_expected_value(config)
    
    # Gross up: 200. Cost: (200 * 0.02) + (100 * 0.02) = 4 + 2 = 6. 
    # Net up: 200 - 6 - 0(liquidity penalty) - 100 = 94
    # Gross down: 100. 
    # EV: (0.3 * 94) - (0.5 * 100) = 28.2 - 50 = -21.8
    
    assert result.is_rare_tail is False
    assert result.implied_guarantee_warning is None
    assert result.expected_value_usd == pytest.approx(-21.8)

def test_rare_tail_expected_value():
    engine = ProbabilityEngine()
    
    config = ExpectedValueConfig(
        target_multiple=100.0, # Rare tail
        probability_of_target=0.05,
        downside_probability=0.9,
        downside_loss_pct=1.0,
        liquidity_available=50000.0,
        execution_cost_pct=0.01,
        time_horizon_days=10,
        position_size=100.0
    )
    
    result = engine.calculate_expected_value(config)
    
    assert result.is_rare_tail is True
    # Probability is discounted heavily for rare tail
    assert result.expected_value_usd < 0 
    assert result.implied_guarantee_warning is None

def test_scenario_analysis():
    engine = ProbabilityEngine()
    estimate = engine.generate_initial_estimate()
    
    result = engine.run_scenario_analysis("0x123", estimate)
    
    assert result.token_address == "0x123"
    assert "rug" in result.scenario_outcomes
    assert "bull" in result.scenario_outcomes
    assert len(result.identified_off_chain_risks) > 0
    assert result.risk_score > 0

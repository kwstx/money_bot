import pytest

from src.ultra_early.engine import UltraEarlyIntelligenceEngine
from src.discovery.schemas import UnifiedChainEvent, EventType
from src.launch.detector import new_launch_detector

@pytest.mark.asyncio
async def test_ultra_early_intelligence_engine():
    engine = UltraEarlyIntelligenceEngine(
        min_discovery_confidence=0.5,
        min_investment_confidence=0.4,
        require_security_pass=True
    )

    token = "0x9999999999999999999999999999999999999999"
    chain = "ethereum"

    event = UnifiedChainEvent(
        event_type=EventType.NEW_TOKEN,
        chain=chain,
        tx_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        token_address=token,
        payload={"is_verified": True, "factory_address": "0xFactory"}
    )

    # Register liquidity in launch detector so rapid liquidity check passes
    new_launch_detector.register_launch(token, chain)
    await new_launch_detector.update_liquidity(token, chain, liquidity_usd=5000.0)

    # 1. Surface ultra-early discovery alert
    assessment = engine.assess_discovery(event)
    assert assessment.discovery_confidence >= 0.8
    assert assessment.investment_confidence == 0.0
    assert assessment.trade_eligible is False
    assert engine.can_generate_trade_proposal(token, chain) is False

    # 2. Run rapid security pass (security pass = True, sufficient pool)
    ass_passed = await engine.run_rapid_security_and_liquidity_checks(
        token_address=token,
        chain=chain,
        security_override_pass=True,
        min_pool_usd=500.0
    )

    assert ass_passed.rapid_security_passed is True
    assert ass_passed.investment_confidence >= 0.4
    assert ass_passed.trade_eligible is True
    assert engine.can_generate_trade_proposal(token, chain) is True

    # 3. Test security failure rejection safety gate
    token_bad = "0x8888888888888888888888888888888888888888"
    event_bad = UnifiedChainEvent(
        event_type=EventType.NEW_TOKEN,
        chain=chain,
        tx_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        token_address=token_bad
    )
    engine.assess_discovery(event_bad)

    ass_failed = await engine.run_rapid_security_and_liquidity_checks(
        token_address=token_bad,
        chain=chain,
        security_override_pass=False, # Honeypot detected!
        min_pool_usd=500.0
    )

    assert ass_failed.rapid_security_passed is False
    assert ass_failed.trade_eligible is False
    assert "Failed rapid security check (potential honeypot/rug)" in ass_failed.rejection_reasons
    assert engine.can_generate_trade_proposal(token_bad, chain) is False

import pytest
from datetime import datetime, timezone, timedelta

from src.launch.detector import NewLaunchDetector
from src.launch.opportunity_engine import OpportunityEngine
from src.discovery.schemas import MilestoneType

@pytest.mark.asyncio
async def test_launch_detector_milestones_and_opportunity_scoring():
    detector = NewLaunchDetector(liquidity_increase_threshold=1.5, whale_buy_usd_threshold=5000.0)
    engine = OpportunityEngine(min_liquidity_usd=1000.0, max_bot_ratio=0.8, max_risk_score=0.6)

    token = "0x1111111111111111111111111111111111111111"
    chain = "ethereum"
    start_time = datetime.now(timezone.utc) - timedelta(minutes=10)

    # 1. Register launch & liquidity
    detector.register_launch(token, chain, deployment_time=start_time)
    await detector.update_liquidity(token, chain, liquidity_usd=10000.0, timestamp=start_time + timedelta(seconds=30))

    # 2. Record first buy
    m1 = await detector.record_swap(
        token_address=token,
        chain=chain,
        buyer_address="0xbuyer1111111111111111111111111111111111",
        is_buy=True,
        amount_usd=500.0,
        timestamp=start_time + timedelta(minutes=1)
    )
    assert len(m1) >= 1
    assert m1[0].milestone == MilestoneType.FIRST_BUY

    # 3. Record whale buy
    m2 = await detector.record_swap(
        token_address=token,
        chain=chain,
        buyer_address="0xwhale11111111111111111111111111111111111",
        is_buy=True,
        amount_usd=10000.0,
        timestamp=start_time + timedelta(minutes=2)
    )
    milestone_types = [m.milestone for m in m2]
    assert MilestoneType.WHALE_ENTRY in milestone_types

    # 4. Record 98 more unique buyers to reach 100 unique buyers
    all_triggered_milestones = []
    for i in range(3, 101):
        m_list = await detector.record_swap(
            token_address=token,
            chain=chain,
            buyer_address=f"0xbuyer_{i:04d}_1111111111111111111111111111",
            is_buy=True,
            amount_usd=100.0,
            timestamp=start_time + timedelta(minutes=3)
        )
        all_triggered_milestones.extend([m.milestone for m in m_list])

    assert MilestoneType.FIRST_100_WALLETS in all_triggered_milestones

    # 5. Evaluate opportunity engine
    eval_result = engine.evaluate_opportunity(token, chain, detector=detector)
    assert eval_result["is_prioritized"] is True
    assert eval_result["priority_score"] >= 25.0
    assert len(eval_result["rejection_reasons"]) == 0

    top = engine.get_top_opportunities(limit=5)
    assert len(top) == 1
    assert top[0]["token_address"] == token

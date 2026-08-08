import pytest
from datetime import datetime, timezone, timedelta

from src.schemas import CanonicalNotificationEvent
from src.intelligence.schemas import DecodedTransaction, AssetTransfer
from src.intelligence.wallet.schemas import WalletProfile, Position, FundingSource
from src.intelligence.wallet.probabilistic_graph import ProbabilisticWalletGraphEngine
from src.intelligence.wallet.smart_money import SmartMoneyPredictiveEngine
from src.intelligence.wallet.whale import WhaleMarketImpactEngine
from src.intelligence.wallet.manipulation import InsiderAndManipulationEngine
from src.intelligence.wallet.intelligence_section_six import SectionSixIntelligenceEngine
from src.workflows.wallet import WalletWorkflow
from src.storage.implementations import postgres_store

# -----------------------------------------------------------------------------
# 1. Smart Money Predictive Skill & Cohort Benchmark Tests
# -----------------------------------------------------------------------------

def test_smart_money_predictive_skill_evaluation():
    engine = SmartMoneyPredictiveEngine(min_trades_required=2)
    profile = WalletProfile(address="0xSmartTrader", chain="ethereum")
    now = datetime.now(timezone.utc)

    # 1. Blank profile evaluation
    blank_eval = engine.evaluate_predictive_skill(profile)
    assert not blank_eval.is_smart_money
    assert blank_eval.predictive_score == 0.0
    assert not blank_eval.skill_vs_luck.is_statistically_significant

    # 2. Add highly consistent profitable positions entered early
    profile.positions["0xtoken1"] = Position(
        token_address="0xtoken1",
        total_bought_tokens=1000.0,
        total_bought_usd=1000.0,
        total_sold_tokens=1000.0,
        total_sold_usd=5000.0,  # 400% ROI
        average_buy_price=1.0,
        realized_pnl_usd=4000.0,
        realized_roi=4.0,
        first_buy_time=now - timedelta(days=10),
        last_trade_time=now - timedelta(days=5),
        trades_count=2
    )

    profile.positions["0xtoken2"] = Position(
        token_address="0xtoken2",
        total_bought_tokens=500.0,
        total_bought_usd=1000.0,
        total_sold_tokens=500.0,
        total_sold_usd=3000.0,  # 200% ROI
        average_buy_price=2.0,
        realized_pnl_usd=2000.0,
        realized_roi=2.0,
        first_buy_time=now - timedelta(days=8),
        last_trade_time=now - timedelta(days=4),
        trades_count=2
    )

    profile.score.total_trades = 4
    profile.score.early_entry_score = 85.0
    profile.score.regime_scores = {"BULL": 80.0, "BEAR": 75.0, "VOLATILE": 70.0}

    token_histories = {
        "0xtoken1": {"entry_mcap_usd": 100_000, "peak_mcap_usd": 2_000_000},  # entered early
        "0xtoken2": {"entry_mcap_usd": 200_000, "peak_mcap_usd": 1_500_000}   # entered early
    }

    eval_result = engine.evaluate_predictive_skill(profile, token_histories)
    assert eval_result.early_accumulation_ratio == 1.0
    assert eval_result.catastrophic_avoidance_score == 100.0
    assert eval_result.skill_vs_luck.cohort_comparison["outperformed_random_buyers"]
    assert eval_result.skill_vs_luck.cohort_comparison["outperformed_ordinary_whales"]
    assert eval_result.skill_vs_luck.z_score > 1.96
    assert eval_result.skill_vs_luck.p_value <= 0.05
    assert eval_result.is_smart_money


# -----------------------------------------------------------------------------
# 2. Whale Executable Liquidity & Market Impact Tests
# -----------------------------------------------------------------------------

def test_whale_executable_liquidity_impact():
    engine = WhaleMarketImpactEngine()
    
    # Wallet holding $50,000 in a pool with $100,000 liquidity (50% executable liquidity share!)
    impact = engine.analyze_whale_position(
        wallet_address="0xWhaleWallet",
        token_address="0xLowLiqToken",
        token_balance=50_000.0,
        token_price_usd=1.0,
        pool_liquidity_usd=100_000.0,
        total_supply=10_000_000.0  # Only 0.5% of total supply, but HUGE % of executable pool liquidity!
    )

    assert impact.supply_percentage == 0.5
    assert impact.executable_liquidity_share == 0.50
    assert impact.concentration_rank == "CRITICAL"
    
    # 25% dump calculation ($12,500 into $100,000 pool)
    sp_25 = impact.sell_pressure_25pct
    assert sp_25.estimated_price_impact_percent > 10.0
    assert sp_25.sell_pressure_index > 50.0

    # Coordinated Whale behavior test
    w1 = WalletProfile(address="0xwhale1", chain="ethereum")
    w2 = WalletProfile(address="0xwhale2", chain="ethereum")
    now = datetime.now(timezone.utc)
    
    w1.positions["0xtokenx"] = Position(token_address="0xtokenx", current_balance=100.0, total_bought_usd=50000.0, last_trade_time=now)
    w2.positions["0xtokenx"] = Position(token_address="0xtokenx", current_balance=200.0, total_bought_usd=80000.0, last_trade_time=now - timedelta(seconds=30))

    alert = engine.detect_coordinated_whale_behavior([w1, w2], "0xtokenx", window_seconds=300.0)
    assert alert is not None
    assert alert.action_type == "ACCUMULATION"
    assert len(alert.participating_whales) == 2


# -----------------------------------------------------------------------------
# 3. Probabilistic Graph & Limitation Modeling Tests
# -----------------------------------------------------------------------------

def test_probabilistic_graph_inference_limitations():
    engine = ProbabilisticWalletGraphEngine(default_prior=0.10)
    now = datetime.now(timezone.utc)

    # 1. Query prior with zero evidence
    rel_blank = engine.evaluate_relationship("0xWalletA", "0xWalletB", "CO_TRADER")
    assert rel_blank.probability == 0.10
    assert "No empirical on-chain evidence" in rel_blank.disclaimer

    # 2. Add multiple evidence traces
    engine.add_evidence(
        source="0xWalletA",
        target="0xWalletB",
        rel_type="FUNDED",
        evidence_type="COMMON_FUNDING",
        weight=0.95,
        details={"time_diff_seconds": 12.0},
        timestamp=now - timedelta(hours=1)
    )

    engine.add_evidence(
        source="0xWalletA",
        target="0xWalletB",
        rel_type="FUNDED",
        evidence_type="CO_TRADING",
        weight=0.85,
        details={"token": "0xTokenZ"},
        timestamp=now - timedelta(minutes=30)
    )

    rel_evaluated = engine.evaluate_relationship("0xWalletA", "0xWalletB", "FUNDED")
    assert rel_evaluated.probability > 0.80
    assert rel_evaluated.confidence_interval[0] < rel_evaluated.probability < rel_evaluated.confidence_interval[1]
    assert "statistical correlation, NOT a guaranteed real-world identity" in rel_evaluated.disclaimer
    assert len(rel_evaluated.evidence_chain) == 2


# -----------------------------------------------------------------------------
# 4. Insider & Manipulation Detection & Score Downgrade Tests
# -----------------------------------------------------------------------------

def test_insider_manipulation_detection_and_downgrade():
    engine = InsiderAndManipulationEngine()
    now = datetime.now(timezone.utc)
    
    # Setup holder profiles
    p1 = WalletProfile(address="0xInsider1", chain="ethereum")
    p2 = WalletProfile(address="0xInsider2", chain="ethereum")
    p3 = WalletProfile(address="0xInsider3", chain="ethereum")

    p1.positions["0xSuspiciousToken"] = Position(token_address="0xSuspiciousToken", current_balance=4000.0, first_buy_time=now)
    p2.positions["0xSuspiciousToken"] = Position(token_address="0xSuspiciousToken", current_balance=4000.0, first_buy_time=now)
    p3.positions["0xSuspiciousToken"] = Position(token_address="0xSuspiciousToken", current_balance=2000.0, first_buy_time=now)

    # Funding sources within 2 mins of buying
    p1.funding_sources.append(FundingSource(sender_address="0xDeployer", token_address="native", amount=1.0, timestamp=now - timedelta(seconds=60), tx_hash="h1"))
    p2.funding_sources.append(FundingSource(sender_address="0xDeployer", token_address="native", amount=1.0, timestamp=now - timedelta(seconds=50), tx_hash="h2"))

    graph = ProbabilisticWalletGraphEngine()
    graph.add_evidence("0xInsider1", "0xInsider2", "INSIDER_CLUSTER", "COMMON_FUNDING", 0.95)

    recent_txs = [
        DecodedTransaction(tx_hash="tx1", chain="ethereum", action_type="SWAP", sender="0xInsider1", timestamp=now),
        DecodedTransaction(tx_hash="tx2", chain="ethereum", action_type="SWAP", sender="0xInsider2", timestamp=now),
        DecodedTransaction(tx_hash="tx3", chain="ethereum", action_type="SWAP", sender="0xInsider3", timestamp=now)
    ]

    report = engine.analyze_token_manipulation(
        token_address="0xSuspiciousToken",
        chain="ethereum",
        holder_profiles=[p1, p2, p3],
        graph_engine=graph,
        recent_transactions=recent_txs,
        launch_timestamp=now - timedelta(seconds=10)
    )

    assert report.overall_manipulation_score > 30.0
    pattern_types = [p.pattern_type for p in report.detected_patterns]
    assert "SNIPER_GROUP" in pattern_types or "BUNDLED_PURCHASE" in pattern_types or "RAPID_FUNDING_CHAIN" in pattern_types

    # Verify score downgrade signal creation
    downgrade = engine.generate_score_downgrade_signals(report)
    assert downgrade.downgrade_recommended
    assert downgrade.security_risk_multiplier > 1.0
    assert downgrade.opportunity_penalty_points > 0.0


# -----------------------------------------------------------------------------
# 5. Integrated SectionSixIntelligenceEngine Tests
# -----------------------------------------------------------------------------

def test_section_six_unified_engine():
    engine = SectionSixIntelligenceEngine()
    profile = WalletProfile(address="0xTestTrader", chain="ethereum")
    
    # 1. Smart Money test
    sm_eval = engine.evaluate_smart_money(profile)
    assert not sm_eval.is_smart_money

    # 2. Whale Impact test
    whale_impact = engine.analyze_whale_impact(
        wallet_address="0xTestTrader",
        token_address="0xTokenA",
        token_balance=1000.0,
        pool_liquidity_usd=50000.0,
        token_price_usd=10.0
    )
    assert whale_impact.holding_usd == 10000.0

    # 3. Probabilistic evidence trace
    prob_rel = engine.record_probabilistic_evidence(
        source="0xFunder",
        target="0xTestTrader",
        rel_type="FUNDED",
        evidence_type="DIRECT_TRANSFER",
        weight=0.90
    )
    assert prob_rel.probability >= 0.50


# -----------------------------------------------------------------------------
# 6. Integrated Workflow Execution Test
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wallet_workflow_with_section_six(monkeypatch):
    workflow = WalletWorkflow()

    db_mock = {}
    async def mock_get_profile(address):
        return db_mock.get(address.lower())
    async def mock_load_all():
        return list(db_mock.values())
    async def mock_upsert(profile):
        db_mock[profile.address.lower()] = profile

    monkeypatch.setattr(workflow, "get_wallet_profile", mock_get_profile)
    monkeypatch.setattr(workflow, "load_all_profiles", mock_load_all)
    monkeypatch.setattr(postgres_store, "upsert_entity", mock_upsert)

    event = CanonicalNotificationEvent(
        source_app_id="webhook_ingest",
        event_category="transaction",
        referenced_wallet_address="0xSectionSixWallet",
        referenced_token_address="0xSectionSixToken",
        blockchain_id="ethereum",
        raw_payload={
            "tx_hash": "0xsix_tx",
            "chain": "ethereum",
            "sender": "0xWhaleFunder",
            "receiver": "0xSectionSixWallet",
            "action": "transfer",
            "assets_involved": [
                {"token_address": "native", "symbol": "ETH", "amount": 10.0, "amount_usd": 30000.0}
            ],
            "economic_value_usd": 30000.0,
            "status": "SUCCESS"
        }
    )

    await workflow.process(event)

    profile = await workflow.get_wallet_profile("0xSectionSixWallet")
    assert profile is not None
    assert "smart_money_predictive_evaluation" in profile.metadata
    assert "latest_token_manipulation_report" in profile.metadata
    assert "latest_downgrade_signal" in profile.metadata

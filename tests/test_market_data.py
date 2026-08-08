import pytest
from datetime import datetime, timezone, timedelta
import asyncio

from src.market_data import (
    PriceObservation,
    ReconciledPrice,
    LiquidityPoolState,
    LiquidityAnalysis,
    LiquidityRiskEvent,
    TradeObservation,
    VolumeAnalysis,
    SupplyBreakdown,
    SupplyEvent,
    ValuationAnalysis,
    PriceEngine,
    LiquidityEngine,
    VolumeEngine,
    ValuationEngine,
    MarketIntelligenceManager,
)
from src.workflows.market import MarketWorkflow
from src.schemas import CanonicalNotificationEvent


@pytest.fixture
def price_engine():
    return PriceEngine(max_staleness_seconds=60.0, max_deviation_threshold=0.25)


@pytest.fixture
def liquidity_engine():
    return LiquidityEngine(sharp_drop_threshold_pct=0.20, concentration_threshold_pct=0.70)


@pytest.fixture
def volume_engine():
    return VolumeEngine(whale_threshold_usd=5000.0)


@pytest.fixture
def valuation_engine():
    return ValuationEngine()


@pytest.fixture
def manager():
    return MarketIntelligenceManager()


# -----------------------------------------------------------------------------
# 1. Price Engine Tests
# -----------------------------------------------------------------------------

def test_price_reconciliation_multi_source(price_engine):
    now = datetime.now(timezone.utc)
    obs = [
        PriceObservation(source_id="UniswapV3", price_usd=1.00, liquidity_usd=100_000, timestamp=now),
        PriceObservation(source_id="Pyth", price_usd=1.02, liquidity_usd=50_000, timestamp=now),
        PriceObservation(source_id="Chainlink", price_usd=0.99, liquidity_usd=50_000, timestamp=now),
    ]

    reconciled = price_engine.reconcile_price("0xtoken", "ethereum", obs)
    assert reconciled.is_reliable is True
    assert 0.99 <= reconciled.price_usd <= 1.02
    assert reconciled.confidence_score > 0.70
    assert reconciled.provider_count == 3
    assert len(reconciled.rejected_sources) == 0


def test_price_reconciliation_stale_and_outlier_rejection(price_engine):
    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(seconds=120)  # > 60s max staleness

    obs = [
        PriceObservation(source_id="UniswapV3", price_usd=1.00, liquidity_usd=100_000, timestamp=now),
        PriceObservation(source_id="Raydium", price_usd=1.01, liquidity_usd=80_000, timestamp=now),
        PriceObservation(source_id="StaleOracle", price_usd=1.00, liquidity_usd=50_000, timestamp=stale_time),
        PriceObservation(source_id="BadDataAggregator", price_usd=50.00, liquidity_usd=100, timestamp=now),  # Outlier
    ]

    reconciled = price_engine.reconcile_price("0xtoken", "ethereum", obs)
    assert "StaleOracle" in reconciled.rejected_sources
    assert "BadDataAggregator" in reconciled.rejected_sources
    assert reconciled.provider_count == 2
    assert 1.00 <= reconciled.price_usd <= 1.01


def test_price_reconciliation_abnormal_movement(price_engine):
    now = datetime.now(timezone.utc)
    # First observation establishes baseline at $1.00
    obs1 = [PriceObservation(source_id="UniswapV3", price_usd=1.00, liquidity_usd=10_000, timestamp=now)]
    price_engine.reconcile_price("0xtoken", "ethereum", obs1)

    # Sudden 100% price spike to $2.00
    obs2 = [PriceObservation(source_id="UniswapV3", price_usd=2.00, liquidity_usd=10_000, timestamp=now)]
    reconciled2 = price_engine.reconcile_price("0xtoken", "ethereum", obs2)

    assert reconciled2.is_reliable is False
    assert any("Abnormal price shift" in r for r in reconciled2.rejection_reasons)


# -----------------------------------------------------------------------------
# 2. Liquidity Engine Tests
# -----------------------------------------------------------------------------

def test_liquidity_depth_and_lp_concentration(liquidity_engine):
    pool = LiquidityPoolState(
        pool_address="0xpool1",
        dex_name="UniswapV3",
        token0_address="0xtoken",
        token1_address="0xweth",
        reserve0=100_000,
        reserve1=100,
        total_liquidity_usd=200_000,
        lp_distribution={
            "0xlp1": 0.80,  # Top LP holds 80%
            "0xlp2": 0.15,
            "0xlp3": 0.05,
        },
    )
    liquidity_engine.update_pool_state("0xtoken", "ethereum", pool)

    analysis, events = liquidity_engine.analyze_liquidity("0xtoken", "ethereum", current_price_usd=1.0)

    assert analysis.total_liquidity_usd == 200_000
    assert analysis.depth_1pct_usd > 0
    assert analysis.depth_2pct_usd > analysis.depth_1pct_usd
    assert analysis.depth_5pct_usd > analysis.depth_2pct_usd
    assert analysis.top3_lp_concentration_pct == 1.0  # 80 + 15 + 5
    assert analysis.risk_level in ["HIGH", "CRITICAL"]

    # Check that high LP concentration risk event was generated
    assert any(e.risk_type == "HIGH_LP_CONCENTRATION" for e in events)


def test_liquidity_drain_risk_detection(liquidity_engine):
    pool = LiquidityPoolState(
        pool_address="0xpool2",
        dex_name="UniswapV2",
        token0_address="0xtoken",
        token1_address="0xusdc",
        total_liquidity_usd=10_000.0,
        lp_distribution={"0xlp1": 0.5},
    )
    liquidity_engine.update_pool_state("0xtoken", "ethereum", pool)

    # Largest holder has $20,000 worth of tokens (2x pool liquidity)
    analysis, events = liquidity_engine.analyze_liquidity(
        "0xtoken", "ethereum", current_price_usd=1.0, largest_holder_token_balance=20_000.0
    )

    assert analysis.drain_risk_detected is True
    assert analysis.risk_level == "CRITICAL"
    assert any(e.risk_type == "DRAIN_RISK" for e in events)


# -----------------------------------------------------------------------------
# 3. Volume Engine Tests
# -----------------------------------------------------------------------------

def test_volume_breakdown_and_wash_trading(volume_engine):
    now = datetime.now(timezone.utc)

    # Simulate organic trades
    volume_engine.record_trade(
        TradeObservation(
            tx_hash="tx1", token_address="0xtoken", chain="ethereum",
            trader_address="0xretail1", is_buy=True, amount_tokens=1000, amount_usd=1000, price_usd=1.0, timestamp=now
        )
    )
    volume_engine.record_trade(
        TradeObservation(
            tx_hash="tx2", token_address="0xtoken", chain="ethereum",
            trader_address="0xsmart1", is_buy=True, amount_tokens=6000, amount_usd=6000, price_usd=1.0,
            timestamp=now, is_smart_money=True, is_whale=True
        )
    )

    # Simulate wash trading (0xwash back and forth buy/sell with same USD amount)
    volume_engine.record_trade(
        TradeObservation(
            tx_hash="tx3", token_address="0xtoken", chain="ethereum",
            trader_address="0xwash", is_buy=True, amount_tokens=10000, amount_usd=10000, price_usd=1.0, timestamp=now
        )
    )
    volume_engine.record_trade(
        TradeObservation(
            tx_hash="tx4", token_address="0xtoken", chain="ethereum",
            trader_address="0xwash", is_buy=False, amount_tokens=10000, amount_usd=10000, price_usd=1.0,
            timestamp=now + timedelta(seconds=2)
        )
    )

    analysis = volume_engine.analyze_volume("0xtoken", "ethereum")

    assert analysis.raw_volume_24h_usd == 27000.0
    assert analysis.smart_money_volume_24h_usd == 6000.0
    assert analysis.whale_volume_24h_usd == 6000.0
    assert analysis.wash_trading_score > 0.30
    assert analysis.suspicious_volume_24h_usd > 0.0


# -----------------------------------------------------------------------------
# 4. Valuation Engine Tests
# -----------------------------------------------------------------------------

def test_valuation_supply_and_events(valuation_engine):
    supply = SupplyBreakdown(
        total_supply=1_000_000.0,
        circulating_supply=600_000.0,
        burned_supply=100_000.0,
        locked_supply=300_000.0,
    )
    valuation_engine.set_supply_breakdown("0xtoken", "ethereum", supply)

    val1 = valuation_engine.calculate_valuation("0xtoken", "ethereum", price_usd=2.50, total_liquidity_usd=50_000.0)

    assert val1.market_cap_usd == 600_000.0 * 2.50  # $1,500,000
    assert val1.fdv_usd == 1_000_000.0 * 2.50        # $2,500,000
    assert val1.effective_market_cap_ratio == 1_500_000.0 / 50_000.0

    # Record token unlock event of 100k tokens
    event = SupplyEvent(
        token_address="0xtoken", chain="ethereum", event_type="UNLOCK", amount=100_000.0, description="Team cliff unlock"
    )
    val2 = valuation_engine.record_supply_event("0xtoken", "ethereum", event)

    assert val2.supply.circulating_supply == 700_000.0
    assert val2.supply.locked_supply == 200_000.0


# -----------------------------------------------------------------------------
# 5. Integration & Workflow Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_market_workflow_end_to_end(manager):
    workflow = MarketWorkflow(manager=manager)
    now = datetime.now(timezone.utc).isoformat()

    canonical_event = CanonicalNotificationEvent(
        source_app_id="unit_test",
        event_category="swap",
        referenced_token_address="0xtesttoken",
        blockchain_id="ethereum",
        raw_payload={
            "price_usd": 5.0,
            "liquidity_usd": 50000.0,
            "price_observations": [
                {"source_id": "DexScreener", "price_usd": 5.0, "liquidity_usd": 50000.0}
            ],
            "trade": {
                "trader_address": "0xuser123",
                "is_buy": True,
                "amount_tokens": 100.0,
                "amount_usd": 500.0,
                "price_usd": 5.0,
            },
            "supply_event": {
                "event_type": "MINT",
                "amount": 50000.0,
                "description": "Staking reward mint",
            },
        },
    )

    await workflow.process(canonical_event)

    intelligence = manager.get_full_token_intelligence("0xtesttoken", "ethereum")

    assert intelligence["token_address"] == "0xtesttoken"
    assert intelligence["price"]["price_usd"] == 5.0
    assert intelligence["volume"]["raw_volume_24h_usd"] == 500.0
    assert intelligence["valuation"]["valuation_confidence_score"] >= 0.0

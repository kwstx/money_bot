import pytest
from datetime import datetime, timezone, timedelta

from src.schemas import CanonicalNotificationEvent
from src.intelligence.schemas import DecodedTransaction, AssetTransfer, BuySellIntelligence
from src.intelligence.wallet import (
    WalletProfile,
    Position,
    WalletProfiler,
    WalletScoringEngine,
    WalletClusteringEngine,
    WalletGraphEngine,
    WalletReputationEngine
)
from src.workflows.wallet import WalletWorkflow
from src.storage.implementations import postgres_store

# -----------------------------------------------------------------------------
# 1. Profiler Tests
# -----------------------------------------------------------------------------

def test_wallet_profiler_tracking():
    profiler = WalletProfiler(followed_addresses=["0xFollowedTrader"])
    
    # Check registry
    assert profiler.is_followed("0xFollowedTrader")
    assert not profiler.is_followed("0xRandom")
    
    # Create profile
    profile = profiler.create_profile("0xTrader", "ethereum")
    assert profile.address == "0xtrader"
    assert profile.chain == "ethereum"
    assert not profile.is_followed
    
    # Record native transfer (Funding Source detection)
    tx_funding = DecodedTransaction(
        tx_hash="0xfunding_tx",
        chain="ethereum",
        timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
        action_type="TRANSFER",
        sender="0xDistributor",
        receiver="0xTrader",
        assets_involved=[AssetTransfer(token_address="native", symbol="ETH", amount=5.0, amount_usd=15000.0)],
        economic_value_usd=15000.0
    )
    profiler.record_transaction(profile, tx_funding)
    assert len(profile.funding_sources) == 1
    assert profile.funding_sources[0].sender_address == "0xdistributor"
    assert profile.funding_sources[0].amount == 5.0

    # Record Swap trade (Buy TOK)
    buy_trade = BuySellIntelligence(
        tx_hash="0xbuy_tx",
        chain="ethereum",
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=45),
        token_address="0xTokenA",
        trader_address="0xTrader",
        direction="BUY",
        amount_tokens=1000.0,
        amount_usd=2000.0,
        price_usd=2.0
    )
    profiler.record_trade(profile, buy_trade)
    assert "0xtokena" in profile.positions
    pos = profile.positions["0xtokena"]
    assert pos.trades_count == 1
    assert pos.current_balance == 1000.0
    assert pos.average_buy_price == 2.0
    assert pos.first_buy_time is not None

    # Record Swap trade (Sell TOK partially)
    sell_trade = BuySellIntelligence(
        tx_hash="0xsell_tx",
        chain="ethereum",
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=30),
        token_address="0xTokenA",
        trader_address="0xTrader",
        direction="SELL",
        amount_tokens=400.0,
        amount_usd=1200.0,  # Sold at 3.0 USD/token
        price_usd=3.0
    )
    profiler.record_trade(profile, sell_trade)
    pos = profile.positions["0xtokena"]
    assert pos.current_balance == 600.0
    # Cost basis was 400 * 2 = 800 USD. Sold for 1200 USD. Realized PNL = +400 USD
    assert pos.realized_pnl_usd == 400.0
    assert pos.realized_roi == 0.20 # 400 / 2000 total bought cost basis
    assert pos.first_buy_time is not None  # not fully exited

    # Record Swap trade (Sell remainder, fully exiting)
    sell_trade2 = BuySellIntelligence(
        tx_hash="0xsell_tx2",
        chain="ethereum",
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=15),
        token_address="0xTokenA",
        trader_address="0xTrader",
        direction="SELL",
        amount_tokens=600.0,
        amount_usd=1200.0,  # Sold at 2.0 USD/token
        price_usd=2.0
    )
    profiler.record_trade(profile, sell_trade2)
    pos = profile.positions["0xtokena"]
    assert pos.current_balance == 0.0
    # Cost basis for second sell was 600 * 2 = 1200 USD. Sold for 1200 USD. Realized PNL = 0.
    # Total PNL is still 400 USD
    assert pos.realized_pnl_usd == 400.0
    assert len(pos.holding_periods) == 1
    assert abs(pos.holding_periods[0] - 1800.0) < 1.0 # 30 mins
    assert pos.first_buy_time is None # reset

    # Verify counterparties
    assert "0xdistributor" in profile.top_counterparties
    cp = profile.top_counterparties["0xdistributor"]
    assert cp.incoming_count == 1
    assert cp.outgoing_count == 0


# -----------------------------------------------------------------------------
# 2. Scoring Engine Tests
# -----------------------------------------------------------------------------

def test_wallet_scoring():
    engine = WalletScoringEngine(min_trades_threshold=2)
    
    # Blank profile score
    profile = WalletProfile(address="0xtrader", chain="ethereum")
    score = engine.calculate_and_update_score(profile)
    assert score.score == 50.0

    # Add trades to positions
    now = datetime.now(timezone.utc)
    profile.positions["0xtokena"] = Position(
        token_address="0xtokena",
        total_bought_tokens=100.0,
        total_bought_usd=100.0,
        total_sold_tokens=100.0,
        total_sold_usd=250.0,  # Profitable win (ROI = 1.5)
        average_buy_price=1.0,
        realized_pnl_usd=150.0,
        realized_roi=1.5,
        first_buy_time=now - timedelta(days=2),
        last_trade_time=now - timedelta(days=1),
        trades_count=2,
        holding_periods=[86400.0]
    )

    profile.positions["0xtokenb"] = Position(
        token_address="0xtokenb",
        total_bought_tokens=100.0,
        total_bought_usd=100.0,
        total_sold_tokens=100.0,
        total_sold_usd=150.0,  # Profitable win (ROI = 0.5)
        average_buy_price=1.0,
        realized_pnl_usd=50.0,
        realized_roi=0.5,
        first_buy_time=now - timedelta(hours=12),
        last_trade_time=now - timedelta(hours=10),
        trades_count=2,
        holding_periods=[7200.0]
    )

    # 1. Run basic score (threshold met)
    score = engine.calculate_and_update_score(profile)
    assert score.min_trades_satisfied
    assert score.total_trades == 4
    assert score.consistency_score == 100.0 # 2/2 winning tokens
    assert score.score > 50.0

    # 2. Early-Entry scoring
    # Set token launch
    token_launches = {"0xtokenb": now - timedelta(hours=12, minutes=5)} # bought 5 mins after launch
    score = engine.calculate_and_update_score(profile, token_launches=token_launches)
    assert score.early_entry_score > 80.0

    # 3. Minimum trades prior / Smoothing check
    engine_strict = WalletScoringEngine(min_trades_threshold=10) # requires 10 trades
    score_smoothed = engine_strict.calculate_and_update_score(profile)
    assert not score_smoothed.min_trades_satisfied
    # Smooth score should be closer to default 50.0 than the raw evaluation
    assert score_smoothed.score < score.score


# -----------------------------------------------------------------------------
# 3. Clustering Engine Tests
# -----------------------------------------------------------------------------

def test_wallet_clustering():
    engine = WalletClusteringEngine(sync_trade_window_seconds=60.0)
    now = datetime.now(timezone.utc)
    
    # Setup profiles
    p1 = WalletProfile(address="0xwalletA", chain="ethereum")
    p2 = WalletProfile(address="0xwalletB", chain="ethereum")
    p3 = WalletProfile(address="0xwalletC", chain="ethereum")

    # Common Funding link: A and B funded by same wallet
    from src.intelligence.wallet.schemas import FundingSource
    p1.funding_sources.append(FundingSource(
        sender_address="0xDistributor", token_address="native", amount=1.0, timestamp=now, tx_hash="tx1"
    ))
    p2.funding_sources.append(FundingSource(
        sender_address="0xDistributor", token_address="native", amount=2.0, timestamp=now + timedelta(seconds=10), tx_hash="tx2"
    ))

    # Synchronized Trading link: B and C bought TokenX within 10 seconds of each other
    p2.positions["0xTokenX"] = Position(token_address="0xTokenX", last_trade_time=now)
    p3.positions["0xTokenX"] = Position(token_address="0xTokenX", last_trade_time=now - timedelta(seconds=10))

    # Direct counterparty link: A and C interact directly
    from src.intelligence.wallet.schemas import CounterpartySummary
    p1.top_counterparties["0xwalletc"] = CounterpartySummary(
        address="0xwalletc", incoming_count=5, outgoing_count=0, total_volume_usd=5000.0, last_interaction_time=now
    )

    profiles = [p1, p2, p3]
    relationships = engine.detect_relationships(profiles)
    
    types = [r["relation_type"] for r in relationships]
    assert "common_funding" in types
    assert "synchronized_trade" in types
    assert "direct_counterparty" in types

    # Check clustering groupings (DFS/BFS components)
    clusters = engine.cluster_profiles(profiles)
    assert len(clusters) == 1
    assert "0xwalleta" in clusters[0]["wallets"]
    assert "0xwalletb" in clusters[0]["wallets"]
    assert "0xwalletc" in clusters[0]["wallets"]


# -----------------------------------------------------------------------------
# 4. Graph Traversals and Funding Flow Tests
# -----------------------------------------------------------------------------

def test_wallet_graphs():
    graph = WalletGraphEngine()
    
    # Construct a funding tree: Exchange -> WalletC -> WalletB -> WalletA
    graph.add_node("0xExchange", "EXCHANGE")
    graph.add_node("0xWalletC", "WALLET")
    graph.add_node("0xWalletB", "WALLET")
    graph.add_node("0xWalletA", "WALLET")
    
    graph.add_relationship("0xExchange", "0xWalletC", "FUNDED", 0.99)
    graph.add_relationship("0xWalletC", "0xWalletB", "FUNDED", 0.90)
    graph.add_relationship("0xWalletB", "0xWalletA", "FUNDED", 0.90)

    # Co-trading edge
    graph.add_relationship("0xWalletB", "0xWalletD", "CO_TRADER", 0.80)

    # 1. Neighbors query
    neighbors = graph.get_neighbors("0xWalletB")
    neighbor_addresses = {n["address"] for n in neighbors}
    assert "0xwalletc" in neighbor_addresses
    assert "0xwalleta" in neighbor_addresses
    assert "0xwalletd" in neighbor_addresses

    # 2. Multi-hop backward funding trace
    funding_paths = graph.trace_funding_flow("0xWalletA")
    assert len(funding_paths) == 1
    path_info = funding_paths[0]
    assert path_info["source_node"] == "0xexchange"
    assert path_info["source_type"] == "EXCHANGE"
    # Cumulative confidence: 0.99 * 0.90 * 0.90 = ~0.8019
    assert abs(path_info["cumulative_confidence"] - 0.8019) < 0.001
    assert len(path_info["path"]) == 3 # Exchange -> C -> B -> A

    # 3. Graph traversal path filter
    results = graph.traverse("0xWalletC", max_hops=2, min_confidence=0.80)
    # Wallet B should be reached (0.90 conf). Wallet A should NOT be reached since 0.90 * 0.90 = 0.81 is above 0.80.
    # But wait, let's verify conf: C->B (0.90), B->A (0.90) => path conf C->A is 0.81.
    reached_nodes = {r["address"] for r in results}
    assert "0xwalletb" in reached_nodes
    assert "0xwalleta" in reached_nodes


# -----------------------------------------------------------------------------
# 5. Reputation Labeling Tests
# -----------------------------------------------------------------------------

def test_wallet_reputation():
    engine = WalletReputationEngine(whale_volume_threshold=10000.0, bot_velocity_threshold=10.0, smart_money_score_threshold=75.0)
    
    # 1. Retail Profile
    profile = WalletProfile(address="0xtrader", chain="ethereum")
    labels = engine.evaluate_reputation(profile)
    assert len(labels) == 1
    assert labels[0].label == "RETAIL"

    # 2. BOT Profile (reversibility)
    profile.behavior.trade_velocity_24h = 15.0  # above bot threshold
    labels = engine.evaluate_reputation(profile)
    label_types = {l.label for l in labels}
    assert "BOT" in label_types
    assert "RETAIL" not in label_types  # replaced

    # Check reversibility: bot stops trading
    profile.behavior.trade_velocity_24h = 2.0
    labels = engine.evaluate_reputation(profile)
    label_types = {l.label for l in labels}
    assert "BOT" not in label_types
    assert "RETAIL" in label_types  # reverted to retail

    # 3. DEVELOPER Profile
    profile.behavior.contracts_deployed_count = 1
    labels = engine.evaluate_reputation(profile)
    label_types = {l.label for l in labels}
    assert "DEVELOPER" in label_types

    # 4. SMART_MONEY Profile
    profile.score.score = 80.0
    profile.score.min_trades_satisfied = True
    labels = engine.evaluate_reputation(profile)
    label_types = {l.label for l in labels}
    assert "SMART_MONEY" in label_types


# -----------------------------------------------------------------------------
# 6. Integrated Wallet Workflow tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wallet_workflow_processing(monkeypatch):
    workflow = WalletWorkflow()
    
    # Mock database storage
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
        referenced_wallet_address="0xTestWallet",
        blockchain_id="ethereum",
        raw_payload={
            "tx_hash": "0xworktx",
            "chain": "ethereum",
            "sender": "0xDistributorAddress",
            "receiver": "0xTestWallet",
            "action": "transfer",
            "assets_involved": [
                {"token_address": "native", "symbol": "ETH", "amount": 1.0, "amount_usd": 3000.0}
            ],
            "economic_value_usd": 3000.0,
            "status": "SUCCESS"
        }
    )
    
    await workflow.process(event)
    
    # Retrieve profile and verify it was populated and saved
    profile = await workflow.get_wallet_profile("0xTestWallet")
    assert profile is not None
    assert profile.address == "0xtestwallet"
    assert len(profile.funding_sources) == 1
    assert profile.funding_sources[0].sender_address == "0xdistributoraddress"

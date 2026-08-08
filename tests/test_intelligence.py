import pytest
from datetime import datetime, timezone, timedelta
import asyncio

from src.schemas import CanonicalNotificationEvent
from src.intelligence.schemas import DecodedTransaction, AssetTransfer, BuySellIntelligence
from src.intelligence.transaction_monitor import TransactionMonitor
from src.intelligence.buy_sell_detector import BuySellDetector
from src.intelligence.flow_engine import FlowEngine
from src.workflows.intelligence import IntelligenceWorkflow
from src.market_data import market_intelligence_manager, PriceObservation

# -----------------------------------------------------------------------------
# 1. Transaction Monitor Tests
# -----------------------------------------------------------------------------

def test_transaction_monitor_decoding():
    monitor = TransactionMonitor(treasury_addresses=["0xTreasuryMultisig"])
    
    # 1. Swap event decoding
    raw_swap = {
        "tx_hash": "0xswap123",
        "chain": "ethereum",
        "sender": "0xTradersAddress",
        "action": "swap",
        "assets_involved": [
            {"token_address": "0xTokenAddress", "symbol": "TOK", "amount": 1000.0, "amount_usd": 5000.0},
            {"token_address": "native", "symbol": "ETH", "amount": 1.5, "amount_usd": 5000.0}
        ],
        "economic_value_usd": 5000.0,
        "status": "SUCCESS"
    }
    decoded = monitor.decode(raw_swap)
    assert decoded.action_type == "SWAP"
    assert decoded.tx_hash == "0xswap123"
    assert decoded.economic_value_usd == 5000.0
    assert len(decoded.assets_involved) == 2
    
    # 2. Treasury transaction decoding
    raw_treasury = {
        "tx_hash": "0xtreasury123",
        "sender": "0xTreasuryMultisig",
        "receiver": "0xVendorAddress",
        "value": "10.0",
        "value_usd": 30000.0,
        "action": "transfer"
    }
    decoded_t = monitor.decode(raw_treasury)
    assert decoded_t.action_type == "TREASURY"
    assert decoded_t.economic_value_usd == 30000.0

    # 3. Contract admin (renouncing ownership) decoding
    raw_admin = {
        "tx_hash": "0xadmin123",
        "sender": "0xDevOwner",
        "input": "0x71505871" # renounceOwnership() selector
    }
    decoded_a = monitor.decode(raw_admin)
    assert decoded_a.action_type == "CONTRACT_ADMIN"

    # 4. Governance voting decoding
    raw_gov = {
        "tx_hash": "0xgov123",
        "sender": "0xVoter",
        "input": "0x5678abcd",
        "metadata": {"logs": ["castVote", "proposalMatched"]}
    }
    raw_gov["input"] = "castVote(uint256,uint8)"
    decoded_g = monitor.decode(raw_gov)
    assert decoded_g.action_type == "GOVERNANCE"

    # 5. Bridge action decoding
    raw_bridge = {
        "tx_hash": "0xbridge123",
        "sender": "0xUser",
        "input": "bridgeTokens(address,uint256,uint16)"
    }
    decoded_b = monitor.decode(raw_bridge)
    assert decoded_b.action_type == "BRIDGE"


# -----------------------------------------------------------------------------
# 2. Buy and Sell Detector Tests
# -----------------------------------------------------------------------------

def test_buy_sell_detector_classification():
    # Setup detector with smart money registry
    detector = BuySellDetector(
        whale_threshold_usd=10000.0,
        retail_threshold_usd=500.0,
        smart_money_addresses=["0xSmartMoneyTrader"]
    )
    
    # Decoded trade setup (BUY TOKENS)
    decoded_tx_buy = DecodedTransaction(
        tx_hash="0xbuy123",
        chain="ethereum",
        action_type="SWAP",
        sender="0xSmartMoneyTrader",
        receiver="0xSmartMoneyTrader",
        assets_involved=[
            AssetTransfer(token_address="0xTokenAddress", symbol="TOK", amount=2000.0, amount_usd=15000.0),
            AssetTransfer(token_address="native", symbol="ETH", amount=5.0, amount_usd=15000.0)
        ],
        economic_value_usd=15000.0
    )
    
    # Run detector
    trade_intel = detector.detect(
        decoded_tx=decoded_tx_buy,
        token_address="0xTokenAddress",
        total_liquidity_usd=100000.0,
        market_cap_usd=1000000.0
    )
    
    assert trade_intel is not None
    assert trade_intel.direction == "BUY"
    assert trade_intel.price_usd == 7.50 # 15000 / 2000
    assert trade_intel.size_relative_to_liquidity == 0.15 # 15000 / 100000
    assert trade_intel.size_relative_to_mcap == 0.015 # 15000 / 1000000
    assert "SMART_MONEY" in trade_intel.wallet_classification
    assert "WHALE" in trade_intel.wallet_classification # > 10k threshold


# -----------------------------------------------------------------------------
# 3. Flow Engine & Sequence Detector Tests
# -----------------------------------------------------------------------------

def test_flow_engine_and_sequence_detection():
    flow_engine = FlowEngine(window_size_seconds=300)
    
    token = "0xTokenAddress"
    chain = "ethereum"
    now = datetime.now(timezone.utc)
    
    # Register native funding transfers to trace funding sequences
    # Funding 1: 0xCentralFund funds 0xNewWallet1
    funding_tx1 = DecodedTransaction(
        tx_hash="0xfund1",
        chain=chain,
        timestamp=now - timedelta(minutes=5),
        action_type="TRANSFER",
        sender="0xCentralFund",
        receiver="0xNewWallet1",
        assets_involved=[AssetTransfer(token_address="native", symbol="ETH", amount=2.0, amount_usd=6000.0)],
        economic_value_usd=6000.0
    )
    # Funding 2: 0xCentralFund funds 0xNewWallet2
    funding_tx2 = DecodedTransaction(
        tx_hash="0xfund2",
        chain=chain,
        timestamp=now - timedelta(minutes=4),
        action_type="TRANSFER",
        sender="0xCentralFund",
        receiver="0xNewWallet2",
        assets_involved=[AssetTransfer(token_address="native", symbol="ETH", amount=2.0, amount_usd=6000.0)],
        economic_value_usd=6000.0
    )
    
    flow_engine.record_decoded_transaction(funding_tx1)
    flow_engine.record_decoded_transaction(funding_tx2)
    
    # Create trades
    trade1 = BuySellIntelligence(
        tx_hash="0xtrade1",
        chain=chain,
        timestamp=now - timedelta(minutes=2),
        token_address=token,
        trader_address="0xNewWallet1",
        direction="BUY",
        amount_tokens=1000.0,
        amount_usd=5000.0,
        price_usd=5.0,
        wallet_classification=["NEW_WALLET"]
    )
    trade2 = BuySellIntelligence(
        tx_hash="0xtrade2",
        chain=chain,
        timestamp=now - timedelta(minutes=1),
        token_address=token,
        trader_address="0xNewWallet2",
        direction="BUY",
        amount_tokens=800.0,
        amount_usd=4000.0,
        price_usd=5.0,
        wallet_classification=["NEW_WALLET"]
    )
    trade3 = BuySellIntelligence(
        tx_hash="0xtrade3",
        chain=chain,
        timestamp=now,
        token_address=token,
        trader_address="0xRetailTrader",
        direction="SELL",
        amount_tokens=100.0,
        amount_usd=500.0,
        price_usd=5.0,
        wallet_classification=["RETAIL"]
    )
    
    flow_engine.record_trade(trade1)
    flow_engine.record_trade(trade2)
    flow_engine.record_trade(trade3)
    
    # Calculate metrics
    flow_intel = flow_engine.calculate_flow_metrics(token, chain, window_seconds=300)
    
    assert flow_intel.buy_volume_usd == 9000.0
    assert flow_intel.sell_volume_usd == 500.0
    assert flow_intel.buy_sell_imbalance > 0.80 # heavily skewed to buy
    assert flow_intel.active_wallets_count == 3
    assert flow_intel.accumulation_status == "ACCUMULATION"
    
    # Sequence checks
    sequences = flow_intel.detected_sequences
    seq_types = [s["type"] for s in sequences]
    
    # Should detect wallet funding purchases
    assert "wallet_funding_purchase" in seq_types
    # Should detect staged accumulation campaign (since both funded by 0xCentralFund)
    assert "staged_accumulation" in seq_types
    
    staged_seq = next(s for s in sequences if s["type"] == "staged_accumulation")
    assert staged_seq["funding_wallet"] == "0xcentralfund"
    assert len(staged_seq["buying_wallets"]) == 2
    assert staged_seq["total_amount_usd"] == 9000.0


# -----------------------------------------------------------------------------
# 4. End-to-End Workflow Integration Test
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_intelligence_workflow_e2e():
    workflow = IntelligenceWorkflow()
    now = datetime.now(timezone.utc)
    
    # Pre-seed Market Intelligence Manager with token valuation parameters
    # to mock real pool stats
    obs = [
        PriceObservation(source_id="UniswapV3", price_usd=10.0, liquidity_usd=50000.0, timestamp=now)
    ]
    await market_intelligence_manager.ingest_price_observations(
        token_address="0xTokToken",
        chain="ethereum",
        observations=obs
    )
    
    # Construct raw swap event payload
    event = CanonicalNotificationEvent(
        source_app_id="webhook_ingest",
        event_category="swap",
        referenced_token_address="0xTokToken",
        blockchain_id="ethereum",
        raw_payload={
            "tx_hash": "0xe2eswap",
            "chain": "ethereum",
            "sender": "0xTraderX",
            "receiver": "0xTraderX",
            "action": "swap",
            "assets_involved": [
                {"token_address": "0xTokToken", "symbol": "TOK", "amount": 100.0, "amount_usd": 1000.0},
                {"token_address": "native", "symbol": "ETH", "amount": 0.3, "amount_usd": 1000.0}
            ],
            "economic_value_usd": 1000.0,
            "status": "SUCCESS"
        }
    )
    
    # Run the workflow
    await workflow.process(event)
    
    # Verify that the trade was registered and metrics calculated
    flow_intel = workflow.flow_engine.calculate_flow_metrics("0xTokToken", "ethereum")
    assert flow_intel.buy_volume_usd == 1000.0
    assert flow_intel.active_wallets_count == 1

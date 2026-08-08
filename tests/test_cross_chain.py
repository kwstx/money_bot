import pytest

from src.adapters.chains.evm import EVMChainAdapter
from src.adapters.chains.solana import SolanaChainAdapter
from src.crosschain.tracker import CrossChainTracker
from src.discovery.schemas import EventType

def test_evm_chain_adapter_parsing():
    adapter = EVMChainAdapter(chain_name="ethereum", confirmations=12)
    assert adapter.chain_id == "ethereum"
    assert adapter.required_confirmations == 12

    # Test deployment parsing
    raw_tx = {
        "hash": "0x1111",
        "blockNumber": 12345,
        "from": "0xDeployerAddress",
        "to": None,
        "creates": "0xNewTokenAddress",
        "input": "0x60806040..."
    }
    events = adapter.parse_transaction(raw_tx)
    assert len(events) == 1
    assert events[0].event_type == EventType.NEW_TOKEN
    assert events[0].token_address == "0xnewtokenaddress"

    # Test pair created event log
    raw_log = {
        "event": "PairCreated",
        "transactionHash": "0x2222",
        "blockNumber": 12346,
        "address": "0xFactoryAddress",
        "token0": "0xToken0Address",
        "token1": "0xToken1Address",
        "pair": "0xPairAddress",
        "dex_name": "UniswapV2"
    }
    log_event = adapter.parse_log_event(raw_log)
    assert log_event is not None
    assert log_event.event_type == EventType.PAIR_CREATED
    assert log_event.pool_address == "0xpairaddress"

def test_solana_chain_adapter_parsing():
    adapter = SolanaChainAdapter(confirmations=1)
    assert adapter.chain_id == "solana"

    raw_tx = {
        "signature": "5Sig...",
        "slot": 99999,
        "payer": "PayerWallet1111111111111111111111111111111",
        "instruction": "InitializeMint",
        "mint": "Mint111111111111111111111111111111111111111",
        "symbol": "SOLTOKEN"
    }
    events = adapter.parse_transaction(raw_tx)
    assert len(events) == 1
    assert events[0].event_type == EventType.NEW_TOKEN
    assert events[0].token_address == "Mint111111111111111111111111111111111111111"

def test_cross_chain_tracker_aggregation():
    tracker = CrossChainTracker()
    group = tracker.create_or_get_group(symbol="USDC", name="USD Coin")

    # Link Ethereum representation (canonical)
    tracker.link_token_to_group(
        group_id=group.group_id,
        chain="ethereum",
        token_address="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        is_canonical=True,
        liquidity_usd=500000.0,
        volume_24h_usd=1000000.0,
        holder_count=10000
    )

    # Link Solana representation (wrapped / bridged)
    tracker.link_token_to_group(
        group_id=group.group_id,
        chain="solana",
        token_address="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        is_canonical=False,
        is_wrapped=True,
        bridge_protocol="Wormhole",
        liquidity_usd=200000.0,
        volume_24h_usd=300000.0,
        holder_count=8000
    )

    updated_group = tracker.get_group_for_token("ethereum", "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")
    assert updated_group is not None
    assert len(updated_group.representations) == 2
    # Non-double counted: canonical liquidity counted, wrapped token ignored in primary sum
    assert updated_group.total_aggregated_liquidity_usd == 500000.0
    assert updated_group.total_deduplicated_holders == 10000

import pytest
import asyncio
from datetime import datetime, timezone

from src.discovery.manager import TokenDiscoveryManager
from src.discovery.schemas import UnifiedChainEvent, EventType

@pytest.mark.asyncio
async def test_token_discovery_manager_new_token():
    manager = TokenDiscoveryManager()
    
    # Mock analysis subscriber
    subscriber_called = []
    async def mock_subscriber(token_addr: str, chain: str):
        subscriber_called.append((token_addr, chain))

    manager.register_analysis_subscriber(mock_subscriber)

    event = UnifiedChainEvent(
        event_type=EventType.NEW_TOKEN,
        chain="ethereum",
        block_number=18000000,
        tx_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        token_address="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        wallet_address="0xd8da6bf26964af9d7eed9e03e53415d37aa9604a",
        payload={
            "symbol": "USDC",
            "name": "USD Coin",
            "decimals": 6,
            "deployer": "0xd8da6bf26964af9d7eed9e03e53415d37aa9604a",
            "initial_supply": 1000000000.0,
            "is_verified": True
        }
    )

    token_record = await manager.process_event(event)
    assert token_record is not None
    assert token_record.address == "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    assert token_record.symbol == "USDC"
    assert token_record.chain == "ethereum"

    key = "ethereum:0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    assert key in manager.deployment_metadata
    assert manager.deployment_metadata[key].is_verified_source is True

    # Verify parallel analysis subscriber was invoked
    assert len(subscriber_called) == 1
    assert subscriber_called[0] == ("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "ethereum")

@pytest.mark.asyncio
async def test_token_discovery_manager_pair_creation():
    manager = TokenDiscoveryManager()
    
    event = UnifiedChainEvent(
        event_type=EventType.PAIR_CREATED,
        chain="solana",
        block_number=200000,
        tx_hash="5Kj...sig",
        token_address="So11111111111111111111111111111111111111112",
        pool_address="RaydiumPool1111111111111111111111111111111",
        payload={
            "symbol": "SOL",
            "name": "Wrapped SOL",
            "dex_name": "Raydium",
            "quote_token": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "initial_liquidity_usd": 50000.0
        }
    )

    token_record = await manager.process_event(event)
    assert token_record is not None
    assert token_record.chain == "solana"
    
    key = "solana:so11111111111111111111111111111111111111112"
    assert key in manager.pools
    assert manager.pools[key][0].pool_address == "RaydiumPool1111111111111111111111111111111"
    assert manager.pools[key][0].initial_liquidity_usd == 50000.0

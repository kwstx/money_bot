import pytest
from src.parser.extractors import (
    WalletExtractor, TokenExtractor, BlockchainExtractor,
    TransactionExtractor, URLExtractor, UsernameExtractor,
    TimestampExtractor, NumericExtractor, ActionVerbExtractor
)

def test_wallet_extractor():
    extractor = WalletExtractor()
    text = "Sent from 0x71C7656EC7ab88b098defB751B7401B5f6d8976F to HN7cABqLq46Zw1MaafXVQd4CqEnX2NKhTKhYQ1qB83Qo"
    entities = extractor.extract(text)
    
    assert len(entities) == 2
    assert entities[0]["metadata"]["chain"] == "evm"
    assert entities[0]["value"] == "0x71C7656EC7ab88b098defB751B7401B5f6d8976F"
    assert entities[1]["metadata"]["chain"] == "solana"
    assert entities[1]["value"] == "HN7cABqLq46Zw1MaafXVQd4CqEnX2NKhTKhYQ1qB83Qo"

def test_token_extractor():
    extractor = TokenExtractor()
    text = "Just bought $BTC and $eth"
    entities = extractor.extract(text)
    assert len(entities) == 2
    assert entities[0]["value"] == "BTC"
    assert entities[1]["value"] == "ETH"

def test_action_extractor():
    extractor = ActionVerbExtractor()
    text = "Someone swapped some tokens and bot more"
    entities = extractor.extract(text)
    
    assert len(entities) == 2
    assert entities[0]["value"] == "swap"
    assert entities[1]["value"] == "buy"

def test_numeric_extractor():
    extractor = NumericExtractor()
    text = "Up 50% after buying 5.5 SOL for $100.50"
    entities = extractor.extract(text)
    
    assert len(entities) == 3
    assert any(e["entity_type"] == "percentage" and e["value"] == "50" for e in entities)
    assert any(e["entity_type"] == "amount" and e["value"] == "5.5" and e["metadata"]["currency"] == "SOL" for e in entities)
    assert any(e["entity_type"] == "amount" and e["value"] == "100.50" and e["metadata"]["currency"] == "USD" for e in entities)

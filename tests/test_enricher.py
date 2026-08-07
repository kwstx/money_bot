import pytest
from src.enricher import NotificationEnricher

def test_enricher_wallet():
    payload = {
        "title": "New transaction",
        "body": "Sent to 0x1234567890abcdef1234567890abcdef12345678"
    }
    category, wallet, token = NotificationEnricher.classify(payload)
    assert category == "wallet"
    assert wallet == "0x1234567890abcdef1234567890abcdef12345678"
    assert token is None

def test_enricher_liquidity():
    payload = {
        "title": "Liquidity Pool Update",
        "body": "Someone added liquidity to the pool."
    }
    category, wallet, token = NotificationEnricher.classify(payload)
    assert category == "liquidity"

def test_enricher_swap():
    payload = {
        "title": "Swap executed",
        "body": "User swapped 100 USDC for 0.05 ETH"
    }
    category, wallet, token = NotificationEnricher.classify(payload)
    assert category == "swap"

def test_enricher_developer():
    payload = {
        "message": "Contract deployed on mainnet."
    }
    category, wallet, token = NotificationEnricher.classify(payload)
    assert category == "developer"

def test_enricher_token():
    payload = {
        "event_type": "New Token Listed"
    }
    category, wallet, token = NotificationEnricher.classify(payload)
    assert category == "token"

def test_enricher_generic():
    payload = {
        "title": "Hello world",
        "body": "This is a generic message."
    }
    category, wallet, token = NotificationEnricher.classify(payload)
    assert category == "generic"

def test_enricher_nested_payload():
    payload = {
        "source": "webhook",
        "payload": {
            "description": "User swapped 10 ETH"
        }
    }
    category, wallet, token = NotificationEnricher.classify(payload)
    assert category == "swap"

"""
Integration Test Datasets for FOMO Listener
"""
import copy

# 1. Valid Standard Notification
VALID_NOTIFICATION = {
    "source": "raydium_tracker",
    "event_type": "new_pool_created",
    "payload": {
        "pool_address": "8x123abc456def789",
        "token_a": "SOL",
        "token_b": "MEME",
        "liquidity": 150000,
        "timestamp": 1690000000,
        "developer_wallet": "DevWallet123"
    },
    "telemetry": {
        "producer_time": 1690000000.123
    }
}

# 2. Malformed Payloads
# Missing required field 'source'
MALFORMED_MISSING_FIELD = {
    "event_type": "price_update",
    "payload": {
        "token": "MEME",
        "price": 0.05
    }
}

# Excessively large payload (to trigger 413)
LARGE_PAYLOAD = {
    "source": "whale_alert",
    "event_type": "large_transfer",
    "payload": {
        "tx_hash": "tx123",
        "details": "A" * 150000  # 150KB string
    },
    "telemetry": {}
}

# 3. Schema Changes (e.g., v1 vs v2)
SCHEMA_V1 = {
    "source": "legacy_monitor",
    "event_type": "swap",
    "payload": {
        "wallet": "WalletXYZ",
        "amount": 100,
        "token": "USDC"
    }
}

SCHEMA_V2 = {
    "source": "v2_monitor",
    "event_type": "swap",
    "payload": {
        "user_address": "WalletXYZ",
        "swap_details": {
            "amount_in": 100,
            "token_in": "USDC",
            "amount_out": 0.5,
            "token_out": "SOL"
        }
    }
}

# 4. For Duplicate Testing
# We can just reuse VALID_NOTIFICATION twice in tests.

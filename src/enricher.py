import re
from typing import Dict, Any, Tuple, Optional

# Basic regex patterns for lightweight classification
# Supports basic EVM (0x...) and Solana (base58) address formats as a rough heuristic
WALLET_PATTERN = re.compile(r'\b(0x[a-fA-F0-9]{40}|[1-9A-HJ-NP-Za-km-z]{32,44})\b')

LIQUIDITY_PATTERN = re.compile(r'\b(liquidity|lp|pool|add liquidity|remove liquidity)\b', re.IGNORECASE)
SWAP_PATTERN = re.compile(r'\b(swap|swapped|swapping|trade|traded|trading|exchange|exchanged)\b', re.IGNORECASE)
DEV_PATTERN = re.compile(r'\b(deploy|deployed|contract|verified|owner|renounce|renounced|mint|minted)\b', re.IGNORECASE)
TOKEN_PATTERN = re.compile(r'\b(token|coin)\b', re.IGNORECASE)
WALLET_EVENT_PATTERN = re.compile(r'\b(wallet|transfer|transferred|send|sent|receive|received)\b', re.IGNORECASE)

class NotificationEnricher:
    """
    Performs lightweight metadata enrichment on incoming notifications.
    Classifies events to aid in efficient downstream routing.
    Heavy analysis is intentionally avoided here to keep the listener fast.
    """
    
    @staticmethod
    def classify(payload: Dict[str, Any]) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Extracts high-level category and potential wallet/token addresses.
        
        Returns:
            Tuple[event_category, wallet_address, token_address]
        """
        text_content = ""
        
        # Accumulate text from common fields for analysis
        for key in ["title", "body", "message", "text", "description", "event_type"]:
            val = payload.get(key)
            if isinstance(val, str):
                text_content += f" {val}"
                
        # Check within nested payload structure if it exists
        nested_payload = payload.get("payload", {})
        if isinstance(nested_payload, dict):
            for key in ["title", "body", "message", "text", "description"]:
                val = nested_payload.get(key)
                if isinstance(val, str):
                    text_content += f" {val}"
                    
        category = "generic"
        wallet_address = None
        token_address = None
        
        # Simple extraction of first matching address-like string
        wallet_match = WALLET_PATTERN.search(text_content)
        if wallet_match:
            # We assign it to wallet_address, but it could be a token address depending on context.
            # Downstream services will do the heavy lifting to differentiate.
            wallet_address = wallet_match.group(0)
            
        # Priority-based classification
        if LIQUIDITY_PATTERN.search(text_content):
            category = "liquidity"
        elif SWAP_PATTERN.search(text_content):
            category = "swap"
        elif DEV_PATTERN.search(text_content):
            category = "developer"
        elif TOKEN_PATTERN.search(text_content):
            category = "token"
        elif WALLET_EVENT_PATTERN.search(text_content) or wallet_address:
            category = "wallet"
            
        return category, wallet_address, token_address

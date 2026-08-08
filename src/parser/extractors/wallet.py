import re
from typing import List, Dict, Any
from .base import BaseExtractor

EVM_WALLET_PATTERN = re.compile(r'\b0x[a-fA-F0-9]{40}\b')
# Solana addresses are base58 encoded, 32-44 characters long
SOLANA_WALLET_PATTERN = re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b')

class WalletExtractor(BaseExtractor):
    """Extracts cryptocurrency wallet addresses (EVM and Solana)."""
    
    def extract(self, text: str) -> List[Dict[str, Any]]:
        entities = []
        
        # Extract EVM wallets
        for match in EVM_WALLET_PATTERN.finditer(text):
            entities.append({
                "entity_type": "wallet",
                "value": match.group(0),
                "context": self._get_context(text, match.start(), match.end()),
                "confidence": 1.0,  # High confidence due to strict pattern and checksum properties
                "metadata": {"chain": "evm"}
            })
            
        # Extract Solana wallets
        for match in SOLANA_WALLET_PATTERN.finditer(text):
            val = match.group(0)
            # Basic heuristic to avoid matching purely numeric or alphabetic strings
            if not val.isnumeric() and not val.isalpha():
                # We can't guarantee it's a wallet without base58 decoding/checksum, 
                # but the pattern + mixed alphanumeric is a strong signal in crypto context.
                entities.append({
                    "entity_type": "wallet",
                    "value": val,
                    "context": self._get_context(text, match.start(), match.end()),
                    "confidence": 0.8,
                    "metadata": {"chain": "solana"}
                })
                
        return entities

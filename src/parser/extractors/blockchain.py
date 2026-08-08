import re
from typing import List, Dict, Any
from .base import BaseExtractor

BLOCKCHAINS = [
    "ethereum", "eth", "solana", "sol", "bsc", "binance smart chain", 
    "base", "arbitrum", "polygon", "matic", "optimism", "avalanche", "avax"
]

# Compile a pattern to match whole words case-insensitively
BLOCKCHAIN_PATTERN = re.compile(r'\b(?:' + '|'.join(map(re.escape, BLOCKCHAINS)) + r')\b', re.IGNORECASE)

class BlockchainExtractor(BaseExtractor):
    """Extracts blockchain names."""
    
    def extract(self, text: str) -> List[Dict[str, Any]]:
        entities = []
        for match in BLOCKCHAIN_PATTERN.finditer(text):
            entities.append({
                "entity_type": "blockchain",
                "value": match.group(0).lower(),
                "context": self._get_context(text, match.start(), match.end()),
                "confidence": 0.8, # Good confidence, but some names like "base" or "sol" might be ambiguous
                "metadata": {}
            })
        return entities

import re
from typing import List, Dict, Any
from .base import BaseExtractor

# EVM tx hash is 0x followed by 64 hex chars
EVM_TX_PATTERN = re.compile(r'\b0x[a-fA-F0-9]{64}\b')
# Solana signatures are base58, length 87-89
SOLANA_TX_PATTERN = re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{87,89}\b')

class TransactionExtractor(BaseExtractor):
    """Extracts transaction hashes/signatures."""
    
    def extract(self, text: str) -> List[Dict[str, Any]]:
        entities = []
        
        for match in EVM_TX_PATTERN.finditer(text):
            entities.append({
                "entity_type": "transaction",
                "value": match.group(0),
                "context": self._get_context(text, match.start(), match.end()),
                "confidence": 1.0,
                "metadata": {"chain": "evm"}
            })
            
        for match in SOLANA_TX_PATTERN.finditer(text):
            entities.append({
                "entity_type": "transaction",
                "value": match.group(0),
                "context": self._get_context(text, match.start(), match.end()),
                "confidence": 0.9,
                "metadata": {"chain": "solana"}
            })
            
        return entities

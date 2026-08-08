import re
from typing import List, Dict, Any
from .base import BaseExtractor

# Controlled event taxonomy mapping regex patterns to standard event types
SEMANTIC_MAPPINGS = [
    (re.compile(r'\b(wallet\s+bought|whale\s+bought|bought\s+(?:the\s+)?dip)\b', re.IGNORECASE), 'SWAP_BUY'),
    (re.compile(r'\b(wallet\s+sold|whale\s+sold|dumped)\b', re.IGNORECASE), 'SWAP_SELL'),
    (re.compile(r'\b(developer\s+added\s+liquidity|lp\s+added|added\s+liquidity)\b', re.IGNORECASE), 'LIQUIDITY_ADD'),
    (re.compile(r'\b(developer\s+removed\s+liquidity|lp\s+removed|rug(?:pull)?)\b', re.IGNORECASE), 'LIQUIDITY_REMOVE'),
    (re.compile(r'\b(new\s+pair\s+launched|fair\s+launch|token\s+launched)\b', re.IGNORECASE), 'TOKEN_LAUNCH'),
    (re.compile(r'\b(large\s+whale\s+accumulation|whale\s+accumulation|heavy\s+buying)\b', re.IGNORECASE), 'WHALE_ACCUMULATION'),
    (re.compile(r'\b(contract\s+verified)\b', re.IGNORECASE), 'CONTRACT_VERIFIED'),
    (re.compile(r'\b(contract\s+renounced|ownership\s+renounced)\b', re.IGNORECASE), 'CONTRACT_RENOUNCED'),
]

class SemanticExtractor(BaseExtractor):
    """
    Extracts semantic events from phrases based on a controlled event taxonomy.
    Maps numerous textual variations to standardized internal event types.
    """
    
    def extract(self, text: str) -> List[Dict[str, Any]]:
        entities = []
        for pattern, event_type in SEMANTIC_MAPPINGS:
            for match in pattern.finditer(text):
                entities.append({
                    "entity_type": "semantic_event",
                    "value": event_type,
                    "context": self._get_context(text, match.start(), match.end()),
                    "confidence": 0.9, # High confidence for specific phrases
                    "metadata": {"original_phrase": match.group(0)}
                })
        return entities

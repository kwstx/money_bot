import re
from typing import List, Dict, Any
from .base import BaseExtractor

# Controlled event taxonomy mapping regex patterns to standard event types with ambiguity-based confidence scores
SEMANTIC_MAPPINGS = [
    # Highly specific/unambiguous semantic terms (Confidence: 0.75 - 0.70)
    (re.compile(r'\b(?:contract\s+verified)\b', re.IGNORECASE), 'CONTRACT_VERIFIED', 0.75),
    (re.compile(r'\b(?:contract\s+renounced|ownership\s+renounced)\b', re.IGNORECASE), 'CONTRACT_RENOUNCED', 0.75),
    (re.compile(r'\b(?:new\s+pair\s+launched|fair\s+launch|token\s+launched)\b', re.IGNORECASE), 'TOKEN_LAUNCH', 0.70),
    
    # Moderately descriptive terms (Confidence: 0.65)
    (re.compile(r'\b(?:wallet\s+bought|whale\s+bought)\b', re.IGNORECASE), 'SWAP_BUY', 0.65),
    (re.compile(r'\b(?:wallet\s+sold|whale\s+sold)\b', re.IGNORECASE), 'SWAP_SELL', 0.65),
    (re.compile(r'\b(?:developer\s+added\s+liquidity|lp\s+added|added\s+liquidity)\b', re.IGNORECASE), 'LIQUIDITY_ADD', 0.65),
    (re.compile(r'\b(?:developer\s+removed\s+liquidity|lp\s+removed)\b', re.IGNORECASE), 'LIQUIDITY_REMOVE', 0.65),
    (re.compile(r'\b(?:large\s+whale\s+accumulation|whale\s+accumulation)\b', re.IGNORECASE), 'WHALE_ACCUMULATION', 0.65),
    
    # Highly ambiguous/slang terms (Confidence: 0.50)
    (re.compile(r'\b(?:bought\s+(?:the\s+)?dip)\b', re.IGNORECASE), 'SWAP_BUY', 0.50),
    (re.compile(r'\b(?:dumped)\b', re.IGNORECASE), 'SWAP_SELL', 0.50),
    (re.compile(r'\b(?:rug(?:pull)?)\b', re.IGNORECASE), 'LIQUIDITY_REMOVE', 0.50),
    (re.compile(r'\b(?:heavy\s+buying)\b', re.IGNORECASE), 'WHALE_ACCUMULATION', 0.50),
]

class SemanticExtractor(BaseExtractor):
    """
    Extracts semantic events from phrases based on a controlled event taxonomy.
    Maps numerous textual variations to standardized internal event types.
    """
    
    def extract(self, text: str) -> List[Dict[str, Any]]:
        entities = []
        for pattern, event_type, confidence in SEMANTIC_MAPPINGS:
            for match in pattern.finditer(text):
                entities.append({
                    "entity_type": "semantic_event",
                    "value": event_type,
                    "context": self._get_context(text, match.start(), match.end()),
                    "confidence": confidence,
                    "metadata": {"original_phrase": match.group(0)}
                })
        return entities

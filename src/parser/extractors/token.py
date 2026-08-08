import re
from typing import List, Dict, Any
from .base import BaseExtractor

TOKEN_SYMBOL_PATTERN = re.compile(r'\$([A-Za-z0-9]+)\b')

class TokenExtractor(BaseExtractor):
    """Extracts token symbols (e.g., $BTC, $ETH)."""
    
    def extract(self, text: str) -> List[Dict[str, Any]]:
        entities = []
        for match in TOKEN_SYMBOL_PATTERN.finditer(text):
            entities.append({
                "entity_type": "token",
                "value": match.group(1).upper(),
                "context": self._get_context(text, match.start(), match.end()),
                "confidence": 0.9,
                "metadata": {}
            })
        return entities

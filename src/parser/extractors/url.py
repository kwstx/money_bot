import re
from typing import List, Dict, Any
from .base import BaseExtractor

URL_PATTERN = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+')

class URLExtractor(BaseExtractor):
    """Extracts URLs."""
    
    def extract(self, text: str) -> List[Dict[str, Any]]:
        entities = []
        for match in URL_PATTERN.finditer(text):
            entities.append({
                "entity_type": "url",
                "value": match.group(0),
                "context": self._get_context(text, match.start(), match.end()),
                "confidence": 1.0,
                "metadata": {}
            })
        return entities

import re
from typing import List, Dict, Any
from .base import BaseExtractor

# Matches basic relative times (e.g. "5 mins ago", "1 hour ago", "10 seconds ago", "2d")
RELATIVE_TIME_PATTERN = re.compile(r'\b(\d+)\s*(sec(?:onds?)?|s|min(?:utes?)?|m|hours?|h|days?|d)\s*ago\b', re.IGNORECASE)
# Basic absolute timestamp (YYYY-MM-DD HH:MM:SS)
ABSOLUTE_TIME_PATTERN = re.compile(r'\b\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\b')

class TimestampExtractor(BaseExtractor):
    """Extracts timestamps (relative or absolute)."""
    
    def extract(self, text: str) -> List[Dict[str, Any]]:
        entities = []
        
        for match in RELATIVE_TIME_PATTERN.finditer(text):
            entities.append({
                "entity_type": "timestamp",
                "value": match.group(0),
                "context": self._get_context(text, match.start(), match.end()),
                "confidence": 0.85,
                "metadata": {"type": "relative"}
            })
            
        for match in ABSOLUTE_TIME_PATTERN.finditer(text):
            entities.append({
                "entity_type": "timestamp",
                "value": match.group(0),
                "context": self._get_context(text, match.start(), match.end()),
                "confidence": 0.95,
                "metadata": {"type": "absolute"}
            })
            
        return entities

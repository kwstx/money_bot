import re
from typing import List, Dict, Any
from .base import BaseExtractor

# Match @ followed by 1 to 32 alphanumeric chars or underscores
USERNAME_PATTERN = re.compile(r'@([a-zA-Z0-9_]{1,32})\b')

class UsernameExtractor(BaseExtractor):
    """Extracts usernames and mentions (e.g., @user)."""
    
    def extract(self, text: str) -> List[Dict[str, Any]]:
        entities = []
        for match in USERNAME_PATTERN.finditer(text):
            entities.append({
                "entity_type": "username",
                "value": match.group(1),
                "context": self._get_context(text, match.start(), match.end()),
                "confidence": 0.85,
                "metadata": {}
            })
        return entities

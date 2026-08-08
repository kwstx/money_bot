import re
from typing import List, Dict, Any
from .base import BaseExtractor

PERCENTAGE_PATTERN = re.compile(r'([+-]?\d+(?:\.\d+)?)\s*%')
# We match numerical values combined with currencies like USD, SOL, ETH, etc.
AMOUNT_PATTERN = re.compile(r'\b(\d+(?:\.\d+)?(?:[kKmMbB])?)\s*(SOL|ETH|BTC|USDT|USDC|USD|\$)\b', re.IGNORECASE)
# Or $ amount
DOLLAR_AMOUNT_PATTERN = re.compile(r'\$\s*(\d+(?:\.\d+)?(?:[kKmMbB])?)\b')

class NumericExtractor(BaseExtractor):
    """Extracts percentages and monetary amounts."""
    
    def extract(self, text: str) -> List[Dict[str, Any]]:
        entities = []
        
        # Extract Percentages
        for match in PERCENTAGE_PATTERN.finditer(text):
            entities.append({
                "entity_type": "percentage",
                "value": match.group(1),
                "context": self._get_context(text, match.start(), match.end()),
                "confidence": 0.95,
                "metadata": {}
            })
            
        # Extract Amounts (suffix currency)
        for match in AMOUNT_PATTERN.finditer(text):
            currency = match.group(2).upper()
            if currency == '$':
                currency = 'USD'
            entities.append({
                "entity_type": "amount",
                "value": match.group(1),
                "context": self._get_context(text, match.start(), match.end()),
                "confidence": 0.9,
                "metadata": {"currency": currency}
            })
            
        # Extract Dollar Amounts (prefix $)
        for match in DOLLAR_AMOUNT_PATTERN.finditer(text):
            entities.append({
                "entity_type": "amount",
                "value": match.group(1),
                "context": self._get_context(text, match.start(), match.end()),
                "confidence": 0.9,
                "metadata": {"currency": "USD"}
            })
            
        return entities

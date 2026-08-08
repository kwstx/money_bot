import re
from typing import List, Dict, Any
from .base import BaseExtractor

# Map of words/abbreviations to their canonical action verb
ACTION_MAPPINGS = {
    "buy": "buy",
    "bought": "buy",
    "bot": "buy",
    "sell": "sell",
    "sold": "sell",
    "swap": "swap",
    "swapped": "swap",
    "mint": "mint",
    "minted": "mint",
    "burn": "burn",
    "burned": "burn",
    "transfer": "transfer",
    "transferred": "transfer",
    "tx": "transaction",
    "liquidate": "liquidate",
    "liquidated": "liquidate",
    "liq": "liquidate" # Could also mean liquidity depending on context, but treating as action here
}

# Compile a regex to match any of the keys
ACTION_PATTERN = re.compile(r'\b(?:' + '|'.join(map(re.escape, ACTION_MAPPINGS.keys())) + r')\b', re.IGNORECASE)

class ActionVerbExtractor(BaseExtractor):
    """Extracts action verbs and normalizes abbreviations/tenses."""
    
    def extract(self, text: str) -> List[Dict[str, Any]]:
        entities = []
        for match in ACTION_PATTERN.finditer(text):
            matched_text = match.group(0).lower()
            canonical_action = ACTION_MAPPINGS.get(matched_text, matched_text)
            
            entities.append({
                "entity_type": "action",
                "value": canonical_action,
                "context": self._get_context(text, match.start(), match.end()),
                "confidence": 0.8, # Good confidence, but context might change meaning
                "metadata": {"original": match.group(0)}
            })
        return entities

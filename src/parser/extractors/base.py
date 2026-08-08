from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseExtractor(ABC):
    """
    Abstract base class for all entity extractors.
    Each extractor is responsible for identifying specific entities in the normalized text
    and returning them as a list of dictionaries with standardized keys.
    """
    
    @abstractmethod
    def extract(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract entities from the provided text.
        
        Args:
            text: The normalized notification text.
            
        Returns:
            A list of entity dictionaries. Each dictionary must have:
            - entity_type: str
            - value: str
            - context: str (surrounding text)
            - confidence: float (0.0 to 1.0)
            - metadata: dict (optional additional info)
        """
        pass
        
    def _get_context(self, text: str, match_start: int, match_end: int, window: int = 30) -> str:
        """Helper to get surrounding context for an extraction."""
        start = max(0, match_start - window)
        end = min(len(text), match_end + window)
        return text[start:end]

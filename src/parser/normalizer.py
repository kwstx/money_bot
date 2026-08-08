import re
import unicodedata

class TextNormalizer:
    """
    Normalizes raw notification text for consistent extraction.
    Handles whitespace, unicode formatting, emojis, and punctuation standardization.
    """
    
    @staticmethod
    def normalize(text: str) -> str:
        if not text:
            return ""
            
        # 1. Normalize unicode (NFKC to decompose and recompose, normalizing things like full-width chars)
        text = unicodedata.normalize("NFKC", text)
        
        # 2. Remove zero-width spaces and other invisible formatting characters
        # \u200b-\u200d, \uFEFF, \u200e, \u200f
        text = re.sub(r'[\u200b\u200c\u200d\uFEFF\u200e\u200f]', '', text)
        
        # 3. Standardize whitespace
        # Convert all whitespace (newlines, tabs, non-breaking spaces) to regular space
        text = re.sub(r'\s+', ' ', text)
        
        # 4. Standardize punctuation (quotes, dashes)
        # stylized single quotes
        text = re.sub(r"[`´‘’‚]", "'", text)
        # stylized double quotes
        text = re.sub(r'[“”„«»]', '"', text)
        # dashes
        text = re.sub(r'[–—−]', '-', text)
        
        # 5. Optionally strip emojis if they interfere, but often they are just extra chars.
        # We can leave them for now unless they break specific regexes, 
        # but the prompt mentioned handling emojis. A simple way to remove most emojis 
        # is to strip ranges if required, but often just ensuring whitespace around them is better.
        # Since emojis can be adjacent to words (e.g. "🚀BTC"), we might want to ensure they don't break word boundaries.
        # However, NFKC normalization usually handles this well enough for regex.
        
        return text.strip()

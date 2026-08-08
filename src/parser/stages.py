import re
from typing import List, Dict, Any

# Regex patterns
EVM_WALLET_PATTERN = re.compile(r'\b0x[a-fA-F0-9]{40}\b')
SOLANA_WALLET_PATTERN = re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b')
TOKEN_SYMBOL_PATTERN = re.compile(r'\$([A-Z0-9]+)\b')
URL_PATTERN = re.compile(r'https?://[^\s]+')
AMOUNT_PATTERN = re.compile(r'\b(\d+(?:\.\d+)?)\s*(SOL|ETH|BTC|USDT|USDC|USD)\b', re.IGNORECASE)


def normalize(text: str) -> str:
    """Stage 1: Normalize text (standardizing whitespace, removing zero-width chars)."""
    if not text:
        return ""
    # Remove zero-width spaces and standardize whitespace
    text = re.sub(r'[\u200b\u200c\u200d\uFEFF]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def preprocess(text: str) -> str:
    """Stage 2: Preprocessing (removing boilerplate or irrelevant symbols)."""
    # For now, return the normalized text as-is. In the future, this could strip known spam footers.
    return text


def extract_entities(text: str) -> List[Dict[str, Any]]:
    """Stage 3: Extract basic entities via regex and heuristics."""
    entities = []
    
    # Helper to get context window
    def get_context(match) -> str:
        start = max(0, match.start() - 30)
        end = min(len(text), match.end() + 30)
        return text[start:end]

    # Extract EVM wallets
    for match in EVM_WALLET_PATTERN.finditer(text):
        entities.append({
            "entity_type": "wallet",
            "value": match.group(0),
            "context": get_context(match),
            "confidence": 1.0,
            "metadata": {"chain": "evm"}
        })
        
    # Extract Solana wallets (basic heuristic)
    for match in SOLANA_WALLET_PATTERN.finditer(text):
        val = match.group(0)
        # Avoid matching base58 strings that are purely numeric or purely alphabetic as a weak heuristic
        if not val.isnumeric() and not val.isalpha():
            entities.append({
                "entity_type": "wallet",
                "value": val,
                "context": get_context(match),
                "confidence": 0.8, # lower confidence without full base58 verification
                "metadata": {"chain": "solana"}
            })

    # Extract Token Symbols
    for match in TOKEN_SYMBOL_PATTERN.finditer(text):
        entities.append({
            "entity_type": "token",
            "value": match.group(1),
            "context": get_context(match),
            "confidence": 0.9,
            "metadata": {}
        })

    # Extract URLs
    for match in URL_PATTERN.finditer(text):
        entities.append({
            "entity_type": "url",
            "value": match.group(0),
            "context": get_context(match),
            "confidence": 1.0,
            "metadata": {}
        })
        
    # Extract Amounts
    for match in AMOUNT_PATTERN.finditer(text):
        entities.append({
            "entity_type": "amount",
            "value": match.group(1),
            "context": get_context(match),
            "confidence": 0.95,
            "metadata": {"currency": match.group(2).upper()}
        })

    return entities


def validate_entities(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Stage 4: Validation (filtering out false positives)."""
    valid_entities = []
    for ent in entities:
        # Specific validation logic can go here (e.g. EVM checksum verification)
        if ent["entity_type"] == "wallet" and ent["metadata"].get("chain") == "solana":
            # Extra checks could be added here
            pass
        valid_entities.append(ent)
    return valid_entities


def enrich_entities(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Stage 5: Enrichment (decorating with more info)."""
    for ent in entities:
        if ent["entity_type"] == "url":
            # Example: check if it's a known dex or block explorer
            if "etherscan.io" in ent["value"] or "solscan.io" in ent["value"]:
                ent["metadata"]["is_explorer"] = True
    return entities


def score_confidence(entities: List[Dict[str, Any]], normalized_text: str) -> float:
    """Stage 6: Scoring (assigning a confidence score to the extraction)."""
    if not entities:
        return 0.1 # Very low confidence if nothing was extracted
    
    # Base score based on the presence of entities
    score = min(1.0, 0.4 + (0.15 * len(entities)))
    
    # If the text is very short but has entities, confidence is high
    if len(normalized_text) < 50 and len(entities) > 0:
        score = min(1.0, score + 0.2)
        
    return score

import re
from typing import List, Dict, Any

from .normalizer import TextNormalizer
from .extractors import (
    WalletExtractor, TokenExtractor, BlockchainExtractor,
    TransactionExtractor, URLExtractor, UsernameExtractor,
    TimestampExtractor, NumericExtractor, ActionVerbExtractor,
    SemanticExtractor
)
import eth_utils
import base58

# Instantiate extractors
EXTRACTORS = [
    WalletExtractor(),
    TokenExtractor(),
    BlockchainExtractor(),
    TransactionExtractor(),
    URLExtractor(),
    UsernameExtractor(),
    TimestampExtractor(),
    NumericExtractor(),
    ActionVerbExtractor(),
    SemanticExtractor()
]

def normalize(text: str) -> str:
    """Stage 1: Normalize text (standardizing whitespace, removing zero-width chars)."""
    return TextNormalizer.normalize(text)

def preprocess(text: str) -> str:
    """Stage 2: Preprocessing (removing boilerplate or irrelevant symbols)."""
    # For now, return the normalized text as-is. In the future, this could strip known spam footers.
    return text

def extract_entities(text: str) -> List[Dict[str, Any]]:
    """Stage 3: Extract entities via modular extractors."""
    entities = []
    
    for extractor in EXTRACTORS:
        entities.extend(extractor.extract(text))

    return entities

def validate_entities(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Stage 4: Validation (filtering out false positives)."""
    valid_entities = []
    for ent in entities:
        is_valid = True
        
        # EVM Checksum Validation
        if ent["metadata"].get("chain") == "evm":
            val = ent["value"]
            if ent["entity_type"] in ["wallet", "token"]:
                # Ensure it's a valid hex address. If it has mixed casing, it must be a valid checksum.
                if not eth_utils.is_address(val):
                    is_valid = False
                elif any(c.isupper() for c in val[2:]) and any(c.islower() for c in val[2:]):
                    if not eth_utils.is_checksum_address(val):
                        is_valid = False

        # Solana Base58 format validation
        if ent["metadata"].get("chain") == "solana":
            val = ent["value"]
            try:
                decoded = base58.b58decode(val)
                if ent["entity_type"] == "wallet" and len(decoded) != 32:
                    is_valid = False
                elif ent["entity_type"] == "transaction" and len(decoded) != 64:
                    is_valid = False
            except ValueError:
                is_valid = False
                
        if is_valid:
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

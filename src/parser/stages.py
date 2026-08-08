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

from typing import Tuple

def validate_entities(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Stage 4: Validation (filtering out false positives and converting units)."""
    valid_entities = []
    
    # Try to initialize web3 for contract validation if possible
    w3 = None
    try:
        from web3 import Web3
        _w3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
        if _w3.is_connected():
            w3 = _w3
    except Exception:
        pass

    for ent in entities:
        ent["is_valid"] = True
        
        # EVM Checksum Validation
        if ent["metadata"].get("chain") == "evm":
            val = ent["value"]
            if ent["entity_type"] in ["wallet", "token"]:
                # Ensure it's a valid hex address. If it has mixed casing, it must be a valid checksum.
                if not eth_utils.is_address(val):
                    ent["is_valid"] = False
                elif any(c.isupper() for c in val[2:]) and any(c.islower() for c in val[2:]):
                    if not eth_utils.is_checksum_address(val):
                        ent["is_valid"] = False
                        
                # Check contract existence for tokens if w3 is available
                if ent["is_valid"] and ent["entity_type"] == "token" and w3:
                    try:
                        code = w3.eth.get_code(Web3.to_checksum_address(val))
                        if code == b'' or code == b'0x':
                            ent["is_valid"] = False
                    except Exception:
                        pass # Ignore if call fails

        # Solana Base58 format validation
        if ent["metadata"].get("chain") == "solana":
            val = ent["value"]
            try:
                decoded = base58.b58decode(val)
                if ent["entity_type"] == "wallet" and len(decoded) != 32:
                    ent["is_valid"] = False
                elif ent["entity_type"] == "transaction" and len(decoded) != 64:
                    ent["is_valid"] = False
            except ValueError:
                ent["is_valid"] = False
                
        # Standardize Numerical Units
        if ent["entity_type"] == "amount":
            try:
                base_val = float(ent["value"])
                multiplier = ent["metadata"].get("multiplier", "")
                if multiplier == 'k':
                    base_val *= 1_000
                elif multiplier == 'm':
                    base_val *= 1_000_000
                elif multiplier == 'b':
                    base_val *= 1_000_000_000
                # Format to remove trailing .0 if integer
                if base_val.is_integer():
                    ent["value"] = str(int(base_val))
                else:
                    ent["value"] = str(base_val)
            except ValueError:
                ent["is_valid"] = False
                
        # We keep all entities, valid or not, but they are flagged.
        valid_entities.append(ent)
            
    return valid_entities

def enrich_entities(entities: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Stage 5: Enrichment (decorating with more info and building relationships)."""
    relationships = []
    
    wallets = [e for e in entities if e["entity_type"] == "wallet" and e.get("is_valid", True)]
    tokens = [e for e in entities if e["entity_type"] == "token" and e.get("is_valid", True)]
    actions = [e for e in entities if e["entity_type"] == "action" and e.get("is_valid", True)]
    
    # Contextual Enrichment
    if wallets and tokens and actions:
        # Link the first action to the primary wallet and tokens
        primary_action = actions[0]["value"]
        primary_wallet = wallets[0]["value"]
        
        # Link primary wallet to all found tokens via the primary action
        for token in tokens:
            relationships.append({
                "subject": primary_wallet,
                "subject_type": "wallet",
                "action": primary_action,
                "object_target": token["value"],
                "object_type": "token",
                "metadata": {"inferred_from_context": True}
            })

    for ent in entities:
        if ent["entity_type"] == "url":
            # Example: check if it's a known dex or block explorer
            if "etherscan.io" in ent["value"] or "solscan.io" in ent["value"]:
                ent["metadata"]["is_explorer"] = True
    return entities, relationships

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

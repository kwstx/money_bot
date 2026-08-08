import logging
import math
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
from src.intelligence.wallet.manipulation_schemas import (
    EvidenceItem,
    ProbabilisticRelationship
)

logger = logging.getLogger(__name__)

class ProbabilisticWalletGraphEngine:
    """
    Explicitly models the limitations of on-chain inference by representing wallet
    relationships as evidence-backed probabilities with 95% confidence intervals,
    rather than absolute or guaranteed real-world identity assertions.
    """
    def __init__(self, default_prior: float = 0.10, decay_half_life_days: float = 30.0):
        self.default_prior = default_prior
        self.decay_rate = math.log(2.0) / max(1.0, decay_half_life_days)
        # Store relationships: (source.lower(), target.lower(), rel_type.upper()) -> List[EvidenceItem]
        self.evidence_store: Dict[Tuple[str, str, str], List[EvidenceItem]] = {}

    def _pair_key(self, source: str, target: str, rel_type: str) -> Tuple[str, str, str]:
        src = source.lower()
        tgt = target.lower()
        # Sort node addresses lexicographically for symmetric relationships (e.g. CLUSTER_PEER, CO_TRADER)
        if rel_type.upper() in ["CLUSTER_PEER", "CO_TRADER", "WASH_PAIR", "SNIPER_GROUP"]:
            if src > tgt:
                src, tgt = tgt, src
        return (src, tgt, rel_type.upper())

    def add_evidence(
        self,
        source: str,
        target: str,
        rel_type: str,
        evidence_type: str,
        weight: float,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """Adds an empirical evidence item supporting a relationship between two wallets."""
        key = self._pair_key(source, target, rel_type)
        if key not in self.evidence_store:
            self.evidence_store[key] = []

        item = EvidenceItem(
            evidence_type=evidence_type.upper(),
            weight=max(0.0, min(1.0, weight)),
            observation_timestamp=timestamp or datetime.now(timezone.utc),
            decay_factor=0.95,
            details=details or {}
        )
        self.evidence_store[key].append(item)
        logger.debug(f"Added evidence {evidence_type} to pair {key[0]} <-> {key[1]} ({key[2]}) with weight {weight}")

    def evaluate_relationship(
        self,
        source: str,
        target: str,
        rel_type: str
    ) -> ProbabilisticRelationship:
        """
        Calculates posterior probability and 95% confidence interval for a relationship
        using dynamic Bayesian evidence combination with exponential time decay.
        """
        key = self._pair_key(source, target, rel_type)
        evidence_list = self.evidence_store.get(key, [])
        now = datetime.now(timezone.utc)

        if not evidence_list:
            # Return baseline prior with wide uncertainty
            return ProbabilisticRelationship(
                source_address=key[0],
                target_address=key[1],
                relationship_type=key[2],
                probability=self.default_prior,
                confidence_interval=(0.01, 0.30),
                evidence_chain=[],
                last_updated=now,
                disclaimer="No empirical on-chain evidence recorded. Baseline prior applied."
            )

        # 1. Calculate time-decayed evidence weights
        decayed_weights = []
        for ev in evidence_list:
            age_days = (now - ev.observation_timestamp).total_seconds() / 86400.0
            decay = math.exp(-self.decay_rate * max(0.0, age_days))
            effective_weight = ev.weight * decay
            decayed_weights.append(effective_weight)

        # 2. Bayesian Log-Odds Combination
        # Prior log odds: log(prior / (1 - prior))
        prior_log_odds = math.log(self.default_prior / (1.0 - self.default_prior))
        accumulated_log_odds = prior_log_odds

        for w in decayed_weights:
            # Convert evidence weight to likelihood ratio
            # w = 0.9 => LR = 0.9 / 0.1 = 9.0; w = 0.5 => LR = 1.0
            bounded_w = max(0.01, min(0.99, w))
            lr = bounded_w / (1.0 - bounded_w)
            accumulated_log_odds += math.log(lr)

        # Convert back to posterior probability
        posterior_prob = 1.0 / (1.0 + math.exp(-accumulated_log_odds))
        posterior_prob = round(max(0.0, min(1.0, posterior_prob)), 4)

        # 3. Calculate 95% Confidence Interval using sample evidence size & variance
        n_evidence = len(decayed_weights)
        total_effective_weight = sum(decayed_weights)
        
        # Standard error inversely proportional to sqrt of total effective weight
        stderr = 0.25 / math.sqrt(max(1.0, total_effective_weight))
        lower_bound = round(max(0.0, posterior_prob - 1.96 * stderr), 4)
        upper_bound = round(min(1.0, posterior_prob + 1.96 * stderr), 4)

        disclaimer = (
            f"Probabilistic inference (P={posterior_prob*100:.1f}%, CI=[{lower_bound*100:.1f}%, {upper_bound*100:.1f}%]) "
            f"supported by {n_evidence} empirical on-chain trace(s). "
            f"This represents statistical correlation, NOT a guaranteed real-world identity association."
        )

        return ProbabilisticRelationship(
            source_address=key[0],
            target_address=key[1],
            relationship_type=key[2],
            probability=posterior_prob,
            confidence_interval=(lower_bound, upper_bound),
            evidence_chain=evidence_list,
            last_updated=now,
            disclaimer=disclaimer
        )

    def get_all_relationships_for_wallet(self, address: str) -> List[ProbabilisticRelationship]:
        """Returns all probabilistic relationships involving a given wallet address."""
        addr = address.lower()
        results = []
        for (src, tgt, rtype) in self.evidence_store.keys():
            if src == addr or tgt == addr:
                rel = self.evaluate_relationship(src, tgt, rtype)
                results.append(rel)
        return results

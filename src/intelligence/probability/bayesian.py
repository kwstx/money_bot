from typing import List, Dict
from datetime import datetime, timezone
from src.intelligence.probability.schemas import ProbabilityEstimate, Evidence, BayesianUpdate

class BayesianUpdater:
    """
    Revises probabilities whenever new evidence arrives, adhering to historical info boundaries.
    """
    
    def __init__(self, base_rates: Dict[str, float]):
        self.base_rates = base_rates
    
    def update_estimate(self, estimate: ProbabilityEstimate, evidence: Evidence) -> ProbabilityEstimate:
        """
        Updates the probability estimate given new evidence.
        Uses a simple Bayesian inspired adjustment scaled by signal strength.
        """
        # Ensure we don't apply evidence from the future relative to the historical boundary
        if evidence.timestamp > estimate.historical_boundary_timestamp:
            return estimate # Ignore future evidence
        
        updates = []
        
        # Example mapping of evidence category to outcome adjustments
        # A real implementation would use proper Bayesian inference (Prior * Likelihood / Marginal)
        # Here we use a heuristic approach based on signal strength
        
        rug_prob = estimate.rug_probability
        growth_prob = estimate.growth_probability
        winner_prob = estimate.winner_probability
        
        if evidence.category in ["smart_money", "verified_development", "liquidity_increase", "holder_retention"]:
            # Positive signals reduce rug, increase growth/winner
            impact = evidence.signal_strength * 0.1 # Max 10% shift per signal
            
            new_rug = max(0.01, rug_prob * (1 - impact))
            updates.append(self._create_update(rug_prob, new_rug, evidence))
            rug_prob = new_rug
            
            new_growth = min(0.99, growth_prob * (1 + impact))
            updates.append(self._create_update(growth_prob, new_growth, evidence))
            growth_prob = new_growth
            
            new_winner = min(0.99, winner_prob * (1 + impact * 1.5))
            updates.append(self._create_update(winner_prob, new_winner, evidence))
            winner_prob = new_winner
            
        elif evidence.category in ["contract_change", "insider_distribution", "falling_liquidity", "social_decay"]:
            # Negative signals increase rug, decrease growth/winner
            impact = abs(evidence.signal_strength) * 0.15 # Max 15% shift per signal
            
            new_rug = min(0.99, rug_prob * (1 + impact * 2))
            updates.append(self._create_update(rug_prob, new_rug, evidence))
            rug_prob = new_rug
            
            new_growth = max(0.01, growth_prob * (1 - impact))
            updates.append(self._create_update(growth_prob, new_growth, evidence))
            growth_prob = new_growth
            
            new_winner = max(0.01, winner_prob * (1 - impact * 1.5))
            updates.append(self._create_update(winner_prob, new_winner, evidence))
            winner_prob = new_winner

        # Update the estimate
        estimate.rug_probability = rug_prob
        estimate.growth_probability = growth_prob
        estimate.winner_probability = winner_prob
        estimate.recent_updates.extend(updates)
        
        # Keep only the last 10 updates for history
        estimate.recent_updates = estimate.recent_updates[-10:]
        
        # Adjust confidence
        estimate.confidence_level = min(0.99, estimate.confidence_level + 0.05)
        
        return estimate

    def _create_update(self, old_val: float, new_val: float, evidence: Evidence) -> BayesianUpdate:
        magnitude = abs(new_val - old_val)
        if new_val > old_val:
            direction = "positive"
        elif new_val < old_val:
            direction = "negative"
        else:
            direction = "neutral"
            
        return BayesianUpdate(
            previous_probability=old_val,
            new_probability=new_val,
            magnitude=magnitude,
            direction=direction,
            evidence_applied=evidence
        )

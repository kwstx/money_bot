from datetime import datetime, timezone
from typing import Dict, Any
from .schemas import DeveloperReputation, TeamActivity, TreasuryState

class DeveloperReputationEngine:
    """Calculates a probabilistic trust score for developers based on multiple intelligence vectors."""
    
    def __init__(self, developer_id: str):
        self.developer_id = developer_id
        
    def calculate_reputation(self, 
                             graph_analysis: Dict[str, Any],
                             team_activity: TeamActivity,
                             treasury_state: TreasuryState,
                             transparency_score: float = 0.5) -> DeveloperReputation:
        """
        Combines historical outcomes, team activity, and treasury behavior 
        to compute a dynamic probabilistic trust score.
        """
        
        # 1. Historical Base Score (0.0 to 1.0)
        success_rate = graph_analysis.get("success_rate", 0.0)
        is_new = graph_analysis.get("is_new_developer", True)
        
        if is_new:
            base_score = 0.5  # Neutral for new developers
        else:
            base_score = success_rate
            
        # 2. Penalties for bad behavior (Rug pulls, abandoned projects, suspicious liquidity)
        rug_patterns = graph_analysis.get("rug_patterns", 0)
        abandoned_count = graph_analysis.get("abandoned_count", 0)
        suspicious_events = graph_analysis.get("suspicious_events", 0)
        
        penalty = 0.0
        penalty += (rug_patterns * 0.4)
        penalty += (abandoned_count * 0.1)
        penalty += (suspicious_events * 0.15)
        
        # 3. Team Activity Modifier
        # High genuine activity boosts score, low/superficial activity slightly lowers it
        activity_modifier = (team_activity.activity_authenticity_score - 0.5) * 0.2
        
        # 4. Treasury Risk Modifier
        treasury_modifier = 0.0
        if treasury_state.risk_level == "HIGH":
            treasury_modifier = -0.3
        elif treasury_state.risk_level == "MEDIUM":
            treasury_modifier = -0.1
        elif treasury_state.risk_level == "LOW" and treasury_state.unexplained_movements_usd == 0:
            treasury_modifier = 0.1
            
        # 5. Transparency Modifier
        transparency_modifier = (transparency_score - 0.5) * 0.2
        
        # Calculate final probabilistic trust score
        trust_score = base_score - penalty + activity_modifier + treasury_modifier + transparency_modifier
        
        # Clamp between 0.0 and 1.0
        trust_score = max(0.0, min(1.0, trust_score))
        
        # Determine communication consistency based on activity authenticity
        comm_consistency = team_activity.activity_authenticity_score
        
        return DeveloperReputation(
            developer_id=self.developer_id,
            timestamp=datetime.now(timezone.utc),
            historical_success_rate=success_rate,
            abandoned_projects_count=abandoned_count,
            rug_patterns_detected=rug_patterns,
            suspicious_liquidity_events=suspicious_events,
            transparency_score=transparency_score,
            communication_consistency=comm_consistency,
            trust_score=trust_score,
            metadata={
                "base_score": base_score,
                "penalty": penalty,
                "activity_modifier": activity_modifier,
                "treasury_modifier": treasury_modifier,
                "transparency_modifier": transparency_modifier
            }
        )

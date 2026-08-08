from typing import List, Dict
from src.intelligence.probability.schemas import Scenario, ProbabilityEstimate, ScenarioAnalysisResult

class ScenarioAnalyzer:
    """
    Tests scenarios like bull, base, bear, rug, liquidity-collapse, macro-shock, and manipulation.
    """
    
    def __init__(self):
        self.default_scenarios = [
            Scenario(name="bull", description="Favorable market conditions, high volume", probability_multiplier=1.5, price_impact_pct=200.0),
            Scenario(name="base", description="Normal market conditions", probability_multiplier=1.0, price_impact_pct=20.0),
            Scenario(name="bear", description="Poor market conditions, low volume", probability_multiplier=0.7, price_impact_pct=-40.0),
            Scenario(name="rug", description="Developer abandons project, steals liquidity", probability_multiplier=5.0, price_impact_pct=-99.0),
            Scenario(name="liquidity-collapse", description="Whales exit simultaneously", probability_multiplier=2.0, price_impact_pct=-80.0),
            Scenario(name="macro-shock", description="Broad market crash (e.g. Bitcoin dumps)", probability_multiplier=1.0, price_impact_pct=-50.0, is_off_chain_risk=True),
            Scenario(name="manipulation", description="Coordinated sophisticated manipulation", probability_multiplier=1.5, price_impact_pct=100.0, is_off_chain_risk=True),
            Scenario(name="sudden_influencer", description="Unexpected influencer shill", probability_multiplier=0.5, price_impact_pct=300.0, is_off_chain_risk=True),
            Scenario(name="hidden_dev_decision", description="Unobservable malicious dev action", probability_multiplier=2.0, price_impact_pct=-90.0, is_off_chain_risk=True),
        ]

    def analyze(self, token_address: str, estimate: ProbabilityEstimate) -> ScenarioAnalysisResult:
        scenario_outcomes = {}
        off_chain_risks = []
        
        # Risk score calculation based on rug/bear vulnerabilities
        risk_accumulator = 0.0
        
        for scenario in self.default_scenarios:
            if scenario.is_off_chain_risk:
                off_chain_risks.append(scenario.name)
                
            # Compute expected price impact under this scenario, given the base probability estimate
            # For instance, if rug probability is high, the "rug" scenario has a very negative impact expectation.
            
            base_prob = 0.1 # default
            if scenario.name == "rug":
                base_prob = estimate.rug_probability
            elif scenario.name == "bull":
                base_prob = estimate.growth_probability
            elif scenario.name == "base":
                base_prob = estimate.winner_probability
                
            scenario_likelihood = base_prob * scenario.probability_multiplier
            
            # Bound likelihood
            scenario_likelihood = min(1.0, max(0.0, scenario_likelihood))
            
            # Expected outcome = likelihood * price_impact
            outcome = scenario_likelihood * scenario.price_impact_pct
            scenario_outcomes[scenario.name] = outcome
            
            # Accumulate risk for negative scenarios
            if scenario.price_impact_pct < 0:
                risk_accumulator += scenario_likelihood * abs(scenario.price_impact_pct)
                
        # Normalize risk score (0 to 1) - heuristic approach
        max_possible_risk = 300.0 
        risk_score = min(1.0, risk_accumulator / max_possible_risk)
        
        return ScenarioAnalysisResult(
            token_address=token_address,
            baseline_estimate=estimate,
            scenario_outcomes=scenario_outcomes,
            identified_off_chain_risks=off_chain_risks,
            risk_score=risk_score
        )

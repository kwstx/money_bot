from datetime import datetime, timezone
from src.intelligence.probability.schemas import ProbabilityEstimate, Evidence, ExpectedValueConfig, ExpectedValueResult, ScenarioAnalysisResult
from src.intelligence.probability.bayesian import BayesianUpdater
from src.intelligence.probability.expected_value import ExpectedValueCalculator
from src.intelligence.probability.scenario import ScenarioAnalyzer

class ProbabilityEngine:
    """
    Orchestrates Probability estimation, Bayesian updating, Expected Value calculation,
    and Scenario analysis.
    """
    
    def __init__(self):
        self.bayesian_updater = BayesianUpdater(base_rates={"rug": 0.8, "growth": 0.15, "winner": 0.05})
        self.ev_calculator = ExpectedValueCalculator()
        self.scenario_analyzer = ScenarioAnalyzer()
        
    def generate_initial_estimate(self) -> ProbabilityEstimate:
        """Generates a baseline estimate for a new token."""
        return ProbabilityEstimate(
            rug_probability=0.8, # Default high rug probability for new tokens
            growth_probability=0.15,
            winner_probability=0.05,
            multiple_return_likelihoods={"2x": 0.1, "10x": 0.02, "100x": 0.001},
            confidence_level=0.1,
            historical_boundary_timestamp=datetime.now(timezone.utc)
        )
        
    def apply_evidence(self, estimate: ProbabilityEstimate, evidence: Evidence) -> ProbabilityEstimate:
        """Applies new evidence via Bayesian updating."""
        return self.bayesian_updater.update_estimate(estimate, evidence)
        
    def calculate_expected_value(self, config: ExpectedValueConfig) -> ExpectedValueResult:
        """Calculates expected value given a configuration."""
        return self.ev_calculator.calculate(config)
        
    def run_scenario_analysis(self, token_address: str, estimate: ProbabilityEstimate) -> ScenarioAnalysisResult:
        """Runs scenario analysis on the current estimate."""
        return self.scenario_analyzer.analyze(token_address, estimate)

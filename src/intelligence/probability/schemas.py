from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import uuid

class Evidence(BaseModel):
    """Represents a piece of new information that updates probabilities."""
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    category: str = Field(..., description="E.g., liquidity, holder_retention, smart_money, contract, social")
    signal_strength: float = Field(..., description="Magnitude of the signal (-1.0 to 1.0)")
    description: str = Field(..., description="Human readable description of the evidence")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
class BayesianUpdate(BaseModel):
    """The result of a probability revision based on new evidence."""
    previous_probability: float
    new_probability: float
    magnitude: float = Field(..., description="Absolute change in probability")
    direction: str = Field(..., description="positive, negative, or neutral")
    evidence_applied: Evidence
    
class ProbabilityEstimate(BaseModel):
    """Current probability estimates for various outcomes."""
    rug_probability: float = Field(ge=0.0, le=1.0)
    growth_probability: float = Field(ge=0.0, le=1.0)
    winner_probability: float = Field(ge=0.0, le=1.0)
    multiple_return_likelihoods: Dict[str, float] = Field(
        default_factory=dict, 
        description="E.g., {'2x': 0.5, '10x': 0.1, '100x': 0.01}"
    )
    confidence_level: float = Field(ge=0.0, le=1.0)
    recent_updates: List[BayesianUpdate] = Field(default_factory=list)
    historical_boundary_timestamp: datetime = Field(
        ..., 
        description="Preserves historical info boundary; model ignores events after this time"
    )

class ExpectedValueConfig(BaseModel):
    """Configuration for expected value calculation."""
    target_multiple: float = Field(..., description="E.g., 2.0 for 2x")
    probability_of_target: float = Field(ge=0.0, le=1.0)
    downside_probability: float = Field(ge=0.0, le=1.0)
    downside_loss_pct: float = Field(..., description="E.g., 1.0 for 100% loss")
    liquidity_available: float = Field(..., description="Liquidity in USD")
    execution_cost_pct: float = Field(..., description="Slippage + fees percentage")
    time_horizon_days: float
    position_size: float = Field(..., description="Intended position size in USD")

class ExpectedValueResult(BaseModel):
    """Result of an expected value calculation."""
    expected_value_usd: float
    expected_value_pct: float
    is_rare_tail: bool = Field(default=False, description="True if target multiple > 50x (extreme outcome)")
    liquidity_penalty: float = Field(..., description="Value lost due to poor liquidity")
    execution_cost: float = Field(..., description="Value lost to fees and slippage")
    implied_guarantee_warning: Optional[str] = Field(
        default=None,
        description="Warning if EV implies unrealistic guaranteed returns"
    )

class Scenario(BaseModel):
    """Definition of a specific risk/reward scenario."""
    name: str = Field(..., description="bull, base, bear, rug, liquidity-collapse, macro-shock, manipulation")
    description: str
    probability_multiplier: float = Field(default=1.0, description="How this scenario scales baseline probabilities")
    price_impact_pct: float = Field(..., description="Expected price impact in this scenario")
    is_off_chain_risk: bool = Field(default=False, description="Whether this risk is unobservable on-chain")

class ScenarioAnalysisResult(BaseModel):
    """Outcome of testing a token against various scenarios."""
    token_address: str
    baseline_estimate: ProbabilityEstimate
    scenario_outcomes: Dict[str, float] = Field(..., description="Expected price impact per scenario name")
    identified_off_chain_risks: List[str] = Field(default_factory=list)
    risk_score: float = Field(ge=0.0, le=1.0, description="Overall scenario risk score")

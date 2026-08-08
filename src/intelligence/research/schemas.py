from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import uuid

# --- Inputs to the AI Research Layer ---

class AggregatedIntelligence(BaseModel):
    """
    A unified view of all intelligence streams for a token at a given point in time.
    Used as the input to the AI Research Engine.
    """
    token_address: str = Field(..., description="The address of the token being analyzed")
    chain: str = Field(..., description="Blockchain network")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    security_metrics: Dict[str, Any] = Field(default_factory=dict, description="Smart contract security signals")
    liquidity_metrics: Dict[str, Any] = Field(default_factory=dict, description="Liquidity depth and provider stability")
    ownership_metrics: Dict[str, Any] = Field(default_factory=dict, description="Token distribution and top holder behavior")
    smart_money_metrics: Dict[str, Any] = Field(default_factory=dict, description="Whale and smart money flow")
    developer_history: Dict[str, Any] = Field(default_factory=dict, description="Creator past performance and behavior")
    social_traction: Dict[str, Any] = Field(default_factory=dict, description="Twitter, Telegram, and narrative momentum")
    narrative_strength: Dict[str, Any] = Field(default_factory=dict, description="Alignment with current market narratives")
    valuation_metrics: Dict[str, Any] = Field(default_factory=dict, description="Market cap, FDV, volume metrics")
    market_regime: str = Field(default="neutral", description="Overall market condition (e.g., bull, bear, crab)")
    execution_conditions: Dict[str, Any] = Field(default_factory=dict, description="Gas fees, slippage, MEV risk")
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


# --- Outputs from the AI Research Layer ---

class ObservedFacts(BaseModel):
    """
    Strictly observed facts derived from on-chain and off-chain data,
    separated from AI interpretations.
    """
    liquidity_state: str = Field(..., description="Factual state of liquidity (e.g., 'Locked for 1 year', 'Decreased 20% in 1h')")
    ownership_state: str = Field(..., description="Factual state of ownership (e.g., 'Top 10 hold 80%', 'Dev sold 5%')")
    social_state: str = Field(..., description="Factual social state (e.g., '1000 mentions/hour', 'Endorsed by influencer X')")
    security_state: str = Field(..., description="Factual security state (e.g., 'Mint function enabled', 'Audit passed')")
    smart_money_state: str = Field(..., description="Factual smart money state (e.g., 'Net inflow of $50k from 3 whales')")


class TokenAssessment(BaseModel):
    """
    The AI's synthesized assessment of the token opportunity.
    """
    bull_case: str = Field(..., description="The optimistic scenario and reasons it could succeed")
    bear_case: str = Field(..., description="The pessimistic scenario and reasons it could fail")
    risk_summary: str = Field(..., description="Summary of key risks (security, financial, narrative)")
    opportunity_summary: str = Field(..., description="Executive summary of the opportunity")
    historical_comparison: str = Field(..., description="Comparison to past similar tokens/events")
    similar_token_analysis: str = Field(..., description="How it stacks up against current competitors")
    thesis_durability: str = Field(..., description="How long this thesis is expected to hold (e.g., 'short-term momentum', 'long-term hold')")


class ValidationCriteria(BaseModel):
    """
    Defines what future events would support or invalidate the thesis.
    """
    supporting_signals: List[str] = Field(default_factory=list, description="Future observations that would strengthen the thesis")
    invalidating_signals: List[str] = Field(default_factory=list, description="Future observations that would break the thesis (e.g., 'LP removal', 'Dev sells remaining allocation')")


class ResearchThesis(BaseModel):
    """
    The complete, coherent token thesis produced by the AI layer.
    """
    thesis_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    token_address: str = Field(...)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    observed_facts: ObservedFacts = Field(..., description="The factual basis for the thesis")
    assessment: TokenAssessment = Field(..., description="The AI's interpretation and comparison")
    validation: ValidationCriteria = Field(..., description="Conditions that validate or invalidate the thesis")
    
    overall_conviction: float = Field(..., description="Overall conviction score from 0.0 to 1.0")
    recommended_action: str = Field(..., description="E.g., 'STRONG BUY', 'ACCUMULATE', 'HOLD', 'AVOID', 'SELL'")
    
    raw_prompt: Optional[str] = Field(default=None, description="The prompt sent to the LLM (for debugging)")
    raw_response: Optional[str] = Field(default=None, description="The raw response from the LLM (for debugging)")


class ChangeDetectionResult(BaseModel):
    """
    Result of comparing new intelligence against an existing thesis.
    """
    token_address: str = Field(...)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    previous_thesis_id: str = Field(...)
    
    is_material_change: bool = Field(..., description="True if a significant shift has occurred")
    change_description: str = Field(..., description="Description of what changed (e.g., 'Massive LP removal detected, invalidating previous safety thesis')")
    affected_areas: List[str] = Field(default_factory=list, description="Areas affected (e.g., 'liquidity', 'security', 'social')")
    requires_new_thesis: bool = Field(..., description="True if the change is large enough to require generating a new thesis")

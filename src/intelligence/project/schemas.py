from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

class GraphNode(BaseModel):
    id: str
    node_type: str = Field(..., description="E.g., WALLET, CONTRACT, REPO, SOCIAL_HANDLE, TREASURY")
    attributes: Dict[str, Any] = Field(default_factory=dict)

class GraphEdge(BaseModel):
    source_id: str
    target_id: str
    edge_type: str = Field(..., description="E.g., DEPLOYED, FUNDED, CONTRIBUTED_TO, ASSOCIATED_WITH")
    attributes: Dict[str, Any] = Field(default_factory=dict)

class DeveloperGraph(BaseModel):
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TeamActivity(BaseModel):
    project_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    communication_frequency: float = Field(default=0.0, description="Messages/announcements per day")
    meaningful_commit_count: int = Field(default=0, description="Commits excluding automated/bot changes")
    roadmap_milestones_completed: int = Field(default=0)
    partnerships_announced: int = Field(default=0)
    
    # Determines if activity feels genuine vs superficial
    activity_authenticity_score: float = Field(default=1.0, description="0.0 to 1.0 (1.0 = highly genuine)")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TreasuryState(BaseModel):
    treasury_wallets: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    total_value_usd: float = Field(default=0.0)
    inflows_24h_usd: float = Field(default=0.0)
    outflows_24h_usd: float = Field(default=0.0)
    
    exchange_transfers_usd: float = Field(default=0.0, description="Funds sent to CEXs")
    liquidity_interactions_usd: float = Field(default=0.0, description="Funds added/removed from DEX liquidity")
    unexplained_movements_usd: float = Field(default=0.0, description="Transfers lacking clear project justification")
    
    risk_level: str = Field(default="LOW", description="LOW, MEDIUM, HIGH based on unexplained movements")

class DeveloperReputation(BaseModel):
    developer_id: str = Field(..., description="Primary identifier (wallet, GitHub handle, etc.)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    historical_success_rate: float = Field(default=0.0, description="0.0 to 1.0 based on past projects surviving/thriving")
    abandoned_projects_count: int = Field(default=0)
    rug_patterns_detected: int = Field(default=0)
    suspicious_liquidity_events: int = Field(default=0)
    
    transparency_score: float = Field(default=0.5, description="0.0 to 1.0")
    communication_consistency: float = Field(default=0.5, description="0.0 to 1.0")
    
    trust_score: float = Field(default=0.5, description="Probabilistic trust score (0.0 to 1.0)")
    
    metadata: Dict[str, Any] = Field(default_factory=dict)

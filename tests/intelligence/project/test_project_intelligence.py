import pytest
from datetime import datetime, timezone
from src.intelligence.project import (
    DeveloperGraphBuilder,
    TeamMonitor,
    TreasuryAnalyzer,
    DeveloperReputationEngine,
    DeveloperGraph,
    TeamActivity,
    TreasuryState,
    DeveloperReputation
)

def test_developer_graph_builder():
    builder = DeveloperGraphBuilder()
    builder.add_node("dev1", "WALLET")
    builder.add_node("contract1", "CONTRACT", {"project_status": "SUCCESS"})
    builder.add_node("contract2", "CONTRACT", {"project_status": "RUG"})
    
    builder.add_edge("dev1", "contract1", "DEPLOYED")
    builder.add_edge("dev1", "contract2", "DEPLOYED")
    
    graph = builder.build_developer_graph()
    assert isinstance(graph, DeveloperGraph)
    assert len(graph.nodes) == 3
    assert len(graph.edges) == 2
    
    analysis = builder.analyze_developer_history("dev1")
    assert analysis["total_projects"] == 2
    assert analysis["success_rate"] == 0.5
    assert analysis["rug_patterns"] == 1
    assert analysis["abandoned_count"] == 0

def test_team_monitor():
    monitor = TeamMonitor("proj1")
    
    commits = [
        {"author": "dev1", "message": "Implemented core trading logic"},
        {"author": "dev1", "message": "Fixed bug in routing"},
        {"author": "dependabot", "message": "Bump requests from 2.25.1 to 2.26.0"},
        {"author": "dev2", "message": "Update README.md"}
    ]
    
    meaningful = monitor.evaluate_github_activity(commits)
    assert meaningful == 2  # First two are meaningful
    
    activity = monitor.track_activity(
        communication_events=10,
        days_active=5.0,
        github_commits=commits,
        milestones_met=1,
        partnerships=0
    )
    
    assert isinstance(activity, TeamActivity)
    assert activity.communication_frequency == 2.0
    assert activity.meaningful_commit_count == 2
    assert activity.activity_authenticity_score > 0.5  # Should be reasonably high

def test_treasury_analyzer():
    analyzer = TreasuryAnalyzer(treasury_wallets=["treasury1"])
    
    txs = [
        # Inflow
        {"sender": "user1", "receiver": "treasury1", "amount_usd": 1000.0, "justification": ""},
        # Legitimate outflow
        {"sender": "treasury1", "receiver": "dev_wallet", "amount_usd": 500.0, "justification": "Salary"},
        # CEX transfer
        {"sender": "treasury1", "receiver": "binance_deposit", "amount_usd": 2000.0, "justification": ""},
        # Unexplained movement
        {"sender": "treasury1", "receiver": "unknown_wallet", "amount_usd": 3000.0, "justification": ""}
    ]
    
    state = analyzer.analyze_transactions(txs)
    
    assert state.inflows_24h_usd == 1000.0
    assert state.outflows_24h_usd == 5500.0
    assert state.exchange_transfers_usd == 2000.0
    assert state.unexplained_movements_usd == 3000.0
    assert state.risk_level == "HIGH"

def test_reputation_engine():
    engine = DeveloperReputationEngine("dev1")
    
    graph_analysis = {
        "success_rate": 0.8,
        "abandoned_count": 0,
        "rug_patterns": 0,
        "suspicious_events": 0,
        "is_new_developer": False
    }
    
    team_activity = TeamActivity(
        project_id="proj1",
        communication_frequency=3.0,
        meaningful_commit_count=10,
        activity_authenticity_score=0.9
    )
    
    treasury_state = TreasuryState(
        treasury_wallets=["t1"],
        risk_level="LOW",
        unexplained_movements_usd=0.0
    )
    
    rep = engine.calculate_reputation(graph_analysis, team_activity, treasury_state, transparency_score=0.9)
    
    assert isinstance(rep, DeveloperReputation)
    assert rep.trust_score > 0.8  # Should be very high given good metrics
    
    # Test penalty
    graph_analysis["rug_patterns"] = 1
    rep_bad = engine.calculate_reputation(graph_analysis, team_activity, treasury_state, transparency_score=0.9)
    assert rep_bad.trust_score < rep.trust_score

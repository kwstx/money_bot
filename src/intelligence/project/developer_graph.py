from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import networkx as nx
from .schemas import DeveloperGraph, GraphNode, GraphEdge

class DeveloperGraphBuilder:
    """Constructs a graph connecting developer entities (wallets, contracts, socials)."""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        
    def add_node(self, node_id: str, node_type: str, attributes: Optional[Dict[str, Any]] = None):
        """Adds a node to the developer graph."""
        attrs = attributes or {}
        self.graph.add_node(node_id, type=node_type, **attrs)
        
    def add_edge(self, source_id: str, target_id: str, edge_type: str, attributes: Optional[Dict[str, Any]] = None):
        """Adds a directed edge representing an association."""
        attrs = attributes or {}
        self.graph.add_edge(source_id, target_id, type=edge_type, **attrs)
        
    def build_developer_graph(self) -> DeveloperGraph:
        """Exports the internal NetworkX graph to a DeveloperGraph schema object."""
        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            node_type = data.get("type", "UNKNOWN")
            attrs = {k: v for k, v in data.items() if k != "type"}
            nodes.append(GraphNode(id=node_id, node_type=node_type, attributes=attrs))
            
        edges = []
        for u, v, data in self.graph.edges(data=True):
            edge_type = data.get("type", "ASSOCIATED")
            attrs = {k: v for k, v in data.items() if k != "type"}
            edges.append(GraphEdge(source_id=u, target_id=v, edge_type=edge_type, attributes=attrs))
            
        return DeveloperGraph(nodes=nodes, edges=edges)
        
    def analyze_developer_history(self, developer_wallet: str) -> Dict[str, Any]:
        """
        Analyzes the graph to determine the developer's history:
        - Successful deliveries
        - Abandoned projects
        - Suspicious liquidity events
        - Repeated rug-like patterns
        """
        if developer_wallet not in self.graph:
            return {
                "success_rate": 0.0,
                "abandoned_count": 0,
                "rug_patterns": 0,
                "suspicious_events": 0,
                "is_new_developer": True
            }
            
        # Find all projects/contracts deployed by this wallet
        deployed_contracts = [
            v for u, v, data in self.graph.edges(data=True) 
            if u == developer_wallet and data.get("type") == "DEPLOYED"
        ]
        
        abandoned_count = 0
        rug_patterns = 0
        suspicious_events = 0
        success_count = 0
        
        for contract in deployed_contracts:
            node_data = self.graph.nodes[contract]
            status = node_data.get("project_status", "UNKNOWN")
            
            if status == "ABANDONED":
                abandoned_count += 1
            elif status == "RUG":
                rug_patterns += 1
            elif status == "SUCCESS":
                success_count += 1
                
            if node_data.get("has_suspicious_liquidity_event", False):
                suspicious_events += 1
                
        total_projects = len(deployed_contracts)
        success_rate = (success_count / total_projects) if total_projects > 0 else 0.0
        
        return {
            "success_rate": success_rate,
            "abandoned_count": abandoned_count,
            "rug_patterns": rug_patterns,
            "suspicious_events": suspicious_events,
            "is_new_developer": total_projects == 0,
            "total_projects": total_projects
        }

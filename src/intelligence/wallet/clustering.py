import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from src.intelligence.schemas import DecodedTransaction
from src.intelligence.wallet.schemas import WalletProfile

logger = logging.getLogger(__name__)

class WalletClusteringEngine:
    """
    Identifies clusters and relationships between wallets based on common funding sources,
    repeated counterparties, synchronized trading, common deployments, and timing patterns.
    """
    def __init__(self, sync_trade_window_seconds: float = 60.0):
        self.sync_trade_window_seconds = sync_trade_window_seconds

    def cluster_profiles(self, profiles: List[WalletProfile]) -> List[Dict[str, Any]]:
        """
        Analyzes a list of wallet profiles to detect and group related wallets (clusters).
        Returns a list of clusters with metadata explaining the links.
        """
        relationships = self.detect_relationships(profiles)
        
        # Build adjacency list
        adj = defaultdict(set)
        rel_by_pair = {}
        
        for rel in relationships:
            w1, w2 = rel["wallet_a"], rel["wallet_b"]
            adj[w1].add(w2)
            adj[w2].add(w1)
            pair_key = tuple(sorted([w1, w2]))
            if pair_key not in rel_by_pair:
                rel_by_pair[pair_key] = []
            rel_by_pair[pair_key].append(rel)

        # Find connected components (clusters) using BFS
        visited = set()
        clusters = []
        
        for profile in profiles:
            addr = profile.address.lower()
            if addr in visited:
                continue
                
            # BFS to find component
            component = []
            queue = [addr]
            visited.add(addr)
            
            while queue:
                curr = queue.pop(0)
                component.append(curr)
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            
            if len(component) > 1:
                # Gather links within this component
                cluster_links = []
                for i in range(len(component)):
                    for j in range(i + 1, len(component)):
                        pk = tuple(sorted([component[i], component[j]]))
                        if pk in rel_by_pair:
                            cluster_links.extend(rel_by_pair[pk])
                            
                clusters.append({
                    "cluster_id": f"cluster_{component[0][:8]}",
                    "wallets": component,
                    "links": cluster_links,
                    "size": len(component)
                })
                
        return clusters

    def detect_relationships(self, profiles: List[WalletProfile]) -> List[Dict[str, Any]]:
        """
        Detects direct peer-to-peer relationships between a set of wallet profiles.
        Returns a list of relationships with details and confidence scores.
        """
        relationships = []
        n = len(profiles)
        
        # Group structures to make detection efficient
        funding_to_wallets = defaultdict(list)
        counterparties_to_wallets = defaultdict(list)
        
        for p in profiles:
            addr = p.address.lower()
            # 1. Map funding sources
            for f in p.funding_sources:
                funding_to_wallets[f.sender_address.lower()].append((addr, f))
            # 2. Map counterparties
            for c_addr in p.top_counterparties.keys():
                counterparties_to_wallets[c_addr.lower()].append(addr)

        # 1. Detect Common Funding Relationships
        for f_source, funded in funding_to_wallets.items():
            if f_source == "0xunknown" or len(funded) < 2:
                continue
            # All pairs in 'funded' share the same funding source
            for i in range(len(funded)):
                for j in range(i + 1, len(funded)):
                    w1, f1 = funded[i]
                    w2, f2 = funded[j]
                    time_diff = abs((f1.timestamp - f2.timestamp).total_seconds())
                    
                    # Confidence is high for common funding, boosted if funded close in time
                    confidence = 0.90
                    if time_diff <= 1800:  # within 30 mins
                        confidence = 0.99
                        
                    relationships.append({
                        "relation_type": "common_funding",
                        "wallet_a": w1,
                        "wallet_b": w2,
                        "confidence": confidence,
                        "details": {
                            "funding_source": f_source,
                            "time_difference_seconds": int(time_diff),
                            "funding_a_tx": f1.tx_hash,
                            "funding_b_tx": f2.tx_hash
                        }
                    })

        # 2. Detect Direct Counterparty / Multi-hop Connections
        # If A and B interact directly
        for i in range(n):
            for j in range(i + 1, n):
                p1 = profiles[i]
                p2 = profiles[j]
                w1 = p1.address.lower()
                w2 = p2.address.lower()
                
                # Check if w1 is a counterparty of w2 or vice versa
                c1 = p1.top_counterparties.get(w2)
                c2 = p2.top_counterparties.get(w1)
                
                if c1 or c2:
                    total_count = (c1.incoming_count + c1.outgoing_count if c1 else 0) + \
                                  (c2.incoming_count + c2.outgoing_count if c2 else 0)
                    total_vol = (c1.total_volume_usd if c1 else 0.0) + (c2.total_volume_usd if c2 else 0.0)
                    
                    confidence = 0.50
                    if total_count >= 5 or total_vol >= 1000.0:
                        confidence = 0.90
                    elif total_count >= 2:
                        confidence = 0.75
                        
                    relationships.append({
                        "relation_type": "direct_counterparty",
                        "wallet_a": w1,
                        "wallet_b": w2,
                        "confidence": confidence,
                        "details": {
                            "transaction_count": total_count,
                            "volume_usd": round(total_vol, 2)
                        }
                    })

        # 3. Detect Synchronized Trading (Co-trading within window)
        for i in range(n):
            for j in range(i + 1, n):
                p1 = profiles[i]
                p2 = profiles[j]
                w1 = p1.address.lower()
                w2 = p2.address.lower()
                
                # Find overlapping tokens in positions
                common_tokens = set(p1.positions.keys()).intersection(p2.positions.keys())
                
                for token in common_tokens:
                    pos1 = p1.positions[token]
                    pos2 = p2.positions[token]
                    
                    # We look at last trade time or metadata to identify close-time executions
                    if pos1.last_trade_time and pos2.last_trade_time:
                        time_diff = abs((pos1.last_trade_time - pos2.last_trade_time).total_seconds())
                        if time_diff <= self.sync_trade_window_seconds:
                            # Synchronized trade detected
                            confidence = 0.70
                            if time_diff <= 10.0: # high-speed synchronization
                                confidence = 0.85
                                
                            relationships.append({
                                "relation_type": "synchronized_trade",
                                "wallet_a": w1,
                                "wallet_b": w2,
                                "confidence": confidence,
                                "details": {
                                    "token_address": token,
                                    "time_difference_seconds": int(time_diff),
                                    "last_trade_time_a": pos1.last_trade_time.isoformat(),
                                    "last_trade_time_b": pos2.last_trade_time.isoformat()
                                }
                            })

        # 4. Detect Common Deployment behavior (e.g. dev/creator contract matches)
        for i in range(n):
            for j in range(i + 1, n):
                p1 = profiles[i]
                p2 = profiles[j]
                w1 = p1.address.lower()
                w2 = p2.address.lower()
                
                # Check if both deployed contracts
                if p1.behavior.contracts_deployed_count > 0 and p2.behavior.contracts_deployed_count > 0:
                    # Let's say if they have active hours similarity > 80%, or explicit deployment metadata
                    # For mock/heuristic, we check if they deploy contracts within 5 minutes of each other (stored in metadata)
                    d_times1 = p1.metadata.get("deployment_timestamps", [])
                    d_times2 = p2.metadata.get("deployment_timestamps", [])
                    
                    for dt1_str in d_times1:
                        for dt2_str in d_times2:
                            try:
                                dt1 = datetime.fromisoformat(dt1_str)
                                dt2 = datetime.fromisoformat(dt2_str)
                                diff = abs((dt1 - dt2).total_seconds())
                                if diff <= 300: # deployed within 5 minutes
                                    relationships.append({
                                        "relation_type": "common_deployment",
                                        "wallet_a": w1,
                                        "wallet_b": w2,
                                        "confidence": 0.85,
                                        "details": {
                                            "time_difference_seconds": int(diff),
                                            "deployment_time_a": dt1_str,
                                            "deployment_time_b": dt2_str
                                        }
                                    })
                                    break
                            except ValueError:
                                pass

        return relationships

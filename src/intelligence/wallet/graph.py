import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)

class WalletGraphEngine:
    """
    Constructs, maintains, and traverses the wallet relationship graph.
    Retains confidence levels for every relationship and allows investigators
    and AI agents to trace paths (e.g. multi-hop funding paths) to related wallets,
    developers, pools, exchanges, and projects.
    """
    def __init__(self):
        # address (lower) -> Node metadata {"address": str, "type": str, "properties": dict}
        self.nodes: Dict[str, Dict[str, Any]] = {}
        # address (lower) -> list of edges: (target_address, rel_type, confidence, properties)
        # We store both incoming and outgoing edges for traversal
        self.outgoing_edges: Dict[str, List[Tuple[str, str, float, Dict[str, Any]]]] = defaultdict(list)
        self.incoming_edges: Dict[str, List[Tuple[str, str, float, Dict[str, Any]]]] = defaultdict(list)

    def add_node(self, address: str, node_type: str = "wallet", properties: Optional[Dict[str, Any]] = None) -> None:
        """Adds or updates a node in the graph."""
        addr = address.lower()
        self.nodes[addr] = {
            "address": addr,
            "type": node_type.upper(),  # WALLET, DEVELOPER, EXCHANGE, POOL, PROJECT
            "properties": properties or {}
        }

    def add_relationship(
        self,
        source: str,
        target: str,
        rel_type: str,
        confidence: float,
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Adds a directed relationship (edge) between two nodes with a confidence score.
        Automatically registers nodes if they don't exist.
        """
        src = source.lower()
        tgt = target.lower()
        rel = rel_type.upper()  # FUNDED, COUNTERPARTY, CO_TRADER, DEPLOYER, LIQUIDITY_PROVIDER
        conf = max(0.0, min(1.0, confidence))
        props = properties or {}

        # Ensure nodes exist
        if src not in self.nodes:
            self.add_node(src, "wallet")
        if tgt not in self.nodes:
            self.add_node(tgt, "wallet")

        # Check if identical relationship already exists. If yes, take the higher confidence
        self.outgoing_edges[src] = [e for e in self.outgoing_edges[src] if not (e[0] == tgt and e[1] == rel)]
        self.outgoing_edges[src].append((tgt, rel, conf, props))

        self.incoming_edges[tgt] = [e for e in self.incoming_edges[tgt] if not (e[0] == src and e[1] == rel)]
        self.incoming_edges[tgt].append((src, rel, conf, props))
        
        logger.debug(f"Added graph edge: {src} -[{rel} ({conf:.2f})]-> {tgt}")

    def get_node(self, address: str) -> Optional[Dict[str, Any]]:
        """Retrieve node info."""
        return self.nodes.get(address.lower())

    def get_neighbors(self, address: str) -> List[Dict[str, Any]]:
        """Returns all direct neighbors, their node details, edge details, and direction."""
        addr = address.lower()
        neighbors = []

        # Outgoing neighbors
        for tgt, rel, conf, props in self.outgoing_edges[addr]:
            node_info = self.nodes.get(tgt, {"address": tgt, "type": "WALLET", "properties": {}})
            neighbors.append({
                "address": tgt,
                "node_type": node_info["type"],
                "relation_type": rel,
                "direction": "OUTGOING",
                "confidence": conf,
                "properties": props
            })

        # Incoming neighbors
        for src, rel, conf, props in self.incoming_edges[addr]:
            node_info = self.nodes.get(src, {"address": src, "type": "WALLET", "properties": {}})
            neighbors.append({
                "address": src,
                "node_type": node_info["type"],
                "relation_type": rel,
                "direction": "INCOMING",
                "confidence": conf,
                "properties": props
            })

        return neighbors

    def traverse(
        self,
        start_address: str,
        max_hops: int = 3,
        min_confidence: float = 0.50
    ) -> List[Dict[str, Any]]:
        """
        Traverses the graph starting from start_address up to max_hops.
        Calculates cumulative path confidence (multiplied along edges) and filters by min_confidence.
        Returns a list of traversed nodes with their path and accumulated confidence.
        """
        start = start_address.lower()
        if start not in self.nodes:
            return []

        # BFS Queue elements: (curr_node, current_hops, cumulative_confidence, path_list)
        queue = [(start, 0, 1.0, [start])]
        visited: Dict[str, float] = {start: 1.0}  # node -> max confidence reached
        results = []

        while queue:
            curr, hops, cum_conf, path = queue.pop(0)

            node_info = self.nodes[curr]
            # Exclude start node from results
            if curr != start:
                results.append({
                    "address": curr,
                    "node_type": node_info["type"],
                    "hops": hops,
                    "path_confidence": round(cum_conf, 4),
                    "path": path
                })

            if hops >= max_hops:
                continue

            # Find all direct outgoing and incoming edges for traversal
            neighbors = []
            for tgt, rel, conf, _ in self.outgoing_edges[curr]:
                neighbors.append((tgt, conf))
            for src, rel, conf, _ in self.incoming_edges[curr]:
                neighbors.append((src, conf))

            for neighbor, edge_conf in neighbors:
                next_conf = cum_conf * edge_conf
                if next_conf < min_confidence:
                    continue

                # If neighbor not visited, or visited with a lower confidence path
                if neighbor not in visited or next_conf > visited[neighbor]:
                    visited[neighbor] = next_conf
                    queue.append((neighbor, hops + 1, next_conf, path + [neighbor]))

        return results

    def trace_funding_flow(self, start_address: str, max_depth: int = 5) -> List[Dict[str, Any]]:
        """
        Traces BACKWARDS along FUNDED edges to find the source of funds.
        Multiplies confidence scores down the path.
        Stops early if a node type is EXCHANGE or if we exceed max_depth.
        Returns the path step-by-step with confidence scores.
        """
        start = start_address.lower()
        if start not in self.nodes:
            return []

        # BFS queue for backward tracing: (curr_node, depth, cum_conf, path_steps)
        # path_steps is a list of dicts describing the hop details
        queue = [(start, 0, 1.0, [])]
        paths_found = []

        while queue:
            curr, depth, cum_conf, steps = queue.pop(0)

            node_info = self.nodes.get(curr, {"type": "WALLET"})
            
            # If we hit an Exchange or reached max depth, or if we have at least one hop, record path
            if node_info["type"] == "EXCHANGE" or depth >= max_depth:
                if steps:
                    paths_found.append({
                        "source_node": curr,
                        "source_type": node_info["type"],
                        "depth": depth,
                        "cumulative_confidence": round(cum_conf, 4),
                        "path": steps
                    })
                continue

            # Find incoming FUNDED edges (who funded 'curr'?)
            funders = [e for e in self.incoming_edges[curr] if e[1] == "FUNDED"]

            if not funders:
                # No more funders. This is the terminal node of this funding chain.
                if steps:
                    paths_found.append({
                        "source_node": curr,
                        "source_type": node_info["type"],
                        "depth": depth,
                        "cumulative_confidence": round(cum_conf, 4),
                        "path": steps
                    })
                continue

            for funder, _, edge_conf, props in funders:
                next_conf = cum_conf * edge_conf
                step_detail = {
                    "from": funder,
                    "to": curr,
                    "edge_confidence": edge_conf,
                    "tx_hash": props.get("tx_hash"),
                    "amount": props.get("amount"),
                    "timestamp": props.get("timestamp")
                }
                queue.append((funder, depth + 1, next_conf, steps + [step_detail]))

        # Return sorted by depth (shortest paths first) and then confidence
        paths_found.sort(key=lambda x: (x["depth"], -x["cumulative_confidence"]))
        return paths_found

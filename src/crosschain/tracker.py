import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from ..discovery.schemas import (
    CrossChainAssetGroup,
    CrossChainTokenRepresentation,
)

logger = logging.getLogger(__name__)

class CrossChainTracker:
    """
    Cross-Chain Intelligence & Asset Tracker.
    Connects related token deployments across chains, tracks bridges, migrations,
    and wrapped assets, while aggregating non-double-counted metrics.
    """

    def __init__(self):
        self.asset_groups: Dict[str, CrossChainAssetGroup] = {}
        self.token_to_group_map: Dict[str, str] = {} # "chain:address" -> group_id

    def create_or_get_group(self, symbol: str, name: str) -> CrossChainAssetGroup:
        canonical_symbol = symbol.upper().strip()
        for group in self.asset_groups.values():
            if group.canonical_symbol == canonical_symbol:
                return group

        new_group = CrossChainAssetGroup(
            asset_name=name,
            canonical_symbol=canonical_symbol,
            representations=[],
            bridges=[],
            total_aggregated_liquidity_usd=0.0,
            total_aggregated_volume_24h_usd=0.0,
            total_deduplicated_holders=0
        )
        self.asset_groups[new_group.group_id] = new_group
        return new_group

    def link_token_to_group(
        self,
        group_id: str,
        chain: str,
        token_address: str,
        pool_address: Optional[str] = None,
        is_canonical: bool = False,
        is_wrapped: bool = False,
        bridge_protocol: Optional[str] = None,
        liquidity_usd: float = 0.0,
        volume_24h_usd: float = 0.0,
        holder_count: int = 0
    ) -> CrossChainAssetGroup:
        group = self.asset_groups.get(group_id)
        if not group:
            raise KeyError(f"CrossChainAssetGroup {group_id} not found.")

        token_key = f"{chain}:{token_address.lower()}"

        # Prevent duplicate representation entry
        existing_rep = None
        for rep in group.representations:
            if rep.chain == chain and rep.token_address.lower() == token_address.lower():
                existing_rep = rep
                break

        if existing_rep:
            existing_rep.pool_address = pool_address or existing_rep.pool_address
            existing_rep.liquidity_usd = liquidity_usd
            existing_rep.volume_24h_usd = volume_24h_usd
            existing_rep.holder_count = holder_count
            existing_rep.is_wrapped = is_wrapped
            existing_rep.bridge_protocol = bridge_protocol
        else:
            rep = CrossChainTokenRepresentation(
                chain=chain,
                token_address=token_address,
                pool_address=pool_address,
                is_canonical=is_canonical,
                is_wrapped=is_wrapped,
                bridge_protocol=bridge_protocol,
                liquidity_usd=liquidity_usd,
                volume_24h_usd=volume_24h_usd,
                holder_count=holder_count
            )
            group.representations.append(rep)

        self.token_to_group_map[token_key] = group_id
        self._recalculate_group_metrics(group)
        logger.info(f"[CrossChain] Linked {token_key} to group {group.canonical_symbol} ({group_id})")
        return group

    def record_bridge_event(
        self,
        source_chain: str,
        source_token: str,
        target_chain: str,
        target_token: str,
        bridge_protocol: str,
        amount: float
    ) -> None:
        src_key = f"{source_chain}:{source_token.lower()}"
        group_id = self.token_to_group_map.get(src_key)

        if not group_id:
            group = self.create_or_get_group(symbol="CROSS_ASSET", name="Cross-Chain Asset")
            group_id = group.group_id
            self.link_token_to_group(group_id, source_chain, source_token)

        self.link_token_to_group(group_id, target_chain, target_token, is_wrapped=True, bridge_protocol=bridge_protocol)

        group = self.asset_groups[group_id]
        group.bridges.append({
            "source_chain": source_chain,
            "source_token": source_token,
            "target_chain": target_chain,
            "target_token": target_token,
            "bridge_protocol": bridge_protocol,
            "amount": amount,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        self._recalculate_group_metrics(group)

    def _recalculate_group_metrics(self, group: CrossChainAssetGroup) -> None:
        """
        Recalculates group metrics while preventing double counting.
        Wrapped / derivative tokens are excluded from primary liquidity sums if canonical exists.
        """
        total_liq = 0.0
        total_vol = 0.0
        max_holders = 0

        canonical_reps = [r for r in group.representations if r.is_canonical]

        for rep in group.representations:
            # If canonical reps exist, ignore pure wrapped tokens to prevent double counting
            if canonical_reps and rep.is_wrapped and not rep.is_canonical:
                continue

            total_liq += rep.liquidity_usd
            total_vol += rep.volume_24h_usd
            max_holders = max(max_holders, rep.holder_count)

        group.total_aggregated_liquidity_usd = round(total_liq, 2)
        group.total_aggregated_volume_24h_usd = round(total_vol, 2)
        # Unique holder estimation without double counting across chains
        group.total_deduplicated_holders = max_holders
        group.updated_at = datetime.now(timezone.utc)

    def get_group_for_token(self, chain: str, token_address: str) -> Optional[CrossChainAssetGroup]:
        token_key = f"{chain}:{token_address.lower()}"
        group_id = self.token_to_group_map.get(token_key)
        if group_id:
            return self.asset_groups.get(group_id)
        return None

cross_chain_tracker = CrossChainTracker()

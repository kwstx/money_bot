import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from .schemas import SupplyBreakdown, SupplyEvent, ValuationAnalysis

logger = logging.getLogger(__name__)

class ValuationEngine:
    """
    Valuation Engine.
    Maintains token supply distribution across categories (total, circulating, burned, locked, treasury, exchange),
    calculates Market Cap, FDV, and Effective Market Cap / Liquidity ratios,
    detects material supply events (minting, burning, unlocks, releases, migrations),
    and estimates valuation confidence and circulating supply assumptions.
    """

    def __init__(self, material_supply_change_pct: float = 0.01):  # 1% shift is material
        self.material_supply_change_pct = material_supply_change_pct
        self.supply_store: Dict[str, SupplyBreakdown] = {}
        self.supply_events: Dict[str, List[SupplyEvent]] = {}
        self.valuation_history: Dict[str, List[ValuationAnalysis]] = {}

    def set_supply_breakdown(
        self, token_address: str, chain: str, breakdown: SupplyBreakdown
    ) -> None:
        key = f"{chain}:{token_address.lower()}"
        self.supply_store[key] = breakdown

    def record_supply_event(
        self, token_address: str, chain: str, event: SupplyEvent
    ) -> ValuationAnalysis:
        key = f"{chain}:{token_address.lower()}"
        if key not in self.supply_events:
            self.supply_events[key] = []
        
        self.supply_events[key].append(event)
        
        # Apply event to existing supply breakdown if available
        breakdown = self.supply_store.get(
            key, SupplyBreakdown(total_supply=100_000_000, circulating_supply=100_000_000)
        )
        
        pct_change = (event.amount / breakdown.total_supply) if breakdown.total_supply > 0 else 0.0
        event.pct_of_total_supply = round(pct_change, 4)

        if event.event_type == "MINT":
            breakdown.total_supply += event.amount
            breakdown.circulating_supply += event.amount
        elif event.event_type == "BURN":
            breakdown.burned_supply += event.amount
            breakdown.circulating_supply = max(0.0, breakdown.circulating_supply - event.amount)
        elif event.event_type == "UNLOCK" or event.event_type == "TREASURY_RELEASE":
            breakdown.locked_supply = max(0.0, breakdown.locked_supply - event.amount)
            breakdown.circulating_supply += event.amount

        self.supply_store[key] = breakdown
        return self.calculate_valuation(token_address, chain, price_usd=0.0)

    def calculate_valuation(
        self,
        token_address: str,
        chain: str,
        price_usd: float,
        total_liquidity_usd: float = 0.0,
        custom_assumptions: Optional[List[str]] = None,
    ) -> ValuationAnalysis:
        key = f"{chain}:{token_address.lower()}"
        supply = self.supply_store.get(
            key, SupplyBreakdown(total_supply=100_000_000, circulating_supply=100_000_000)
        )
        events = self.supply_events.get(key, [])
        now = datetime.now(timezone.utc)

        # Basic calculations
        circulating = supply.circulating_supply
        total = supply.total_supply
        
        market_cap_usd = circulating * price_usd
        fdv_usd = total * price_usd

        # Effective Market Cap to Liquidity Ratio
        emc_ratio = (market_cap_usd / total_liquidity_usd) if total_liquidity_usd > 0 else 0.0

        # Confidence Estimation based on supply data completeness
        assumptions: List[str] = custom_assumptions or []
        confidence_score = 1.0

        if supply.circulating_supply == supply.total_supply and supply.locked_supply == 0:
            assumptions.append("Assuming 100% circulating supply (no explicit lockup/vesting data verified)")
            confidence_score -= 0.15

        if supply.treasury_supply == 0 and supply.locked_supply == 0:
            assumptions.append("Treasury and team unvested tokens are unmapped")
            confidence_score -= 0.15

        if price_usd <= 0:
            confidence_score = 0.0
            assumptions.append("Price is unverified or zero")

        confidence_score = max(0.0, min(1.0, confidence_score))

        analysis = ValuationAnalysis(
            token_address=token_address,
            chain=chain,
            price_usd=round(price_usd, 8),
            market_cap_usd=round(market_cap_usd, 2),
            fdv_usd=round(fdv_usd, 2),
            supply=supply,
            effective_market_cap_ratio=round(emc_ratio, 2),
            valuation_confidence_score=round(confidence_score, 4),
            circulating_supply_assumptions=assumptions,
            recent_supply_events=events[-10:],  # last 10 events
            updated_at=now,
        )

        # Store in history
        if key not in self.valuation_history:
            self.valuation_history[key] = []
        self.valuation_history[key].append(analysis)
        if len(self.valuation_history[key]) > 50:
            self.valuation_history[key] = self.valuation_history[key][-50:]

        return analysis

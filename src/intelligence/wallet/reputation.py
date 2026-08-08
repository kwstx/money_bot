import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from src.intelligence.wallet.schemas import WalletProfile, ReputationLabel
from src.intelligence.wallet.graph import WalletGraphEngine

logger = logging.getLogger(__name__)

class WalletReputationEngine:
    """
    Evaluates and assigns reversible, evidence-driven labels to wallets.
    Labels include SMART_MONEY, WHALE, RETAIL, DEVELOPER, INSIDER_CANDIDATE,
    EXCHANGE, MARKET_MAKER, LIQUIDITY_PROVIDER, TREASURY, BOT, and UNKNOWN.
    """
    def __init__(
        self,
        whale_volume_threshold: float = 100000.0,
        bot_velocity_threshold: float = 50.0,
        smart_money_score_threshold: float = 75.0
    ):
        self.whale_volume_threshold = whale_volume_threshold
        self.bot_velocity_threshold = bot_velocity_threshold
        self.smart_money_score_threshold = smart_money_score_threshold

    def evaluate_reputation(
        self,
        profile: WalletProfile,
        graph_engine: Optional[WalletGraphEngine] = None
    ) -> List[ReputationLabel]:
        """
        Runs all reputation rules on a wallet profile and returns the active labels.
        Older labels are replaced, keeping categorization reversible and up-to-date.
        """
        now = datetime.now(timezone.utc)
        labels: List[ReputationLabel] = []

        total_vol = sum(c.total_volume_usd for c in profile.top_counterparties.values())
        total_txs = profile.behavior.swap_count + profile.behavior.transfer_count + profile.behavior.liquidity_ops_count

        # 1. BOT Rule
        # High velocity (trades/day), or high total transactions with zero holding time, or metadata flag
        bot_evidence = []
        if profile.behavior.trade_velocity_24h >= self.bot_velocity_threshold:
            bot_evidence.append(f"High trade velocity: {profile.behavior.trade_velocity_24h} trades/24h")
        # Check active hour distribution: if transactions are spread across 24h, likely automated
        active_hours_count = sum(1 for h in profile.behavior.active_hours if h > 0)
        if active_hours_count >= 18 and total_txs >= 100:
            bot_evidence.append(f"Automated active hours profile (active in {active_hours_count}/24 hours)")
        if profile.metadata.get("is_bot") or profile.metadata.get("bot_flag"):
            bot_evidence.append("Flagged as bot in transaction logs")

        if bot_evidence:
            labels.append(ReputationLabel(
                label="BOT",
                confidence=0.90 if len(bot_evidence) > 1 else 0.70,
                evidence=bot_evidence,
                assigned_at=now
            ))

        # 2. DEVELOPER Rule
        # Deployed contracts
        dev_evidence = []
        if profile.behavior.contracts_deployed_count > 0:
            dev_evidence.append(f"Deployed {profile.behavior.contracts_deployed_count} contract(s)")
        if profile.metadata.get("is_developer") or profile.metadata.get("is_deployer"):
            dev_evidence.append("Identified as developer/deployer in creation logs")

        if dev_evidence:
            labels.append(ReputationLabel(
                label="DEVELOPER",
                confidence=0.99,
                evidence=dev_evidence,
                assigned_at=now
            ))

        # 3. EXCHANGE Rule
        # Direct counterparty to CEX or containing CEX labels
        cex_evidence = []
        for c_addr, summary in profile.top_counterparties.items():
            if any(k in c_addr.lower() for k in ["binance", "coinbase", "kraken", "kucoin", "okx", "bybit", "hotbit"]):
                cex_evidence.append(f"Direct transfers to/from known CEX: {c_addr}")
        if profile.metadata.get("is_exchange") or "exchange" in profile.metadata.get("labels", []):
            cex_evidence.append("Flagged as exchange hot/cold wallet in registries")

        if cex_evidence:
            labels.append(ReputationLabel(
                label="EXCHANGE",
                confidence=0.95,
                evidence=cex_evidence,
                assigned_at=now
            ))

        # 4. TREASURY Rule
        # Multisig tags or multisig sender
        treasury_evidence = []
        if profile.metadata.get("is_treasury") or profile.metadata.get("is_multisig"):
            treasury_evidence.append("Identified multisig treasury contract")
        if profile.behavior.liquidity_ops_count > 10 and total_vol > 500000 and profile.behavior.swap_count == 0:
            # Mostly transfers/liquidity, likely treasury operations
            treasury_evidence.append("High volume transfer/liquidity patterns with zero swaps")

        if treasury_evidence:
            labels.append(ReputationLabel(
                label="TREASURY",
                confidence=0.90,
                evidence=treasury_evidence,
                assigned_at=now
            ))

        # 5. LIQUIDITY_PROVIDER Rule
        # Adds or removes liquidity
        lp_evidence = []
        if profile.behavior.liquidity_ops_count > 0:
            lp_evidence.append(f"Executed {profile.behavior.liquidity_ops_count} liquidity addition/removal events")
        
        if lp_evidence:
            labels.append(ReputationLabel(
                label="LIQUIDITY_PROVIDER",
                confidence=0.95,
                evidence=lp_evidence,
                assigned_at=now
            ))

        # 6. MARKET_MAKER Rule
        # Balanced swap volumes, high swap count, and very short holding periods
        mm_evidence = []
        if (profile.behavior.swap_count >= 30 and 
            profile.behavior.average_holding_period_seconds > 0 and 
            profile.behavior.average_holding_period_seconds < 3600): # < 1 hour
            
            # Check balanced buy/sell volume
            buys_vol = sum(p.total_bought_usd for p in profile.positions.values())
            sells_vol = sum(p.total_sold_usd for p in profile.positions.values())
            total_trade_vol = buys_vol + sells_vol
            if total_trade_vol > 10000:
                imbalance = abs(buys_vol - sells_vol) / total_trade_vol if total_trade_vol > 0 else 1.0
                if imbalance <= 0.20: # tightly balanced buy/sell pressure
                    mm_evidence.append(f"Balanced inventory swaps (imbalance: {imbalance:.2f}) with short holding time")

        if mm_evidence:
            labels.append(ReputationLabel(
                label="MARKET_MAKER",
                confidence=0.85,
                evidence=mm_evidence,
                assigned_at=now
            ))

        # 7. WHALE Rule
        # High balances or massive volumes
        whale_evidence = []
        if total_vol >= self.whale_volume_threshold:
            whale_evidence.append(f"High total trading volume: ${total_vol:,.2f}")
        for pos in profile.positions.values():
            if pos.current_balance * pos.average_buy_price >= 50000.0:
                whale_evidence.append(f"Holds single token position worth > $50,000")
                break

        if whale_evidence:
            labels.append(ReputationLabel(
                label="WHALE",
                confidence=0.90,
                evidence=whale_evidence,
                assigned_at=now
            ))

        # 8. SMART_MONEY Rule
        # Verified score >= threshold with at least min_trades
        sm_evidence = []
        if profile.score.score >= self.smart_money_score_threshold and profile.score.min_trades_satisfied:
            sm_evidence.append(f"High historical performance score: {profile.score.score}/100 across {profile.score.total_trades} trades")
        
        if sm_evidence:
            labels.append(ReputationLabel(
                label="SMART_MONEY",
                confidence=0.85,
                evidence=sm_evidence,
                assigned_at=now
            ))

        # 9. INSIDER_CANDIDATE Rule
        # Early buyer with high profits, especially if linked to developer/deployer in graph
        insider_evidence = []
        early_wins = []
        for token, pos in profile.positions.items():
            # Check if early entry score for position is high (implies bought near launch)
            # If they got a high ROI (>3x)
            roi = pos.realized_roi + pos.unrealized_roi
            if roi >= 3.0:
                # If we have early entry indication in score
                if profile.score.early_entry_score >= 80.0:
                    early_wins.append(token)

        if early_wins:
            insider_evidence.append(f"Early entry and high ROI (>3x) on token(s): {', '.join(early_wins)}")
            
            # Check graph for links to developers/creators
            if graph_engine:
                # Get backward paths to developer nodes
                relations = graph_engine.get_neighbors(profile.address)
                for r in relations:
                    if r["node_type"] == "DEVELOPER" or r["relation_type"] == "DEPLOYER":
                        insider_evidence.append(f"Direct relationship found to developer node: {r['address']}")
                        break

        if insider_evidence:
            labels.append(ReputationLabel(
                label="INSIDER_CANDIDATE",
                confidence=0.90 if any("developer" in e for e in insider_evidence) else 0.70,
                evidence=insider_evidence,
                assigned_at=now
            ))

        # 10. RETAIL Rule
        # Low trade volumes, low average prices, and none of the institutional/technical labels match
        retail_evidence = []
        if not labels: # default to retail if no institutional behaviors matches
            retail_evidence.append("Standard trading size and frequency; no programmatic, dev, CEX, or whale characteristics")
            labels.append(ReputationLabel(
                label="RETAIL",
                confidence=0.80,
                evidence=retail_evidence,
                assigned_at=now
            ))

        # Update profile list
        profile.reputation_labels = labels
        profile.updated_at = now
        return labels

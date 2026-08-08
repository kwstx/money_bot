import logging
import math
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from src.intelligence.wallet.schemas import WalletProfile, WalletScore

logger = logging.getLogger(__name__)

class WalletScoringEngine:
    """
    Evaluates wallet trading performance across early entry, consistency,
    risk-adjusted returns, token discovery success, holding discipline, and exit timing.
    Applies exponential decay over time and a Bayesian prior for low trade counts.
    """
    def __init__(self, min_trades_threshold: int = 5, decay_half_life_days: float = 90.0):
        self.min_trades_threshold = min_trades_threshold
        # decay_rate = ln(2) / half_life
        self.decay_rate = math.log(2.0) / max(1.0, decay_half_life_days)

    def calculate_and_update_score(
        self,
        profile: WalletProfile,
        token_launches: Optional[Dict[str, datetime]] = None,
        token_peak_prices: Optional[Dict[str, float]] = None
    ) -> WalletScore:
        """
        Calculates and updates all scoring dimensions for a WalletProfile.
        Returns the updated WalletScore.
        """
        now = datetime.now(timezone.utc)
        token_launches = token_launches or {}
        token_peak_prices = token_peak_prices or {}

        positions = list(profile.positions.values())
        total_trades = sum(p.trades_count for p in positions)
        
        if not positions or total_trades == 0:
            profile.score = WalletScore(
                score=50.0,
                early_entry_score=50.0,
                consistency_score=50.0,
                risk_adjusted_profit_score=50.0,
                holding_discipline_score=50.0,
                exit_timing_score=50.0,
                min_trades_satisfied=False,
                total_trades=0,
                last_updated=now
            )
            return profile.score

        # Collect dimension parameters with time decay weights
        decayed_wins = 0.0
        decayed_exits = 0.0
        weighted_rois = []
        weighted_early_entry_scores = []
        weighted_holding_discipline_scores = []
        weighted_exit_timing_scores = []
        
        # Track regime metrics (simple timestamp-based split: e.g. Bull vs Bear)
        # We define a dummy regime splitter based on year/month or metadata flag
        regime_trades = {"BULL": [], "BEAR": []}

        success_count_2x = 0
        success_count_5x = 0
        success_count_10x = 0

        for pos in positions:
            if pos.trades_count == 0 or not pos.last_trade_time:
                continue

            # Calculate time decay weight
            days_since_trade = (now - pos.last_trade_time).total_seconds() / 86400.0
            weight = math.exp(-self.decay_rate * days_since_trade)

            # Determine regime
            # Standard heuristic: let's look at profile metadata or timestamp
            # E.g. we classify trades in 2026/02-2026/08 as BULL, other as BEAR/NEUTRAL
            regime = "BULL" if pos.last_trade_time.year >= 2026 and pos.last_trade_time.month in [1, 2, 3, 4, 5, 6, 7, 8] else "BEAR"

            # 1. Win Rate & Consistency
            # Profitable means total return is positive
            pnl = pos.realized_pnl_usd + pos.unrealized_pnl_usd
            roi = pos.realized_roi + pos.unrealized_roi

            if pos.total_sold_tokens > 0 or pos.current_balance > 0:
                decayed_exits += weight
                if pnl > 0:
                    decayed_wins += weight
                weighted_rois.append((roi, weight))
                regime_trades[regime].append((pnl > 0, weight))

            # 2. Early-Entry Quality
            launch_time = token_launches.get(pos.token_address)
            if launch_time and pos.first_buy_time:
                gap_seconds = (pos.first_buy_time - launch_time).total_seconds()
                # If bought before launch (e.g. pre-sale) or at block 0
                gap_seconds = max(0.1, gap_seconds)
                # Score decay curve: 100 for immediate, decreases logarithmically
                # If gap is 1 min (60s), score = 100 - 10 * log(2) = 93
                # If gap is 24 hrs (86400s), score = 100 - 10 * log(1441) = ~27
                ee_score = max(0.0, 100.0 - 10.0 * math.log10(gap_seconds / 60.0 + 1.0))
                weighted_early_entry_scores.append((ee_score, weight))

            # 3. Success Identification ROI thresholds
            max_roi = max(pos.realized_roi, pos.unrealized_roi)
            if max_roi >= 10.0:
                success_count_10x += 1
            elif max_roi >= 5.0:
                success_count_5x += 1
            elif max_roi >= 2.0:
                success_count_2x += 1

            # 4. Holding Discipline
            # Panic selling penalty: if they exit at a loss and the token peak was high
            discipline = 50.0
            if pos.total_sold_tokens > 0:
                if pos.realized_roi < -0.30:
                    # Subtract points for selling at a substantial loss
                    discipline -= 20.0
                elif pos.realized_roi > 0.0:
                    # Add points for holding to a profit
                    discipline += 20.0
                    # Additional point for long holding periods
                    avg_hold = sum(pos.holding_periods) / len(pos.holding_periods) if pos.holding_periods else 0.0
                    if avg_hold > 86400: # held longer than a day
                        discipline += 10.0
            discipline = max(0.0, min(100.0, discipline))
            weighted_holding_discipline_scores.append((discipline, weight))

            # 5. Exit Timing Quality
            # Compare average sell price vs peak price observed
            peak_price = token_peak_prices.get(pos.token_address)
            if peak_price and peak_price > 0 and pos.total_sold_tokens > 0:
                avg_sell = pos.total_sold_usd / pos.total_sold_tokens if pos.total_sold_tokens > 0 else 0.0
                # Efficiency score: ratio of sell price to peak price
                exit_score = (avg_sell / peak_price) * 100.0
                weighted_exit_timing_scores.append((min(100.0, exit_score), weight))

        # --- Aggregate Dimensions ---
        
        # Consistency Score
        consistency_score = 50.0
        if decayed_exits > 0:
            consistency_score = (decayed_wins / decayed_exits) * 100.0

        # Risk-Adjusted Profitability Score (ROI mean/variance)
        risk_score = 50.0
        if weighted_rois:
            total_w = sum(w for _, w in weighted_rois)
            mean_roi = sum(r * w for r, w in weighted_rois) / total_w if total_w > 0 else 0.0
            
            # Variance calculation
            variance = 0.0
            if len(weighted_rois) > 1:
                variance = sum(w * ((r - mean_roi) ** 2) for r, w in weighted_rois) / total_w
            std_dev = math.sqrt(variance) if variance > 0 else 0.0
            
            # Sharpe-like ratio: mean / std_dev
            # If standard deviation is very low or 0, base score directly on mean_roi
            if std_dev > 0.01:
                sharpe_eq = mean_roi / std_dev
                # Map sharpe to score: sharpe of 1.0 -> 80, 2.0 -> 95, 0.0 -> 50, negative -> lower
                risk_score = 50.0 + 30.0 * math.tanh(sharpe_eq)
            else:
                # Direct mapping of mean ROI: ROI of 100% (1.0) -> 80, 500% (5.0) -> 95, 0% -> 50, -50% -> 25
                risk_score = 50.0 + 30.0 * math.tanh(mean_roi)
                
        # Ability to identify successful tokens booster
        # Combine success counts into a score booster
        success_score = min(100.0, 50.0 + (success_count_2x * 10) + (success_count_5x * 20) + (success_count_10x * 35))
        # Blend risk score with success identification score to form overall profitability dimension
        profitability_score = (risk_score * 0.6) + (success_score * 0.4)

        # Early Entry Score
        early_entry_score = 50.0
        if weighted_early_entry_scores:
            total_w = sum(w for _, w in weighted_early_entry_scores)
            early_entry_score = sum(s * w for s, w in weighted_early_entry_scores) / total_w

        # Holding Discipline Score
        holding_score = 50.0
        if weighted_holding_discipline_scores:
            total_w = sum(w for _, w in weighted_holding_discipline_scores)
            holding_score = sum(s * w for s, w in weighted_holding_discipline_scores) / total_w

        # Exit Timing Score
        exit_timing_score = 50.0
        if weighted_exit_timing_scores:
            total_w = sum(w for _, w in weighted_exit_timing_scores)
            exit_timing_score = sum(s * w for s, w in weighted_exit_timing_scores) / total_w

        # Compute Regime Scores
        regime_scores = {}
        for reg, trades in regime_trades.items():
            if trades:
                w_wins = sum(w for win, w in trades if win)
                w_total = sum(w for _, w in trades)
                regime_scores[reg] = (w_wins / w_total * 100.0) if w_total > 0 else 50.0
            else:
                regime_scores[reg] = 50.0

        # Calculate raw overall score (weighted average of all dimensions)
        raw_overall = (
            early_entry_score * 0.20 +
            consistency_score * 0.20 +
            profitability_score * 0.30 +
            holding_score * 0.15 +
            exit_timing_score * 0.15
        )

        # Apply Bayesian Prior/Smoothing for low trade count
        # Prevents permanently labeling a wallet as highly successful based on 1-2 lucky trades.
        min_satisfied = total_trades >= self.min_trades_threshold
        if total_trades < self.min_trades_threshold:
            # Smooth towards baseline 50.0
            smoothed_score = (raw_overall * total_trades + 50.0 * (self.min_trades_threshold - total_trades)) / self.min_trades_threshold
        else:
            smoothed_score = raw_overall

        updated_score = WalletScore(
            score=round(max(0.0, min(100.0, smoothed_score)), 2),
            early_entry_score=round(early_entry_score, 2),
            consistency_score=round(consistency_score, 2),
            risk_adjusted_profit_score=round(profitability_score, 2),
            holding_discipline_score=round(holding_score, 2),
            exit_timing_score=round(exit_timing_score, 2),
            regime_scores={k: round(v, 2) for k, v in regime_scores.items()},
            min_trades_satisfied=min_satisfied,
            total_trades=total_trades,
            last_updated=now
        )
        
        profile.score = updated_score
        return updated_score

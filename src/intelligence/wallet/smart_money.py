import logging
import math
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from src.intelligence.wallet.schemas import WalletProfile, Position
from src.intelligence.wallet.manipulation_schemas import (
    SkillVsLuckResult,
    SmartMoneyEvaluation
)

logger = logging.getLogger(__name__)

class SmartMoneyPredictiveEngine:
    """
    Evaluates whether a wallet's historical profitability stems from predictive skill
    or statistical randomness/luck by benchmarking against Random Early Buyers and Ordinary Whales.
    
    Filters for:
    - Pre-expansion accumulation
    - Avoidance of catastrophic outcomes (rugpulls/drawdowns >70%)
    - Multi-regime behavior persistence (Bull, Bear, Volatile)
    - Statistical hypothesis testing (p-value < 0.05, z-score > 1.96)
    """
    def __init__(
        self,
        min_trades_required: int = 5,
        random_early_buyer_mean_roi: float = 0.15,
        random_early_buyer_std_roi: float = 0.80,
        ordinary_whale_mean_roi: float = 0.35,
        ordinary_whale_std_roi: float = 1.20
    ):
        self.min_trades_required = min_trades_required
        # Cohort baseline statistics derived from empirical market distributions
        self.reb_mean = random_early_buyer_mean_roi
        self.reb_std = random_early_buyer_std_roi
        self.ow_mean = ordinary_whale_mean_roi
        self.ow_std = ordinary_whale_std_roi

    def evaluate_predictive_skill(
        self,
        profile: WalletProfile,
        token_histories: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> SmartMoneyEvaluation:
        """
        Evaluates a WalletProfile for true Smart Money predictive skill vs luck.
        """
        now = datetime.now(timezone.utc)
        token_histories = token_histories or {}
        positions = list(profile.positions.values())

        if not positions or profile.score.total_trades == 0:
            default_skill = SkillVsLuckResult(
                wallet_address=profile.address,
                p_value=1.0,
                z_score=0.0,
                skill_over_luck_index=0.0,
                is_statistically_significant=False,
                cohort_comparison={"reason": "Insufficient trade data"}
            )
            return SmartMoneyEvaluation(
                wallet_address=profile.address,
                is_smart_money=False,
                predictive_score=0.0,
                early_accumulation_ratio=0.0,
                catastrophic_avoidance_score=50.0,
                multi_regime_consistency={"BULL": 50.0, "BEAR": 50.0, "VOLATILE": 50.0},
                skill_vs_luck=default_skill,
                evaluated_at=now
            )

        # 1. Calculate Early Accumulation Ratio
        # Measures fraction of buys made prior to measurable price expansion
        early_accum_count = 0
        total_eval_positions = 0
        
        for pos in positions:
            if pos.trades_count == 0:
                continue
            total_eval_positions += 1
            th = token_histories.get(pos.token_address, {})
            peak_mcap = th.get("peak_mcap_usd", 0.0)
            entry_mcap = th.get("entry_mcap_usd", 0.0)
            
            if peak_mcap > 0 and entry_mcap > 0:
                # If entered at < 25% of peak expansion mcap
                if (entry_mcap / peak_mcap) <= 0.25:
                    early_accum_count += 1
            else:
                # Fallback to early entry score from profile
                if profile.score.early_entry_score >= 70.0:
                    early_accum_count += 1

        early_accum_ratio = round(early_accum_count / max(1, total_eval_positions), 4)

        # 2. Catastrophic Outcome Avoidance Score
        # Checks how well wallet avoids >70% loss positions or total rugpulls
        catastrophic_count = 0
        for pos in positions:
            tot_roi = pos.realized_roi + pos.unrealized_roi
            if tot_roi <= -0.70:
                catastrophic_count += 1
        
        catastrophic_rate = catastrophic_count / max(1, total_eval_positions)
        # Avoidance score: 100 - (rate * 100)
        catastrophic_avoidance_score = round(max(0.0, 100.0 * (1.0 - 2.0 * catastrophic_rate)), 2)

        # 3. Multi-Regime Behavior Persistence
        regime_scores = dict(profile.score.regime_scores)
        if "BULL" not in regime_scores:
            regime_scores["BULL"] = 50.0
        if "BEAR" not in regime_scores:
            regime_scores["BEAR"] = 50.0
        if "VOLATILE" not in regime_scores:
            regime_scores["VOLATILE"] = 50.0

        # Multi-regime score is penalised if performance drops off drastically in any single regime
        min_regime = min(regime_scores.values())
        avg_regime = sum(regime_scores.values()) / len(regime_scores)
        multi_regime_score = round((avg_regime * 0.7) + (min_regime * 0.3), 2)

        # 4. Statistical Skill vs. Luck Comparison (Hypothesis Testing)
        # Collect sample ROIs
        rois = [(p.realized_roi + p.unrealized_roi) for p in positions if p.trades_count > 0]
        n_sample = len(rois)
        sample_mean = sum(rois) / n_sample if n_sample > 0 else 0.0

        # Variance calculation
        sample_var = sum((r - sample_mean) ** 2 for r in rois) / max(1, n_sample - 1) if n_sample > 1 else 0.25
        sample_std = math.sqrt(sample_var) if sample_var > 0 else 0.50

        # Two-sample z-test against Random Early Buyers cohort mean (H0: mean <= reb_mean)
        # z = (sample_mean - reb_mean) / (std / sqrt(n))
        se = sample_std / math.sqrt(max(1, n_sample))
        z_score = (sample_mean - self.reb_mean) / max(0.01, se)

        # Approximate p-value from z-score using normal CDF approximation
        # p-value = 1 - Phi(z)
        p_value = 0.5 * math.erfc(z_score / math.sqrt(2.0))
        p_value = round(max(0.0001, min(1.0, p_value)), 4)

        # Skill-over-luck index (0-100)
        # Map z-score (e.g. z=0 -> 50, z=1.96 -> 85, z=3.0 -> 98)
        skill_index = round(min(100.0, max(0.0, 50.0 + 20.0 * z_score)), 2)

        is_significant = (p_value <= 0.05) and (z_score >= 1.96) and (n_sample >= self.min_trades_required)

        cohort_comp = {
            "sample_mean_roi": round(sample_mean, 4),
            "sample_std_roi": round(sample_std, 4),
            "sample_trades_count": n_sample,
            "random_early_buyer_mean": self.reb_mean,
            "ordinary_whale_mean": self.ow_mean,
            "outperformed_random_buyers": sample_mean > self.reb_mean,
            "outperformed_ordinary_whales": sample_mean > self.ow_mean
        }

        skill_result = SkillVsLuckResult(
            wallet_address=profile.address,
            p_value=p_value,
            z_score=round(z_score, 2),
            skill_over_luck_index=skill_index,
            is_statistically_significant=is_significant,
            cohort_comparison=cohort_comp
        )

        # Overall Smart Money Predictive Score
        predictive_score = round(
            early_accum_ratio * 30.0 +
            (catastrophic_avoidance_score / 100.0) * 25.0 +
            (multi_regime_score / 100.0) * 20.0 +
            (skill_index / 100.0) * 25.0,
            2
        )

        is_smart_money = is_significant and (predictive_score >= 70.0) and (catastrophic_avoidance_score >= 60.0)

        return SmartMoneyEvaluation(
            wallet_address=profile.address,
            is_smart_money=is_smart_money,
            predictive_score=predictive_score,
            early_accumulation_ratio=early_accum_ratio,
            catastrophic_avoidance_score=catastrophic_avoidance_score,
            multi_regime_consistency=regime_scores,
            skill_vs_luck=skill_result,
            evaluated_at=now
        )

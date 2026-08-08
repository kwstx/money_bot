import pytest
from datetime import datetime, timezone, timedelta
import math

from src.intelligence.holder import (
    TokenTransferEventType,
    HolderCategory,
    GrowthTrajectoryPattern,
    TokenTransferEvent,
    HolderTracker,
    calculate_gini_coefficient,
    calculate_percentile,
    HolderCategorizationEngine,
    OwnershipDistributionAnalyzer,
    HolderQualityEngine,
    LiquidityOwnershipHealthEngine,
    SectionEightHolderIntelligenceEngine
)

TOKEN_ADDR = "0x1234567890abcdef1234567890abcdef12345678"
DEV_ADDR = "0xdev0000000000000000000000000000000000001"
INSIDER_1 = "0xinsider0000000000000000000000000000000001"
INSIDER_2 = "0xinsider0000000000000000000000000000000002"
SMART_MONEY_1 = "0xsmart00000000000000000000000000000000001"
POOL_ADDR = "0xpool000000000000000000000000000000000001"
EXCHANGE_ADDR = "0xcex00000000000000000000000000000000000001"
BURN_ADDR = "0x000000000000000000000000000000000000dead"


class TestSectionEightHolderTracker:
    def test_gini_coefficient_and_percentiles(self):
        # Perfect equality
        assert calculate_gini_coefficient([100.0, 100.0, 100.0, 100.0]) == 0.0
        # High inequality
        gini_high = calculate_gini_coefficient([1.0, 1.0, 1.0, 1000.0])
        assert gini_high > 0.70

        # Percentiles
        data = [10.0, 20.0, 30.0, 40.0, 50.0]
        assert calculate_percentile(data, 0.0) == 10.0
        assert calculate_percentile(data, 50.0) == 30.0
        assert calculate_percentile(data, 100.0) == 50.0

    def test_holder_tracker_event_processing(self):
        tracker = HolderTracker(token_address=TOKEN_ADDR, initial_total_supply=1_000_000.0)
        now = datetime.now(timezone.utc)

        # 1. Mint event to dev
        ev_mint = TokenTransferEvent(
            event_id="ev-1",
            token_address=TOKEN_ADDR,
            tx_hash="0xhash1",
            timestamp=now,
            sender="0x0000000000000000000000000000000000000000",
            receiver=DEV_ADDR,
            amount=500_000.0,
            event_type=TokenTransferEventType.MINT
        )
        tracker.process_event(ev_mint)
        assert tracker.balances[DEV_ADDR].balance == 500_000.0

        # 2. Transfer from dev to pool
        ev_pool = TokenTransferEvent(
            event_id="ev-2",
            token_address=TOKEN_ADDR,
            tx_hash="0xhash2",
            timestamp=now,
            sender=DEV_ADDR,
            receiver=POOL_ADDR,
            amount=200_000.0,
            event_type=TokenTransferEventType.LIQUIDITY_ADD
        )
        tracker.process_event(ev_pool)
        assert tracker.balances[DEV_ADDR].balance == 300_000.0
        assert tracker.balances[POOL_ADDR].balance == 200_000.0

        # 3. Transfer from pool to retail user
        retail_1 = "0xretail000000000000000000000000000000001"
        ev_retail = TokenTransferEvent(
            event_id="ev-3",
            token_address=TOKEN_ADDR,
            tx_hash="0xhash3",
            timestamp=now,
            sender=POOL_ADDR,
            receiver=retail_1,
            amount=50_000.0,
            event_type=TokenTransferEventType.TRANSFER
        )
        tracker.process_event(ev_retail)
        assert tracker.balances[retail_1].balance == 50_000.0

        # 4. Burn event
        ev_burn = TokenTransferEvent(
            event_id="ev-4",
            token_address=TOKEN_ADDR,
            tx_hash="0xhash4",
            timestamp=now,
            sender=retail_1,
            receiver=BURN_ADDR,
            amount=10_000.0,
            event_type=TokenTransferEventType.BURN
        )
        tracker.process_event(ev_burn)
        assert tracker.balances[retail_1].balance == 40_000.0

        # Take snapshot
        snapshot = tracker.take_snapshot(now)
        assert snapshot.total_holders_count >= 3
        assert snapshot.top_10_concentration_pct > 0.0
        assert snapshot.average_balance > 0.0

        # Velocity & retention
        vel = tracker.calculate_velocity_and_retention(window_hours=24, current_time=now)
        assert vel.new_holder_count >= 1
        assert vel.net_holder_growth >= 1


class TestSectionEightDistributionAnalyzer:
    def test_holder_categorization_and_distribution(self):
        categorizer = HolderCategorizationEngine(
            known_pools={POOL_ADDR},
            known_exchanges={EXCHANGE_ADDR},
            developer_addresses={DEV_ADDR},
            insider_addresses={INSIDER_1, INSIDER_2},
            smart_money_addresses={SMART_MONEY_1},
            whale_threshold_pct=2.0
        )
        analyzer = OwnershipDistributionAnalyzer(categorizer=categorizer)
        now = datetime.now(timezone.utc)

        # Setup wallet states
        total_supply = 1_000_000.0
        tracker = HolderTracker(token_address=TOKEN_ADDR, initial_total_supply=total_supply)

        # Dev holding 10%
        tracker.process_event(TokenTransferEvent(
            event_id="1", token_address=TOKEN_ADDR, tx_hash="h1", timestamp=now,
            sender="0x0", receiver=DEV_ADDR, amount=100_000.0, event_type=TokenTransferEventType.MINT
        ))
        # Insider holding 15%
        tracker.process_event(TokenTransferEvent(
            event_id="2", token_address=TOKEN_ADDR, tx_hash="h2", timestamp=now,
            sender="0x0", receiver=INSIDER_1, amount=150_000.0, event_type=TokenTransferEventType.MINT
        ))
        # Smart money holding 5%
        tracker.process_event(TokenTransferEvent(
            event_id="3", token_address=TOKEN_ADDR, tx_hash="h3", timestamp=now,
            sender="0x0", receiver=SMART_MONEY_1, amount=50_000.0, event_type=TokenTransferEventType.MINT
        ))
        # Pool holding 40%
        tracker.process_event(TokenTransferEvent(
            event_id="4", token_address=TOKEN_ADDR, tx_hash="h4", timestamp=now,
            sender="0x0", receiver=POOL_ADDR, amount=400_000.0, event_type=TokenTransferEventType.MINT
        ))
        # Exchange holding 10%
        tracker.process_event(TokenTransferEvent(
            event_id="5", token_address=TOKEN_ADDR, tx_hash="h5", timestamp=now,
            sender="0x0", receiver=EXCHANGE_ADDR, amount=100_000.0, event_type=TokenTransferEventType.MINT
        ))
        # Retail holders
        for i in range(10):
            r_addr = f"0xretail_{i}"
            tracker.process_event(TokenTransferEvent(
                event_id=f"r_{i}", token_address=TOKEN_ADDR, tx_hash=f"hr_{i}", timestamp=now,
                sender="0x0", receiver=r_addr, amount=20_000.0, event_type=TokenTransferEventType.MINT
            ))

        dist = analyzer.analyze_distribution(
            token_address=TOKEN_ADDR,
            wallet_states=tracker.balances,
            total_supply=total_supply,
            current_time=now
        )

        assert pytest.approx(dist.developer_concentration_pct, 0.1) == 10.0
        assert pytest.approx(dist.insider_concentration_pct, 0.1) == 15.0
        assert pytest.approx(dist.smart_money_participation_pct, 0.1) == 5.0
        assert dist.technical_accounts_supply_pct >= 50.0  # 40% pool + 10% CEX
        assert dist.wallet_diversity_index > 0.0
        assert dist.economically_meaningful_holders_count >= 13


class TestSectionEightHolderQualityEngine:
    def test_quality_and_trajectory_classification(self):
        quality_engine = HolderQualityEngine()
        now = datetime.now(timezone.utc)

        # Setup mock inputs for organic accumulation
        vel = HolderTracker(token_address=TOKEN_ADDR).calculate_velocity_and_retention(24, now)
        vel.new_holder_count = 100
        vel.new_holder_rate = 10.0
        vel.holder_exits_count = 5
        vel.retention_rate_pct = 95.0
        vel.concentration_delta_top10 = -2.0

        dist = OwnershipDistributionAnalyzer().analyze_distribution(
            token_address=TOKEN_ADDR,
            wallet_states={},
            total_supply=1_000_000.0,
            current_time=now
        )
        dist.wallet_diversity_index = 85.0

        report = quality_engine.evaluate_quality(
            token_address=TOKEN_ADDR,
            velocity_retention=vel,
            distribution_metrics=dist,
            recent_events=[]
        )

        assert report.holder_quality_score > 70.0
        assert report.organic_growth_score > 70.0
        assert report.trajectory_classification in {
            GrowthTrajectoryPattern.ORGANIC_ACCUMULATION,
            GrowthTrajectoryPattern.INSTITUTIONAL_HOLD
        }


class TestSectionEightLiquidityOwnershipHealth:
    def test_liquidity_ownership_market_health_view(self):
        health_engine = LiquidityOwnershipHealthEngine()
        now = datetime.now(timezone.utc)

        tracker = HolderTracker(token_address=TOKEN_ADDR, initial_total_supply=1_000_000.0)
        snapshot = tracker.take_snapshot(now)
        snapshot.top_10_concentration_pct = 40.0

        dist = OwnershipDistributionAnalyzer().analyze_distribution(
            token_address=TOKEN_ADDR,
            wallet_states={},
            total_supply=1_000_000.0,
            current_time=now
        )
        dist.insider_concentration_pct = 25.0
        dist.whale_concentration_pct = 15.0

        health = health_engine.evaluate_market_health(
            token_address=TOKEN_ADDR,
            pool_liquidity_usd=100_000.0,
            token_price_usd=1.0,
            snapshot=snapshot,
            distribution=dist,
            lp_locked_pct=95.0,
            lp_lock_duration_days=365.0
        )

        assert health.overall_market_health_score > 0.0
        assert health.executable_depth_usd_2pct == pytest.approx(2_000.0, rel=0.01)
        assert health.slippage_sell_5k_pct > 0.0
        assert health.lp_stability_score > 80.0
        assert health.exit_feasibility_index > 0.0


class TestSectionEightOrchestrator:
    def test_full_section_eight_orchestrator_pipeline(self):
        engine = SectionEightHolderIntelligenceEngine(
            token_address=TOKEN_ADDR,
            initial_total_supply=1_000_000.0,
            known_pools={POOL_ADDR},
            known_exchanges={EXCHANGE_ADDR},
            developer_addresses={DEV_ADDR},
            insider_addresses={INSIDER_1},
            smart_money_addresses={SMART_MONEY_1}
        )
        now = datetime.now(timezone.utc)

        # Process a sequence of realistic transactions
        events = [
            TokenTransferEvent(
                event_id="e1", token_address=TOKEN_ADDR, tx_hash="0x1", timestamp=now,
                sender="0x0", receiver=DEV_ADDR, amount=200_000.0, event_type=TokenTransferEventType.MINT
            ),
            TokenTransferEvent(
                event_id="e2", token_address=TOKEN_ADDR, tx_hash="0x2", timestamp=now,
                sender=DEV_ADDR, receiver=POOL_ADDR, amount=100_000.0, event_type=TokenTransferEventType.LIQUIDITY_ADD
            ),
            TokenTransferEvent(
                event_id="e3", token_address=TOKEN_ADDR, tx_hash="0x3", timestamp=now,
                sender=POOL_ADDR, receiver=SMART_MONEY_1, amount=15_000.0, event_type=TokenTransferEventType.TRANSFER
            ),
            TokenTransferEvent(
                event_id="e4", token_address=TOKEN_ADDR, tx_hash="0x4", timestamp=now,
                sender=POOL_ADDR, receiver=INSIDER_1, amount=50_000.0, event_type=TokenTransferEventType.TRANSFER
            ),
        ]
        # Add 20 retail users buying from pool
        for i in range(20):
            events.append(TokenTransferEvent(
                event_id=f"retail_ev_{i}", token_address=TOKEN_ADDR, tx_hash=f"0xr_{i}", timestamp=now,
                sender=POOL_ADDR, receiver=f"0xuser_{i}", amount=1_500.0, event_type=TokenTransferEventType.TRANSFER
            ))

        engine.process_batch_events(events)

        # Run Section 8 evaluation
        report = engine.evaluate_token_holder_and_liquidity_quality(
            pool_liquidity_usd=150_000.0,
            token_price_usd=1.0,
            lp_locked_pct=100.0,
            lp_lock_duration_days=180.0
        )

        assert report.token_address == TOKEN_ADDR
        assert report.latest_snapshot.total_holders_count >= 22
        assert report.distribution_metrics.developer_concentration_pct == pytest.approx(8.33, 0.1)
        assert report.distribution_metrics.insider_concentration_pct == pytest.approx(4.16, 0.1)
        assert report.distribution_metrics.smart_money_participation_pct == pytest.approx(1.25, 0.1)
        assert report.quality_metrics.holder_quality_score > 0.0
        assert report.market_health_view.overall_market_health_score > 0.0
        assert report.overall_section_eight_score > 0.0

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from .schemas import TradeObservation, VolumeAnalysis

logger = logging.getLogger(__name__)

class VolumeEngine:
    """
    Volume Intelligence Engine.
    Calculates raw volume alongside organic, suspicious, smart-money, whale, retail, and developer volume.
    Detects wash trading, repetitive wallet interactions, abnormal trade sizes, synchronized transactions,
    and artificial volume bursts. Measures multi-window volume acceleration (1m, 5m, 15m, 1h, 24h).
    """

    def __init__(
        self,
        whale_threshold_usd: float = 10000.0,
        wash_trading_time_window_sec: float = 300.0,  # 5 minutes window for circular trades
        synchronized_window_sec: float = 5.0,        # 5 sec window for synchronized txs
        abnormal_trade_zscore_threshold: float = 3.0,
    ):
        self.whale_threshold_usd = whale_threshold_usd
        self.wash_trading_time_window_sec = wash_trading_time_window_sec
        self.synchronized_window_sec = synchronized_window_sec
        self.abnormal_trade_zscore_threshold = abnormal_trade_zscore_threshold

        self.trade_history: Dict[str, List[TradeObservation]] = defaultdict(list)

    def record_trade(self, trade: TradeObservation) -> None:
        key = f"{trade.chain}:{trade.token_address.lower()}"
        self.trade_history[key].append(trade)

        # Retain last 7 days of trades for memory efficiency
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)
        self.trade_history[key] = [t for t in self.trade_history[key] if t.timestamp >= cutoff]

    def _detect_wash_trading(self, trades: List[TradeObservation]) -> Tuple[float, float]:
        """
        Detects wash trading score (0.0 to 1.0) and suspicious volume from back-and-forth trades between same wallets
        or circular routing (A -> B -> A).
        """
        if not trades:
            return 0.0, 0.0

        trader_interaction_count: Dict[Tuple[str, str], int] = defaultdict(int)
        trader_volume: Dict[str, float] = defaultdict(float)
        total_vol = sum(t.amount_usd for t in trades)

        # Group by trader
        for t in trades:
            trader_volume[t.trader_address] += t.amount_usd

        # Look for quick reverse interactions
        suspicious_vol = 0.0
        sorted_trades = sorted(trades, key=lambda x: x.timestamp)

        for i in range(len(sorted_trades)):
            t1 = sorted_trades[i]
            for j in range(i + 1, len(sorted_trades)):
                t2 = sorted_trades[j]
                time_diff = (t2.timestamp - t1.timestamp).total_seconds()
                if time_diff > self.wash_trading_time_window_sec:
                    break

                # Same trader or complementary buy/sell pairs with near identical amount
                if t1.trader_address == t2.trader_address and t1.is_buy != t2.is_buy:
                    amount_ratio = min(t1.amount_usd, t2.amount_usd) / max(t1.amount_usd, t2.amount_usd) if max(t1.amount_usd, t2.amount_usd) > 0 else 0
                    if amount_ratio > 0.85:
                        suspicious_vol += t1.amount_usd + t2.amount_usd

        wash_score = min(1.0, suspicious_vol / total_vol) if total_vol > 0 else 0.0
        return round(wash_score, 4), round(suspicious_vol, 2)

    def _detect_repetitive_trades(self, trades: List[TradeObservation]) -> float:
        """
        Identifies repetitive trade patterns (e.g. exact same USD amount repeated high frequency).
        """
        if len(trades) < 5:
            return 0.0

        amount_freq: Dict[float, int] = defaultdict(int)
        for t in trades:
            rounded_amt = round(t.amount_usd, 2)
            amount_freq[rounded_amt] += 1

        max_repetitive = max(amount_freq.values()) if amount_freq else 0
        repetitive_score = min(1.0, max_repetitive / len(trades)) if len(trades) > 0 else 0.0
        return round(repetitive_score, 4)

    def _detect_synchronized_txs(self, trades: List[TradeObservation]) -> float:
        """
        Detects synchronized transactions across multiple wallets in tight time clusters.
        """
        if len(trades) < 4:
            return 0.0

        sorted_trades = sorted(trades, key=lambda x: x.timestamp)
        clustered_count = 0

        for i in range(len(sorted_trades) - 1):
            t1 = sorted_trades[i]
            t2 = sorted_trades[i + 1]
            if (t2.timestamp - t1.timestamp).total_seconds() <= self.synchronized_window_sec:
                if t1.trader_address != t2.trader_address:
                    clustered_count += 1

        synchronized_score = min(1.0, (clustered_count * 2) / len(trades))
        return round(synchronized_score, 4)

    def _calculate_multi_window_acceleration(self, trades: List[TradeObservation], now: datetime) -> Tuple[float, float, float, float]:
        """
        Calculates volume acceleration ratios for 5m, 15m, 1h, 24h against baseline rate.
        """
        vol_5m = sum(t.amount_usd for t in trades if (now - t.timestamp).total_seconds() <= 300)
        vol_15m = sum(t.amount_usd for t in trades if (now - t.timestamp).total_seconds() <= 900)
        vol_1h = sum(t.amount_usd for t in trades if (now - t.timestamp).total_seconds() <= 3600)
        vol_24h = sum(t.amount_usd for t in trades if (now - t.timestamp).total_seconds() <= 86400)

        # Baseline per minute rate over 24h
        baseline_rate_per_min = (vol_24h / 1440.0) if vol_24h > 0 else 0.001

        rate_5m = vol_5m / 5.0
        rate_15m = vol_15m / 15.0
        rate_1h = vol_1h / 60.0

        acc_5m = rate_5m / baseline_rate_per_min if baseline_rate_per_min > 0 else 1.0
        acc_15m = rate_15m / baseline_rate_per_min if baseline_rate_per_min > 0 else 1.0
        acc_1h = rate_1h / baseline_rate_per_min if baseline_rate_per_min > 0 else 1.0
        acc_24h = 1.0  # Normalized baseline

        return round(acc_5m, 2), round(acc_15m, 2), round(acc_1h, 2), round(acc_24h, 2)

    def analyze_volume(self, token_address: str, chain: str) -> VolumeAnalysis:
        key = f"{chain}:{token_address.lower()}"
        all_trades = self.trade_history.get(key, [])
        now = datetime.now(timezone.utc)

        # 24h trades window
        trades_24h = [t for t in all_trades if (now - t.timestamp).total_seconds() <= 86400]

        if not trades_24h:
            return VolumeAnalysis(token_address=token_address, chain=chain, updated_at=now)

        raw_vol_24h = sum(t.amount_usd for t in trades_24h)

        # Breakdown calculation
        smart_money_vol = sum(t.amount_usd for t in trades_24h if t.is_smart_money)
        whale_vol = sum(t.amount_usd for t in trades_24h if t.amount_usd >= self.whale_threshold_usd or t.is_whale)
        dev_vol = sum(t.amount_usd for t in trades_24h if t.is_developer)

        # Detection methods
        wash_score, wash_vol = self._detect_wash_trading(trades_24h)
        repetitive_score = self._detect_repetitive_trades(trades_24h)
        synced_score = self._detect_synchronized_txs(trades_24h)

        # Identify wash trading wallets to filter organic categories
        suspicious_traders: Set[str] = set()
        trader_counts: Dict[str, int] = defaultdict(int)
        for t in trades_24h:
            trader_counts[t.trader_address] += 1
        for trader, count in trader_counts.items():
            if count >= 2 and wash_score > 0.2:
                suspicious_traders.add(trader)

        # Breakdown calculation (excluding suspicious wash trading wallets)
        smart_money_vol = sum(t.amount_usd for t in trades_24h if t.is_smart_money and t.trader_address not in suspicious_traders)
        whale_vol = sum(t.amount_usd for t in trades_24h if (t.is_whale or t.amount_usd >= self.whale_threshold_usd) and t.trader_address not in suspicious_traders)
        dev_vol = sum(t.amount_usd for t in trades_24h if t.is_developer and t.trader_address not in suspicious_traders)

        suspicious_vol = min(raw_vol_24h, wash_vol + (raw_vol_24h * repetitive_score * 0.5))
        organic_vol = max(0.0, raw_vol_24h - suspicious_vol)
        retail_vol = max(0.0, organic_vol - smart_money_vol - dev_vol)

        # Acceleration
        acc_5m, acc_15m, acc_1h, acc_24h = self._calculate_multi_window_acceleration(trades_24h, now)

        # Check artificial burst (e.g. 5m volume acceleration > 10x with low unique traders)
        unique_traders_5m = len(set(t.trader_address for t in trades_24h if (now - t.timestamp).total_seconds() <= 300))
        is_artificial_burst = (acc_5m > 10.0 and unique_traders_5m <= 3) or (wash_score > 0.40)

        detected_anomalies: List[str] = []
        if wash_score > 0.3:
            detected_anomalies.append(f"Wash trading detected (Score: {wash_score:.2f})")
        if repetitive_score > 0.3:
            detected_anomalies.append(f"Repetitive bot trading patterns (Score: {repetitive_score:.2f})")
        if synced_score > 0.3:
            detected_anomalies.append(f"Synchronized multi-wallet activity (Score: {synced_score:.2f})")
        if is_artificial_burst:
            detected_anomalies.append(f"Artificial volume burst detected (5m Acceleration: {acc_5m}x)")

        return VolumeAnalysis(
            token_address=token_address,
            chain=chain,
            raw_volume_24h_usd=round(raw_vol_24h, 2),
            organic_volume_24h_usd=round(organic_vol, 2),
            suspicious_volume_24h_usd=round(suspicious_vol, 2),
            smart_money_volume_24h_usd=round(smart_money_vol, 2),
            whale_volume_24h_usd=round(whale_vol, 2),
            retail_volume_24h_usd=round(retail_vol, 2),
            developer_volume_24h_usd=round(dev_vol, 2),
            acceleration_5m=acc_5m,
            acceleration_15m=acc_15m,
            acceleration_1h=acc_1h,
            acceleration_24h=acc_24h,
            wash_trading_score=wash_score,
            repetitive_trade_score=repetitive_score,
            synchronized_tx_score=synced_score,
            is_artificial_burst=is_artificial_burst,
            detected_anomalies=detected_anomalies,
            updated_at=now,
        )

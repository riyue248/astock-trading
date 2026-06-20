"""
趋势策略 — MA排列 + MACD确认 + 金叉/死叉
"""
import pandas as pd

from engine.strategies.base import BaseStrategy, SignalResult


class TrendStrategy(BaseStrategy):
    name = "trend"

    def __init__(self, fast_ma=5, slow_ma=20, trend_ma=60):
        self.fast_ma = fast_ma
        self.slow_ma = slow_ma
        self.trend_ma = trend_ma

    def generate_signal(self, df: pd.DataFrame) -> SignalResult:
        if df.empty or len(df) < self.trend_ma:
            return SignalResult("hold", 0.0, 0.0, "insufficient data")

        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last

        ma_fast = last.get(f"ma{self.fast_ma}", 0)
        ma_slow = last.get(f"ma{self.slow_ma}", 0)
        ma_trend = last.get(f"ma{self.trend_ma}", 0)
        prev_ma_fast = prev.get(f"ma{self.fast_ma}", 0)
        prev_ma_slow = prev.get(f"ma{self.slow_ma}", 0)

        dif = last.get("macd_dif", 0)
        dea = last.get("macd_dea", 0)
        hist = last.get("macd_hist", 0)
        prev_hist = prev.get("macd_hist", 0)

        # 1. MA alignment score (-1 to +1)
        if ma_fast and ma_slow and ma_trend:
            if ma_fast > ma_slow > ma_trend:
                alignment_score = 1.0
            elif ma_fast > ma_slow:
                alignment_score = 0.5
            elif ma_fast < ma_slow < ma_trend:
                alignment_score = -1.0
            elif ma_fast < ma_slow:
                alignment_score = -0.5
            else:
                alignment_score = 0.0
        else:
            alignment_score = 0.0

        # 2. MACD momentum score
        if dif and dea:
            if dif > dea and hist > 0:
                macd_score = 1.0
            elif dif > dea:
                macd_score = 0.5
            elif dif < dea and hist < 0:
                macd_score = -1.0
            elif dif < dea:
                macd_score = -0.5
            else:
                macd_score = 0.0
        else:
            macd_score = 0.0

        # 3. Golden cross / Death cross detection
        golden_cross = (prev_ma_fast <= prev_ma_slow and ma_fast > ma_slow) if (prev_ma_fast and prev_ma_slow) else False
        death_cross = (prev_ma_fast >= prev_ma_slow and ma_fast < ma_slow) if (prev_ma_fast and prev_ma_slow) else False

        # Combine
        score = alignment_score * 0.5 + macd_score * 0.5

        if golden_cross and alignment_score > 0:
            action = "buy"
            confidence = min(0.9, (score + 1) / 2)  # Map to 0-0.9
        elif death_cross and alignment_score < 0:
            action = "sell"
            confidence = min(0.9, (-score + 1) / 2)
        elif alignment_score > 0.3 and macd_score > 0:
            action = "buy"
            confidence = 0.6
        elif alignment_score < -0.3 and macd_score < 0:
            action = "sell"
            confidence = 0.6
        else:
            action = "hold"
            confidence = 0.3

        reason = (f"MA{alignment_score:+.1f} MACD{macd_score:+.1f} "
                  f"{'GoldenX' if golden_cross else 'DeathX' if death_cross else ''}")

        return SignalResult(action, round(score, 4), round(confidence, 4), reason)

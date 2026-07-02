"""
趋势策略 — MA排列 + MACD确认 + 金叉/死叉
v2: 降低trend_ma到40（适配90天数据窗口），增加EMA fallback和NaN保护
"""
import numpy as np
import pandas as pd

from engine.strategies.base import BaseStrategy, SignalResult


class TrendStrategy(BaseStrategy):
    name = "trend"

    def __init__(self, fast_ma=5, slow_ma=20, trend_ma=40):
        self.fast_ma = fast_ma
        self.slow_ma = slow_ma
        self.trend_ma = trend_ma

    @staticmethod
    def _safe_val(series, key, default=0.0):
        """安全取值，过滤 NaN。"""
        v = series.get(key, default)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return default
        return v

    def generate_signal(self, df: pd.DataFrame) -> SignalResult:
        # 需要足够数据计算 MA(trend_ma) 和 MACD(26)
        min_rows = max(self.trend_ma, 26)
        if df.empty or len(df) < min_rows:
            return SignalResult("hold", 0.0, 0.0, "insufficient data")

        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last

        ma_fast = self._safe_val(last, f"ma{self.fast_ma}")
        ma_slow = self._safe_val(last, f"ma{self.slow_ma}")
        ma_trend = self._safe_val(last, f"ma{self.trend_ma}")

        # Fallback: 如果趋势MA不可用（数据不够），用EMA26替代
        if not ma_trend or ma_trend == 0:
            ma_trend = self._safe_val(last, "ema26")

        prev_ma_fast = self._safe_val(prev, f"ma{self.fast_ma}")
        prev_ma_slow = self._safe_val(prev, f"ma{self.slow_ma}")

        dif = self._safe_val(last, "macd_dif")
        dea = self._safe_val(last, "macd_dea")
        hist = self._safe_val(last, "macd_hist")
        prev_hist = self._safe_val(prev, "macd_hist")
        prev_dif = self._safe_val(prev, "macd_dif")
        prev_dea = self._safe_val(prev, "macd_dea")

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
        elif ma_fast and ma_slow:
            # 趋势MA不可用，只用快慢线
            if ma_fast > ma_slow:
                alignment_score = 0.6
            else:
                alignment_score = -0.6
        else:
            alignment_score = 0.0

        # 2. MACD momentum score — 增加柱状图变化趋势
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

            # MACD 柱收窄/放大加分
            if hist and prev_hist:
                if hist > prev_hist and hist > 0:
                    macd_score += 0.2  # 红柱放大→动能增强
                elif hist < prev_hist and hist < 0:
                    macd_score -= 0.2  # 绿柱放大→动能减弱
        else:
            macd_score = 0.0

        macd_score = max(-1.0, min(1.0, macd_score))

        # 3. Golden cross / Death cross detection
        golden_cross = False
        death_cross = False
        if prev_ma_fast and prev_ma_slow and ma_fast and ma_slow:
            golden_cross = (prev_ma_fast <= prev_ma_slow and ma_fast > ma_slow)
            death_cross = (prev_ma_fast >= prev_ma_slow and ma_fast < ma_slow)

        # 4. MACD 金叉/死叉辅助
        macd_golden = (prev_dif <= prev_dea and dif > dea) if (prev_dif and prev_dea and dif and dea) else False
        macd_death = (prev_dif >= prev_dea and dif < dea) if (prev_dif and prev_dea and dif and dea) else False

        # Combine
        score = alignment_score * 0.5 + macd_score * 0.5

        # Decision — 更多触发条件
        if golden_cross and alignment_score > 0:
            action = "buy"
            confidence = min(0.9, (score + 1) / 2)
        elif death_cross and alignment_score < 0:
            action = "sell"
            confidence = min(0.9, (-score + 1) / 2)
        elif alignment_score > 0.3 and macd_score > 0:
            action = "buy"
            confidence = 0.6
        elif alignment_score < -0.3 and macd_score < 0:
            action = "sell"
            confidence = 0.6
        elif macd_golden and alignment_score >= 0:
            action = "buy"
            confidence = 0.55
        elif macd_death and alignment_score <= 0:
            action = "sell"
            confidence = 0.55
        elif alignment_score > 0.5:
            action = "buy"
            confidence = 0.50
        elif alignment_score < -0.5:
            action = "sell"
            confidence = 0.50
        else:
            action = "hold"
            confidence = 0.3

        reason = (f"MA{alignment_score:+.1f} MACD{macd_score:+.1f} "
                  f"{'GoldenX' if golden_cross else 'DeathX' if death_cross else ''}"
                  f"{' MACD-X' if macd_golden or macd_death else ''}")

        return SignalResult(action, round(score, 4), round(confidence, 4), reason)

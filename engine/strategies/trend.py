"""
趋势策略 — MA排列 + MACD确认 + 金叉/死叉 + 成交量验证
v3: 连续化MA排列分数 + 金叉需放量确认 + NaN保护
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
        min_rows = max(self.trend_ma, 26)
        if df.empty or len(df) < min_rows:
            return SignalResult("hold", 0.0, 0.0, "insufficient data")

        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last

        ma_fast = self._safe_val(last, f"ma{self.fast_ma}")
        ma_slow = self._safe_val(last, f"ma{self.slow_ma}")
        ma_trend = self._safe_val(last, f"ma{self.trend_ma}")

        # Fallback: EMA26 if trend MA unavailable
        if not ma_trend or ma_trend == 0:
            ma_trend = self._safe_val(last, "ema26")

        prev_ma_fast = self._safe_val(prev, f"ma{self.fast_ma}")
        prev_ma_slow = self._safe_val(prev, f"ma{self.slow_ma}")

        # Volume for confirmation
        volume = self._safe_val(last, "volume")
        vol_ma5 = self._safe_val(last, "volume_ma5", 1.0)
        has_volume = volume > 0 and vol_ma5 > 0 and volume > vol_ma5

        dif = self._safe_val(last, "macd_dif")
        dea = self._safe_val(last, "macd_dea")
        hist = self._safe_val(last, "macd_hist")
        prev_hist = self._safe_val(prev, "macd_hist")
        prev_dif = self._safe_val(prev, "macd_dif")
        prev_dea = self._safe_val(prev, "macd_dea")

        # ── 1. MA alignment: 连续化分数 ──
        # 用 (fast - slow) / slow 的比例替代离散的 0/0.5/1.0
        # 映射到 [-1, 1] 范围
        if ma_fast and ma_slow and ma_trend:
            # 快慢线偏离程度
            slope = (ma_fast - ma_slow) / ma_slow  # e.g. 0.03 = 3% above
            alignment_base = np.tanh(slope * 20)   # tanh 平滑映射到 [-1, 1]
            # 趋势方向确认: 是否 MA快 > MA慢 > MA趋势
            if ma_fast > ma_slow > ma_trend:
                alignment_score = max(0.6, alignment_base)   # 完美多头，保底 0.6
            elif ma_fast > ma_slow:
                alignment_score = max(0.3, alignment_base * 0.7)
            elif ma_fast < ma_slow < ma_trend:
                alignment_score = min(-0.6, alignment_base)  # 完美空头，上限 -0.6
            elif ma_fast < ma_slow:
                alignment_score = min(-0.3, alignment_base * 0.7)
            else:
                alignment_score = alignment_base
        elif ma_fast and ma_slow:
            # 只有快慢线，无趋势线
            slope = (ma_fast - ma_slow) / ma_slow
            alignment_score = np.tanh(slope * 20) * 1.2
            alignment_score = max(-1.0, min(1.0, alignment_score))
        else:
            alignment_score = 0.0

        # ── 2. MACD momentum score ──
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

            # MACD 柱变化趋势
            if hist and prev_hist:
                if hist > prev_hist and hist > 0:
                    macd_score += 0.2  # 红柱放大
                elif hist < prev_hist and hist < 0:
                    macd_score -= 0.2  # 绿柱放大
        else:
            macd_score = 0.0

        macd_score = max(-1.0, min(1.0, macd_score))

        # ── 3. Golden cross / Death cross ──
        golden_cross = False
        death_cross = False
        if prev_ma_fast and prev_ma_slow and ma_fast and ma_slow:
            golden_cross = (prev_ma_fast <= prev_ma_slow and ma_fast > ma_slow)
            death_cross = (prev_ma_fast >= prev_ma_slow and ma_fast < ma_slow)

        # ── 4. MACD 金叉/死叉 ──
        macd_golden = (prev_dif <= prev_dea and dif > dea) if (prev_dif and prev_dea and dif and dea) else False
        macd_death = (prev_dif >= prev_dea and dif < dea) if (prev_dif and prev_dea and dif and dea) else False

        # ── Combine score ──
        score = alignment_score * 0.5 + macd_score * 0.5

        # ── Decision ──
        # 金叉买入需要成交量确认（防止无量空涨假突破）
        if golden_cross and alignment_score > 0 and has_volume:
            action = "buy"
            confidence = min(0.9, (score + 1) / 2)
        elif golden_cross and alignment_score > 0 and not has_volume:
            # 金叉但无量 → 降级为弱买入
            action = "buy"
            confidence = 0.40
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

        vol_tag = "Vol+" if has_volume else ""
        reason = (f"MA{alignment_score:+.1f} MACD{macd_score:+.1f} "
                  f"{'GoldenX' if golden_cross else 'DeathX' if death_cross else ''}"
                  f"{' MACD-X' if macd_golden or macd_death else ''}"
                  f"{' ' + vol_tag if vol_tag else ''}")

        return SignalResult(action, round(score, 4), round(confidence, 4), reason)

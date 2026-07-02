"""
反转策略 — RSI超买超卖 + KDJ背离 + 布林带位置 + 反弹确认
v2: RSI/KDJ去重（取max不累加）+ 买入需反弹确认
"""
import pandas as pd
import numpy as np

from engine.strategies.base import BaseStrategy, SignalResult


class ReversalStrategy(BaseStrategy):
    name = "reversal"

    def __init__(self, rsi_period=14, oversold=30, overbought=70):
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought

    @staticmethod
    def _safe_val(series, key, default=0.0):
        v = series.get(key, default)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return default
        return v

    def generate_signal(self, df: pd.DataFrame) -> SignalResult:
        if df.empty or len(df) < 20:
            return SignalResult("hold", 0.0, 0.0, "insufficient data")

        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last

        close = self._safe_val(last, "close")
        open_p = self._safe_val(last, "open")
        prev_close = self._safe_val(prev, "close")
        prev_low = self._safe_val(prev, "low")
        rsi_val = self._safe_val(last, "rsi14", 50)
        k = self._safe_val(last, "kdj_k", 50)
        d = self._safe_val(last, "kdj_d", 50)
        j = self._safe_val(last, "kdj_j", 50)
        boll_upper = self._safe_val(last, "boll_upper")
        boll_lower = self._safe_val(last, "boll_lower")

        # ── 反弹确认条件 ──
        # 买入前必须满足以下至少一项:
        #   a) 今日收阳 (close > open)
        #   b) 今日收盘高于昨日最低 (close > prev_low, 不再创新低)
        #   c) 今日收盘高于昨日收盘 (close > prev_close, 止跌)
        bounce_confirmed = (close > open_p) or (close > prev_low) or (close > prev_close)
        is_bullish_candle = close > open_p

        reasons = []
        buy_score = 0.0
        sell_score = 0.0

        # ── 1. RSI extremes ──
        if rsi_val and not np.isnan(rsi_val):
            if rsi_val < self.oversold:
                buy_score += 0.4
                reasons.append(f"RSI({rsi_val:.0f})<{self.oversold}")
            elif rsi_val < 40:
                buy_score += 0.15
                reasons.append(f"RSI={rsi_val:.0f}")
            elif rsi_val > self.overbought:
                sell_score += 0.4
                reasons.append(f"RSI({rsi_val:.0f})>{self.overbought}")
            elif rsi_val > 60:
                sell_score += 0.15

        # ── 2. KDJ (与RSI去重: 只取增量部分) ──
        # RSI和KDJ高度共线，不再简单累加。KDJ只在极端区域提供增量。
        if k and d and j:
            rsi_contrib = 0.0
            if rsi_val and not np.isnan(rsi_val):
                if rsi_val < self.oversold:
                    rsi_contrib = 0.4
                elif rsi_val < 40:
                    rsi_contrib = 0.15

            if j < 0 and k < 20:
                # KDJ极端超卖 → 增量 = max(0, 0.3 - rsi已贡献)
                kdj_add = max(0, 0.3 - rsi_contrib * 0.75)
                buy_score += kdj_add
                if kdj_add > 0.05:
                    reasons.append("KDJ-oversold")
            elif j > 100 and k > 80:
                sell_score += 0.3
                reasons.append("KDJ-overbought")
            elif k > d and j > k:
                buy_score += 0.1
            elif k < d and j < k:
                sell_score += 0.1

        # ── 3. Bollinger band position ──
        if boll_lower and boll_upper and close:
            if close <= boll_lower * 1.01:
                buy_score += 0.2
                reasons.append("AtLowerBand")
            elif close <= boll_lower * 1.03:
                buy_score += 0.1
            elif close >= boll_upper * 0.99:
                sell_score += 0.2
                reasons.append("AtUpperBand")
            elif close >= boll_upper * 0.97:
                sell_score += 0.1

        # ── 4. KDJ divergence (last 10 bars) ──
        if len(df) >= 10:
            recent = df.iloc[-10:]
            price_lows = recent["low"].values
            kdj_k_vals = recent["kdj_k"].values
            if len(price_lows) >= 5 and len(kdj_k_vals) >= 5:
                price_min_idx = np.argmin(price_lows)
                kdj_min_idx = np.argmin(kdj_k_vals[:len(price_lows)])
                if (price_min_idx > len(price_lows) // 2 and
                    kdj_min_idx < len(price_lows) // 2):
                    buy_score += 0.2
                    reasons.append("BullDiv")

                price_max_idx = np.argmax(recent["high"].values)
                kdj_max_idx = np.argmax(kdj_k_vals[:len(price_lows)])
                if (price_max_idx > len(price_lows) // 2 and
                    kdj_max_idx < len(price_lows) // 2):
                    sell_score += 0.2
                    reasons.append("BearDiv")

        # ── Decision ──
        # 买入: 需要反弹确认，防止接飞刀
        if buy_score > sell_score and buy_score > 0.4:
            if is_bullish_candle:
                # 收阳确认 → 正常买入
                action = "buy"
                score = min(1.0, buy_score)
                confidence = min(0.85, buy_score)
                reasons.append("BullCandle")
            elif bounce_confirmed:
                # 止跌但未收阳 → 弱买入
                action = "buy"
                score = min(0.8, buy_score)
                confidence = min(0.55, buy_score * 0.7)
                reasons.append("Bounce")
            else:
                # 没有反弹确认 → 不买（防止接飞刀）
                action = "hold"
                score = buy_score * 0.3
                confidence = 0.15
                reasons.append("NoConfirm")
        elif sell_score > buy_score and sell_score > 0.4:
            action = "sell"
            score = -min(1.0, sell_score)
            confidence = min(0.85, sell_score)
        elif buy_score > 0.2:
            if bounce_confirmed:
                action = "buy"
                score = buy_score * 0.7
                confidence = 0.35
            else:
                action = "hold"
                score = buy_score * 0.2
                confidence = 0.15
        elif sell_score > 0.2:
            action = "sell"
            score = -sell_score
            confidence = 0.4
        else:
            action = "hold"
            score = buy_score - sell_score
            confidence = 0.2

        return SignalResult(action, round(score, 4), round(confidence, 4), "|".join(reasons))

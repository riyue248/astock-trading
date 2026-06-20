"""
反转策略 — RSI超买超卖 + KDJ背离 + 布林带位置
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

    def generate_signal(self, df: pd.DataFrame) -> SignalResult:
        if df.empty or len(df) < 20:
            return SignalResult("hold", 0.0, 0.0, "insufficient data")

        last = df.iloc[-1]
        close = last.get("close", 0)
        rsi_val = last.get("rsi14", 50)
        k = last.get("kdj_k", 50)
        d = last.get("kdj_d", 50)
        j = last.get("kdj_j", 50)
        boll_upper = last.get("boll_upper", 0)
        boll_lower = last.get("boll_lower", 0)
        boll_middle = last.get("boll_middle", 0)

        reasons = []
        buy_score = 0.0
        sell_score = 0.0

        # 1. RSI extremes
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

        # 2. KDJ divergence check (simple: extreme values)
        if k and d and j:
            if j < 0 and k < 20:
                buy_score += 0.3
                reasons.append("KDJ-oversold")
            elif j > 100 and k > 80:
                sell_score += 0.3
                reasons.append("KDJ-overbought")
            elif k > d and j > k:
                buy_score += 0.1
            elif k < d and j < k:
                sell_score += 0.1

        # 3. Bollinger band position
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

        # 4. KDJ divergence (last 10 bars)
        if len(df) >= 10:
            recent = df.iloc[-10:]
            price_lows = recent["low"].values
            kdj_k_vals = recent["kdj_k"].values
            if len(price_lows) >= 5 and len(kdj_k_vals) >= 5:
                # Bullish divergence: price makes lower low, KDJ makes higher low
                price_min_idx = np.argmin(price_lows)
                kdj_min_idx = np.argmin(kdj_k_vals[:len(price_lows)])
                if (price_min_idx > len(price_lows) // 2 and
                    kdj_min_idx < len(price_lows) // 2):
                    buy_score += 0.2
                    reasons.append("BullDiv")

                # Bearish divergence: price makes higher high, KDJ makes lower high
                price_max_idx = np.argmax(recent["high"].values)
                kdj_max_idx = np.argmax(kdj_k_vals[:len(price_lows)])
                if (price_max_idx > len(price_lows) // 2 and
                    kdj_max_idx < len(price_lows) // 2):
                    sell_score += 0.2
                    reasons.append("BearDiv")

        # Decision
        if buy_score > sell_score and buy_score > 0.4:
            action = "buy"
            score = min(1.0, buy_score)
            confidence = min(0.85, buy_score)
        elif sell_score > buy_score and sell_score > 0.4:
            action = "sell"
            score = -min(1.0, sell_score)
            confidence = min(0.85, sell_score)
        elif buy_score > 0.2:
            action = "buy"
            score = buy_score
            confidence = 0.4
        elif sell_score > 0.2:
            action = "sell"
            score = -sell_score
            confidence = 0.4
        else:
            action = "hold"
            score = buy_score - sell_score
            confidence = 0.2

        return SignalResult(action, round(score, 4), round(confidence, 4), "|".join(reasons))

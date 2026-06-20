"""
动量策略 — 放量突破 + 价格动能
"""
import pandas as pd

from engine.strategies.base import BaseStrategy, SignalResult


class MomentumStrategy(BaseStrategy):
    name = "momentum"

    def __init__(self, volume_ratio=1.5, price_surge=0.03):
        self.volume_ratio = volume_ratio
        self.price_surge = price_surge

    def generate_signal(self, df: pd.DataFrame) -> SignalResult:
        if df.empty or len(df) < 10:
            return SignalResult("hold", 0.0, 0.0, "insufficient data")

        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last

        close = last.get("close", 0)
        open_p = last.get("open", 0)
        volume = last.get("volume", 0)
        vol_ma5 = last.get("volume_ma5", 1)
        ma5 = last.get("ma5", 0)
        ma10 = last.get("ma10", 0)

        prev_close = prev.get("close", 0)
        prev_volume = prev.get("volume", 0)

        reasons = []
        score = 0.0

        # 1. Volume breakout
        if vol_ma5 and vol_ma5 > 0 and volume > vol_ma5 * self.volume_ratio:
            score += 0.35
            reasons.append(f"VolBreak({volume/vol_ma5:.1f}x)")
        elif vol_ma5 and vol_ma5 > 0 and volume > vol_ma5 * 1.2:
            score += 0.15
            reasons.append("VolHigh")

        # 2. Price surge
        if open_p and open_p > 0:
            day_change = (close - open_p) / open_p
            if day_change > self.price_surge:
                score += 0.3
                reasons.append(f"Surge({day_change:+.1%})")
            elif day_change > 0.01:
                score += 0.1
                reasons.append("Up")

        # 3. Momentum continuation
        if ma5 and ma10 and close > ma5 > ma10:
            score += 0.2
            reasons.append("Momentum")
        elif close > ma5:
            score += 0.1

        # 4. Volume-price health check
        if close and prev_close and volume and prev_volume:
            price_up = close > prev_close
            vol_up = volume > prev_volume
            if price_up and vol_up:
                score += 0.15
                reasons.append("Healthy")
            elif not price_up and vol_up:
                score -= 0.3
                reasons.append("!Distributing")

        score = max(-1.0, min(1.0, score))

        if score > 0.6:
            action = "buy"
            confidence = min(0.9, score)
        elif score < -0.2:
            action = "sell"
            confidence = min(0.9, -score)
        else:
            action = "hold"
            confidence = 0.3

        return SignalResult(action, round(score, 4), round(confidence, 4), "|".join(reasons))

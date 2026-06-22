"""
市场状态检测 — ADX 判断趋势/震荡
"""
import logging

import pandas as pd

from data.fetcher import fetch_index_history

logger = logging.getLogger(__name__)

# Cache: (date, regime_label, adx_value)
_regime_cache: dict = {}


def detect_regime() -> dict:
    """
    检测当前市场状态。
    使用上证指数 ADX(14) 判断。
    返回: {regime, adx_value, date}

    ADX > 25 → trending（趋势市，趋势策略加重）
    ADX < 20 → ranging（震荡市，反转策略加重）
    20-25   → transition（过渡期，中性权重）
    """
    from datetime import datetime
    from engine.indicators import adx

    today = datetime.now().strftime("%Y-%m-%d")

    # Return cached result for today
    if _regime_cache.get("date") == today:
        return {"regime": _regime_cache["regime"],
                "adx_value": _regime_cache["adx_value"],
                "date": today}

    try:
        # Fetch Shanghai Composite history explicitly. Do not route through
        # stock history, where 000001 means sz000001 (平安银行).
        df = fetch_index_history("sh000001", days=60)

        if df is None or df.empty or len(df) < 20:
            logger.warning("Insufficient index data for regime detection")
            return {"regime": "transition", "adx_value": 20, "date": today}

        # Compute ADX
        if "high" not in df.columns or "low" not in df.columns:
            # Use close as proxy if no high/low
            df["high"] = df["close"] * 1.01
            df["low"] = df["close"] * 0.99

        adx_df = adx(df["high"], df["low"], df["close"], period=14)
        latest_adx = adx_df["adx"].iloc[-1]

        if pd.isna(latest_adx):
            regime = "transition"
            latest_adx = 20
        elif latest_adx > 25:
            regime = "trending"
        elif latest_adx < 20:
            regime = "ranging"
        else:
            regime = "transition"

        _regime_cache["date"] = today
        _regime_cache["regime"] = regime
        _regime_cache["adx_value"] = round(float(latest_adx), 2)

        logger.info(f"Market regime: {regime} (ADX={latest_adx:.1f})")
        return {"regime": regime, "adx_value": round(float(latest_adx), 2), "date": today}

    except Exception as e:
        logger.warning(f"Regime detection failed: {e}")
        return {"regime": "transition", "adx_value": 20, "date": today}


def get_regime_weights(base_weights: dict) -> dict:
    """
    根据市场状态调整策略权重。

    base_weights: {"trend": 0.40, "momentum": 0.35, "reversal": 0.25}
    返回调整后的权重字典。
    """
    regime_info = detect_regime()
    regime = regime_info["regime"]

    weights = dict(base_weights)

    if regime == "trending":
        weights["trend"] *= 1.5
        weights["reversal"] *= 0.5
    elif regime == "ranging":
        weights["trend"] *= 0.5
        weights["reversal"] *= 1.5

    # Normalize to sum to 1.0
    total = sum(weights.values())
    if total > 0:
        weights = {k: v / total for k, v in weights.items()}

    return weights

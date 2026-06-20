"""
技术指标计算 — 纯 pandas/numpy
包含 ADX 用于市场状态检测
"""
import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def macd(close: pd.Series, fast=12, slow=26, signal=9) -> pd.DataFrame:
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    dif = ema_fast - ema_slow
    dea = ema(dif, signal)
    hist = (dif - dea) * 2
    return pd.DataFrame({"dif": dif, "dea": dea, "hist": hist})


def rsi(close: pd.Series, period=14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def kdj(high, low, close, n=9, m1=3, m2=3) -> pd.DataFrame:
    ll = low.rolling(n).min()
    hh = high.rolling(n).max()
    rsv = ((close - ll) / (hh - ll).replace(0, np.nan)) * 100
    k = rsv.ewm(alpha=1 / m1, adjust=False).mean().fillna(50)
    d = k.ewm(alpha=1 / m2, adjust=False).mean().fillna(50)
    j = 3 * k - 2 * d
    return pd.DataFrame({"k": k, "d": d, "j": j})


def bollinger(close, period=20, stddev=2.0) -> pd.DataFrame:
    middle = sma(close, period)
    std = close.rolling(period).std()
    return pd.DataFrame({
        "upper": middle + stddev * std,
        "middle": middle,
        "lower": middle - stddev * std,
    })


def atr(high, low, close, period=14) -> pd.Series:
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def adx(high, low, close, period=14) -> pd.DataFrame:
    """
    ADX — 平均趋向指数。
    返回 DataFrame: adx, plus_di, minus_di
    """
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_val = tr.ewm(alpha=1 / period, adjust=False).mean()

    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    plus_di = 100 * pd.Series(plus_dm).ewm(alpha=1 / period, adjust=False).mean() / atr_val
    minus_di = 100 * pd.Series(minus_dm).ewm(alpha=1 / period, adjust=False).mean() / atr_val

    dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
    adx_val = dx.ewm(alpha=1 / period, adjust=False).mean()

    return pd.DataFrame({"adx": adx_val, "plus_di": plus_di, "minus_di": minus_di})


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """为 DataFrame 添加所有常用指标。"""
    df = df.copy()
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]

    for p in [5, 10, 20, 60]:
        df[f"ma{p}"] = sma(c, p)
    for p in [12, 26]:
        df[f"ema{p}"] = ema(c, p)

    macd_df = macd(c)
    df["macd_dif"] = macd_df["dif"]
    df["macd_dea"] = macd_df["dea"]
    df["macd_hist"] = macd_df["hist"]

    df["rsi14"] = rsi(c, 14)

    kdj_df = kdj(h, l, c)
    df["kdj_k"] = kdj_df["k"]
    df["kdj_d"] = kdj_df["d"]
    df["kdj_j"] = kdj_df["j"]

    boll_df = bollinger(c)
    df["boll_upper"] = boll_df["upper"]
    df["boll_middle"] = boll_df["middle"]
    df["boll_lower"] = boll_df["lower"]

    df["atr14"] = atr(h, l, c, 14)

    adx_df = adx(h, l, c, 14)
    df["adx"] = adx_df["adx"]
    df["plus_di"] = adx_df["plus_di"]
    df["minus_di"] = adx_df["minus_di"]

    if len(v) > 0:
        df["volume_ma5"] = sma(v, 5)
        df["volume_ma10"] = sma(v, 10)

    return df

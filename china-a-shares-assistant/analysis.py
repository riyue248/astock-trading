"""规则化走势分析:基于历史日线数据计算技术指标,并生成中文走势总结。

不依赖任何外部模型或 API,全部基于价格/成交量的确定性计算。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_moving_averages(df: pd.DataFrame, windows=(5, 20, 60)) -> pd.DataFrame:
    """为历史数据追加均线列 ma5 / ma20 / ma60。"""
    out = df.copy()
    for w in windows:
        out[f"ma{w}"] = out["close"].rolling(w).mean()
    return out


def _pct(a: float, b: float) -> float | None:
    """从 b 到 a 的涨跌幅百分比。"""
    if b in (0, None) or a is None or pd.isna(a) or pd.isna(b):
        return None
    return (a / b - 1) * 100


def compute_metrics(df: pd.DataFrame) -> dict:
    """计算一组用于总结的关键统计量。"""
    if df is None or df.empty or len(df) < 2:
        return {}

    close = df["close"].astype(float)
    last = close.iloc[-1]
    n = len(close)

    def ret_over(days: int):
        if n > days:
            return _pct(last, close.iloc[-days - 1])
        return None

    daily_ret = close.pct_change().dropna()
    # 近 60 日年化波动率(按 250 交易日)
    recent = daily_ret.tail(60)
    volatility = float(recent.std() * np.sqrt(250) * 100) if len(recent) > 5 else None

    # 区间最大回撤
    roll_max = close.cummax()
    drawdown = (close / roll_max - 1) * 100
    max_drawdown = float(drawdown.min()) if not drawdown.empty else None

    ma = add_moving_averages(df)
    ma5 = ma["ma5"].iloc[-1] if "ma5" in ma else None
    ma20 = ma["ma20"].iloc[-1] if "ma20" in ma else None
    ma60 = ma["ma60"].iloc[-1] if "ma60" in ma else None

    return {
        "last": float(last),
        "ret_5": ret_over(5),
        "ret_20": ret_over(20),
        "ret_60": ret_over(60),
        "ret_250": ret_over(250),
        "ret_all": _pct(last, close.iloc[0]),
        "high_52w": float(close.max()),
        "low_52w": float(close.min()),
        "volatility": volatility,
        "max_drawdown": max_drawdown,
        "ma5": float(ma5) if ma5 is not None and not pd.isna(ma5) else None,
        "ma20": float(ma20) if ma20 is not None and not pd.isna(ma20) else None,
        "ma60": float(ma60) if ma60 is not None and not pd.isna(ma60) else None,
        "n_days": n,
    }


def _trend_phrase(ret: float | None, span: str) -> str | None:
    if ret is None:
        return None
    if ret >= 15:
        word = "大幅上涨"
    elif ret >= 5:
        word = "上涨"
    elif ret > 1:
        word = "小幅上行"
    elif ret >= -1:
        word = "基本横盘"
    elif ret > -5:
        word = "小幅回落"
    elif ret > -15:
        word = "下跌"
    else:
        word = "大幅下跌"
    return f"{span}{word}({ret:+.1f}%)"


def summarize(df: pd.DataFrame, name: str = "") -> str:
    """生成中文走势总结文本(Markdown)。"""
    m = compute_metrics(df)
    if not m:
        return "数据不足,无法生成走势总结。"

    lines: list[str] = []

    # 1) 短中长期走势
    spans = [
        _trend_phrase(m.get("ret_5"), "近一周"),
        _trend_phrase(m.get("ret_20"), "近一月"),
        _trend_phrase(m.get("ret_60"), "近一季"),
        _trend_phrase(m.get("ret_250"), "近一年"),
    ]
    spans = [s for s in spans if s]
    if spans:
        lines.append("**区间表现:** " + "、".join(spans) + "。")

    # 2) 均线排列
    ma5, ma20, ma60 = m.get("ma5"), m.get("ma20"), m.get("ma60")
    last = m.get("last")
    if None not in (ma5, ma20, ma60):
        if ma5 > ma20 > ma60:
            arrange = "均线呈**多头排列**(MA5>MA20>MA60),中短期趋势偏强"
        elif ma5 < ma20 < ma60:
            arrange = "均线呈**空头排列**(MA5<MA20<MA60),中短期趋势偏弱"
        else:
            arrange = "均线**交织缠绕**,趋势方向不明朗"
        pos = "上方" if last and last >= ma20 else "下方"
        lines.append(f"**均线结构:** {arrange};当前股价位于 20 日均线{pos}。")

    # 3) 位置(相对一年高低点)
    hi, lo = m.get("high_52w"), m.get("low_52w")
    if hi and lo and hi > lo and last:
        pos_pct = (last - lo) / (hi - lo) * 100
        lines.append(
            f"**价格位置:** 区间内最高 {hi:.2f}、最低 {lo:.2f},"
            f"当前 {last:.2f} 处于区间 {pos_pct:.0f}% 分位。"
        )

    # 4) 波动与回撤
    vol, mdd = m.get("volatility"), m.get("max_drawdown")
    risk_bits = []
    if vol is not None:
        level = "较高" if vol >= 40 else ("中等" if vol >= 25 else "较低")
        risk_bits.append(f"近 60 日年化波动率约 {vol:.0f}%(波动{level})")
    if mdd is not None:
        risk_bits.append(f"区间最大回撤 {mdd:.1f}%")
    if risk_bits:
        lines.append("**波动与风险:** " + "、".join(risk_bits) + "。")

    # 5) 一句话综合判断
    short = m.get("ret_20")
    long = m.get("ret_250")
    if short is not None and long is not None:
        if short > 0 and long > 0:
            verdict = "短期与长期均向上,处于上升通道"
        elif short < 0 and long < 0:
            verdict = "短期与长期均向下,处于下行趋势"
        elif short > 0 >= long:
            verdict = "长期偏弱但近期出现反弹迹象"
        else:
            verdict = "长期向上但近期有所调整"
        lines.append(f"**综合判断:** {verdict}。")

    note = "\n\n> 以上为基于历史价格的规则化统计,仅供参考,不构成投资建议。"
    title = f"### 📈 {name} 走势总结\n\n" if name else ""
    return title + "\n\n".join(lines) + note

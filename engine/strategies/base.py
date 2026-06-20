"""
策略抽象基类
"""
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class SignalResult:
    action: str                # 'buy', 'sell', 'hold'
    score: float               # -1.0 to +1.0
    confidence: float          # 0.0 to 1.0
    reason: str = ""           # Human-readable summary


class BaseStrategy:
    """所有策略的基类。"""
    name: str = "base"

    def generate_signal(self, df: pd.DataFrame) -> SignalResult:
        """
        根据历史K线DataFrame生成交易信号。
        df 必须包含 indicator_service.add_all_indicators 的所有列。
        返回 SignalResult。
        """
        raise NotImplementedError

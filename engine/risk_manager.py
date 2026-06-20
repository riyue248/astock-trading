"""
风险管理器 — 仓位计算 + 回撤控制
"""
import logging
import math

from config import settings

logger = logging.getLogger(__name__)


class RiskManager:
    """仓位计算和风控。"""

    def __init__(self):
        self.max_position_pct = settings.MAX_POSITION_PCT
        self.max_positions = settings.MAX_POSITIONS
        self.stop_loss_pct = settings.STOP_LOSS_PCT
        self.take_profit_pct = settings.TAKE_PROFIT_PCT
        self.max_drawdown = settings.MAX_PORTFOLIO_DRAWDOWN

    def calculate_position_size(self, score: float, win_rate: float,
                                 portfolio_value: float, price: float) -> int:
        """
        用半凯利公式计算仓位大小。

        凯利比例 f = win_rate - (1 - win_rate) / (avg_win / avg_loss)
        半凯利 = f / 2

        返回值: 股数（100的整数倍）
        """
        if score <= 0 or win_rate <= 0.1:
            return 0

        # Conservative win/loss ratio assumption
        avg_win = 0.05   # 5% average win
        avg_loss = 0.04  # 4% average loss (tighter with stop loss)
        ratio = avg_win / max(avg_loss, 0.001)

        # Kelly fraction
        kelly = win_rate - (1 - win_rate) / ratio
        kelly = max(0, min(kelly, 0.25))  # Cap at 25%

        # Half-Kelly
        half_kelly = kelly / 2

        # Score multiplier: higher score → bigger bet
        score_mult = min(1.0, (score - settings.BUY_THRESHOLD) / 0.6 + 0.5)
        score_mult = max(0.3, score_mult)

        # Calculate position value
        position_value = portfolio_value * half_kelly * score_mult

        # Cap at max position size
        max_value = portfolio_value * self.max_position_pct
        position_value = min(position_value, max_value)

        if position_value <= 0 or price <= 0:
            return 0

        shares = int(position_value / price)
        # Round down to 100-share lots
        shares = (shares // 100) * 100

        return max(shares, 0)

    @staticmethod
    def calculate_stop_loss(entry_price: float) -> float:
        return entry_price * (1 + settings.STOP_LOSS_PCT)

    @staticmethod
    def calculate_take_profit(entry_price: float) -> float:
        return entry_price * (1 + settings.TAKE_PROFIT_PCT)

    def check_portfolio_ok(self, drawdown_pct: float) -> bool:
        """检查组合是否允许新开仓。"""
        return abs(drawdown_pct) < self.max_drawdown

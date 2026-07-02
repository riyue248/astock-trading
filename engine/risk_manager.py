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

        从 DB 加载真实的 avg_win/avg_loss，无数据时用保守默认值。

        返回值: 股数（100的整数倍）
        """
        if score <= 0 or win_rate <= 0.1:
            return 0

        # Load real trade stats from DB, fall back to conservative defaults
        avg_win, avg_loss = self._load_trade_stats()

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

    @staticmethod
    def _load_trade_stats() -> tuple[float, float]:
        """
        从 DB 的策略表现表中加载真实 avg_win / avg_loss。
        返回 (avg_win, avg_loss)，默认为 (0.08, 0.05)。
        """
        try:
            from data.database import SessionLocal
            from models.orm import StrategyPerformance
            from sqlalchemy import select
            with SessionLocal() as db:
                perfs = db.execute(select(StrategyPerformance)).scalars().all()
                if perfs:
                    total_trades = sum(p.total_trades or 0 for p in perfs)
                    if total_trades >= 5:
                        # Weighted average across strategies
                        total_wins = sum(p.wins or 0 for p in perfs)
                        total_losses = sum(p.losses or 0 for p in perfs)
                        avg_w = sum((p.avg_win_pct or 0) * (p.wins or 0) for p in perfs)
                        avg_l = sum((p.avg_loss_pct or 0) * (p.losses or 0) for p in perfs)
                        real_avg_win = avg_w / max(total_wins, 1)
                        real_avg_loss = avg_l / max(total_losses, 1)
                        if real_avg_win > 0 and real_avg_loss > 0:
                            return (real_avg_win, real_avg_loss)
        except Exception:
            pass
        # Conservative defaults
        return (0.08, 0.05)

    def check_portfolio_ok(self, drawdown_pct: float) -> bool:
        """检查组合是否允许新开仓。"""
        return abs(drawdown_pct) < self.max_drawdown

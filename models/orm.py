"""
SQLAlchemy ORM 模型 — 6张表
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from data.database import Base


class TradeLog(Base):
    """每笔交易记录。"""
    __tablename__ = "trade_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), index=True)
    name: Mapped[str] = mapped_column(String(50), default="")
    side: Mapped[str] = mapped_column(String(4))            # 'buy' or 'sell'
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    amount: Mapped[float] = mapped_column(Float)
    commission: Mapped[float] = mapped_column(Float, default=0)
    signal_score: Mapped[float] = mapped_column(Float, nullable=True)
    strategies: Mapped[str] = mapped_column(String(100), default="")
    market_regime: Mapped[str] = mapped_column(String(20), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    close_reason: Mapped[str] = mapped_column(String(50), nullable=True)
    profit_pct: Mapped[float] = mapped_column(Float, nullable=True)
    profit_amount: Mapped[float] = mapped_column(Float, nullable=True)

    def to_dict(self):
        return {
            "id": self.id, "symbol": self.symbol, "name": self.name,
            "side": self.side, "quantity": self.quantity,
            "price": round(self.price, 2), "amount": round(self.amount, 2),
            "commission": round(self.commission, 4),
            "signal_score": round(self.signal_score, 4) if self.signal_score else None,
            "strategies": self.strategies, "market_regime": self.market_regime,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "close_reason": self.close_reason,
            "profit_pct": round(self.profit_pct, 4) if self.profit_pct else None,
            "profit_amount": round(self.profit_amount, 2) if self.profit_amount else None,
        }


class Position(Base):
    """当前持仓。"""
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(50), default="")
    quantity: Mapped[int] = mapped_column(Integer)
    avg_cost: Mapped[float] = mapped_column(Float)
    current_price: Mapped[float] = mapped_column(Float, default=0)
    market_value: Mapped[float] = mapped_column(Float, default=0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0)
    stop_loss_price: Mapped[float] = mapped_column(Float, default=0)
    take_profit_price: Mapped[float] = mapped_column(Float, default=0)
    buy_trade_ids: Mapped[str] = mapped_column(String(200), default="")
    entry_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    signal_score: Mapped[float] = mapped_column(Float, nullable=True)
    strategies: Mapped[str] = mapped_column(String(100), default="")

    def to_dict(self):
        return {
            "id": self.id, "symbol": self.symbol, "name": self.name,
            "quantity": self.quantity,
            "avg_cost": round(self.avg_cost, 2),
            "current_price": round(self.current_price, 2),
            "market_value": round(self.market_value, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "unrealized_pnl_pct": round(self.unrealized_pnl / (self.avg_cost * self.quantity) * 100, 2)
            if (self.avg_cost * self.quantity) > 0 else 0,
            "stop_loss_price": round(self.stop_loss_price, 2),
            "take_profit_price": round(self.take_profit_price, 2),
            "entry_date": self.entry_date.isoformat() if self.entry_date else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "signal_score": round(self.signal_score, 4) if self.signal_score else None,
            "strategies": self.strategies,
        }


class Signal(Base):
    """每次扫描生成的信号日志。"""
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), index=True)
    name: Mapped[str] = mapped_column(String(50), default="")
    trend_score: Mapped[float] = mapped_column(Float, nullable=True)
    trend_action: Mapped[str] = mapped_column(String(10), nullable=True)
    momentum_score: Mapped[float] = mapped_column(Float, nullable=True)
    momentum_action: Mapped[str] = mapped_column(String(10), nullable=True)
    reversal_score: Mapped[float] = mapped_column(Float, nullable=True)
    reversal_action: Mapped[str] = mapped_column(String(10), nullable=True)
    composite_score: Mapped[float] = mapped_column(Float, nullable=True)
    final_action: Mapped[str] = mapped_column(String(10))   # 'buy','sell','hold'
    decision_reason: Mapped[str] = mapped_column(String(200), default="")
    market_regime: Mapped[str] = mapped_column(String(20), default="")
    strategy_weights: Mapped[str] = mapped_column(String(100), default="")
    scanned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def to_dict(self):
        return {
            "id": self.id, "symbol": self.symbol, "name": self.name,
            "trend_score": round(self.trend_score, 4) if self.trend_score else None,
            "trend_action": self.trend_action,
            "momentum_score": round(self.momentum_score, 4) if self.momentum_score else None,
            "momentum_action": self.momentum_action,
            "reversal_score": round(self.reversal_score, 4) if self.reversal_score else None,
            "reversal_action": self.reversal_action,
            "composite_score": round(self.composite_score, 4) if self.composite_score else None,
            "final_action": self.final_action,
            "decision_reason": self.decision_reason,
            "market_regime": self.market_regime,
            "strategy_weights": self.strategy_weights,
            "scanned_at": self.scanned_at.isoformat() if self.scanned_at else None,
        }


class EquitySnapshot(Base):
    """每日净值快照。"""
    __tablename__ = "equity_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10), index=True)
    total_equity: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)
    market_value: Mapped[float] = mapped_column(Float)
    daily_pnl: Mapped[float] = mapped_column(Float, nullable=True)
    daily_return_pct: Mapped[float] = mapped_column(Float, nullable=True)
    drawdown_pct: Mapped[float] = mapped_column(Float, nullable=True)
    open_positions: Mapped[int] = mapped_column(Integer, default=0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def to_dict(self):
        return {
            "date": self.date, "total_equity": round(self.total_equity, 2),
            "cash": round(self.cash, 2), "market_value": round(self.market_value, 2),
            "daily_pnl": round(self.daily_pnl, 2) if self.daily_pnl else 0,
            "daily_return_pct": round(self.daily_return_pct, 4) if self.daily_return_pct else 0,
            "drawdown_pct": round(self.drawdown_pct, 4) if self.drawdown_pct else 0,
            "open_positions": self.open_positions,
        }


class StrategyPerformance(Base):
    """策略滚动表现。"""
    __tablename__ = "strategy_performance"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(50), unique=True)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0)
    avg_win_pct: Mapped[float] = mapped_column(Float, default=0)
    avg_loss_pct: Mapped[float] = mapped_column(Float, default=0)
    profit_factor: Mapped[float] = mapped_column(Float, default=0)
    current_weight: Mapped[float] = mapped_column(Float, default=0.33)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def to_dict(self):
        return {
            "strategy_name": self.strategy_name, "total_trades": self.total_trades,
            "wins": self.wins, "losses": self.losses,
            "win_rate": round(self.win_rate, 4), "avg_win_pct": round(self.avg_win_pct, 4),
            "avg_loss_pct": round(self.avg_loss_pct, 4),
            "profit_factor": round(self.profit_factor, 4),
            "current_weight": round(self.current_weight, 4),
        }


class StrategyParams(Base):
    """策略当前参数和网格搜索结果。"""
    __tablename__ = "strategy_params"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(50), unique=True)
    params_json: Mapped[str] = mapped_column(Text)
    sharpe: Mapped[float] = mapped_column(Float, nullable=True)
    total_return: Mapped[float] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def to_dict(self):
        return {
            "strategy_name": self.strategy_name, "params_json": self.params_json,
            "sharpe": round(self.sharpe, 4) if self.sharpe else None,
            "total_return": round(self.total_return, 4) if self.total_return else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

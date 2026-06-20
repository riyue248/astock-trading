"""
Pydantic 请求/响应模型
"""
from pydantic import BaseModel
from typing import Optional


class PortfolioSummary(BaseModel):
    initial_capital: float
    total_equity: float
    cash: float
    market_value: float
    total_return_pct: float
    drawdown_pct: float
    position_count: int
    max_positions: int
    halted: bool
    positions: list[dict] = []


class TradeQuery(BaseModel):
    page: int = 1
    limit: int = 50
    symbol: Optional[str] = None
    side: Optional[str] = None
    close_reason: Optional[str] = None


class SignalQuery(BaseModel):
    limit: int = 50
    symbol: Optional[str] = None


class ControlRequest(BaseModel):
    action: str  # "start" | "stop" | "pause" | "resume"


class SystemStatus(BaseModel):
    running: bool
    trading: bool
    trading_status: str
    last_scan: Optional[str] = None
    next_scan: Optional[str] = None
    scan_count: int = 0
    total_trades: int = 0
    open_positions: int = 0
    data_ok: bool = True

"""
模拟交易账户
- 买入/卖出/持仓管理
- 止损止盈自动检查
- 状态持久化到 SQLite
"""
import logging
from datetime import datetime

from sqlalchemy import select, delete

from config import settings
from data.database import SessionLocal, init_db

logger = logging.getLogger(__name__)


class PaperAccount:
    """模拟交易账户。"""

    def __init__(self, initial_capital: float = None):
        init_db()
        self.initial_capital = initial_capital or settings.INITIAL_CAPITAL
        self._cash = self.initial_capital
        self._positions: dict = {}      # symbol -> Position dict
        self._peak_equity = self.initial_capital
        self._halt_trading = False      # Halt if max drawdown hit

    # ─── Properties ──────────────────────────────────

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def positions(self) -> dict:
        return self._positions

    @property
    def position_count(self) -> int:
        return len(self._positions)

    @property
    def is_halted(self) -> bool:
        return self._halt_trading

    def market_value(self) -> float:
        return sum(
            p["quantity"] * p.get("current_price", p["avg_cost"])
            for p in self._positions.values()
        )

    def total_equity(self) -> float:
        return self._cash + self.market_value()

    def drawdown_pct(self) -> float:
        peak = self._peak_equity
        current = self.total_equity()
        if peak <= 0:
            return 0
        return (current - peak) / peak

    # ─── Buy ─────────────────────────────────────────

    def buy(self, symbol: str, name: str, price: float, quantity: int,
            signal_score: float = 0, strategies: str = "",
            market_regime: str = "") -> dict | None:
        """
        执行买入。返回 trade dict 或 None。
        自动检查: 持仓上限、单只上限、现金充足
        """
        from models.orm import TradeLog, Position

        # Checklist
        if self._halt_trading:
            logger.warning("Trading halted (max drawdown). Buy rejected.")
            return None
        if self.position_count >= settings.MAX_POSITIONS:
            logger.info(f"Max positions ({settings.MAX_POSITIONS}) reached. Buy rejected.")
            return None
        if symbol in self._positions:
            logger.info(f"Already holding {symbol}. Skip buy.")
            return None

        amount = price * quantity
        commission = amount * settings.COMMISSION_RATE
        total_cost = amount + commission

        if self._cash < total_cost:
            logger.info(f"Insufficient cash ({self._cash:.0f} < {total_cost:.0f}). Buy rejected.")
            return None

        max_single = self.total_equity() * settings.MAX_POSITION_PCT
        if total_cost > max_single:
            logger.info(f"Position size ({total_cost:.0f}) exceeds 30% limit ({max_single:.0f}).")
            return None

        # Execute
        self._cash -= total_cost
        stop_loss = price * (1 + settings.STOP_LOSS_PCT)
        take_profit = price * (1 + settings.TAKE_PROFIT_PCT)

        now = datetime.now()
        with SessionLocal() as db:
            # Trade log
            trade = TradeLog(
                symbol=symbol, name=name, side="buy",
                quantity=quantity, price=price, amount=amount,
                commission=commission, signal_score=signal_score,
                strategies=strategies, market_regime=market_regime,
                created_at=now,
            )
            db.add(trade)
            db.flush()

            # Position
            pos = Position(
                symbol=symbol, name=name, quantity=quantity,
                avg_cost=price, current_price=price,
                market_value=amount, unrealized_pnl=0,
                stop_loss_price=stop_loss,
                take_profit_price=take_profit,
                buy_trade_ids=str(trade.id),
                entry_date=now, last_updated=now,
                signal_score=signal_score, strategies=strategies,
            )
            db.add(pos)
            db.commit()

            trade_dict = trade.to_dict()
            pos_dict = pos.to_dict()

        self._positions[symbol] = pos_dict
        logger.info(f"BUY {symbol} {name}: {quantity}sh @ {price:.2f} = {amount:.0f}")

        return trade_dict

    # ─── Sell ─────────────────────────────────────────

    def sell(self, symbol: str, price: float, reason: str = "signal") -> dict | None:
        """
        执行卖出。返回 trade dict 或 None。
        """
        from models.orm import TradeLog, Position

        if symbol not in self._positions:
            logger.warning(f"Symbol {symbol} not in positions. Sell rejected.")
            return None

        pos = self._positions[symbol]
        quantity = pos["quantity"]
        amount = price * quantity
        commission = amount * settings.COMMISSION_RATE
        net_amount = amount - commission

        cost_basis = pos["avg_cost"] * quantity
        profit = net_amount - cost_basis - pos.get("total_commission", 0)
        profit_pct = profit / cost_basis if cost_basis > 0 else 0

        self._cash += net_amount

        now = datetime.now()
        with SessionLocal() as db:
            # Trade log
            trade = TradeLog(
                symbol=symbol, name=pos["name"], side="sell",
                quantity=quantity, price=price, amount=amount,
                commission=commission,
                signal_score=pos.get("signal_score"),
                strategies=pos.get("strategies", ""),
                created_at=now,
                close_reason=reason,
                profit_pct=profit_pct,
                profit_amount=profit,
            )
            db.add(trade)

            # Remove position
            db.execute(delete(Position).where(Position.symbol == symbol))
            db.commit()

            trade_dict = trade.to_dict()

        del self._positions[symbol]
        logger.info(f"SELL {symbol}: {quantity}sh @ {price:.2f} | "
                    f"PnL: {profit:+.0f} ({profit_pct:+.2%}) | Reason: {reason}")

        # Update peak equity
        current_equity = self.total_equity()
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity

        # Check drawdown halt (reenable if recovered)
        dd = self.drawdown_pct()
        if dd <= -settings.MAX_PORTFOLIO_DRAWDOWN:
            self._halt_trading = True
            logger.warning(f"HALT: drawdown {dd:.2%} exceeds limit")
        elif dd > -settings.MAX_PORTFOLIO_DRAWDOWN * 0.5:
            self._halt_trading = False

        return trade_dict

    # ─── Position Update ──────────────────────────────

    def update_market_prices(self, prices: dict):
        """
        更新持仓市值。prices: {symbol: current_price}
        """
        from models.orm import Position

        for symbol, price in prices.items():
            if symbol in self._positions:
                pos = self._positions[symbol]
                pos["current_price"] = price
                pos["market_value"] = price * pos["quantity"]
                pos["unrealized_pnl"] = pos["market_value"] - pos["avg_cost"] * pos["quantity"]
                pos["last_updated"] = datetime.now().isoformat()

        # Update DB
        with SessionLocal() as db:
            for symbol, pos in self._positions.items():
                stmt = select(Position).where(Position.symbol == symbol)
                db_pos = db.execute(stmt).scalar_one_or_none()
                if db_pos:
                    db_pos.current_price = pos["current_price"]
                    db_pos.market_value = pos["market_value"]
                    db_pos.unrealized_pnl = pos["unrealized_pnl"]
                    db_pos.last_updated = datetime.now()
            db.commit()

    # ─── Stop Loss / Take Profit Check ────────────────

    def check_stop_conditions(self) -> list[dict]:
        """
        检查所有持仓的止损止盈条件。
        返回需要卖出的持仓列表 [{symbol, reason, price}]。
        """
        to_sell = []
        for symbol, pos in self._positions.items():
            price = pos.get("current_price", pos["avg_cost"])
            if price <= pos["stop_loss_price"]:
                to_sell.append({"symbol": symbol, "reason": "stop_loss", "price": price})
            elif price >= pos["take_profit_price"]:
                to_sell.append({"symbol": symbol, "reason": "take_profit", "price": price})
        return to_sell

    # ─── Equity Snapshot ──────────────────────────────

    def snapshot_equity(self):
        """记录当前净值快照。"""
        from models.orm import EquitySnapshot

        today = datetime.now().strftime("%Y-%m-%d")
        equity = self.total_equity()
        mv = self.market_value()
        dd = self.drawdown_pct()

        # Get previous snapshot for daily PnL
        prev_equity = equity
        with SessionLocal() as db:
            stmt = (select(EquitySnapshot)
                    .where(EquitySnapshot.date < today)
                    .order_by(EquitySnapshot.date.desc())
                    .limit(1))
            prev = db.execute(stmt).scalar_one_or_none()
            if prev:
                prev_equity = prev.total_equity

        daily_pnl = equity - prev_equity
        daily_return = daily_pnl / prev_equity if prev_equity > 0 else 0

        with SessionLocal() as db:
            # Check if already have snapshot for today
            existing = db.execute(
                select(EquitySnapshot).where(EquitySnapshot.date == today)
            ).scalar_one_or_none()

            if existing:
                existing.total_equity = equity
                existing.cash = self._cash
                existing.market_value = mv
                existing.daily_pnl = daily_pnl
                existing.daily_return_pct = daily_return
                existing.drawdown_pct = dd
                existing.open_positions = self.position_count
                existing.recorded_at = datetime.now()
            else:
                snap = EquitySnapshot(
                    date=today, total_equity=equity,
                    cash=self._cash, market_value=mv,
                    daily_pnl=daily_pnl, daily_return_pct=daily_return,
                    drawdown_pct=dd, open_positions=self.position_count,
                    recorded_at=datetime.now(),
                )
                db.add(snap)
            db.commit()

    # ─── Load State ───────────────────────────────────

    def load_state(self):
        """从DB恢复持仓状态（重启后调用）。"""
        from models.orm import Position, TradeLog, EquitySnapshot

        with SessionLocal() as db:
            positions = db.execute(select(Position)).scalars().all()
            for p in positions:
                self._positions[p.symbol] = p.to_dict()

            # Recalculate cash from trade log
            total_buys = 0
            total_sells = 0
            trades = db.execute(select(TradeLog).order_by(TradeLog.id)).scalars().all()
            for t in trades:
                if t.side == "buy":
                    total_buys += t.amount + (t.commission or 0)
                else:
                    total_sells += t.amount - (t.commission or 0)

            self._cash = self.initial_capital - total_buys + total_sells

            # Recalculate peak
            snapshots = db.execute(
                select(EquitySnapshot).order_by(EquitySnapshot.date)
            ).scalars().all()
            if snapshots:
                self._peak_equity = max(s.total_equity for s in snapshots)
            else:
                self._peak_equity = self.initial_capital

        logger.info(f"State loaded: cash={self._cash:.0f}, positions={self.position_count}, "
                    f"equity={self.total_equity():.0f}")

    # ─── Summary ──────────────────────────────────────

    def get_summary(self) -> dict:
        equity = self.total_equity()
        total_return = (equity - self.initial_capital) / self.initial_capital
        return {
            "initial_capital": self.initial_capital,
            "total_equity": round(equity, 2),
            "cash": round(self._cash, 2),
            "market_value": round(self.market_value(), 2),
            "net_profit": round(equity - self.initial_capital, 2),
            "total_return_pct": round(total_return * 100, 2),
            "drawdown_pct": round(self.drawdown_pct() * 100, 2),
            "position_count": self.position_count,
            "max_positions": settings.MAX_POSITIONS,
            "halted": self._halt_trading,
            "positions": list(self._positions.values()),
        }

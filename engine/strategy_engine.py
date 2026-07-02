"""
策略编排器 — 扫描候选池 → 运行策略 → 评分 → 执行交易
"""
import logging
from datetime import datetime

from config import settings
from data.database import SessionLocal
from data.fetcher import get_candidate_pool, fetch_stock_history
from engine.indicators import add_all_indicators
from engine.scoring_engine import ScoringEngine
from engine.paper_account import PaperAccount
from engine.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class StrategyEngine:
    """扫描和交易编排。"""

    def __init__(self, account: PaperAccount, scoring: ScoringEngine, optimizer=None):
        self.account = account
        self.scoring = scoring
        self.optimizer = optimizer
        self.risk = RiskManager()
        self.scan_count = 0
        self.last_scan_time: datetime | None = None
        # Cooldown: {symbol: datetime} — 卖出后冷却期
        self._sell_cooldown: dict[str, datetime] = {}

    def run_scan(self) -> dict:
        """
        执行一次完整的扫描-决策-交易循环。
        返回 scan_result dict。
        """
        self.scan_count += 1
        self.last_scan_time = datetime.now()
        t_start = datetime.now()

        result = {
            "scan_id": self.scan_count,
            "time": self.last_scan_time.isoformat(),
            "candidates_scanned": 0,
            "signals_generated": 0,
            "buys": [],
            "sells": [],
            "errors": [],
        }

        # 1. Update market prices for existing positions
        try:
            held_symbols = set(self.account.positions.keys())
            if held_symbols:
                from data.fetcher import fetch_spot_batch
                sina_codes = list(held_symbols)
                spots = fetch_spot_batch(sina_codes)
                prices = {}
                for spot in spots:
                    code = spot.get("代码", "")
                    price = spot.get("最新价", 0)
                    if code and price:
                        prices[code] = price
                self.account.update_market_prices(prices)
        except Exception as e:
            result["errors"].append(f"price_update: {e}")

        # 2. Check stop-loss / take-profit
        try:
            to_sell = self.account.check_stop_conditions()
            for sell_order in to_sell:
                trade = self.account.sell(
                    sell_order["symbol"],
                    sell_order["price"],
                    sell_order["reason"],
                )
                if trade:
                    self._record_trade_result(trade)
                    self._sell_cooldown[sell_order["symbol"]] = datetime.now()
                    result["sells"].append({
                        "symbol": sell_order["symbol"],
                        "price": sell_order["price"],
                        "reason": sell_order["reason"],
                        "pnl": trade.get("profit_amount", 0),
                    })
        except Exception as e:
            result["errors"].append(f"stop_check: {e}")

        # 3. Get candidate pool (with retry if too few valid)
        try:
            pool_size = settings.CANDIDATE_POOL_SIZE
            candidates = get_candidate_pool(pool_size)
            result["candidates_scanned"] = len(candidates)

            # 如果有效候选太少，翻倍重试一次
            if len(candidates) < settings.CANDIDATE_MIN_VALID and pool_size < 500:
                logger.info(f"Only {len(candidates)} candidates, retrying with double pool...")
                candidates = get_candidate_pool(min(pool_size * 2, 500))
                result["candidates_scanned"] = len(candidates)
        except Exception as e:
            logger.error(f"Candidate pool error: {e}")
            result["errors"].append(f"candidates: {e}")
            # Fallback: scan only held positions
            candidates = []
            for sym in held_symbols:
                candidates.append({"代码": sym, "名称": ""})

        if not candidates:
            return result

        # 4. Score each candidate
        stock_scores = []
        held_sina = set(self.account.positions.keys())

        with SessionLocal() as db:
            for stock in candidates:
                symbol = stock.get("代码", "")
                name = stock.get("名称", "")
                if not symbol:
                    continue

                try:
                    # Fetch history
                    df = fetch_stock_history(symbol, days=settings.DEFAULT_HISTORY_DAYS)
                    if df is None or df.empty or len(df) < 20:
                        continue

                    # Compute indicators
                    df = add_all_indicators(df)

                    # Score
                    score_result = self.scoring.score_stock(df)
                    stock_scores.append({
                        "symbol": symbol,
                        "name": name,
                        **score_result,
                    })
                    result["signals_generated"] += 1

                    # Log signal
                    self.scoring.log_signal(symbol, name, score_result, db)

                except Exception as e:
                    logger.debug(f"Score error for {symbol}: {e}")
                    continue

            db.commit()

        # 5. Track trend activity & rank
        self.scoring.track_trend_activity(stock_scores)
        ranked = self.scoring.rank_candidates(stock_scores, held_sina)

        # 6. Execute buys (if not halted)
        if not self.account.is_halted:
            for buy_rec in ranked["buy"]:
                try:
                    symbol = buy_rec["symbol"]

                    # Cooldown check: 卖出后冷却期内不买回
                    if symbol in self._sell_cooldown:
                        sold_at = self._sell_cooldown[symbol]
                        cooldown_sec = settings.SELL_COOLDOWN_HOURS * 3600
                        if (datetime.now() - sold_at).total_seconds() < cooldown_sec:
                            logger.info(f"Cooldown: {symbol} sold {sold_at.strftime('%H:%M')}, skip re-buy")
                            continue
                        else:
                            del self._sell_cooldown[symbol]

                    name = buy_rec["name"]
                    score = buy_rec["composite_score"]

                    # Get current price
                    from data.fetcher import fetch_spot_batch
                    spot = fetch_spot_batch([symbol])
                    if not spot:
                        continue
                    price = spot[0].get("最新价", 0)
                    if price <= 0:
                        continue

                    # Calculate position size
                    equity = self.account.total_equity()
                    win_rate = self._get_avg_win_rate()
                    qty = self.risk.calculate_position_size(score, win_rate, equity, price)

                    if qty < 100:
                        continue  # Too small

                    # Execute
                    strategies = ",".join(
                        s for s in ["trend", "momentum", "reversal"]
                        if buy_rec["signals"][s].action == "buy"
                    )
                    trade = self.account.buy(
                        symbol, name, price, qty, score,
                        strategies, str(buy_rec.get("market_regime", "")),
                    )
                    if trade:
                        result["buys"].append({
                            "symbol": symbol, "name": name,
                            "price": price, "quantity": qty,
                            "score": score, "strategies": strategies,
                        })
                        held_sina.add(symbol)

                except Exception as e:
                    result["errors"].append(f"buy_{symbol}: {e}")

        # 7. Execute sells (strategy-driven, not stop-loss)
        for sell_rec in ranked["sell"]:
            try:
                symbol = sell_rec["symbol"]
                if symbol not in self.account.positions:
                    continue

                from data.fetcher import fetch_spot_batch
                spot = fetch_spot_batch([symbol])
                if not spot:
                    continue
                price = spot[0].get("最新价", 0)
                if price <= 0:
                    continue

                trade = self.account.sell(symbol, price, "signal")
                if trade:
                    self._record_trade_result(trade)
                    self._sell_cooldown[sell_order["symbol"]] = datetime.now()
                    result["sells"].append({
                        "symbol": symbol,
                        "price": price,
                        "reason": "signal",
                        "pnl": trade.get("profit_amount", 0),
                    })
            except Exception as e:
                result["errors"].append(f"sell_{symbol}: {e}")

        # 8. Snapshot equity
        try:
            self.account.snapshot_equity()
        except Exception as e:
            result["errors"].append(f"snapshot: {e}")

        elapsed = (datetime.now() - t_start).total_seconds()
        result["elapsed_sec"] = round(elapsed, 2)

        if result["buys"] or result["sells"]:
            logger.info(f"Scan#{self.scan_count}: "
                        f"{len(result['buys'])} buys, {len(result['sells'])} sells, "
                        f"{result['signals_generated']} signals, {elapsed:.1f}s")

        return result

    def _record_trade_result(self, trade: dict):
        """Update optimizer stats after a position is closed."""
        if not self.optimizer or not trade:
            return
        try:
            self.optimizer.update_trade_result(
                trade.get("strategies", ""),
                trade.get("profit_pct", 0) or 0,
            )
            self.scoring.update_weights(self.optimizer.get_current_weights())
        except Exception as e:
            logger.warning(f"Optimizer update failed: {e}")

    def _get_avg_win_rate(self) -> float:
        """获取策略平均胜率。"""
        try:
            from models.orm import StrategyPerformance
            with SessionLocal() as db:
                perfs = db.query(StrategyPerformance).all()
                if perfs:
                    rates = [p.win_rate for p in perfs if p.total_trades >= 5]
                    if rates:
                        return sum(rates) / len(rates)
        except Exception:
            pass
        return 0.45  # Conservative default

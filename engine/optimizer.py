"""
优化器 — 策略权重调整 + 周度参数网格搜索
"""
import json
import logging
from datetime import datetime

from sqlalchemy import select

from config import settings
from data.database import SessionLocal
from models.orm import StrategyPerformance, StrategyParams, TradeLog
from engine.regime_detector import detect_regime

logger = logging.getLogger(__name__)


class Optimizer:
    """持续优化的控制器。"""

    def __init__(self):
        self._init_performance_rows()

    def _init_performance_rows(self):
        """初始化策略表现行。"""
        with SessionLocal() as db:
            for name in ["trend", "momentum", "reversal"]:
                existing = db.execute(
                    select(StrategyPerformance).where(StrategyPerformance.strategy_name == name)
                ).scalar_one_or_none()
                if not existing:
                    db.add(StrategyPerformance(
                        strategy_name=name,
                        current_weight=settings.WEIGHT_TREND if name == "trend"
                        else settings.WEIGHT_MOMENTUM if name == "momentum"
                        else settings.WEIGHT_REVERSAL,
                    ))
                # Init params
                existing_params = db.execute(
                    select(StrategyParams).where(StrategyParams.strategy_name == name)
                ).scalar_one_or_none()
                if not existing_params:
                    default_params = {
                        "trend": {"fast_ma": 5, "slow_ma": 20, "trend_ma": 60},
                        "momentum": {"volume_ratio": 1.5, "price_surge": 0.03},
                        "reversal": {"rsi_period": 14, "oversold": 30, "overbought": 70},
                    }
                    db.add(StrategyParams(
                        strategy_name=name,
                        params_json=json.dumps(default_params.get(name, {})),
                        updated_at=datetime.now(),
                    ))
            db.commit()

    # ─── Weight Adjustment ──────────────────────────

    def update_trade_result(self, strategy_names: str, profit_pct: float):
        """
        每次交易平仓后调用，更新策略表现。
        strategy_names: "trend,momentum" (comma-separated)
        """
        if not strategy_names:
            return
        strategies = [s.strip() for s in strategy_names.split(",")]

        with SessionLocal() as db:
            for name in strategies:
                perf = db.execute(select(StrategyPerformance).where(StrategyPerformance.strategy_name == name)).scalar_one_or_none()
                if not perf:
                    continue
                perf.total_trades = (perf.total_trades or 0) + 1
                if profit_pct > 0:
                    perf.wins = (perf.wins or 0) + 1
                    # Update rolling avg win
                    n = perf.wins
                    old_avg = perf.avg_win_pct or 0
                    perf.avg_win_pct = (old_avg * (n - 1) + profit_pct) / n if n > 0 else profit_pct
                else:
                    perf.losses = (perf.losses or 0) + 1
                    n = perf.losses
                    old_avg = perf.avg_loss_pct or 0
                    perf.avg_loss_pct = (old_avg * (n - 1) + abs(profit_pct)) / n if n > 0 else abs(profit_pct)

                total = perf.wins + perf.losses
                perf.win_rate = perf.wins / total if total > 0 else 0

                # Profit factor
                gross_profit = (perf.avg_win_pct or 0) * (perf.wins or 0)
                gross_loss = (perf.avg_loss_pct or 0) * (perf.losses or 0)
                perf.profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

                perf.updated_at = datetime.now()

            db.commit()

        # Recalculate ensemble weights
        self.recalculate_weights()

    def recalculate_weights(self):
        """基于最近表现重新计算策略权重。"""
        base = {
            "trend": settings.WEIGHT_TREND,
            "momentum": settings.WEIGHT_MOMENTUM,
            "reversal": settings.WEIGHT_REVERSAL,
        }

        with SessionLocal() as db:
            for name in base:
                perf = db.execute(select(StrategyPerformance).where(StrategyPerformance.strategy_name == name)).scalar_one_or_none()
                if perf and perf.total_trades and perf.total_trades >= 5:
                    # Adjust: win_rate > 0.5 → boost, < 0.5 → penalty
                    wr = perf.win_rate or 0
                    adjustment = 1 + (wr - 0.5) * 0.5  # ±25% max
                    base[name] *= max(0.5, min(1.5, adjustment))

            # Normalize
            total = sum(base.values())
            if total > 0:
                for name in base:
                    base[name] = round(base[name] / total, 4)
                    perf = db.execute(select(StrategyPerformance).where(StrategyPerformance.strategy_name == name)).scalar_one_or_none()
                    if perf:
                        perf.current_weight = base[name]
            db.commit()

        logger.info(f"Recalculated weights: {base}")
        return base

    # ─── Weekly Grid Search ──────────────────────────

    def run_grid_search(self) -> dict:
        """
        周度参数网格搜索。
        对每个策略测试多组参数，选夏普比率最高的组合。
        运行时较长（约30-60秒），应在后台线程执行。
        """
        results = {}
        for name in ["trend", "momentum", "reversal"]:
            try:
                best = self._grid_search_strategy(name)
                results[name] = best
            except Exception as e:
                logger.error(f"Grid search failed for {name}: {e}")
                results[name] = {"error": str(e)}

        logger.info(f"Grid search complete: {results}")
        return results

    def _grid_search_strategy(self, name: str) -> dict:
        """对单个策略执行网格搜索。"""
        import numpy as np
        from data.fetcher import fetch_stock_history
        from engine.indicators import add_all_indicators
        from engine.strategies.trend import TrendStrategy
        from engine.strategies.momentum import MomentumStrategy
        from engine.strategies.reversal import ReversalStrategy

        # Define parameter grids
        grids = {
            "trend": [
                {"fast_ma": f, "slow_ma": s}
                for f in [3, 5, 10] for s in [15, 20, 30] if f < s
            ],
            "momentum": [
                {"volume_ratio": vr, "price_surge": ps}
                for vr in [1.2, 1.5, 1.8] for ps in [0.02, 0.03, 0.05]
            ],
            "reversal": [
                {"oversold": os_, "overbought": ob}
                for os_ in [25, 30, 35] for ob in [65, 70, 75]
            ],
        }

        param_combos = grids.get(name, [])
        if not param_combos:
            return {}

        # Test on a few representative stocks
        test_symbols = ["sh600519", "sz000001", "sh601318", "sz300750"]
        best_params = None
        best_sharpe = -999

        for params in param_combos[:9]:  # Limit to 9 combos max
            all_returns = []
            for sym in test_symbols[:3]:
                df = fetch_stock_history(sym, settings.OPTIMIZER_BACKTEST_DAYS)
                if df is None or df.empty or len(df) < 30:
                    continue
                df = add_all_indicators(df)

                # Create strategy with test params
                if name == "trend":
                    strat = TrendStrategy(**params)
                elif name == "momentum":
                    strat = MomentumStrategy(**params)
                else:
                    strat = ReversalStrategy(**params)

                # Simple backtest: if signal was "buy", simulate holding for 3 days
                returns = []
                for i in range(20, len(df) - 3):
                    sub_df = df.iloc[:i + 1]
                    signal = strat.generate_signal(sub_df)
                    if signal.action == "buy":
                        entry = df.iloc[i]["close"]
                        exit_ = df.iloc[min(i + 3, len(df) - 1)]["close"]
                        ret = (exit_ - entry) / entry
                        returns.append(ret)

                if returns:
                    all_returns.extend(returns)

            if all_returns:
                avg_ret = np.mean(all_returns)
                std_ret = np.std(all_returns) or 0.001
                sharpe = avg_ret / std_ret * np.sqrt(252 / 3)  # Annualized
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_params = dict(params)

        if best_params:
            with SessionLocal() as db:
                sp = db.execute(select(StrategyParams).where(StrategyParams.strategy_name == name)).scalar_one_or_none()
                if sp:
                    sp.params_json = json.dumps(best_params)
                    sp.sharpe = round(best_sharpe, 4)
                    sp.updated_at = datetime.now()
                db.commit()

        return {"params": best_params, "sharpe": round(best_sharpe, 4)} if best_params else {}

    def get_current_weights(self) -> dict:
        """获取当前策略权重。"""
        weights = {}
        with SessionLocal() as db:
            for name in ["trend", "momentum", "reversal"]:
                perf = db.execute(select(StrategyPerformance).where(StrategyPerformance.strategy_name == name)).scalar_one_or_none()
                if perf:
                    weights[name] = perf.current_weight
        return weights or {
            "trend": settings.WEIGHT_TREND,
            "momentum": settings.WEIGHT_MOMENTUM,
            "reversal": settings.WEIGHT_REVERSAL,
        }

    def get_current_params(self) -> dict:
        """获取当前策略参数。"""
        params = {}
        with SessionLocal() as db:
            for name in ["trend", "momentum", "reversal"]:
                sp = db.execute(select(StrategyParams).where(StrategyParams.strategy_name == name)).scalar_one_or_none()
                if sp:
                    params[name] = json.loads(sp.params_json)
        return params

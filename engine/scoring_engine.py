"""
多策略信号聚合 + 排名引擎
"""
import json
import logging
from datetime import datetime

import pandas as pd

from config import settings
from engine.strategies.trend import TrendStrategy
from engine.strategies.momentum import MomentumStrategy
from engine.strategies.reversal import ReversalStrategy
from engine.regime_detector import get_regime_weights
from models.orm import Signal

logger = logging.getLogger(__name__)


class ScoringEngine:
    """信号聚合和排名。"""

    def __init__(self):
        # Base weights
        self.base_weights = {
            "trend": settings.WEIGHT_TREND,
            "momentum": settings.WEIGHT_MOMENTUM,
            "reversal": settings.WEIGHT_REVERSAL,
        }

        # Override weights (from optimizer)
        self._override_weights: dict = {}

        # Strategies
        self.strategies = {
            "trend": TrendStrategy(),
            "momentum": MomentumStrategy(),
            "reversal": ReversalStrategy(),
        }

    @property
    def current_weights(self) -> dict:
        if self._override_weights:
            return dict(self._override_weights)
        return get_regime_weights(self.base_weights)

    def update_weights(self, weights: dict):
        """从 optimizer 更新权重。"""
        self._override_weights = dict(weights)
        logger.info(f"Weights updated: {weights}")

    def update_params(self, strategy_name: str, params: dict):
        """更新策略参数。"""
        if strategy_name in self.strategies:
            for k, v in params.items():
                if hasattr(self.strategies[strategy_name], k):
                    setattr(self.strategies[strategy_name], k, v)
            logger.info(f"Params updated for {strategy_name}: {params}")

    def score_stock(self, df: pd.DataFrame) -> dict:
        """
        对单只股票运行所有策略并综合打分。
        返回: {symbol, signals: {...}, composite_score, final_action, reason, ...}
        """
        results = {}
        composite = 0.0
        weights = self.current_weights

        for name, strategy in self.strategies.items():
            signal = strategy.generate_signal(df)
            results[name] = signal
            composite += signal.score * weights.get(name, 0.33)

        composite = round(composite, 4)

        # Decision
        buy_signals = sum(1 for s in results.values() if s.action == "buy")
        sell_signals = sum(1 for s in results.values() if s.action == "sell")

        if composite >= settings.BUY_THRESHOLD and buy_signals >= 1:
            action = "buy"
        elif composite <= -settings.SELL_THRESHOLD and sell_signals >= 2:
            action = "sell"
        else:
            action = "hold"

        # Reason
        reasons = [f"{n}={s.score:.2f}({s.action})" for n, s in results.items()]
        regime = get_regime_weights(self.base_weights)  # Will be cached
        reason = f"composite={composite:.3f} | {' '.join(reasons)}"

        return {
            "composite_score": composite,
            "final_action": action,
            "decision_reason": reason,
            "strategy_weights": json.dumps(weights),
            "signals": results,
        }

    def rank_candidates(self, stock_scores: list[dict], held_symbols: set) -> dict:
        """
        对所有候选股的评分结果进行排名。
        stock_scores: [{symbol, name, ...score fields}]
        held_symbols: 已持有的股票set

        返回: {buy_candidates: [...], sell_candidates: [...]}
        """
        buy_list = []
        sell_list = []

        for s in stock_scores:
            if s["symbol"] in held_symbols:
                # Already held — check if we should sell
                if s["final_action"] == "sell":
                    sell_list.append(s)
            else:
                if s["final_action"] == "buy":
                    buy_list.append(s)

        # Sort buy by composite_score descending
        buy_list.sort(key=lambda x: x["composite_score"], reverse=True)
        sell_list.sort(key=lambda x: x["composite_score"])  # Most negative first

        # Limit buys to available slots
        available_slots = settings.MAX_POSITIONS - len(held_symbols)
        buy_list = buy_list[:max(0, available_slots)]

        return {"buy": buy_list, "sell": sell_list}

    def log_signal(self, symbol: str, name: str, score_result: dict, db_session):
        """记录信号到数据库。"""
        signals = score_result["signals"]
        s = Signal(
            symbol=symbol,
            name=name,
            trend_score=signals["trend"].score,
            trend_action=signals["trend"].action,
            momentum_score=signals["momentum"].score,
            momentum_action=signals["momentum"].action,
            reversal_score=signals["reversal"].score,
            reversal_action=signals["reversal"].action,
            composite_score=score_result["composite_score"],
            final_action=score_result["final_action"],
            decision_reason=score_result["decision_reason"],
            market_regime=str(get_regime_weights({})),
            strategy_weights=score_result["strategy_weights"],
            scanned_at=datetime.now(),
        )
        db_session.add(s)

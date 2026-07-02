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
from engine.regime_detector import detect_regime, get_regime_weights
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

        # Dead-weight tracking: 趋势策略连续无信号计数
        self._trend_silent_count = 0
        self._trend_silent_threshold = 3  # 连续3次无信号则触发权重转移

        # Strategies
        self.strategies = {
            "trend": TrendStrategy(),
            "momentum": MomentumStrategy(),
            "reversal": ReversalStrategy(),
        }

    @property
    def current_weights(self) -> dict:
        base = self._override_weights if self._override_weights else dict(self.base_weights)

        # 趋势策略连续无信号 → 转移权重给动量（不在这里记日志，避免每只股票都打）
        if self._trend_silent_count >= self._trend_silent_threshold:
            base = dict(base)  # 拷贝，不修改原值
            transfer = base.get("trend", 0.4) * 0.5  # 转一半
            base["trend"] -= transfer
            base["momentum"] += transfer

        return get_regime_weights(base)

    @property
    def trend_weight_adjusted(self) -> bool:
        """趋势权重是否已被自动削减。"""
        return self._trend_silent_count >= self._trend_silent_threshold

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
            composite += signal.score * weights.get(name, 0.0)

        composite = round(composite, 4)

        # Decision
        buy_signals = sum(1 for s in results.values() if s.action == "buy")
        sell_signals = sum(1 for s in results.values() if s.action == "sell")

        # 强信号绕过：任一策略自身置信度达标即触发
        strong_buy = any(
            s.confidence >= settings.STRONG_SIGNAL_CONFIDENCE and s.action == "buy"
            for s in results.values()
        )
        strong_sell = any(
            s.confidence >= settings.STRONG_SIGNAL_CONFIDENCE and s.action == "sell"
            for s in results.values()
        )

        # ── 冲突检测: 策略严重分歧 → 不交易 ──
        scores_list = [s.score for s in results.values()]
        has_strong_buy_signal = any(s > 0.5 for s in scores_list)
        has_strong_sell_signal = any(s < -0.5 for s in scores_list)
        conflict = has_strong_buy_signal and has_strong_sell_signal

        # ── 共识检测: 三策略一致 → 降低门槛 ──
        consensus_buy = buy_signals >= 2 and sell_signals == 0
        consensus_sell = sell_signals >= 2 and buy_signals == 0
        all_agree_buy = buy_signals >= 3
        all_agree_sell = sell_signals >= 3

        if conflict:
            # 矛盾信号 → 观望（除非某策略极端强势）
            if strong_buy and not has_strong_sell_signal:
                action = "buy"
            elif strong_sell and not has_strong_buy_signal:
                action = "sell"
            else:
                action = "hold"
        elif all_agree_buy and composite > 0:
            # 三策略全票通过 → 大幅降低门槛
            action = "buy"
        elif all_agree_sell and composite < 0:
            action = "sell"
        elif strong_buy and composite > 0:
            action = "buy"
        elif consensus_buy and composite >= settings.BUY_THRESHOLD * 0.6:
            # 二策略同意 → 降低门槛 40%
            action = "buy"
        elif composite >= settings.BUY_THRESHOLD and buy_signals >= 1:
            action = "buy"
        elif strong_sell and composite < 0:
            action = "sell"
        elif consensus_sell and composite <= -(settings.SELL_THRESHOLD * 0.6):
            action = "sell"
        elif (
            composite <= -settings.SELL_THRESHOLD and sell_signals >= 1
        ) or (
            composite <= -(settings.SELL_THRESHOLD * 0.5) and sell_signals >= 2
        ):
            action = "sell"
        else:
            action = "hold"

        # Reason
        reasons = [f"{n}={s.score:.2f}({s.action})" for n, s in results.items()]
        reason = f"composite={composite:.3f} | {' '.join(reasons)}"

        return {
            "composite_score": composite,
            "final_action": action,
            "decision_reason": reason,
            "strategy_weights": json.dumps(weights),
            "signals": results,
        }

    def track_trend_activity(self, stock_scores: list[dict]):
        """
        每次扫描结束后调用，跟踪趋势策略是否产生有效信号。
        连续 N 次无信号 → 自动降低趋势权重。
        """
        has_trend_action = any(
            s.get("signals", {}).get("trend") and s["signals"]["trend"].action in ("buy", "sell")
            for s in stock_scores
        )
        if has_trend_action:
            if self._trend_silent_count >= self._trend_silent_threshold:
                # 趋势恢复 → 日志
                logger.info(
                    f"Trend strategy recovered after {self._trend_silent_count} silent scans, "
                    f"restoring normal weights"
                )
            self._trend_silent_count = 0
        else:
            self._trend_silent_count += 1
            if self._trend_silent_count == self._trend_silent_threshold:
                # 刚触发阈值 → 打印一次转移量
                base_w = self.base_weights
                transfer = base_w.get("trend", 0.4) * 0.5
                logger.warning(
                    f"Trend strategy silent for {self._trend_silent_count} scans — "
                    f"auto-redistributing {transfer:.1%} weight from trend to momentum"
                )
            elif self._trend_silent_count > self._trend_silent_threshold:
                logger.warning(
                    f"Trend strategy still silent ({self._trend_silent_count} scans), "
                    f"weights remain adjusted"
                )

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
            market_regime=json.dumps(detect_regime(), ensure_ascii=False),
            strategy_weights=score_result["strategy_weights"],
            scanned_at=datetime.now(),
        )
        db_session.add(s)

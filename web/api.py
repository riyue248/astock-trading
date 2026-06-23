"""
REST API 端点
"""
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func, desc

import web.app as app_module
from data.database import SessionLocal
from models.orm import TradeLog, Signal, EquitySnapshot, StrategyPerformance, StrategyParams
from models.schemas import TradeQuery

logger = logging.getLogger(__name__)
router = APIRouter(tags=["api"])

# Helper to get current instances (set by lifespan)
def _pa(): return app_module.paper_account
def _ts(): return app_module.trading_scheduler
def _se(): return app_module.scoring_engine
def _op(): return app_module.optimizer


# ─── Portfolio ────────────────────────────────────

@router.get("/portfolio")
async def get_portfolio():
    if not _pa():
        return {"error": "Account not initialized"}
    return _pa().get_summary()


# ─── Positions ────────────────────────────────────

@router.get("/positions")
async def get_positions():
    if not _pa():
        return {"positions": []}
    return {"positions": list(_pa().positions.values())}


# ─── Trades ───────────────────────────────────────

@router.get("/trades")
async def get_trades(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    symbol: str = Query(None),
    side: str = Query(None),
    close_reason: str = Query(None),
):
    with SessionLocal() as db:
        stmt = select(TradeLog)
        if symbol:
            stmt = stmt.where(TradeLog.symbol == symbol)
        if side:
            stmt = stmt.where(TradeLog.side == side)
        if close_reason:
            stmt = stmt.where(TradeLog.close_reason == close_reason)
        stmt = stmt.order_by(desc(TradeLog.id)).offset((page - 1) * limit).limit(limit)
        trades = db.execute(stmt).scalars().all()

        # Count
        count_stmt = select(func.count(TradeLog.id))
        if symbol:
            count_stmt = count_stmt.where(TradeLog.symbol == symbol)
        total = db.execute(count_stmt).scalar() or 0

    return {
        "trades": [t.to_dict() for t in trades],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.get("/trades/stats")
async def get_trade_stats():
    with SessionLocal() as db:
        all_trades = db.execute(
            select(TradeLog)
        ).scalars().all()

        buys = [t for t in all_trades if t.side == "buy"]
        sells = [t for t in all_trades if t.side == "sell"]
        wins = [t for t in sells if (t.profit_pct or 0) > 0]
        losses = [t for t in sells if (t.profit_pct or 0) < 0]

        return {
            "total_trades": len(all_trades),
            "open_positions": len(buys) - len(sells),
            "closed_trades": len(sells),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(sells) if sells else 0,
            "total_pnl": sum(t.profit_amount or 0 for t in sells),
            "avg_win_pct": sum(t.profit_pct or 0 for t in wins) / len(wins) if wins else 0,
            "avg_loss_pct": sum(t.profit_pct or 0 for t in losses) / len(losses) if losses else 0,
        }


# ─── Signals ──────────────────────────────────────

@router.get("/signals")
async def get_signals(limit: int = Query(50, ge=1, le=200)):
    with SessionLocal() as db:
        signals = db.execute(
            select(Signal).order_by(desc(Signal.id)).limit(limit)
        ).scalars().all()
    return {"signals": [s.to_dict() for s in signals]}


# ─── Equity ───────────────────────────────────────

@router.get("/equity")
async def get_equity():
    with SessionLocal() as db:
        snaps = db.execute(
            select(EquitySnapshot).order_by(EquitySnapshot.date)
        ).scalars().all()
    return {"equity": [s.to_dict() for s in snaps]}


# ─── Performance ──────────────────────────────────

@router.get("/performance")
async def get_performance():
    with SessionLocal() as db:
        perfs = db.execute(select(StrategyPerformance)).scalars().all()
    return {"strategies": [p.to_dict() for p in perfs]}


# ─── Params ───────────────────────────────────────

@router.get("/params")
async def get_params():
    with SessionLocal() as db:
        params = db.execute(select(StrategyParams)).scalars().all()
    return {"params": [p.to_dict() for p in params]}


# ─── Market Overview (717 stocks) ────────────────

@router.get("/market")
async def get_market():
    """市场总览：指数 + 涨幅榜 + 板块热度"""
    try:
        from data.fetcher import get_candidate_pool, fetch_index_spot
        from data.sector_analysis import analyze_sectors

        # Fetch all 717 stocks
        spots = get_candidate_pool(200)

        # Top gainers (change > 0 only)
        gainers = [s for s in spots if s.get("涨跌幅", 0) > 0]
        gainers.sort(key=lambda x: x.get("涨跌幅", 0), reverse=True)

        # Top losers (change < 0 only)
        losers = [s for s in spots if s.get("涨跌幅", 0) < 0]
        losers.sort(key=lambda x: x.get("涨跌幅", 0))

        # Indices
        idx_df = fetch_index_spot()
        indices = idx_df.to_dict("records") if not idx_df.empty else []

        # Sectors
        sector_data = analyze_sectors()

        return {
            "indices": indices,
            "top_gainers": gainers[:20],
            "top_losers": losers[:20],
            "total_stocks": len(spots),
            "sectors": sector_data.get("sectors", []),
            "data_time": spots[0].get("时间", "") if spots else "",
        }
    except Exception as e:
        return {"error": str(e), "indices": [], "top_gainers": [], "top_losers": [], "sectors": []}


# ─── Sector Analysis ─────────────────────────────

@router.get("/sectors")
async def get_sectors():
    """获取板块热度分析"""
    try:
        from data.sector_analysis import analyze_sectors
        return analyze_sectors()
    except Exception as e:
        return {"error": str(e), "sectors": []}


# ─── Status ───────────────────────────────────────

@router.get("/status")
async def get_status():
    if not _ts():
        return {"running": False}
    status = _ts().get_status()
    # Add account info
    if _pa():
        status["equity"] = _pa().total_equity()
        status["positions"] = _pa().position_count
    return status


# ─── Control ──────────────────────────────────────

@router.post("/control")
async def control_system(data: dict):
    action = data.get("action", "")
    if not _ts():
        raise HTTPException(500, "Scheduler not initialized")

    if action == "pause":
        _ts().pause()
        return {"status": "paused"}
    elif action == "resume":
        _ts().resume()
        return {"status": "resumed"}
    elif action == "scan":
        result = await _ts().run_manual_scan()
        return {"status": "scanned", "result": result}
    elif action == "optimize":
        if _op():
            result = _op().recalculate_weights()
            if _se():
                _se().update_weights(result)
            return {"status": "optimized", "weights": result}
    else:
        raise HTTPException(400, f"Unknown action: {action}")

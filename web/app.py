"""
Web 仪表盘 — FastAPI 应用
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import jinja2
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import settings
from data.database import init_db

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# ─── Shared state ──────────────────────────────────
sse_queues: set[asyncio.Queue] = set()
trading_scheduler = None
scoring_engine = None
paper_account = None
optimizer = None

# ─── Templates ─────────────────────────────────────
TPL_DIR = Path(__file__).parent / "templates"
TPL_DIR.mkdir(parents=True, exist_ok=True)

templates_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TPL_DIR)),
    autoescape=jinja2.select_autoescape(),
    cache_size=0,
)
templates = Jinja2Templates(env=templates_env)


async def broadcast_sse(data: dict):
    """Push data to all SSE clients."""
    dead = set()
    for q in sse_queues:
        try:
            if q.full():
                _ = q.get_nowait()
            q.put_nowait(data)
        except Exception:
            dead.add(q)
    sse_queues.difference_update(dead)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global trading_scheduler, scoring_engine, paper_account, optimizer

    logger.info("Starting Paper Trading System...")
    init_db()

    # Init components
    from engine.paper_account import PaperAccount
    from engine.scoring_engine import ScoringEngine
    from engine.scheduler import TradingScheduler
    from engine.optimizer import Optimizer
    from engine.strategy_engine import StrategyEngine

    paper_account = PaperAccount(settings.INITIAL_CAPITAL)
    paper_account.load_state()

    scoring_engine = ScoringEngine()
    optimizer = Optimizer()

    # Apply persisted weights
    weights = optimizer.get_current_weights()
    scoring_engine.update_weights(weights)
    params = optimizer.get_current_params()
    for name, p in params.items():
        scoring_engine.update_params(name, p)

    strategy_engine = StrategyEngine(paper_account, scoring_engine)

    trading_scheduler = TradingScheduler()
    trading_scheduler.set_engine(strategy_engine)
    trading_scheduler.set_broadcast(broadcast_sse)

    await trading_scheduler.start()
    yield
    await trading_scheduler.stop()
    logger.info("Paper Trading System stopped.")


def create_app() -> FastAPI:
    app = FastAPI(title="Paper Trading Dashboard", version="0.1.0", lifespan=lifespan)
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    from web.api import router as api_router
    from web.sse import router as sse_router
    from web.pages import router as pages_router

    app.include_router(api_router, prefix="/api")
    app.include_router(sse_router, prefix="/api")
    app.include_router(pages_router)

    @app.get("/health")
    async def health():
        return {"status": "ok", "data_source": "sina"}

    return app


app = create_app()

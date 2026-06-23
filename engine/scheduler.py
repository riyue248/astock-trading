"""
主调度器 — 5分钟交易循环
"""
import asyncio
import logging
import time
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import settings
from utils.trading_calendar import is_trading_time

logger = logging.getLogger(__name__)


class TradingScheduler:
    """交易循环调度器。"""

    def __init__(self):
        self._scheduler: AsyncIOScheduler | None = None
        self._last_scan = 0.0
        self.scan_count = 0
        self._engine = None       # StrategyEngine, set after init
        self._account = None      # PaperAccount
        self._broadcast = None    # SSE broadcast callback
        self._paused = False     # Allow manual pause via API
        self._afternoon_snapshot_done = False
        self._executor = None    # ThreadPoolExecutor, set in start()
        self._scheduler_started = False  # Track actual startup success
        self._last_heartbeat = 0.0       # Track last job execution time

    @property
    def is_paused(self):
        return self._paused

    def set_engine(self, engine):
        self._engine = engine
        self._account = engine.account if engine else None

    def set_broadcast(self, callback):
        self._broadcast = callback

    async def start(self):
        import concurrent.futures
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="scan")
        self._scheduler = AsyncIOScheduler()

        # ── Handle APScheduler v3 vs v4 compatibility ──
        # v3: start() is synchronous (starts bg thread)
        # v4: start() is async coroutine (must be awaited)
        start_result = self._scheduler.start()
        if asyncio.iscoroutine(start_result):
            await start_result
            logger.info("APScheduler v4+ detected — start() awaited")

        # v4: add_job may be async; v3: synchronous
        add_result = self._scheduler.add_job(
            self._check_and_scan,
            trigger=IntervalTrigger(seconds=settings.CHECK_INTERVAL_SECONDS),
            id="scan_loop",
            replace_existing=True,
        )
        if asyncio.iscoroutine(add_result):
            await add_result

        self._scheduler_started = True
        self._last_heartbeat = time.time()

        # Immediate startup heartbeat to verify scheduler is alive
        is_trading, status = is_trading_time()
        logger.info(
            "Trading scheduler STARTED | check_interval=%ds | scan_interval=%ds | "
            "trading_status=%s | is_trading=%s",
            settings.CHECK_INTERVAL_SECONDS, settings.SCAN_INTERVAL_SECONDS,
            status, is_trading,
        )

        # Run an immediate check so user doesn't wait 60s for first cycle
        await self._check_and_scan()

    async def stop(self):
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None
        logger.info("Trading scheduler stopped")

    def pause(self):
        self._paused = True
        logger.info("Trading PAUSED by user")

    def resume(self):
        self._paused = False
        logger.info("Trading RESUMED by user")

    async def _check_and_scan(self):
        """每60秒检查一次，交易时段每5分钟扫描一次。"""
        self._last_heartbeat = time.time()

        if self._paused or not self._engine:
            return

        is_trading, status = is_trading_time()

        # Broadcast status
        if self._broadcast:
            try:
                await self._broadcast({
                    "type": "status",
                    "is_trading": is_trading,
                    "status": status,
                    "paused": self._paused,
                    "scan_count": self.scan_count,
                })
            except Exception:
                pass

        # Reset snapshot flag when market opens
        if is_trading:
            self._afternoon_snapshot_done = False

        # End-of-day snapshot (check even outside trading hours)
        if status == "closed" and not self._afternoon_snapshot_done:
            try:
                self._account.snapshot_equity()
                self._afternoon_snapshot_done = True
                logger.info("End-of-day equity snapshot saved")
            except Exception:
                pass

        if not is_trading:
            return

        # Check if 5 minutes elapsed since last scan
        now = time.time()
        if now - self._last_scan < settings.SCAN_INTERVAL_SECONDS:
            return

        # 防止上次扫描未完成时再次触发
        if getattr(self, '_scan_running', False):
            logger.info("Previous scan still running, skip this cycle")
            return

        self._last_scan = now
        self.scan_count += 1
        self._scan_running = True

        logger.info(f"=== Scan #{self.scan_count} at {datetime.now().strftime('%H:%M:%S')} ===")

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(self._executor, self._engine.run_scan)
            if self._broadcast:
                await self._broadcast({
                    "type": "scan_result",
                    **result,
                })
        except Exception as e:
            logger.error(f"Scan error: {e}", exc_info=True)
            if self._broadcast:
                try:
                    await self._broadcast({
                        "type": "scan_error",
                        "error": str(e),
                    })
                except Exception:
                    pass
        finally:
            self._scan_running = False

    async def run_manual_scan(self) -> dict:
        """手动触发一次扫描（API调用）。

        将扫描提交到线程池后台执行，立即返回。
        避免因扫描耗时（~2分钟）导致 HTTP 超时。
        """
        if not self._engine:
            return {"error": "Engine not initialized"}
        if not self._executor:
            return {"error": "Executor not initialized"}

        # 防止重复触发
        if getattr(self, '_scan_running', False):
            return {"status": "scan_already_running", "scan_count": self.scan_count}

        self._scan_running = True

        async def _run_scan_bg():
            try:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(self._executor, self._engine.run_scan)
                if self._broadcast:
                    await self._broadcast({
                        "type": "scan_result",
                        **result,
                    })
            except Exception as e:
                logger.error(f"Manual scan error: {e}", exc_info=True)
                if self._broadcast:
                    try:
                        await self._broadcast({
                            "type": "scan_error",
                            "error": str(e),
                        })
                    except Exception:
                        pass
            finally:
                self._scan_running = False

        asyncio.create_task(_run_scan_bg())
        return {"status": "scan_started", "message": "扫描已在后台启动，结果请查看仪表盘"}

    def get_status(self) -> dict:
        is_trading, status = is_trading_time()
        heartbeat_ago = time.time() - self._last_heartbeat if self._last_heartbeat else None
        return {
            "running": self._scheduler_started,
            "paused": self._paused,
            "trading": is_trading,
            "trading_status": status,
            "scan_count": self.scan_count,
            "last_scan": datetime.fromtimestamp(self._last_scan).isoformat()
            if self._last_scan else None,
            "scheduler_healthy": heartbeat_ago is not None and heartbeat_ago < 180,
            "last_heartbeat_sec_ago": round(heartbeat_ago, 1) if heartbeat_ago else None,
            "scan_running": getattr(self, '_scan_running', False),
        }

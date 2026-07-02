"""
集中配置 — 模拟交易系统
"""
from datetime import time
from pathlib import Path


class Settings:
    # --- Paths ---
    PROJECT_ROOT = Path(__file__).parent
    DATA_DIR = PROJECT_ROOT / "data"
    DB_PATH = DATA_DIR / "papertrade.db"

    # --- Account ---
    INITIAL_CAPITAL = 500_000.0
    COMMISSION_RATE = 0.00025       # 0.025% per side
    MIN_SHARES_PER_TRADE = 100      # 1 lot = 100 shares
    MAX_POSITIONS = 10              # Max concurrent positions
    MAX_POSITION_PCT = 0.30         # Single position ≤ 30%
    MAX_PORTFOLIO_DRAWDOWN = 0.15   # Halt buys if drawdown > 15%

    # --- Stop Loss / Take Profit ---
    STOP_LOSS_PCT = -0.08           # -8%
    TAKE_PROFIT_PCT = 0.15          # +15%

    # --- Strategy Weights (initial) ---
    WEIGHT_TREND = 0.40
    WEIGHT_MOMENTUM = 0.35
    WEIGHT_REVERSAL = 0.25

    # --- Scoring ---
    BUY_THRESHOLD = 0.18            # Composite score to trigger buy (曾0.40→0.25→0.18)
    SELL_THRESHOLD = 0.30           # Composite score to trigger sell
    STRONG_SIGNAL_CONFIDENCE = 0.75 # Bypass threshold if any strategy is this confident
    CANDIDATE_POOL_SIZE = 300       # Top N by volume (曾717→200→300)
    CANDIDATE_MIN_VALID = 50        # Min valid candidates before retry with double pool

    # --- Trading hours ---
    MORNING_START = time(9, 30)
    MORNING_END = time(11, 30)
    AFTERNOON_START = time(13, 0)
    AFTERNOON_END = time(15, 0)

    # --- Scan / Scheduler ---
    SCAN_INTERVAL_SECONDS = 300     # 5 minutes
    CHECK_INTERVAL_SECONDS = 60     # Check every 60s if scan is due
    DATA_CACHE_TTL = 30             # Spot data cache TTL (seconds)

    # --- Optimizer ---
    OPTIMIZER_TRADE_LOOKBACK = 20   # Recent trades for win rate calc
    OPTIMIZER_BACKTEST_DAYS = 60    # Days for weekly grid search
    OPTIMIZER_RUN_DAY = "saturday"  # Day to run grid search
    OPTIMIZER_RUN_HOUR = 9          # Run at 9:00 AM

    # --- Chart ---
    DEFAULT_HISTORY_DAYS = 90       # Default lookback for indicators


settings = Settings()

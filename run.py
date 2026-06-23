"""
自动化A股模拟交易系统 — 启动入口
"""
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("=" * 50)
    print("  Automated Paper Trading System")
    print("  自动化A股模拟交易系统")
    print("=" * 50)
    print(f"  Initial Capital: ¥500,000")
    print(f"  Strategy: Trend + Momentum + Reversal")
    print(f"  Scan: Every 5 min during trading hours")
    print(f"  Dashboard: http://localhost:8000")
    print("=" * 50)

    import uvicorn
    uvicorn.run(
        "web.app:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )

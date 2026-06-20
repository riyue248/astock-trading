"""
数据获取 — 新浪财经API
复用 E:/量化项目 中的 Sina 数据源
"""
import logging
import os
import re
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

from config import settings

logger = logging.getLogger(__name__)

# Disable system proxy
os.environ["NO_PROXY"] = "*"
try:
    import urllib.request
    urllib.request.getproxies = lambda: {}
except Exception:
    pass


def _make_session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://finance.sina.com.cn",
    })
    return s


def _parse_sina_spot_line(line: str) -> dict | None:
    """解析新浪实时行情行。"""
    m = re.search(r'hq_str_(\w+)="(.+)"', line)
    if not m or len((fields := m.group(2).split(","))) < 6:
        return None
    code = m.group(1)
    return {
        "代码": code, "名称": fields[0],
        "今开": float(fields[1]) if fields[1] else 0,
        "昨收": float(fields[2]) if fields[2] else 0,
        "最新价": float(fields[3]) if fields[3] else 0,
        "最高": float(fields[4]) if fields[4] else 0,
        "最低": float(fields[5]) if fields[5] else 0,
        "成交量": float(fields[8]) if len(fields) > 8 and fields[8] else 0,
        "成交额": float(fields[9]) if len(fields) > 9 and fields[9] else 0,
        "涨跌额": float(fields[3]) - float(fields[2]) if fields[3] and fields[2] else 0,
        "涨跌幅": round((float(fields[3]) - float(fields[2])) / float(fields[2]) * 100, 2)
        if fields[2] and fields[3] and float(fields[2]) > 0 else 0,
    }


# Cache
_spot_cache: tuple[float, list[dict]] | None = None


def fetch_spot_batch(symbols: list[str]) -> list[dict]:
    """批量获取实时行情（新浪，主力）。"""
    if not symbols:
        return []
    results = []
    for i in range(0, len(symbols), 80):
        batch = symbols[i:i + 80]
        try:
            url = "http://hq.sinajs.cn/list=" + ",".join(batch)
            resp = _make_session().get(url, timeout=10)
            for line in resp.text.split("\n"):
                parsed = _parse_sina_spot_line(line.strip())
                if parsed:
                    results.append(parsed)
        except Exception as e:
            logger.warning(f"Spot batch fetch error: {e}")
    return results


# ─── Tencent API (backup, no proxy issues) ──────────

_TX_HEADERS = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}


def _tx_symbol(sina_code: str) -> str:
    """新浪代码 → 腾讯代码格式: sh600519 → sh600519, sz000001 → sz000001"""
    return sina_code


def fetch_spot_tencent(symbols: list[str]) -> list[dict]:
    """
    腾讯实时行情（备用数据源）。
    接口: qt.gtimg.cn
    格式: 每行以 ~ 分隔字段
    """
    if not symbols:
        return []
    # Convert sina format to tencent format if needed
    tx_codes = [_tx_symbol(s) for s in symbols]
    batch = ",".join(tx_codes[:50])  # 腾讯单次限制约50个代码
    try:
        url = f"https://qt.gtimg.cn/q={batch}"
        resp = _make_session().get(url, headers=_TX_HEADERS, timeout=10)
        results = []
        for line in resp.text.strip().split("\n"):
            line = line.strip()
            if not line or "=" not in line:
                continue
            # Parse: v_sh600519="1~贵州茅台~1235.00~..."
            m = re.search(r'v_(\w+)="(.+)"', line)
            if not m:
                continue
            code = m.group(1)
            fields = m.group(2).split("~")
            if len(fields) < 40:
                continue
            results.append({
                "代码": code, "名称": fields[1],
                "最新价": float(fields[3]) if fields[3] else 0,
                "昨收": float(fields[4]) if fields[4] else 0,
                "今开": float(fields[5]) if fields[5] else 0,
                "成交量": float(fields[6]) if fields[6] else 0,
                "最高": float(fields[33]) if fields[33] else 0,
                "最低": float(fields[34]) if fields[34] else 0,
                "成交额": float(fields[37]) if fields[37] else 0,
                "涨跌幅": float(fields[32]) if fields[32] else 0,
                "涨跌额": float(fields[31]) if fields[31] else 0,
                "换手率": float(fields[38]) if len(fields) > 38 and fields[38] else 0,
                "市盈率-动态": float(fields[39]) if len(fields) > 39 and fields[39] else 0,
            })
        return results
    except Exception as e:
        logger.warning(f"Tencent spot error: {e}")
        return []


def get_candidate_pool(top_n: int = None) -> list[dict]:
    """
    获取候选股票池（成交量前N）。
    如果盘中拿不到实时成交量排序，先用预设的活跃股票池。
    """
    if top_n is None:
        top_n = settings.CANDIDATE_POOL_SIZE

    # 活跃股票池（成交量前100 + 主流指数成分股）
    active_stocks = [
        # 金融
        "sh601398", "sh601939", "sh601288", "sh601328", "sh600036",
        "sh601166", "sh600000", "sh600030", "sh601318", "sh601628",
        "sh601601", "sh600837", "sz000001", "sz002142",
        # 消费
        "sh600519", "sz000858", "sz000568", "sz002304", "sh600887",
        "sh600809", "sz000333", "sz002475", "sz300750", "sz002594",
        # 科技
        "sh688981", "sh603259", "sz300059", "sh600276", "sz002415",
        "sh601012", "sh600585", "sh600031", "sz000651", "sz300015",
        # 周期
        "sh600900", "sh601857", "sh600028", "sh601088", "sh600188",
        "sz000002", "sz001979", "sh600048",
        # 医药
        "sh600196", "sz300760", "sh600763", "sh603392",
        # 新能源
        "sz300274", "sh688390", "sz002129",
        # 半导体
        "sh688256", "sh688041", "sz002049",
        # 其他活跃
        "sz000725", "sh600418", "sz300124", "sh688111",
        "sz002230", "sh600150", "sz000063", "sh601899",
        "sh600941", "sz300308", "sh688012",
    ]

    # Try to get real-time volume ranking
    try:
        spots = fetch_spot_batch(active_stocks[:80])
        spots.sort(key=lambda x: x.get("成交量", 0), reverse=True)
        return spots[:top_n]
    except Exception:
        pass

    return fetch_spot_batch(active_stocks[:top_n])


def fetch_stock_history(symbol: str, days: int = None) -> pd.DataFrame:
    """
    获取个股历史K线（通过AKShare的Sina数据源）。
    """
    if days is None:
        days = settings.DEFAULT_HISTORY_DAYS

    code = str(symbol).zfill(6)
    prefix = "sh" if code.startswith(("6", "9")) else "sz"
    sina_code = f"{prefix}{code}"

    try:
        import akshare as ak
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        df = ak.stock_zh_a_daily(
            symbol=sina_code, start_date=start_date,
            end_date=end_date, adjust="qfq",
        )
        if df is None or df.empty:
            return pd.DataFrame()

        col_map = {
            "date": "date", "open": "open", "high": "high",
            "low": "low", "close": "close", "volume": "volume",
            "amount": "amount", "turnover": "turnover",
        }
        df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        if "close" in df.columns and "change_pct" not in df.columns:
            df["change_pct"] = df["close"].pct_change() * 100

        return df
    except Exception as e:
        logger.warning(f"History fetch error for {symbol}: {e}")
        return pd.DataFrame()


def fetch_index_spot() -> pd.DataFrame:
    """获取主要指数行情。"""
    symbols = ["sh000001", "sz399001", "sz399006", "sh000688"]
    url = "http://hq.sinajs.cn/list=" + ",".join(symbols)
    try:
        resp = _make_session().get(url, timeout=10)
        results = []
        for line in resp.text.split("\n"):
            m = re.search(r'hq_str_(\w+)="(.+)"', line.strip())
            if not m:
                continue
            f = m.group(2).split(",")
            if len(f) < 6:
                continue
            name_map = {"sh000001": "上证指数", "sz399001": "深证成指",
                        "sz399006": "创业板指", "sh000688": "科创50"}
            code_map = {"sh000001": "000001", "sz399001": "399001",
                        "sz399006": "399006", "sh000688": "000688"}
            results.append({
                "code": code_map.get(m.group(1), m.group(1)),
                "name": name_map.get(m.group(1), f[0]),
                "price": float(f[3]) if f[3] else 0,
                "change_pct": round((float(f[3]) - float(f[2])) / float(f[2]) * 100, 2)
                if f[2] and f[3] and float(f[2]) > 0 else 0,
            })
        return pd.DataFrame(results)
    except Exception as e:
        logger.warning(f"Index fetch error: {e}")
        return pd.DataFrame()

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


# Index constituent code cache
_INDEX_CODES: list[str] | None = None


def _load_index_codes() -> list[str]:
    """加载沪深300 + 中证500成分股代码（缓存在内存）。"""
    global _INDEX_CODES
    if _INDEX_CODES is not None and len(_INDEX_CODES) > 0:
        return _INDEX_CODES

    codes = []
    try:
        import akshare as ak
        for idx in ["000300", "000905"]:
            try:
                df = ak.index_stock_cons(symbol=idx)
                if "品种代码" in df.columns:
                    codes.extend(df["品种代码"].tolist())
                elif "code" in df.columns:
                    codes.extend(df["code"].tolist())
            except Exception:
                pass
        codes = [str(c).zfill(6) for c in codes]
        codes = list(set(codes))
        if len(codes) > 100:
            _INDEX_CODES = codes
            logger.info(f"Loaded {len(codes)} index constituent codes")
    except Exception as e:
        logger.warning(f"Failed to load index codes: {e}")

    # Fallback: hardcoded 200+ active stocks
    if not _INDEX_CODES or len(_INDEX_CODES) < 100:
        _INDEX_CODES = [
            "600519","600036","601318","600276","600900","601398","601939",
            "600030","601166","600887","603259","600809","601012","600585",
            "600031","688981","688256","688041","601857","600028","601088",
            "600188","600048","601628","601601","600837","600000","600196",
            "600763","603392","688111","688012","603288","601216","600968",
            "600808","600418","600150","601899","600941","601328","601288",
            "600050","600104","600690","600406","600570","600588","600795",
            "600886","600893","600999","601006","601111","601668","601766",
            "601800","601919","603986","000001","000002","000858","002594",
            "300750","000333","002415","000651","300059","002475","000568",
            "002304","000725","300015","002142","000776","002230","300124",
            "000063","002049","000977","002236","300274","688390","002129",
            "300760","002517","300474","001386","688819","001203","600132",
            "000630","002155","300450","600233","002092","600499","000831",
            "002603","600346","600426","000975","300308","688390",
        ]
    return _INDEX_CODES


def get_candidate_pool(top_n: int = None) -> list[dict]:
    """
    获取候选股票池（从沪深300+中证500成分股中拉实时行情）。
    """
    if top_n is None:
        top_n = settings.CANDIDATE_POOL_SIZE

    codes = _load_index_codes()
    # Convert to Sina format
    sina_codes = []
    for c in codes:
        c = str(c).zfill(6)
        prefix = "sh" if c.startswith(("6", "9")) else "sz"
        sina_codes.append(f"{prefix}{c}")

    # Batch fetch
    all_spots = fetch_spot_tencent(sina_codes[:top_n])
    if not all_spots:
        all_spots = fetch_spot_batch(sina_codes[:top_n])

    # Sort by volume for active selection
    if all_spots:
        all_spots.sort(key=lambda x: x.get("成交量", 0), reverse=True)

    return all_spots[:top_n]


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

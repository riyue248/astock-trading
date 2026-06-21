"""
板块分析 — 基于行业分组计算板块平均涨幅
不使用 Eastmoney，纯 Sina/Tencent 实时数据
"""
import logging
from functools import lru_cache

import pandas as pd

from data.fetcher import fetch_spot_tencent

logger = logging.getLogger(__name__)

# 热门板块 → 成分股（沪深300+中证500范围内）
SECTOR_STOCKS = {
    "半导体": [
        "sh688981","sh688256","sh688041","sz002049","sh603986","sh688012",
        "sh688396","sh688126","sh688536","sh688200","sh603290","sh688608",
        "sz300661","sz300782","sh600460","sz002185","sh688385","sz300623",
    ],
    "存储/芯片": [
        "sh688256","sh688041","sh603986","sh688385","sz002049","sh688525",
        "sz300474","sh688110","sz301308","sh688123","sz002415","sz000063",
        "sz300857","sh603501","sh688008",
    ],
    "AI算力": [
        "sz002415","sz300308","sh603019","sz000977","sh688111","sh688256",
        "sz002230","sz300502","sh688041","sh600845","sz300394","sh688313",
        "sh688516","sz002335",
    ],
    "光通信": [
        "sz300308","sz300502","sh688313","sz000063","sz300394","sh688498",
        "sz002281","sh600487","sh688205","sh688195",
    ],
    "新能源": [
        "sz300750","sh601012","sz002594","sz300274","sh688390","sz002129",
        "sh600438","sz300763","sh600885","sz002709","sh688599","sz300014",
    ],
    "消费电子": [
        "sz002475","sh603259","sz002241","sh600745","sz300433","sh688036",
        "sz000725","sh688772","sz300136","sh600703",
    ],
    "医药生物": [
        "sh600276","sz300760","sh600196","sh600763","sh603392","sz300015",
        "sh600085","sz300759","sz000963","sh688180","sz300347","sh688202",
        "sh688185","sz002007",
    ],
    "白酒消费": [
        "sh600519","sz000858","sz000568","sz002304","sh600809","sz000596",
        "sh600559","sh603369","sz000860","sh600702",
    ],
    "金融": [
        "sh601398","sh601939","sh601288","sh601328","sh600036","sh601166",
        "sh600000","sh600030","sh601318","sh601628","sh601601","sz000001",
        "sh600837","sz002142",
    ],
    "机器人/自动化": [
        "sz300124","sh688017","sz002230","sh688111","sz300750","sz002415",
        "sh603019","sz300161","sh688003","sh688160","sz300124","sh688777",
    ],
}


@lru_cache(maxsize=1)
def _cached_sector_analysis():
    """缓存5秒的板块分析结果"""
    pass


def analyze_sectors() -> dict:
    """
    分析各板块表现。
    返回: {sector_name: {avg_change_pct, stock_count, top_stocks: [...]}}
    """
    # Collect all unique stocks
    all_codes = set()
    for stocks in SECTOR_STOCKS.values():
        all_codes.update(stocks)

    # Fetch all prices at once
    code_list = list(all_codes)
    spots = fetch_spot_tencent(code_list)

    if not spots:
        return {"error": "数据获取失败", "sectors": []}

    # Build price map
    price_map = {}
    for s in spots:
        code = s.get("代码", "")
        if code:
            price_map[code] = s

    # Analyze each sector
    results = []
    for sector_name, stocks in SECTOR_STOCKS.items():
        sector_stocks = []
        changes = []

        for code in stocks:
            s = price_map.get(code)
            if s:
                change_pct = s.get("涨跌幅", 0)
                changes.append(change_pct)
                sector_stocks.append({
                    "code": code,
                    "name": s.get("名称", ""),
                    "price": s.get("最新价", 0),
                    "change_pct": change_pct,
                })

        if changes:
            avg_change = sum(changes) / len(changes)
            # Sort by change descending
            sector_stocks.sort(key=lambda x: x["change_pct"], reverse=True)

            results.append({
                "sector": sector_name,
                "avg_change_pct": round(avg_change, 2),
                "stock_count": len(sector_stocks),
                "top_gainers": [s for s in sector_stocks if s["change_pct"] > 0][:3],
                "top_losers": [s for s in sector_stocks if s["change_pct"] < 0][-3:][::-1],
                "all_stocks": sector_stocks[:5],
            })

    # Sort by average change descending
    results.sort(key=lambda x: x["avg_change_pct"], reverse=True)

    return {
        "sectors": results,
        "top_3_sectors": results[:3],
        "total_stocks_analyzed": len(price_map),
        "data_time": spots[0].get("时间", "") if spots else "",
    }

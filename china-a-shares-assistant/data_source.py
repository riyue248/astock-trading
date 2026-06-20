"""数据层:基于 AkShare 封装中国 A 股的查询、行情、历史、财务与新闻接口。

数据源说明(已针对常见网络/代理环境挑选稳定来源):
  - 代码/名称表 : stock_info_a_code_name
  - 估值与市值  : stock_value_em        (东财 datacenter,含收盘价/涨跌幅/PE/PB/市值)
  - 日线行情    : stock_zh_a_daily      (新浪;腾讯 stock_zh_a_hist_tx 作备份)
  - 财务摘要    : stock_financial_abstract_ths (同花顺)
  - 个股新闻    : stock_news_em
注:部分网络下东财实时盘口主机(push2.eastmoney.com)可能不可达,因此行情以
最新交易日收盘数据为准,适合资讯与复盘,并非盘中逐笔实时数据。

所有函数均做防御性处理:接口出错时返回空结构而非抛异常,便于界面统一展示。
"""

from __future__ import annotations

import datetime as _dt
from functools import lru_cache

import akshare as ak
import pandas as pd
import requests

_TX_URL = "https://qt.gtimg.cn/q="
_TX_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0",
}


# ---------------------------------------------------------------------------
# 代码 / 名称解析
# ---------------------------------------------------------------------------

# 全市场代码表的进程内缓存。只缓存成功(非空)结果,避免一次网络抖动
# 把空表永久缓存、毒化整个会话。
_CODES_CACHE: pd.DataFrame | None = None


def _all_a_codes(retries: int = 3) -> pd.DataFrame:
    """全部 A 股代码与名称,带进程内缓存(仅缓存成功结果)。

    返回列:code(6 位代码)、name(简称)。
    """
    global _CODES_CACHE
    if _CODES_CACHE is not None and not _CODES_CACHE.empty:
        return _CODES_CACHE

    for _ in range(retries):
        try:
            df = ak.stock_info_a_code_name()
            df = df.rename(columns={"代码": "code", "名称": "name"})
            if "code" not in df.columns and df.shape[1] >= 2:
                df.columns = ["code", "name"][: df.shape[1]]
            df["code"] = df["code"].astype(str).str.zfill(6)
            df = df[["code", "name"]]
            if not df.empty:
                _CODES_CACHE = df
                return df
        except Exception:
            continue
    return pd.DataFrame(columns=["code", "name"])


def classify_board(code: str) -> str:
    """按代码前缀划分板块。"""
    code = str(code).zfill(6)
    if code.startswith(("688", "689")):
        return "科创板"
    if code.startswith(("300", "301")):
        return "创业板"
    if code.startswith(("4", "8", "920", "92")):
        return "北交所"
    if code.startswith(("60",)):
        return "沪市主板"
    if code.startswith(("000", "001", "002", "003")):
        return "深市主板"
    return "其他"


# ---------------------------------------------------------------------------
# 交易时段判断(用于盘中自动刷新)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=2)
def _trade_dates(_day_bucket: int) -> frozenset:
    """A 股交易日集合(含节假日排除),按天缓存。失败返回空集。"""
    try:
        df = ak.tool_trade_date_hist_sina()
        return frozenset(pd.to_datetime(df["trade_date"]).dt.date)
    except Exception:
        return frozenset()


def is_trading_now(now: _dt.datetime | None = None) -> bool:
    """当前是否处于 A 股正常交易时段(交易日的 9:30–11:30 或 13:00–15:00)。"""
    now = now or _dt.datetime.now()
    if now.weekday() >= 5:                       # 周末
        return False
    cal = _trade_dates(now.toordinal() // 1)     # 按自然日缓存
    if cal and now.date() not in cal:            # 交易日历可用且今日非交易日(节假日)
        return False
    t = now.time()
    am = _dt.time(9, 30) <= t <= _dt.time(11, 30)
    pm = _dt.time(13, 0) <= t <= _dt.time(15, 0)
    return am or pm


def _sina_symbol(code: str) -> str:
    """6 位代码 → 新浪/腾讯所需的带交易所前缀代码,如 sh600519 / sz000001 / bj830799。"""
    code = str(code).zfill(6)
    if code.startswith(("60", "68", "90", "11", "51", "58")):
        return "sh" + code
    if code.startswith(("00", "30", "20", "15", "16", "12")):
        return "sz" + code
    if code.startswith(("4", "8", "92")):
        return "bj" + code
    # 兜底:6/9 开头归上交所,其余归深交所
    return ("sh" if code[0] in "69" else "sz") + code


def resolve_symbol(query: str) -> dict | None:
    """把用户输入(代码或名称)解析为 {code, name}。返回 None 表示无法解析。"""
    if not query:
        return None
    query = query.strip()
    codes = _all_a_codes()
    if codes.empty:
        if query.isdigit() and len(query) == 6:
            return {"code": query, "name": query}
        return None

    if query.isdigit():
        q = query.zfill(6)
        hit = codes[codes["code"] == q]
        if not hit.empty:
            row = hit.iloc[0]
            return {"code": row["code"], "name": row["name"]}
        return None

    exact = codes[codes["name"] == query]
    if not exact.empty:
        row = exact.iloc[0]
        return {"code": row["code"], "name": row["name"]}
    fuzzy = codes[codes["name"].str.contains(query, na=False)]
    if not fuzzy.empty:
        row = fuzzy.iloc[0]
        return {"code": row["code"], "name": row["name"]}
    return None


def search_candidates(query: str, limit: int = 10) -> pd.DataFrame:
    """根据输入返回候选股票列表(代码 + 名称),用于消歧。"""
    codes = _all_a_codes()
    if codes.empty or not query:
        return pd.DataFrame(columns=["code", "name"])
    query = query.strip()
    if query.isdigit():
        mask = codes["code"].str.contains(query, na=False)
    else:
        mask = codes["name"].str.contains(query, na=False)
    return codes[mask].head(limit).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 历史 K 线(新浪为主,腾讯备份)
# ---------------------------------------------------------------------------

def _hist_sina(code: str, start: str, end: str, adjust: str) -> pd.DataFrame:
    df = ak.stock_zh_a_daily(symbol=_sina_symbol(code), start_date=start,
                             end_date=end, adjust=adjust)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns={"outstanding_share": "out_share"})
    df["date"] = pd.to_datetime(df["date"])
    if "turnover" in df.columns:        # 新浪换手率为小数,换算成百分比
        df["turnover"] = df["turnover"] * 100
    df["pct_chg"] = df["close"].pct_change() * 100
    keep = [c for c in ["date", "open", "close", "high", "low",
                        "volume", "amount", "pct_chg", "turnover"] if c in df.columns]
    return df[keep].sort_values("date").reset_index(drop=True)


def _hist_tx(code: str, start: str, end: str) -> pd.DataFrame:
    df = ak.stock_zh_a_hist_tx(symbol=_sina_symbol(code),
                               start_date=start, end_date=end)
    if df is None or df.empty:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"])
    df["pct_chg"] = df["close"].pct_change() * 100
    keep = [c for c in ["date", "open", "close", "high", "low", "pct_chg"]
            if c in df.columns]
    return df[keep].sort_values("date").reset_index(drop=True)


def get_history(code: str, days: int = 365, adjust: str = "qfq") -> pd.DataFrame:
    """日线历史数据(默认前复权)。

    返回列:date, open, close, high, low, volume, amount, pct_chg, turnover。
    """
    code = str(code).zfill(6)
    end = _dt.date.today()
    start = end - _dt.timedelta(days=days)
    s, e = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")

    for fetch in (lambda: _hist_sina(code, s, e, adjust),
                  lambda: _hist_tx(code, s, e)):
        try:
            df = fetch()
            if not df.empty:
                return df
        except Exception:
            continue
    return pd.DataFrame()


# ---------------------------------------------------------------------------
# 实时行情(腾讯 qt.gtimg.cn,单只 / 批量)
# ---------------------------------------------------------------------------

# 腾讯实时字段下标 → 统一字段名(已实测 88 字段)
_TX_FIELDS = {
    3: "最新价", 4: "昨收", 5: "今开", 30: "时间", 31: "涨跌额",
    32: "涨跌幅", 33: "最高", 34: "最低", 38: "换手率", 39: "市盈率TTM",
    43: "振幅", 44: "流通市值", 45: "总市值", 46: "市净率", 49: "量比",
}


def _to_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _parse_tx_line(line: str) -> tuple[str, dict] | None:
    """解析一行 v_sh600519="..."; 返回 (6位代码, 行情字典)。"""
    if "=" not in line or '"' not in line:
        return None
    var = line.split("=", 1)[0].strip()          # v_sh600519
    body = line.split('"', 1)[1].rsplit('"', 1)[0]
    arr = body.split("~")
    if len(arr) < 46:
        return None
    code = var[-6:]
    out: dict = {"名称": arr[1]}
    for idx, key in _TX_FIELDS.items():
        if idx < len(arr):
            out[key] = arr[idx] if key == "时间" else _to_float(arr[idx])
    # 市值单位由“亿元”换算为“元”,与估值接口保持一致
    for k in ("总市值", "流通市值"):
        if out.get(k) is not None:
            out[k] = out[k] * 1e8
    # 成交额(元):取“价格/量(手)/额(元)”字段的第三段
    if len(arr) > 35 and "/" in str(arr[35]):
        parts = str(arr[35]).split("/")
        if len(parts) >= 3:
            out["成交额"] = _to_float(parts[2])
    # 数据日期:从时间戳 yyyymmddHHMMSS 提取
    t = str(out.get("时间") or "")
    if len(t) >= 8:
        out["数据日期"] = f"{t[0:4]}-{t[4:6]}-{t[6:8]}"
        out["时间"] = f"{t[8:10]}:{t[10:12]}:{t[12:14]}" if len(t) >= 14 else None
    return code, out


def get_realtime_many(codes: list[str]) -> dict[str, dict]:
    """批量实时行情。返回 {6位代码: 行情字典}。失败时返回空 dict。"""
    syms = [_sina_symbol(str(c).zfill(6)) for c in codes if c]
    if not syms:
        return {}
    result: dict[str, dict] = {}
    # 腾讯单次 URL 不宜过长,按 60 只分批
    for i in range(0, len(syms), 60):
        chunk = syms[i:i + 60]
        try:
            r = requests.get(_TX_URL + ",".join(chunk), headers=_TX_HEADERS, timeout=10)
            r.encoding = "gbk"
            for line in r.text.strip().splitlines():
                parsed = _parse_tx_line(line)
                if parsed:
                    result[parsed[0]] = parsed[1]
        except Exception:
            continue
    return result


def get_realtime(code: str) -> dict:
    """单只实时行情。"""
    code = str(code).zfill(6)
    return get_realtime_many([code]).get(code, {})


# ---------------------------------------------------------------------------
# 估值补充(东财 datacenter,日频:PE静/市销率)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=64)
def _value_em_cached(code: str, _bucket: int) -> pd.DataFrame:
    try:
        return ak.stock_value_em(symbol=code)
    except Exception:
        return pd.DataFrame()


def _value_em(code: str) -> pd.DataFrame:
    """东财估值历史(含收盘价/涨跌幅/PE/PB/市值),按 5 分钟分桶缓存。"""
    bucket = int(_dt.datetime.now().timestamp() // 300)
    return _value_em_cached(code, bucket)


def get_quote(code: str) -> dict:
    """获取单只股票的行情与关键指标(实时优先,收盘数据兜底)。

    字段:数据日期、时间、最新价、涨跌幅、涨跌额、今开、昨收、最高、最低、
    成交量、成交额、换手率、市盈率TTM、市盈率(静)、市净率、市销率、总市值、流通市值、
    振幅、量比、实时(bool)。缺失字段为 None。
    """
    code = str(code).zfill(6)

    # 1) 实时优先(腾讯)
    rt = get_realtime(code)
    if rt.get("最新价") is not None:
        rt["实时"] = True
        # 市销率腾讯不提供,从估值接口补(日频,盘中变化极小)
        try:
            val = _value_em(code)
            if not val.empty:
                rt.setdefault("市盈率(静)", val.iloc[-1].get("PE(静)"))
                rt["市销率"] = val.iloc[-1].get("市销率")
        except Exception:
            pass
        return rt

    # 2) 收盘数据兜底(新浪日线 + 东财估值)
    return _quote_eod(code)


def _quote_eod(code: str) -> dict:
    """收盘数据组装(实时源不可用时的兜底)。"""
    out: dict = {"实时": False}
    ref_date = None  # 锚定交易日,保证各字段自洽

    # 价格 / 开高低 / 成交 / 换手(新浪日线最后一行,同一交易日)
    try:
        h = get_history(code, days=15)
        if not h.empty:
            last = h.iloc[-1]
            ref_date = pd.to_datetime(last["date"]).date()
            out["数据日期"] = str(ref_date)
            out["最新价"] = float(last["close"])
            out["今开"] = last.get("open")
            out["最高"] = last.get("high")
            out["最低"] = last.get("low")
            out["成交量"] = last.get("volume")
            out["成交额"] = last.get("amount")
            if "turnover" in h.columns:
                out["换手率"] = last.get("turnover")
            if "pct_chg" in h.columns:
                out["涨跌幅"] = last.get("pct_chg")
            if len(h) >= 2:
                prev_close = float(h.iloc[-2]["close"])
                out["昨收"] = prev_close
                out["涨跌额"] = out["最新价"] - prev_close
    except Exception:
        pass

    # 估值与市值(东财 datacenter),对齐到与行情相同的交易日
    try:
        val = _value_em(code)
        if not val.empty:
            vrow = None
            if ref_date is not None and "数据日期" in val.columns:
                m = val[val["数据日期"].astype(str) == str(ref_date)]
                if not m.empty:
                    vrow = m.iloc[-1]
            if vrow is None:
                # 行情缺失时,退化为 value_em 自身最新行
                vrow = val.iloc[-1]
                if ref_date is None:
                    out["数据日期"] = str(vrow.get("数据日期"))
                    out["最新价"] = vrow.get("当日收盘价")
                    out["涨跌幅"] = vrow.get("当日涨跌幅")
            out["总市值"] = vrow.get("总市值")
            out["流通市值"] = vrow.get("流通市值")
            out["市盈率TTM"] = vrow.get("PE(TTM)")
            out["市盈率(静)"] = vrow.get("PE(静)")
            out["市净率"] = vrow.get("市净率")
            out["市销率"] = vrow.get("市销率")
    except Exception:
        pass

    return out


@lru_cache(maxsize=2048)
def _industry_cached(code: str, _day_bucket: int) -> str:
    """单只股票所属行业(证监会行业大类),按天缓存。失败返回 '未分类'。"""
    try:
        end = _dt.date.today().strftime("%Y%m%d")
        df = ak.stock_industry_change_cninfo(symbol=code, start_date="20180101",
                                             end_date=end)
        if df is not None and not df.empty:
            row = df.sort_values("变更日期").iloc[-1]   # 取最新一次分类
            for col in ("行业大类", "行业门类", "行业中类"):
                v = row.get(col)
                if isinstance(v, str) and v.strip():
                    return v.strip()
    except Exception:
        pass
    return "未分类"


def get_industry(code: str) -> str:
    """单只股票所属行业(巨潮·证监会分类),按天缓存。"""
    code = str(code).zfill(6)
    return _industry_cached(code, _dt.date.today().toordinal())


def get_basic_info(code: str) -> dict:
    """个股基础信息(行业、上市时间、总股本等)。东财实时主机不可达时可能为空。"""
    code = str(code).zfill(6)
    try:
        df = ak.stock_individual_info_em(symbol=code)
        return dict(zip(df["item"], df["value"]))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# 财务基本面(同花顺)
# ---------------------------------------------------------------------------

def get_financials(code: str) -> pd.DataFrame:
    """财务摘要(按报告期),含营收、净利润、ROE、毛利率、负债率等。"""
    code = str(code).zfill(6)
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        if df is not None and not df.empty:
            return df.sort_values("报告期", ascending=False).reset_index(drop=True)
    except Exception:
        pass
    try:
        return ak.stock_financial_abstract(symbol=code)
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# 个股新闻(东财)
# ---------------------------------------------------------------------------

def get_news(code: str, limit: int = 15) -> pd.DataFrame:
    """个股近期新闻。返回列:time, title, source, url, content。"""
    code = str(code).zfill(6)
    try:
        df = ak.stock_news_em(symbol=code)
    except Exception:
        return pd.DataFrame(columns=["time", "title", "source", "url", "content"])

    if df is None or df.empty:
        return pd.DataFrame(columns=["time", "title", "source", "url", "content"])

    rename = {
        "发布时间": "time", "新闻标题": "title", "文章来源": "source",
        "新闻链接": "url", "新闻内容": "content",
    }
    df = df.rename(columns=rename)
    keep = [c for c in ["time", "title", "source", "url", "content"] if c in df.columns]
    return df[keep].head(limit).reset_index(drop=True)

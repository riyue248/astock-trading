"""股票资讯小项目 —— Streamlit 网页应用。

三个页面:
  📈 个股详情 —— 实时行情、K 线走势、规则化走势总结、财务、新闻
  ⭐ 自选股   —— 自选清单的实时行情表格(本地持久化)
  🆚 多股对比 —— 多只股票归一化走势叠加 + 关键指标横向对比

运行:  streamlit run app.py
"""

from __future__ import annotations

import datetime as dt
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import analysis
import data_source as ds
import storage

st.set_page_config(page_title="A股资讯助手", page_icon="📊", layout="wide")


# ---------------------------------------------------------------------------
# 带缓存的数据获取
# ---------------------------------------------------------------------------

@st.cache_data(ttl=20, show_spinner=False)
def cached_quote(code: str) -> dict:
    return ds.get_quote(code)


@st.cache_data(ttl=20, show_spinner=False)
def cached_realtime_many(codes: tuple[str, ...]) -> dict:
    return ds.get_realtime_many(list(codes))


@st.cache_data(ttl=300, show_spinner=False)
def cached_history(code: str, days: int) -> pd.DataFrame:
    return ds.get_history(code, days=days)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_financials(code: str) -> pd.DataFrame:
    return ds.get_financials(code)


@st.cache_data(ttl=900, show_spinner=False)
def cached_news(code: str) -> pd.DataFrame:
    return ds.get_news(code)


@st.cache_data(ttl=600, show_spinner=False)
def cached_candidates(query: str) -> pd.DataFrame:
    return ds.search_candidates(query)


@st.cache_data(ttl=86400, show_spinner=False)
def cached_industry(code: str) -> str:
    return ds.get_industry(code)


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fmt_big(v) -> str:
    n = _num(v)
    if n is None:
        return "—"
    if abs(n) >= 1e8:
        return f"{n / 1e8:.2f} 亿"
    if abs(n) >= 1e4:
        return f"{n / 1e4:.2f} 万"
    return f"{n:.2f}"


def _fmt(v, suffix="") -> str:
    n = _num(v)
    if n is None:
        return "—"
    return f"{n:.2f}{suffix}"


PERIODS = {"近 3 个月": 90, "近 6 个月": 180, "近 1 年": 365, "近 2 年": 730}


# ---------------------------------------------------------------------------
# 图表
# ---------------------------------------------------------------------------

def render_kline(df: pd.DataFrame, name: str):
    ma = analysis.add_moving_averages(df)
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.72, 0.28], vertical_spacing=0.03,
        subplot_titles=(f"{name} K线 / 均线", "成交量"),
    )
    fig.add_trace(
        go.Candlestick(
            x=ma["date"], open=ma["open"], high=ma["high"],
            low=ma["low"], close=ma["close"], name="K线",
            increasing_line_color="#e34a4a", decreasing_line_color="#2ca02c",
        ),
        row=1, col=1,
    )
    for w, color in (("ma5", "#ff9900"), ("ma20", "#3366cc"), ("ma60", "#9933cc")):
        if w in ma:
            fig.add_trace(
                go.Scatter(x=ma["date"], y=ma[w], name=w.upper(),
                           line=dict(width=1, color=color)),
                row=1, col=1,
            )
    colors = ["#e34a4a" if c >= o else "#2ca02c"
              for c, o in zip(ma["close"], ma["open"])]
    fig.add_trace(
        go.Bar(x=ma["date"], y=ma["volume"], name="成交量",
               marker_color=colors, showlegend=False),
        row=2, col=1,
    )
    fig.update_layout(
        height=560, xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
    )
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# 页面:个股详情
# ---------------------------------------------------------------------------

def page_detail():
    with st.sidebar:
        st.subheader("查询")
        query = st.text_input("股票名称 / 代码", value="贵州茅台",
                              placeholder="如:贵州茅台 或 600519")
        period_label = st.selectbox("历史区间", list(PERIODS.keys()), index=2)
    period_days = PERIODS[period_label]

    if not query:
        st.info("请在左侧输入股票名称或代码。")
        return

    resolved = ds.resolve_symbol(query)
    if resolved is None:
        st.warning(f"未能匹配「{query}」。下面是可能的候选,请用更精确的名称或代码重试:")
        st.dataframe(cached_candidates(query), use_container_width=True, hide_index=True)
        return

    code, name = resolved["code"], resolved["name"]

    head_l, head_r = st.columns([4, 1])
    with head_l:
        st.subheader(f"{name}  ·  {code}")
    with head_r:
        watched = storage.is_watched(code)
        if watched:
            if st.button("⭐ 已自选(移除)", use_container_width=True):
                storage.remove_watch(code)
                st.rerun()
        else:
            if st.button("☆ 加入自选", type="primary", use_container_width=True):
                storage.add_watch(code, name)
                st.rerun()

    quote = cached_quote(code)
    if quote.get("实时"):
        st.caption(f"🟢 实时行情　数据时间:{quote.get('数据日期', '—')} "
                   f"{quote.get('时间') or ''}　·　来源:腾讯财经")
    else:
        st.caption(f"数据日期:{quote.get('数据日期', '—')}　·　最新交易日收盘数据(实时源暂不可用)")

    c1, c2, c3, c4 = st.columns(4)
    price = _num(quote.get("最新价"))
    chg = _num(quote.get("涨跌幅"))
    c1.metric("最新价", _fmt(price), f"{chg:+.2f}%" if chg is not None else None)
    c2.metric("今开 / 昨收", f"{_fmt(quote.get('今开'))} / {_fmt(quote.get('昨收'))}")
    c3.metric("最高 / 最低", f"{_fmt(quote.get('最高'))} / {_fmt(quote.get('最低'))}")
    c4.metric("换手率", _fmt(quote.get("换手率"), "%"))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("市盈率(TTM)", _fmt(quote.get("市盈率TTM")))
    c6.metric("市净率", _fmt(quote.get("市净率")))
    c7.metric("总市值", _fmt_big(quote.get("总市值")))
    c8.metric("成交额", _fmt_big(quote.get("成交额")))

    st.divider()

    hist = cached_history(code, period_days)
    if hist.empty:
        st.error("未获取到历史行情数据,可能是接口暂时不可用或该代码无日线数据。")
    else:
        left, right = st.columns([3, 2])
        with left:
            render_kline(hist, name)
        with right:
            st.markdown(analysis.summarize(hist, name))

    st.divider()

    tab_fin, tab_news = st.tabs(["📑 财务基本面", "📰 个股新闻"])
    with tab_fin:
        fin = cached_financials(code)
        if fin is None or fin.empty:
            st.info("暂无财务数据。")
        else:
            st.dataframe(fin, use_container_width=True, hide_index=True)
            st.caption("财务摘要(按报告期),含营收、净利润、ROE、毛利率、负债率等。")
    with tab_news:
        news = cached_news(code)
        if news is None or news.empty:
            st.info("暂无近期新闻。")
        else:
            for _, row in news.iterrows():
                url, title = row.get("url", ""), row.get("title", "")
                head = f"**[{title}]({url})**" if url else f"**{title}**"
                st.markdown(head)
                st.caption(f"{row.get('time', '')}　·　{row.get('source', '')}")
                content = str(row.get("content", "") or "")
                if content:
                    st.write(content[:160] + ("…" if len(content) > 160 else ""))
                st.divider()


# ---------------------------------------------------------------------------
# 页面:自选股
# ---------------------------------------------------------------------------

def _watch_color(v):
    if v is None or pd.isna(v):
        return ""
    return "color:#e34a4a" if v > 0 else ("color:#2ca02c" if v < 0 else "")


def _styled_watch(df: pd.DataFrame):
    fmt = {
        "最新价": "{:.2f}", "涨跌幅%": "{:+.2f}", "换手率%": "{:.2f}",
        "市盈率TTM": "{:.1f}", "市净率": "{:.2f}", "总市值(亿)": "{:.0f}",
    }
    fmt = {k: v for k, v in fmt.items() if k in df.columns}
    return df.style.map(_watch_color, subset=["涨跌幅%"]).format(fmt, na_rep="—")


def _build_watch_df(items: list[dict], with_industry: bool) -> pd.DataFrame:
    codes = tuple(it["code"] for it in items)
    rt = cached_realtime_many(codes)
    rows = []
    for it in items:
        q = rt.get(it["code"], {})
        row = {
            "名称": it["name"], "代码": it["code"],
            "板块": ds.classify_board(it["code"]),
            "最新价": _num(q.get("最新价")),
            "涨跌幅%": _num(q.get("涨跌幅")),
            "换手率%": _num(q.get("换手率")),
            "市盈率TTM": _num(q.get("市盈率TTM")),
            "市净率": _num(q.get("市净率")),
            "总市值(亿)": (_num(q.get("总市值")) / 1e8) if q.get("总市值") else None,
        }
        if with_industry:
            row["行业"] = cached_industry(it["code"])
        rows.append(row)
    return pd.DataFrame(rows)


def _watch_body(items: list[dict]):
    """自选股表格主体(放入 fragment,盘中可自动刷新)。"""
    group_by = st.session_state.get("wl_group", "不分组")
    sort_by = st.session_state.get("wl_sort", "默认")

    df = _build_watch_df(items, with_industry=(group_by == "按行业"))

    if sort_by == "涨跌幅 高→低":
        df = df.sort_values("涨跌幅%", ascending=False, na_position="last")
    elif sort_by == "涨跌幅 低→高":
        df = df.sort_values("涨跌幅%", ascending=True, na_position="last")

    group_col = {"按板块": "板块", "按行业": "行业"}.get(group_by)
    if group_col and group_col in df.columns:
        for gval, gdf in df.groupby(group_col, sort=False):
            avg = gdf["涨跌幅%"].mean(skipna=True)
            avg_s = f"{avg:+.2f}%" if pd.notna(avg) else "—"
            st.markdown(f"**{gval}**　({len(gdf)} 只,平均 {avg_s})")
            st.dataframe(_styled_watch(gdf.drop(columns=[group_col])),
                         use_container_width=True, hide_index=True)
    else:
        show = df.drop(columns=["行业"], errors="ignore")
        st.dataframe(_styled_watch(show), use_container_width=True, hide_index=True)

    st.caption(f"🟢 实时行情来自腾讯财经　·　更新于 {dt.datetime.now():%H:%M:%S}")


def page_watchlist():
    st.subheader("⭐ 自选股")
    items = storage.load_watchlist()
    if not items:
        st.info("自选股为空。到「📈 个股详情」页查询某只股票后,点「☆ 加入自选」即可添加。")
        return

    c1, c2, c3 = st.columns([1.2, 1.2, 1])
    c1.selectbox("分组方式", ["不分组", "按板块", "按行业"], key="wl_group")
    c2.selectbox("排序", ["默认", "涨跌幅 高→低", "涨跌幅 低→高"], key="wl_sort")
    with c3:
        st.write("")
        st.write("")
        if st.button("🔄 刷新", use_container_width=True):
            cached_realtime_many.clear()
            st.rerun()

    trading = ds.is_trading_now()
    if trading:
        st.caption("🟢 交易时段:表格每 5 分钟自动刷新")
    else:
        st.caption("⚪ 当前非交易时段:不自动刷新(可点「🔄 刷新」手动更新)")

    # 仅交易时段开启自动刷新(run_every=None 表示不自动重跑)
    render = st.fragment(run_every=(300 if trading else None))(_watch_body)
    render(items)

    rm = st.selectbox("移除自选股", ["—"] + [f"{it['name']} ({it['code']})" for it in items])
    if rm != "—" and st.button("移除", type="secondary"):
        storage.remove_watch(rm.split("(")[-1].strip(")"))
        st.rerun()


# ---------------------------------------------------------------------------
# 页面:多股对比
# ---------------------------------------------------------------------------

def page_compare():
    st.subheader("🆚 多股对比")
    watch = storage.load_watchlist()
    default = " ".join(it["code"] for it in watch[:4]) or "600519 000858 000001"

    raw = st.text_input("对比股票(名称或代码,空格 / 逗号分隔,建议 2–6 只)", value=default)
    period_label = st.selectbox("对比区间", list(PERIODS.keys()), index=2)
    days = PERIODS[period_label]

    tokens = [t for t in re.split(r"[\s,，]+", raw.strip()) if t]
    selected: list[tuple[str, str]] = []
    seen = set()
    for tk in tokens:
        r = ds.resolve_symbol(tk)
        if r and r["code"] not in seen:
            selected.append((r["code"], r["name"]))
            seen.add(r["code"])

    if not selected:
        st.info("请输入至少一只可识别的股票。")
        return

    # 归一化走势叠加(起点 = 100)
    fig = go.Figure()
    perf = {}
    for code, name in selected:
        h = cached_history(code, days)
        if h.empty:
            continue
        base = float(h["close"].iloc[0])
        if base == 0:
            continue
        norm = h["close"] / base * 100
        fig.add_trace(go.Scatter(x=h["date"], y=norm, name=f"{name}", mode="lines"))
        perf[code] = norm.iloc[-1] - 100  # 区间涨幅 %

    fig.add_hline(y=100, line_dash="dot", line_color="#999")
    fig.update_layout(
        height=480, title=f"归一化价格走势(起点=100,{period_label})",
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified", yaxis_title="相对涨幅",
    )
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    st.plotly_chart(fig, use_container_width=True)

    # 指标横向对比
    rt = cached_realtime_many(tuple(c for c, _ in selected))
    rows = []
    for code, name in selected:
        q = rt.get(code, {})
        rows.append({
            "名称": name, "代码": code,
            "最新价": _num(q.get("最新价")),
            "涨跌幅%": _num(q.get("涨跌幅")),
            f"{period_label}涨幅%": perf.get(code),
            "市盈率TTM": _num(q.get("市盈率TTM")),
            "市净率": _num(q.get("市净率")),
            "总市值(亿)": (_num(q.get("总市值")) / 1e8) if q.get("总市值") else None,
        })
    df = pd.DataFrame(rows)
    styled = df.style.format({
        "最新价": "{:.2f}", "涨跌幅%": "{:+.2f}", f"{period_label}涨幅%": "{:+.1f}",
        "市盈率TTM": "{:.1f}", "市净率": "{:.2f}", "总市值(亿)": "{:.0f}",
    }, na_rep="—")
    st.dataframe(styled, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

st.title("📊 A股资讯助手")

with st.sidebar:
    page = st.radio("页面", ["📈 个股详情", "⭐ 自选股", "🆚 多股对比"])
    st.divider()

if page == "📈 个股详情":
    page_detail()
elif page == "⭐ 自选股":
    page_watchlist()
else:
    page_compare()

st.divider()
st.caption("⚠️ 行情数据来自腾讯/新浪/东财/同花顺等公开来源,仅用于信息聚合与学习,不构成任何投资建议。")

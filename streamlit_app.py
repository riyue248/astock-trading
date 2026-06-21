"""
A股量化交易监控台 — Streamlit 云端部署版
布局对齐本地 FastAPI 仪表盘
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["NO_PROXY"] = "*"

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from sqlalchemy import select, desc

st.set_page_config(
    page_title="A股量化交易",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Custom CSS ─────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    :root {
        --bg: #07111f;
        --panel: rgba(13, 27, 45, 0.88);
        --panel-2: rgba(17, 35, 58, 0.78);
        --border: rgba(148, 163, 184, 0.18);
        --muted: #8ea2ba;
        --text: #e7eef8;
        --blue: #38bdf8;
        --green: #22c55e;
        --red: #f43f5e;
        --amber: #f59e0b;
    }
    html, body, [class*="css"] {
        font-family: 'Inter', 'Microsoft YaHei', 'PingFang SC', sans-serif;
        letter-spacing: 0;
    }
    .stApp {
        color: var(--text);
        background:
            radial-gradient(circle at 8% 0%, rgba(56, 189, 248, 0.16), transparent 30%),
            linear-gradient(180deg, #07111f 0%, #0a1423 46%, #08101c 100%);
    }
    header { background: transparent !important; }
    footer { visibility: hidden; }
    .main > div { padding-top: 1.2rem; max-width: 1500px; }
    h1, h2, h3, h4, h5 { color: var(--text); font-weight: 750; }
    hr { border-color: var(--border); margin: 1.1rem 0; }

    .hero {
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        gap: 1rem;
        padding: 22px 24px;
        margin: 0 0 18px;
        border: 1px solid var(--border);
        border-radius: 8px;
        background:
            linear-gradient(135deg, rgba(56, 189, 248, 0.13), rgba(34, 197, 94, 0.04)),
            rgba(13, 27, 45, 0.76);
        box-shadow: 0 16px 45px rgba(2, 6, 23, 0.28);
    }
    .hero-title { font-size: 1.7rem; font-weight: 800; margin: 0 0 4px; }
    .hero-subtitle { color: var(--muted); font-size: 0.92rem; }
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        border: 1px solid rgba(56, 189, 248, 0.28);
        border-radius: 999px;
        color: #c7f3ff;
        background: rgba(56, 189, 248, 0.10);
        white-space: nowrap;
    }
    .section-title {
        margin: 1rem 0 0.6rem;
        font-size: 1.03rem;
        font-weight: 750;
        color: #dbeafe;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 14px 16px;
        box-shadow: 0 10px 26px rgba(2, 6, 23, 0.18);
    }
    [data-testid="stMetric"] label {
        color: var(--muted) !important;
        font-size: 0.76rem;
        font-weight: 600;
    }
    [data-testid="stMetricValue"] {
        color: var(--text) !important;
        font-size: 1.42rem;
        font-weight: 750;
    }
    [data-testid="stMetricDelta"] { font-weight: 700; }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0b1628, #08111f);
        border-right: 1px solid var(--border);
    }
    [data-testid="stSidebar"] * { color: var(--text); }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #0ea5e9, #2563eb);
        border: 1px solid rgba(125, 211, 252, 0.35);
        color: white;
        border-radius: 8px;
        font-weight: 700;
        width: 100%;
        box-shadow: 0 10px 24px rgba(14, 165, 233, 0.20);
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #38bdf8, #3b82f6);
        border-color: rgba(186, 230, 253, 0.75);
    }
    .stTextInput input {
        border-radius: 8px;
        border-color: var(--border);
        background: rgba(15, 23, 42, 0.72);
    }

    /* Dataframe */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: 8px;
        overflow: hidden;
        font-size: 0.88rem;
        box-shadow: 0 12px 28px rgba(2, 6, 23, 0.16);
    }

    /* Navigation tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background: rgba(8, 17, 31, 0.68);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 6px;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: var(--muted);
        border-radius: 7px;
        font-weight: 700;
        padding: 8px 12px;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(56, 189, 248, 0.16) !important;
        color: #e0f7ff !important;
        box-shadow: inset 0 0 0 1px rgba(56, 189, 248, 0.22);
    }

    /* Expanders */
    .streamlit-expanderHeader {
        background: var(--panel-2);
        border-radius: 8px;
        font-weight: 700;
    }

    /* Alert boxes */
    .stAlert {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 8px;
    }
    @media (max-width: 760px) {
        .hero { align-items: flex-start; flex-direction: column; padding: 18px; }
        .hero-title { font-size: 1.35rem; }
    }
</style>
""", unsafe_allow_html=True)

# ─── Auto-refresh control ───────────────────────────

AUTO_REFRESH = st.sidebar.checkbox("🔄 自动刷新（盘中每30秒）", value=True)
REFRESH_SECONDS = 30


def render_hero(status_label: str):
    """Render the compact dashboard header."""
    st.markdown(
        f"""
        <div class="hero">
            <div>
                <div class="hero-title">A股量化交易监控台</div>
                <div class="hero-subtitle">指数概览、板块热度、个股技术面与模拟交易状态集中查看</div>
            </div>
            <div class="status-pill">{status_label} · {datetime.now().strftime('%H:%M:%S')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def select_columns(df: pd.DataFrame, columns: dict[str, str]) -> pd.DataFrame:
    """Return a renamed frame without failing when a data source omits columns."""
    available = [col for col in columns if col in df.columns]
    return df[available].rename(columns={col: columns[col] for col in available})


def format_quote_table(df: pd.DataFrame) -> pd.DataFrame:
    display = select_columns(
        df,
        {
            "代码": "代码",
            "名称": "名称",
            "最新价": "最新价",
            "涨跌幅": "涨跌幅",
            "今开": "今开",
            "最高": "最高",
            "最低": "最低",
            "成交量": "成交量",
            "成交额": "成交额",
        },
    ).copy()
    for col in ["最新价", "今开", "最高", "最低"]:
        if col in display.columns:
            display[col] = pd.to_numeric(display[col], errors="coerce").map(lambda v: f"{v:.2f}" if pd.notna(v) else "--")
    if "涨跌幅" in display.columns:
        display["涨跌幅"] = pd.to_numeric(display["涨跌幅"], errors="coerce").map(lambda v: f"{v:+.2f}%" if pd.notna(v) else "--")
    if "成交量" in display.columns:
        display["成交量"] = pd.to_numeric(display["成交量"], errors="coerce").map(lambda v: f"{v/10000:.0f}万" if pd.notna(v) else "--")
    if "成交额" in display.columns:
        display["成交额"] = pd.to_numeric(display["成交额"], errors="coerce").map(lambda v: f"{v/100000000:.2f}亿" if pd.notna(v) else "--")
    return display


def chart_layout(height: int, top: int = 24) -> dict:
    return dict(
        height=height,
        margin=dict(l=46, r=30, t=top, b=24),
        paper_bgcolor="rgba(13, 27, 45, 0.80)",
        plot_bgcolor="rgba(13, 27, 45, 0.80)",
        font=dict(color="#e7eef8", size=10),
        hoverlabel=dict(bgcolor="#0f172a", bordercolor="#334155", font_size=12),
        hovermode="x unified",
    )


# ─── Data fetchers ──────────────────────────────────

@st.cache_data(ttl=15, show_spinner=False)
def fetch_active_stocks(top_n: int = 100) -> pd.DataFrame:
    """获取全市场活跃股票行情（沪深300+中证500成分股）"""
    from data.fetcher import get_candidate_pool
    results = get_candidate_pool(top_n)
    if results:
        df = pd.DataFrame(results)
        if "涨跌幅" in df.columns:
            df = df.sort_values("涨跌幅", ascending=False)
        return df
    return pd.DataFrame()


@st.cache_data(ttl=15, show_spinner=False)
def fetch_indices() -> pd.DataFrame:
    """获取四大指数"""
    from data.fetcher import fetch_index_spot
    return fetch_index_spot()


@st.cache_data(ttl=60, show_spinner=False)
def fetch_stock_data(symbol: str, days: int = 120) -> pd.DataFrame:
    """获取个股K线+指标"""
    from data.fetcher import fetch_stock_history
    from engine.indicators import add_all_indicators
    df = fetch_stock_history(symbol, days)
    if not df.empty:
        df = add_all_indicators(df)
    return df


@st.cache_data(ttl=30, show_spinner=False)
def load_trading_data():
    """加载本地模拟交易数据（若数据库可用）"""
    try:
        from data.database import SessionLocal
        from models.orm import EquitySnapshot, TradeLog, Position, StrategyPerformance
        with SessionLocal() as db:
            pos = [p.to_dict() for p in db.execute(select(Position)).scalars().all()]
            snaps = [s.to_dict() for s in db.execute(select(EquitySnapshot).order_by(EquitySnapshot.date)).scalars().all()]
            trades = [t.to_dict() for t in db.execute(select(TradeLog).order_by(desc(TradeLog.id)).limit(100)).scalars().all()]
            perfs = [p.to_dict() for p in db.execute(select(StrategyPerformance)).scalars().all()]
        return {"positions": pos, "equity": snaps, "trades": trades, "strategies": perfs}
    except Exception:
        return None


# ─── Trading status ─────────────────────────────────

@st.cache_data(ttl=30, show_spinner=False)
def get_market_status() -> dict:
    try:
        from utils.trading_calendar import is_trading_time
        is_trading, status = is_trading_time()
        labels = {"live": "🟢 交易中", "lunch_break": "🟡 午间休市",
                   "closed": "⚫ 已收盘", "holiday": "🔴 休市"}
        return {"trading": is_trading, "status": status, "label": labels.get(status, status)}
    except:
        return {"trading": False, "status": "closed", "label": "⚫ 未知"}


# ─── Navigation ─────────────────────────────────────

mkt_status = get_market_status()
render_hero(mkt_status["label"])
tabs = st.tabs(["📊 市场总览", "🔥 板块分析", "📈 个股详情", "📋 模拟交易", "📖 郑希投研", "⭐ 自选股"])

# ─── Tab 1: 市场总览 ────────────────────────────────

with tabs[0]:
    section_title("📊 市场总览")

    # Index cards
    idx_data = fetch_indices()
    if not idx_data.empty:
        idx_list = idx_data.to_dict("records")
    else:
        idx_list = []

    if idx_list:
        cols = st.columns(len(idx_list))
        for i, idx in enumerate(idx_list):
            pct = idx.get("change_pct", 0)
            color = "#00c853" if pct > 0 else "#ff1744" if pct < 0 else "#8899aa"
            sign = "+" if pct > 0 else ""
            cols[i].metric(
                idx.get("name", ""),
                f"{(idx.get('price', 0)):.2f}",
                f"{sign}{pct:.2f}%",
            )

    # Market movers + candlestick quick view
    col_left, col_right = st.columns([1, 1])

    with col_left:
        section_title("🔥 涨幅榜")
        spot_df = fetch_active_stocks(30)
        if not spot_df.empty:
            display_df = format_quote_table(spot_df).head(10)
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                height=380,
            )
        else:
            st.info("行情数据暂不可用，请稍后刷新。")

    with col_right:
        section_title("📉 跌幅榜")
        if not spot_df.empty and "涨跌幅" in spot_df.columns:
            losers = spot_df.sort_values("涨跌幅", ascending=True).head(10)
            display_losers = format_quote_table(losers)
            st.dataframe(
                display_losers,
                use_container_width=True,
                hide_index=True,
                height=380,
            )
        else:
            st.info("暂无跌幅榜数据。")

    # Quick equity curve from trading data
    trading = load_trading_data()
    if trading and trading.get("equity") and len(trading["equity"]) > 1:
        section_title("📈 净值曲线")
        eq = trading["equity"]
        dates = [e["date"] for e in eq]
        values = [e["total_equity"] for e in eq]
        peak = np.maximum.accumulate(values)
        drawdown = [(v - p) / p * 100 for v, p in zip(values, peak)]

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(
            x=dates, y=values, mode="lines", name="净值",
            line=dict(color="#42a5f5", width=2),
            fill="tozeroy", fillcolor="rgba(66,165,245,0.1)",
        ), secondary_y=False)
        fig.add_trace(go.Scatter(
            x=dates, y=drawdown, mode="lines", name="回撤%",
            line=dict(color="#ff1744", width=1, dash="dot"),
            fill="tozeroy", fillcolor="rgba(255,23,68,0.05)",
        ), secondary_y=True)

        fig.update_layout(
            **chart_layout(280, top=8),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        fig.update_yaxes(title_text="净值", secondary_y=False, gridcolor="rgba(148,163,184,0.12)")
        fig.update_yaxes(title_text="回撤 %", secondary_y=True, gridcolor="rgba(148,163,184,0.08)")
        st.plotly_chart(fig, use_container_width=True)

# ─── Tab 2: 板块分析 ────────────────────────────────

with tabs[1]:
    section_title("🔥 板块热度分析")
    st.caption("基于沪深300+中证500成分股实时行情，按行业分组计算平均涨幅")

    from data.sector_analysis import analyze_sectors
    sector_data = analyze_sectors()

    if "error" not in sector_data:
        sectors = sector_data.get("sectors", [])

        if sectors:
            # Top 5 sector cards
            top5 = sectors[:5]
            cols = st.columns(5)
            for i, sec in enumerate(top5):
                avg = sec["avg_change_pct"]
                color = "#00c853" if avg > 0 else "#ff1744"
                sign = "+" if avg > 0 else ""
                cols[i].metric(
                    f"{'🥇' if i==0 else '🥈' if i==1 else '🥉' if i==2 else ''} {sec['sector']}",
                    f"{sign}{avg:.2f}%",
                    f"{sec['stock_count']}只成分股",
                )

            st.markdown("---")

            # Detailed sector breakdown
            section_title("板块明细")
            for sec in sectors:
                avg = sec["avg_change_pct"]
                color = "#00c853" if avg > 0 else "#ff1744"
                sign = "+" if avg > 0 else ""

                with st.expander(
                    f"{'🟢' if avg > 0 else '🔴'} **{sec['sector']}** — "
                    f"平均 {sign}{avg:.2f}% ({sec['stock_count']}只)",
                    expanded=(abs(avg) > 1.0 or sec in sectors[:3]),
                ):
                    if sec.get("all_stocks"):
                        df = pd.DataFrame(sec["all_stocks"])
                        display = select_columns(
                            df,
                            {"code": "代码", "name": "名称", "price": "最新价", "change_pct": "涨跌幅"},
                        )
                        if "最新价" in display.columns:
                            display["最新价"] = pd.to_numeric(display["最新价"], errors="coerce").map(lambda v: f"{v:.2f}" if pd.notna(v) else "--")
                        if "涨跌幅" in display.columns:
                            display["涨跌幅"] = pd.to_numeric(display["涨跌幅"], errors="coerce").map(lambda v: f"{v:+.2f}%" if pd.notna(v) else "--")
                        st.dataframe(
                            display,
                            use_container_width=True,
                            hide_index=True,
                        )

                        # Highlight recommendation
                        if avg > 0.5 and sec.get("top_gainers"):
                            st.success(
                                f"📈 **{sec['sector']}** 板块整体走强，领涨: "
                                + "、".join(
                                    f"{s['name']}({s['code']}) +{s['change_pct']:.1f}%"
                                    for s in sec["top_gainers"][:3]
                                )
                            )
    else:
        st.warning("板块数据暂不可用（休市或网络问题）")

    st.caption("⚠️ 以上为数据分析，不构成投资建议")

# ─── Tab 3: 个股详情 ────────────────────────────────

with tabs[2]:
    section_title("📈 个股详情")

    col_search, col_info = st.columns([1, 3])
    with col_search:
        symbol_input = st.text_input("股票代码", placeholder="600519", key="stock_input")
        if st.button("🔍 查询", key="search_btn"):
            st.session_state.search_symbol = symbol_input.strip()

    symbol = st.session_state.get("search_symbol", "")
    if symbol:
        df = fetch_stock_data(symbol, days=120)
        if not df.empty:
            last = df.iloc[-1]
            prev_close = df.iloc[-2]["close"] if len(df) > 1 else last["close"]
            change = last["close"] - prev_close
            change_pct = change / prev_close * 100 if prev_close else 0

            # Info cards row
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            color = "#00c853" if change_pct > 0 else "#ff1744"
            c1.metric("现价", f"{last['close']:.2f}", f"{change_pct:+.2f}%")
            c2.metric("今开", f"{last.get('open', 0):.2f}")
            c3.metric("昨收", f"{prev_close:.2f}")
            c4.metric("最高", f"{last.get('high', 0):.2f}")
            c5.metric("最低", f"{last.get('low', 0):.2f}")
            c6.metric("成交量", f"{last.get('volume', 0)/10000:.0f}万" if last.get('volume') else "--")

            # Candlestick + indicators
            fig = make_subplots(
                rows=4, cols=1, shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.45, 0.15, 0.2, 0.2],
                subplot_titles=("K线 + MA", "成交量", "MACD", "RSI + KDJ"),
            )

            # K-line
            fig.add_trace(go.Candlestick(
                x=df["date"], open=df["open"], high=df["high"],
                low=df["low"], close=df["close"], name="K线",
                increasing_line_color="#00c853", decreasing_line_color="#ff1744",
            ), row=1, col=1)
            for ma, color, w in [("ma5", "#42a5f5", 1), ("ma20", "#ffa726", 1), ("ma60", "#ce93d8", 1)]:
                if ma in df.columns:
                    fig.add_trace(go.Scatter(x=df["date"], y=df[ma], name=ma.upper(),
                                             line=dict(color=color, width=w)), row=1, col=1)

            # Volume
            colors = ["#00c853" if df.iloc[i]["close"] >= df.iloc[i]["open"] else "#ff1744"
                      for i in range(len(df))]
            fig.add_trace(go.Bar(x=df["date"], y=df["volume"], name="量",
                                 marker_color=colors, opacity=0.5), row=2, col=1)

            # MACD
            if "macd_dif" in df.columns:
                fig.add_trace(go.Scatter(x=df["date"], y=df["macd_dif"], name="DIF",
                                         line=dict(color="#42a5f5", width=1)), row=3, col=1)
                fig.add_trace(go.Scatter(x=df["date"], y=df["macd_dea"], name="DEA",
                                         line=dict(color="#ffa726", width=1)), row=3, col=1)
                macd_colors = ["#00c853" if v >= 0 else "#ff1744" for v in (df.get("macd_hist", pd.Series([0]*len(df))).fillna(0))]
                fig.add_trace(go.Bar(x=df["date"], y=df["macd_hist"].fillna(0), name="HIST",
                                     marker_color=macd_colors, opacity=0.6), row=3, col=1)

            # RSI + KDJ
            if "rsi14" in df.columns:
                fig.add_trace(go.Scatter(x=df["date"], y=df["rsi14"], name="RSI",
                                         line=dict(color="#ce93d8", width=1.5)), row=4, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="#ff1744", opacity=0.5, row=4, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="#00c853", opacity=0.5, row=4, col=1)
            if "kdj_k" in df.columns:
                fig.add_trace(go.Scatter(x=df["date"], y=df["kdj_k"], name="K",
                                         line=dict(color="#42a5f5", width=1)), row=4, col=1)
                fig.add_trace(go.Scatter(x=df["date"], y=df["kdj_d"], name="D",
                                         line=dict(color="#ffa726", width=1)), row=4, col=1)

            fig.update_layout(
                **chart_layout(720, top=34),
                showlegend=True,
                xaxis_rangeslider_visible=False,
            )
            fig.update_xaxes(gridcolor="rgba(148,163,184,0.12)")
            fig.update_yaxes(gridcolor="rgba(148,163,184,0.12)")
            st.plotly_chart(fig, use_container_width=True)

            # Indicator summary
            section_title("技术指标摘要")
            ic1, ic2, ic3, ic4, ic5 = st.columns(5)
            rsi_val = last.get("rsi14", 0)
            ic1.metric("RSI(14)", f"{rsi_val:.1f}",
                       "超买" if rsi_val > 70 else "超卖" if rsi_val < 30 else "中性")
            ic2.metric("MACD DIF/DEA", f"{last.get('macd_dif',0):.3f}/{last.get('macd_dea',0):.3f}")
            ic3.metric("KDJ K/D/J", f"{last.get('kdj_k',0):.1f}/{last.get('kdj_d',0):.1f}/{last.get('kdj_j',0):.1f}")
            ic4.metric("BOLL (上/下)", f"{last.get('boll_upper',0):.2f}/{last.get('boll_lower',0):.2f}")
            ic5.metric("ADX", f"{last.get('adx',0):.1f}",
                       "趋势" if last.get('adx',0) > 25 else "震荡" if last.get('adx',0) < 20 else "过渡")
        else:
            st.info("请输入股票代码查询，如 600519（贵州茅台）")
    else:
        st.info("👆 输入股票代码，点击查询。支持 000001 / 600519 / 300750 等")

# ─── Tab 4: 模拟交易 ────────────────────────────────

with tabs[3]:
    section_title("📋 模拟交易监控")
    trading = load_trading_data()

    if trading:
        equity = trading["equity"]
        total_equity = equity[-1]["total_equity"] if equity else 500000
        total_return = (total_equity - 500000) / 500000 * 100

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("总资产", f"¥{total_equity:,.0f}", f"{total_return:+.2f}%")
        c2.metric("持仓数", str(len(trading["positions"])))
        c3.metric("交易总数", str(len(trading["trades"])))

        if trading["positions"]:
            mv = sum(p.get("market_value", 0) for p in trading["positions"])
            upnl = sum(p.get("unrealized_pnl", 0) for p in trading["positions"])
            c4.metric("持仓市值", f"¥{mv:,.0f}")
            c5.metric("浮盈", f"¥{upnl:+,.0f}" if upnl != 0 else "¥0")
        else:
            c4.metric("持仓市值", "¥0")
            c5.metric("浮盈", "¥0")

        # Count today's trades
        today = datetime.now().strftime("%Y-%m-%d")
        today_trades = [t for t in trading["trades"] if t.get("created_at", "").startswith(today)]
        c6.metric("今日交易", str(len(today_trades)))

        # Position cards
        if trading["positions"]:
            section_title("当前持仓")
            for p in trading["positions"]:
                pnl_color = "#00c853" if p.get("unrealized_pnl", 0) > 0 else "#ff1744"
                with st.expander(
                    f"{'🟢' if p.get('unrealized_pnl',0) > 0 else '🔴'} "
                    f"{p['symbol']} {p['name']} — {p['quantity']}股 "
                    f"@ ¥{p['avg_cost']:.2f} | 浮盈: ¥{p.get('unrealized_pnl',0):+,.0f}",
                    expanded=True,
                ):
                    cols = st.columns(6)
                    cols[0].metric("成本价", f"¥{p['avg_cost']:.2f}")
                    cols[1].metric("现价", f"¥{p['current_price']:.2f}")
                    cols[2].metric("市值", f"¥{p.get('market_value',0):,.0f}")
                    cols[3].metric("浮盈%", f"{p.get('unrealized_pnl_pct',0):+.2f}%")
                    cols[4].metric("止损价", f"¥{p.get('stop_loss_price',0):.2f}")
                    cols[5].metric("策略", p.get("strategies",""))

        # Recent trades
        if trading["trades"]:
            section_title("最近交易")
            trades_df = pd.DataFrame(trading["trades"][:20])
            show = ["created_at", "symbol", "name", "side", "price", "quantity", "profit_pct", "close_reason", "strategies"]
            show = [c for c in show if c in trades_df.columns]
            st.dataframe(trades_df[show], use_container_width=True, hide_index=True)

        # Strategy performance
        if trading["strategies"]:
            section_title("策略表现")
            perf_cols = st.columns(len(trading["strategies"]))
            for i, sp in enumerate(trading["strategies"]):
                with perf_cols[i]:
                    st.metric(
                        sp["strategy_name"],
                        f"胜率 {(sp['win_rate']*100):.0f}%",
                        f"权重 {(sp['current_weight']*100):.0f}% | {sp['total_trades']}笔",
                    )
    else:
        st.info("📡 模拟交易数据暂不可用（本地数据库未连接）。部署到云端后，交易引擎在本地运行时此处将显示实时数据。")

# ─── Tab 5: 郑希投研 ────────────────────────────────

with tabs[4]:
    section_title("📖 郑希投资方法参考")

    method_path = "zhengxi-views/references/method.md"
    if os.path.exists(method_path):
        with open(method_path, "r", encoding="utf-8") as f:
            method_text = f.read()
    else:
        method_text = "文件未找到"

    tab_a, tab_b = st.tabs(["投资框架", "语料检索"])

    with tab_a:
        # Show key highlights
        st.markdown("""
        #### 核心方法论（从57篇公开语料蒸馏）

        **1. 景气方向先行**
        自上而下选赛道——先找景气向上的行业，再挑个股。关注产业链通胀环节、
        供给端创造的增量需求、全球比较优势。

        **2. ROE 低位弹性**
        偏好 ROE 处于历史低位但有修复弹性的公司——而非 ROE 已经很高的。
        核心是判断 ROE 能否回升、回升驱动力是否可持续。

        **3. 全球比较优势**
        中国制造业在全球产业链中的比较优势——哪些环节有不可替代性、
        哪些公司有定价权。

        **4. 流动性 + 周期拼接**
        关注流动性与市场周期的拼接——不追高、等回调、分批建仓。
        用"周期拼接"思路做波段，而非长期持有不动。

        **5. 业绩印证**
        最终看业绩能否印证判断——营收增速、毛利率趋势、净利润质量。
        """)

        with st.expander("查看完整方法论"):
            st.markdown(method_text[:8000] if len(method_text) > 8000 else method_text)

    with tab_b:
        search = st.text_input("搜索郑希观点", placeholder="如：AI算力、光通信、半导体、ROE、新能源")
        if search:
            import subprocess
            script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "zhengxi-views/scripts/search_corpus.py")
            if os.path.exists(script):
                try:
                    result = subprocess.run(
                        ["python", script, search],
                        capture_output=True, text=True, timeout=30,
                        cwd=os.path.dirname(os.path.abspath(__file__)),
                    )
                    output = result.stdout[:5000] if result.stdout else "无匹配结果"
                    st.code(output, language="markdown")
                except Exception as e:
                    st.warning(f"检索失败: {e}")
            else:
                st.warning("检索脚本路径未找到")

# ─── Tab 6: 自选股 ──────────────────────────────────

with tabs[5]:
    section_title("⭐ 自选股")

    if "watchlist" not in st.session_state:
        st.session_state.watchlist = []

    col_a, col_b = st.columns([3, 1])
    with col_a:
        new_sym = st.text_input("输入代码加入自选", placeholder="如 600519, 000001", key="wl_input")
    with col_b:
        if st.button("➕ 加入", key="wl_add") and new_sym:
            for code_part in new_sym.replace("，", ",").split(","):
                code_part = code_part.strip().zfill(6)
                if code_part.isdigit() and len(code_part) == 6:
                    prefix = "sh" if code_part.startswith(("6", "9")) else "sz"
                    st.session_state.watchlist.append(f"{prefix}{code_part}")
            st.session_state.watchlist = list(dict.fromkeys(st.session_state.watchlist))

    if st.session_state.watchlist:
        from data.fetcher import fetch_spot_tencent, fetch_spot_batch
        wl_symbols = list(dict.fromkeys(st.session_state.watchlist))
        quotes = pd.DataFrame(fetch_spot_tencent(wl_symbols) or fetch_spot_batch(wl_symbols))
        wl_data = quotes[quotes["代码"].isin(st.session_state.watchlist)] if not quotes.empty else pd.DataFrame()

        if not wl_data.empty:
            display = format_quote_table(wl_data)
            st.dataframe(display, use_container_width=True, hide_index=True, height=400)

            if st.button("🗑 清空自选", key="wl_clear"):
                st.session_state.watchlist = []
        else:
            st.info("正在加载行情...")
    else:
        st.info("👆 输入股票代码加入自选，如 600519（贵州茅台）")

# ─── Sidebar info ────────────────────────────────────

st.sidebar.markdown("### 📈 A股量化交易系统")
st.sidebar.caption("数据源: 腾讯 qt.gtimg.cn + 新浪")
st.sidebar.caption("策略: Trend(40%) + Momentum(35%) + Reversal(25%)")
st.sidebar.caption("初始资金: ¥500,000")
st.sidebar.markdown("---")
st.sidebar.caption(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ─── Auto-refresh ────────────────────────────────────

if AUTO_REFRESH:
    import time
    time.sleep(REFRESH_SECONDS)
    st.rerun()

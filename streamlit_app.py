"""
A股量化交易监控台 — Streamlit 云端部署版
整合: 实时行情 + 模拟交易监控 + 郑希投研框架
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["NO_PROXY"] = "*"

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from sqlalchemy import select, desc, func

# Page config
st.set_page_config(
    page_title="A股量化交易监控",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Data helpers ───────────────────────────────────

@st.cache_data(ttl=30)
def load_portfolio():
    """加载模拟账户摘要"""
    from data.database import SessionLocal
    from models.orm import EquitySnapshot, TradeLog, Position
    with SessionLocal() as db:
        pos = db.execute(select(Position)).scalars().all()
        snaps = db.execute(select(EquitySnapshot).order_by(EquitySnapshot.date)).scalars().all()
        trades = db.execute(select(TradeLog).order_by(desc(TradeLog.id)).limit(50)).scalars().all()
    return {
        "positions": [p.to_dict() for p in pos],
        "equity": [s.to_dict() for s in snaps],
        "trades": [t.to_dict() for t in trades],
    }


@st.cache_data(ttl=10)
def fetch_realtime_quotes(symbols: list[str]) -> list[dict]:
    """获取实时行情（腾讯接口）"""
    from data.fetcher import fetch_spot_tencent, fetch_spot_batch
    # Try Tencent first (no proxy issues)
    results = fetch_spot_tencent(symbols)
    if not results:
        results = fetch_spot_batch(symbols)
    return results


@st.cache_data(ttl=60)
def search_stock(keyword: str) -> list[dict]:
    """搜索股票"""
    from data.fetcher import fetch_spot_tencent
    # Try direct lookup
    sina_codes = []
    kw = keyword.strip()
    if kw.isdigit():
        code = kw.zfill(6)
        prefix = "sh" if code.startswith(("6", "9")) else "sz"
        sina_codes = [f"{prefix}{code}"]
    if sina_codes:
        results = fetch_spot_tencent(sina_codes)
        if results:
            return results
    return []


# ─── Sidebar ────────────────────────────────────────

st.sidebar.title("📈 A股量化监控")
page = st.sidebar.radio("页面", ["📊 模拟交易", "🔍 个股查询", "📖 郑希投研", "⭐ 自选股"])

st.sidebar.markdown("---")
st.sidebar.caption(f"更新时间: {datetime.now().strftime('%H:%M:%S')}")
try:
    from utils.trading_calendar import is_trading_time
    _, status = is_trading_time()
    status_map = {"live": "🟢 交易中", "lunch_break": "🟡 午休", "closed": "⚫ 已收盘", "holiday": "🔴 休市"}
    st.sidebar.info(status_map.get(status, status))
except:
    pass

# ─── Page 1: 模拟交易 ───────────────────────────────

if page == "📊 模拟交易":
    st.title("📊 模拟交易监控")

    data = load_portfolio()

    # Summary cards
    col1, col2, col3, col4, col5 = st.columns(5)
    positions = data["positions"]
    equity = data["equity"]

    total_equity = 500000
    if equity:
        total_equity = equity[-1]["total_equity"]
    total_return = (total_equity - 500000) / 500000 * 100

    col1.metric("总资产", f"¥{total_equity:,.0f}", f"{total_return:+.2f}%")
    col2.metric("持仓数", str(len(positions)))
    col3.metric("交易记录", str(len(data["trades"])))

    if positions:
        market_val = sum(p.get("market_value", 0) for p in positions)
        col4.metric("持仓市值", f"¥{market_val:,.0f}")
        unrealized = sum(p.get("unrealized_pnl", 0) for p in positions)
        col5.metric("浮动盈亏", f"¥{unrealized:+,.0f}", delta_color="normal")

    # Equity curve
    if equity:
        st.subheader("净值曲线")
        dates = [e["date"] for e in equity]
        values = [e["total_equity"] for e in equity]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dates, y=values, mode="lines", name="净值",
                                 line=dict(color="#42a5f5", width=2),
                                 fill="tozeroy", fillcolor="rgba(66,165,245,0.1)"))
        fig.update_layout(height=300, paper_bgcolor="#0f1b2d", plot_bgcolor="#0f1b2d",
                          font=dict(color="#e0e0e0"), margin=dict(l=50, r=20, t=10, b=30))
        st.plotly_chart(fig, use_container_width=True)

    # Positions table
    if positions:
        st.subheader("当前持仓")
        pos_df = pd.DataFrame(positions)
        if not pos_df.empty:
            show_cols = ["symbol", "name", "quantity", "avg_cost", "current_price", "unrealized_pnl", "stop_loss_price", "take_profit_price", "strategies"]
            show_cols = [c for c in show_cols if c in pos_df.columns]
            st.dataframe(pos_df[show_cols], use_container_width=True, hide_index=True)

    # Recent trades
    if data["trades"]:
        st.subheader("最近交易")
        trades_df = pd.DataFrame(data["trades"])
        st.dataframe(trades_df, use_container_width=True, hide_index=True)

# ─── Page 2: 个股查询 ───────────────────────────────

elif page == "🔍 个股查询":
    st.title("🔍 个股查询")

    keyword = st.text_input("输入股票代码或名称", placeholder="如 600519 或 贵州茅台")

    if keyword:
        results = search_stock(keyword)
        if results:
            stock = results[0]
            name = stock.get("名称", "")
            price = stock.get("最新价", 0)
            change_pct = stock.get("涨跌幅", 0)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric(name, f"¥{price:.2f}", f"{change_pct:+.2f}%")
            col2.metric("今开", f"{stock.get('今开', 0):.2f}")
            col3.metric("最高", f"{stock.get('最高', 0):.2f}")
            col4.metric("最低", f"{stock.get('最低', 0):.2f}")

            # Fetch history for chart
            from data.fetcher import fetch_stock_history
            from engine.indicators import add_all_indicators

            df = fetch_stock_history(keyword, days=120)
            if not df.empty:
                df = add_all_indicators(df)
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=df["date"], open=df["open"], high=df["high"],
                    low=df["low"], close=df["close"], name="K线"))
                if "ma5" in df.columns:
                    fig.add_trace(go.Scatter(x=df["date"], y=df["ma5"], name="MA5",
                                             line=dict(color="#42a5f5", width=1)))
                if "ma20" in df.columns:
                    fig.add_trace(go.Scatter(x=df["date"], y=df["ma20"], name="MA20",
                                             line=dict(color="#ffa726", width=1)))
                fig.update_layout(height=400, xaxis_rangeslider_visible=False,
                                  paper_bgcolor="#0f1b2d", plot_bgcolor="#0f1b2d",
                                  font=dict(color="#e0e0e0"))
                st.plotly_chart(fig, use_container_width=True)

                # Indicators
                last = df.iloc[-1]
                cols = st.columns(5)
                cols[0].metric("RSI(14)", f"{last.get('rsi14', 0):.1f}")
                cols[1].metric("MACD DIF", f"{last.get('macd_dif', 0):.3f}")
                cols[2].metric("KDJ-K", f"{last.get('kdj_k', 0):.1f}")
                cols[3].metric("ATR(14)", f"{last.get('atr14', 0):.2f}")
                cols[4].metric("ADX", f"{last.get('adx', 0):.1f}")
        else:
            st.warning("未找到该股票")

# ─── Page 3: 郑希投研 ────────────────────────────────

elif page == "📖 郑希投研":
    st.title("📖 郑希投资方法参考")

    # Read and display the methodology
    method_path = "zhengxi-views/references/method.md"
    if os.path.exists(method_path):
        with open(method_path, "r", encoding="utf-8") as f:
            method_text = f.read()
    else:
        method_text = "文件未找到"

    tab1, tab2 = st.tabs(["投资方法", "语料检索"])

    with tab1:
        st.markdown(method_text[:5000] if len(method_text) > 5000 else method_text)
        if len(method_text) > 5000:
            st.caption("(显示前 5000 字，完整内容见项目文件)")

    with tab2:
        search_term = st.text_input("搜索郑希观点", placeholder="如: AI 算力, ROE, 半导体")
        if search_term:
            import subprocess
            script = "zhengxi-views/scripts/search_corpus.py"
            if os.path.exists(script):
                result = subprocess.run(
                    ["python", script, search_term],
                    capture_output=True, text=True, timeout=30,
                )
                st.text(result.stdout[:3000] if result.stdout else "无匹配结果")
            else:
                st.warning("检索脚本未找到")

# ─── Page 4: 自选股 ──────────────────────────────────

elif page == "⭐ 自选股":
    st.title("⭐ 自选股")

    if "watchlist" not in st.session_state:
        st.session_state.watchlist = []

    # Add stock
    col1, col2 = st.columns([3, 1])
    with col1:
        new_stock = st.text_input("输入代码加入自选", placeholder="600519")
    with col2:
        if st.button("加入") and new_stock:
            code = new_stock.strip().zfill(6)
            prefix = "sh" if code.startswith(("6", "9")) else "sz"
            st.session_state.watchlist.append(f"{prefix}{code}")
            st.session_state.watchlist = list(set(st.session_state.watchlist))

    if st.session_state.watchlist:
        quotes = fetch_realtime_quotes(st.session_state.watchlist)
        if quotes:
            df = pd.DataFrame(quotes)
            show_cols = ["代码", "名称", "最新价", "涨跌幅", "成交量", "成交额", "换手率"]
            show_cols = [c for c in show_cols if c in df.columns]
            st.dataframe(df[show_cols], use_container_width=True, hide_index=True)

            if st.button("清空自选"):
                st.session_state.watchlist = []
    else:
        st.info("暂无自选股，请添加")

<div align="center">

# 📊 A股资讯助手

**实时行情 · K线走势 · 走势总结 · 自选股 · 多股对比**

*「输入股票名称或代码,实时查看股价与各项指标,并总结近期长期走势与每日新闻」*

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://chinese-a-stock.streamlit.app/)

![版本](https://img.shields.io/badge/版本-v1.0-blue) ![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white) ![框架](https://img.shields.io/badge/框架-Streamlit-FF4B4B?logo=streamlit&logoColor=white) ![市场](https://img.shields.io/badge/市场-A股-e34a4a) ![数据源](https://img.shields.io/badge/数据源-腾讯·新浪·东财·同花顺-2ca02c)

**[🚀 在线体验](https://chinese-a-stock.streamlit.app/)** · [功能](#功能) · [安装与运行](#安装与运行) · [部署](#部署到-streamlit-云) · [文件结构](#文件结构) · [说明](#说明)

</div>

---

一个中国 A 股资讯网页应用:输入股票名称或代码,即可查看实时行情、关键指标、K 线走势图、
规则化走势总结、财务基本面与近期个股新闻;支持自选股与多股对比。

## 功能

三个页面(左侧切换):

- **📈 个股详情**
  - 实时行情:最新价、涨跌幅、今开/昨收/最高/最低、换手率、市盈率、市净率、总市值、成交额
  - 走势图:Plotly 蜡烛图 + MA5/MA20/MA60 均线 + 成交量
  - 走势总结:基于均线、区间收益、波动率、回撤的规则化中文总结(短/中/长期)
  - 财务基本面:营收、净利润、ROE、毛利率、负债率等财务摘要
  - 个股新闻:近期相关新闻列表与摘要
  - 一键 ☆ 加入自选 / 移除
- **⭐ 自选股**:自选清单的实时行情表格(涨跌幅红绿着色),会话级隔离(每位访客独立)
  - 按涨跌幅排序;按**板块**(主板/科创板/创业板/北交所)或**行业**(证监会分类)分组,每组带平均涨跌幅
  - **盘中自动刷新**:仅在 A 股交易时段(交易日 9:30–11:30 / 13:00–15:00)每 5 分钟自动刷新,非交易时段静默
- **🆚 多股对比**:多只股票**归一化走势叠加**(起点=100)+ 最新价/涨跌幅/区间涨幅/PE/PB/市值横向对比表

数据来源:[AkShare](https://akshare.akfamily.xyz/) + 腾讯/新浪实时接口,免费、无需 token。

| 数据 | 来源 |
|------|------|
| **实时行情**(价格/涨跌幅/PE/PB/市值/换手) | 腾讯(`qt.gtimg.cn`,单只+批量) |
| 历史 K 线 / 开高低 / 成交量 | 新浪(`stock_zh_a_daily`,腾讯备份) |
| 估值补充(PE静 / 市销率) | 东方财富 datacenter(`stock_value_em`) |
| 财务摘要(ROE / 负债率 / 营收 / 净利…) | 同花顺(`stock_financial_abstract_ths`) |
| 个股新闻 | 东方财富(`stock_news_em`) |
| 所属行业(分组用) | 巨潮 cninfo(`stock_industry_change_cninfo`) |
| 交易日历(自动刷新用) | 新浪(`tool_trade_date_hist_sina`) |

## 安装与运行

```bash
# 1. 安装依赖(国内建议加镜像,如 -i https://mirrors.aliyun.com/pypi/simple/)
pip install -r requirements.txt

# 2. 启动网页(随后浏览器打开 http://localhost:8501)
streamlit run app.py
```

> 若 `streamlit` / `pip` 不在 PATH,用模块方式调用:
> `python -m pip install -r requirements.txt` 、`python -m streamlit run app.py`。

## 部署到 Streamlit 云

好友无需安装任何东西,打开链接即用(本项目已部署在 <https://chinese-a-stock.streamlit.app/>):

1. 把本项目上传到一个 GitHub 仓库;
2. 打开 [share.streamlit.io](https://share.streamlit.io),用 GitHub 登录 → **New app** → 选择仓库 / 分支,Main file 填 `app.py` → **Deploy**;
3. 等待安装依赖(数分钟),得到 `https://xxx.streamlit.app` 永久免费链接,分享即可。

> ⚠️ Streamlit 云服务器位于海外,国内行情接口可能变慢或偶尔取不到数据;核心的价格 / K线 / 新闻一般可用,行业 / 财务等增强数据可能不稳定。

自选股为**会话级隔离**:每位访客拥有独立的自选股,互不影响(关闭页面后不保留,每次打开载入默认清单)。

## 文件结构

| 文件 | 说明 |
|------|------|
| `app.py` | Streamlit 网页主程序(三页:个股详情 / 自选股 / 多股对比) |
| `data_source.py` | 数据层:查询、实时行情(单只+批量)、历史、财务、新闻、行业、交易日历 |
| `analysis.py` | 规则化走势分析:均线、收益、波动率、回撤与中文总结 |
| `storage.py` | 自选股管理(会话级,`st.session_state`) |
| `.streamlit/config.toml` | Streamlit 配置 |
| `requirements.txt` | 依赖清单 |

## 说明

- 个股详情与自选股的行情为**腾讯实时数据**(盘中为实时价,收盘后为当日收盘);页面顶部标注数据时间。实时源不可用时自动回退到最新交易日收盘数据。
- 走势总结完全基于历史价格的确定性统计,**仅供参考,不构成投资建议**。
- 若本机配有代理(如 Clash/V2Ray),东方财富实时盘口主机 `push2.eastmoney.com` 可能不可达;本项目已规避该主机,实时行情改用腾讯 `qt.gtimg.cn`(代理开关均可用)。
- AkShare 上游接口偶有变动,若某项数据为空,多为接口临时不可用,稍后重试即可。

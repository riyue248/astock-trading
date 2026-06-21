# A股量化自动交易系统

## 项目概述
基于 Python 的 A 股模拟交易系统。三大策略（趋势/动量/反转）自动扫描市场、打分、买卖，搭配 Web 仪表盘实时监控。

## 架构

```
E:\自动预测\
├── engine/           # 核心交易引擎
│   ├── paper_account.py      # 模拟账户（买卖/持仓/止损止盈）
│   ├── strategy_engine.py    # 策略编排器（扫描→打分→执行）
│   ├── scoring_engine.py     # 多策略信号聚合+排名
│   ├── scheduler.py          # 主循环（APScheduler，每5分钟扫描）
│   ├── risk_manager.py       # 仓位计算（Kelly公式）+ 风控
│   ├── regime_detector.py    # ADX 市场状态检测（趋势/震荡）
│   ├── optimizer.py          # 权重调整 + 参数网格搜索
│   ├── indicators.py         # 技术指标（MA/MACD/RSI/KDJ/BOLL/ADX）
│   └── strategies/
│       ├── base.py           # 策略抽象基类
│       ├── trend.py          # 趋势策略（MA排列+MACD确认，权重40%）
│       ├── momentum.py       # 动量策略（放量突破，权重35%）
│       └── reversal.py       # 反转策略（RSI/KDJ超买超卖，权重25%）
├── data/
│   ├── fetcher.py            # 数据获取（新浪+腾讯双源）
│   ├── database.py           # SQLAlchemy 引擎
│   └── sector_analysis.py    # 板块热度分析
├── models/
│   ├── orm.py                # 6 张 SQLite 表
│   └── schemas.py            # Pydantic 模型
├── web/                      # FastAPI 仪表盘（Jinja2 + Plotly.js）
│   ├── app.py                # FastAPI 主应用
│   ├── api.py                # REST 端点
│   ├── sse.py                # SSE 实时推送
│   ├── pages.py              # 页面路由
│   ├── templates/            # 5 个页面模板
│   └── static/               # CSS + JS
├── streamlit_app.py          # Streamlit 云端版（6 Tab 页面）
├── deploy.py                 # 一键部署脚本
├── run.py                    # 本地启动入口
├── config.py                 # 集中配置
├── .env                      # 服务器密码（不提交 Git）
└── utils/
    └── trading_calendar.py   # A股交易日历
```

## 数据流

```
交易时段 (9:30-15:00):
  APScheduler 每60秒检查 → 每5分钟触发扫描
  → 获取沪深300+中证500成分股（717只）实时行情（腾讯 qt.gtimg.cn）
  → 对每只股票：拉90天K线 → 计算技术指标 → 三个策略分别打分
  → ADX 检测市场状态 → 调整策略权重
  → 综合评分 = trend×w_trend + momentum×w_momentum + reversal×w_reversal
  → 评分 > 0.4 买入，< -0.3 卖出
  → 止损 -8%、止盈 +15% 自动检查
  → 写入 SQLite → SSE 推送到 Web 仪表盘
```

## 数据源

| 数据 | 来源 | 备注 |
|------|------|------|
| 实时行情 | 腾讯 qt.gtimg.cn | 主力，无需代理 |
| 历史K线 | AKShare stock_zh_a_daily | 新浪后端 |
| 指数 | 新浪 hq.sinajs.cn | |
| 成分股 | AKShare index_stock_cons | 沪深300+中证500 |

**注意**：东方财富 (eastmoney) 在本机代理/VPN 环境下不通，已全部切换至腾讯+新浪。

## 启动方式

### 本地开发
```bash
python run.py                      # 启动 FastAPI + 交易引擎
python deploy.py                   # 一键部署到云端
streamlit run streamlit_app.py     # 启动 Streamlit 本地版
```

### 云端部署
```bash
# 服务器: 139.129.97.101:8000（阿里云青岛）
# 账户: root
# 密码: 见 .env 文件
# 项目路径: /opt/astock-trading
# systemd 服务: astock-trader（开机自启）

ssh root@139.129.97.101
systemctl status astock-trader   # 查看状态
systemctl restart astock-trader  # 重启
journalctl -u astock-trader -f   # 查看日志
```

## 三个策略详解

### Trend（趋势）- 权重 40%
- **买入信号**：MA5 上穿 MA20（金叉）+ MA多头排列 + MACD DIF > DEA
- **卖出信号**：死叉 + 空头排列
- **适用市况**：单边趋势行情（ADX > 25 时权重×1.5）

### Momentum（动量）- 权重 35%
- **买入信号**：成交量放大 1.5倍 + 价格涨超 3% + 价量配合健康
- **卖出信号**：放量下跌（-0.3 出货惩罚分）
- **适用市况**：板块轮动、资金集中涌入

### Reversal（反转）- 权重 25%
- **买入信号**：RSI < 30 超卖 + KDJ 底背离 + 布林下轨
- **卖出信号**：RSI > 70 超买 + KDJ 顶背离
- **适用市况**：震荡市（ADX < 20 时权重×1.5）

## 数据库表

| 表 | 字段 | 用途 |
|------|------|------|
| trade_log | id, symbol, side, price, quantity, profit_pct, close_reason... | 每笔交易 |
| positions | symbol, quantity, avg_cost, stop_loss_price, take_profit_price... | 当前持仓 |
| signals | symbol, trend_score, momentum_score, reversal_score, composite_score... | 扫描日志 |
| equity_snapshot | date, total_equity, cash, drawdown_pct... | 每日净值 |
| strategy_performance | strategy_name, win_rate, avg_win_pct, current_weight... | 策略表现 |
| strategy_params | strategy_name, params_json, sharpe... | 策略参数 |

## 三个访问入口

| 入口 | 地址 | 用途 |
|------|------|------|
| 本地仪表盘 | http://localhost:8000 | Codex 优化后的主力看盘 |
| 云端仪表盘 | http://139.129.97.101:8000 | 24/7 在线，关电脑也跑 |
| Streamlit 云端 | https://riyue248-astock-trading.streamlit.app | 手机随时看 |

## 当前状态
- 账户：¥500,000 初始资金
- 持仓：0
- 风控：单只≤30%，总回撤≤15%，止损-8%，止盈+15%
- 交易时间：9:30-11:30, 13:00-15:00（北京时间）
- 云端：阿里云青岛，systemd 自启，24/7 运行

## 常见问题

**Q: 电脑关机了还会交易吗？**
A: 会。交易引擎在阿里云上跑。本地 `localhost:8000` 只是看盘工具。

**Q: 怎么更新代码到云端？**
A: 运行 `python deploy.py`（自动 git push → SSH 到云 → git pull → 重启）

**Q: 东方财富数据不通怎么办？**
A: 已全部切到腾讯+新浪。如果还不行，检查 VPN/代理。

**Q: 怎么添加新策略？**
A: 在 `engine/strategies/` 下新建文件，继承 `BaseStrategy`，实现 `generate_signal()`，然后在 `scoring_engine.py` 中注册。

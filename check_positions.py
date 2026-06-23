"""Check positions on cloud server."""
import paramiko, json

HOST = "139.129.97.101"
USER = "root"
PASSWORD = "Msylbw2002@"
PROJECT = "/opt/astock-trading"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=15)

def run(cmd, timeout=30):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(out.strip())
    if err.strip(): print("[!]", err.strip())

print("=== 当前持仓 ===")
run(f"cd {PROJECT} && python3 -c \"
from data.database import SessionLocal
from models.orm import Position
from sqlalchemy import select
db=SessionLocal()
positions = db.execute(select(Position)).scalars().all()
for p in positions:
    print(f'{p.symbol} {p.name}: {p.quantity}股 @ ¥{p.avg_cost:.2f} | 现价 ¥{p.current_price:.2f} | 市值 ¥{p.market_value:.0f} | 浮盈 ¥{p.unrealized_pnl:.0f} ({p.unrealized_pnl/(p.avg_cost*p.quantity)*100:.1f}%)')
if not positions:
    print('空仓')
db.close()
\"")

print("\n=== 最近10笔交易 ===")
run(f"cd {PROJECT} && python3 -c \"
from data.database import SessionLocal
from models.orm import TradeLog
from sqlalchemy import select, desc
db=SessionLocal()
trades = db.execute(select(TradeLog).order_by(desc(TradeLog.id)).limit(10)).scalars().all()
for t in trades:
    pnl = f'PnL: {t.profit_pct*100:+.2f}%' if t.profit_pct else ''
    print(f'#{t.id} {t.side.upper()} {t.symbol} {t.name}: {t.quantity}股 @ ¥{t.price:.2f} | {t.strategies} | {pnl}')
db.close()
\"")

c.close()

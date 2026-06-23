"""Check scan results on cloud server."""
import paramiko, time, requests

HOST = "139.129.97.101"
USER = "root"
PASSWORD = "Msylbw2002@"
PROJECT = "/opt/astock-trading"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=15)

def run(cmd, timeout=30):
    print(f">>> {cmd}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(out.strip())
    if err.strip(): print("[!]", err.strip())
    return out

# Check latest logs
print("=== Latest 30 log lines ===")
run("journalctl -u astock-trader --no-pager -n 30")

# Check if scan produced results
print("\n=== Signal count in DB ===")
run(f"cd {PROJECT} && python3 -c \"from data.database import SessionLocal; from models.orm import Signal; from sqlalchemy import select, func; db=SessionLocal(); print('Signals:', db.execute(select(func.count(Signal.id))).scalar()); db.close()\" 2>&1")

print("\n=== Trade count in DB ===")
run(f"cd {PROJECT} && python3 -c \"from data.database import SessionLocal; from models.orm import TradeLog; from sqlalchemy import select, func; db=SessionLocal(); print('Trades:', db.execute(select(func.count(TradeLog.id))).scalar()); db.close()\" 2>&1")

c.close()

# API check (retry, server should be responsive now)
print("\n=== API Status ===")
time.sleep(2)
try:
    r = requests.get(f"http://{HOST}:8000/api/status", timeout=15)
    print(r.json())
except Exception as e:
    print(f"Still loading: {e}")

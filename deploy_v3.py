"""Deploy latest changes to cloud — pull + restart."""
import paramiko, time, requests

HOST = "139.129.97.101"
USER = "root"
PASSWORD = "Msylbw2002@"
PROJECT = "/opt/astock-trading"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print(f"Connecting to {HOST}...")
c.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=15)
print("Connected!\n")

def run(cmd, timeout=60):
    print(f">>> {cmd}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(out.strip())
    if err.strip(): print("[!]", err.strip())

# Git pull
run(f"cd {PROJECT} && git pull origin master")

# Restart
run("systemctl restart astock-trader")
time.sleep(4)

# Verify
print("\n=== Service status ===")
run("systemctl status astock-trader --no-pager -l | head -12")

print("\n=== Startup log ===")
run("journalctl -u astock-trader --no-pager -n 10 | grep -E 'STARTED|scan|Scan|error|Error' || journalctl -u astock-trader --no-pager -n 5")

# API check
print("\n=== API status ===")
try:
    r = requests.get(f"http://{HOST}:8000/api/status", timeout=15)
    s = r.json()
    print(f"Scheduler: running={s['running']}, healthy={s['scheduler_healthy']}")
    print(f"Trading: {s['trading']} ({s['trading_status']})")
    print(f"Scan count: {s['scan_count']}")
    print(f"Equity: {s.get('equity', 'N/A')}")
    print(f"Positions: {s.get('positions', 'N/A')}")
except Exception as e:
    print(f"API not ready yet: {e}")

c.close()
print("\n=== Deploy complete ===")

"""Cloud deploy script — SSH to Aliyun, pull, install, restart."""
import paramiko
import time

HOST = "139.129.97.101"
USER = "root"
PASSWORD = "Msylbw2002@"
PROJECT = "/opt/astock-trading"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print(f"Connecting to {HOST}...")
c.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=15)
print("Connected!")


def run(cmd, timeout=120):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip():
        print(out.strip())
    if err.strip():
        print("[stderr]", err.strip())
    return out, err


# Step 1: Git pull
run(f"cd {PROJECT} && git pull origin master")

# Step 2: Install dependencies
run(f"cd {PROJECT} && pip install -r requirements.txt -q 2>&1", timeout=120)

# Step 3: Restart service
print("\n>>> Restarting astock-trader...")
run("systemctl restart astock-trader")
time.sleep(3)

# Step 4: Service status
run("systemctl status astock-trader --no-pager -l")

# Step 5: Recent logs (look for scheduler startup)
print("\n=== Recent logs (looking for 'STARTED') ===")
run("journalctl -u astock-trader --no-pager -n 40 | grep -E 'STARTED|scheduler|error|Error|scan|Scan' || journalctl -u astock-trader --no-pager -n 20")

# Step 6: Health check
print("\n=== Health check ===")
import requests
try:
    r = requests.get(f"http://{HOST}:8000/health", timeout=10)
    print(f"Health: {r.status_code} - {r.json()}")
    r2 = requests.get(f"http://{HOST}:8000/api/status", timeout=10)
    print(f"Status: {r2.json()}")
except Exception as e:
    print(f"Health check failed: {e}")

c.close()
print("\n=== Deploy complete ===")

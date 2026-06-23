"""Fix cloud deployment — stash dirty files, git pull, restart, verify."""
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


def run(cmd, timeout=120):
    print(f">>> {cmd}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip():
        print(out.strip())
    if err.strip():
        print("[!]", err.strip())
    return out, err


# Step 1: Stash any local changes on server
print("=== Step 1: Stash local changes ===")
run(f"cd {PROJECT} && git stash push -m 'auto-stash-before-deploy'")
run(f"cd {PROJECT} && git status --short")

# Step 2: Git pull
print("\n=== Step 2: Git pull ===")
out, err = run(f"cd {PROJECT} && git pull origin master")
if "Aborting" in out or "Aborting" in err:
    print("ERROR: git pull still failing!")
    c.close()
    exit(1)

# Step 3: pip install
print("\n=== Step 3: pip install ===")
run(f"cd {PROJECT} && pip install -r requirements.txt -q 2>&1", timeout=120)

# Step 4: Restart service
print("\n=== Step 4: Restart astock-trader ===")
run("systemctl restart astock-trader")
time.sleep(4)

# Step 5: Check status
print("\n=== Step 5: Service status ===")
run("systemctl status astock-trader --no-pager -l | head -20")

# Step 6: Check logs for our new "STARTED" signature
print("\n=== Step 6: Verify new code is running ===")
out, _ = run("journalctl -u astock-trader --no-pager -n 15")
if "STARTED" in out and "check_interval" in out:
    print("*** SUCCESS: New scheduler code is active! ***")
elif "Trading scheduler started" in out:
    print("WARNING: Still running OLD code — new code not deployed")
else:
    print("UNKNOWN: Cannot determine which version is running")

# Step 7: Health & Status
print("\n=== Step 7: API checks ===")
try:
    r = requests.get(f"http://{HOST}:8000/health", timeout=10)
    print(f"Health: {r.status_code} {r.json()}")
    r2 = requests.get(f"http://{HOST}:8000/api/status", timeout=10)
    status = r2.json()
    print(f"Scheduler running: {status.get('running')}")
    print(f"Scheduler healthy: {status.get('scheduler_healthy')}")
    print(f"Trading: {status.get('trading')} ({status.get('trading_status')})")
    print(f"Scan count: {status.get('scan_count')}")
    print(f"Last heartbeat: {status.get('last_heartbeat_sec_ago')}s ago")
except Exception as e:
    print(f"API check failed: {e}")

c.close()
print("\n=== Done ===")

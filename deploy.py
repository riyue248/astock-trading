"""
One-click deploy: local -> GitHub -> cloud server
Usage: python deploy.py
"""
import os
import subprocess
import sys

# Config (password from .env file, NOT committed to Git)
SERVER_IP = "139.129.97.101"
SERVER_PORT = 22
SERVER_USER = "root"
PROJECT_DIR = "/opt/astock-trading"
LOCAL_DIR = r"E:\自动预测"


def _load_password():
    env_file = os.path.join(LOCAL_DIR, ".env")
    if os.path.exists(env_file):
        for line in open(env_file, encoding="utf-8"):
            line = line.strip()
            if line.startswith("SERVER_PASS="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("SERVER_PASS", "")


SERVER_PASS = _load_password()


def run(cmd, cwd=None):
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def main():
    print("=" * 50)
    print("  A-Share Trading System - One-Click Deploy")
    print("=" * 50)

    # Step 1: Git commit & push
    print("\n>>> Step 1/3: Push local code to GitHub...")
    run("git add -A", cwd=LOCAL_DIR)

    _, status, _ = run("git status --porcelain", cwd=LOCAL_DIR)
    if status.strip():
        run('git commit -m "Auto deploy"', cwd=LOCAL_DIR)
        print("  Changes committed")

    code, out, err = run("git push", cwd=LOCAL_DIR)
    if code == 0:
        print("  OK - Pushed to GitHub")
    else:
        print(f"  FAILED to push: {err[:200]}")
        return

    # Step 2: Deploy to cloud
    print("\n>>> Step 2/3: Deploy to cloud server...")
    if not SERVER_PASS:
        print("  FAILED: No password. Set SERVER_PASS in .env file")
        return

    deploy_code = (
        "import paramiko\n"
        "c = paramiko.SSHClient()\n"
        "c.set_missing_host_key_policy(paramiko.AutoAddPolicy())\n"
        f"c.connect('{SERVER_IP}', port={SERVER_PORT}, username='{SERVER_USER}', password='{SERVER_PASS}', timeout=15)\n"
        f"stdin, stdout, stderr = c.exec_command('cd {PROJECT_DIR} && git pull && systemctl restart astock-trader', timeout=20)\n"
        "print(stdout.read().decode()[-300:])\n"
        "c.close()\n"
    )
    code, out, err = run(f'"{sys.executable}" -c "{deploy_code}"')
    if code == 0:
        print("  OK - Cloud server updated and restarted")
    else:
        print(f"  FAILED: {err[:200] if err else out[:200]}")
        return

    # Step 3: Verify
    print("\n>>> Step 3/3: Verify deployment...")
    verify_code = (
        "import requests\n"
        f"try:\n"
        f"    r = requests.get('http://{SERVER_IP}:8000/health', timeout=8)\n"
        f"    print(f'Status: {{r.status_code}} - {{r.json()}}')\n"
        f"except Exception as e:\n"
        f"    print(f'Cannot connect: {{e}}')\n"
    )
    code, out, err = run(f'"{sys.executable}" -c "{verify_code}"')
    print(f"  {out.strip()}")

    print(f"\n  Dashboard: http://{SERVER_IP}:8000")
    print(f"  Streamlit: https://riyue248-astock-trading.streamlit.app")
    print("=" * 50)
    print("  Deploy finished")
    print("=" * 50)


if __name__ == "__main__":
    main()

"""
一键部署：本地代码 → GitHub → 云端服务器
用法：python deploy.py
"""
import os
import subprocess
import sys
import time

# ─── 配置（密码从 .env 文件读取，不提交 Git） ──────
SERVER_IP = "139.129.97.101"
SERVER_PORT = 22
SERVER_USER = "root"
PROJECT_DIR = "/opt/astock-trading"
LOCAL_DIR = r"E:\自动预测"

# 从 .env 文件读取密码
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
    """Run a shell command."""
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def step(msg, emoji="📌"):
    print(f"\n{emoji} {msg}")


def main():
    print("=" * 55)
    print("  🔧 A股交易系统 — 一键部署")
    print("=" * 55)

    # ─── Step 1: Git commit & push ──────────────────
    step("Step 1/3: 提交本地代码到 GitHub...")
    code, out, err = run("git add -A", cwd=LOCAL_DIR)
    if code != 0:
        print(f"  ⚠️ git add 出错: {err}")
    else:
        print("  ✅ 文件已暂存")

    # Check if there are changes to commit
    _, status, _ = run("git status --porcelain", cwd=LOCAL_DIR)
    if status.strip():
        code, out, err = run('git commit -m "Auto deploy: update from local"', cwd=LOCAL_DIR)
        if code == 0:
            print("  ✅ 已提交更改")
        else:
            print(f"  ℹ️ {out.strip()}")

    code, out, err = run("git push", cwd=LOCAL_DIR)
    if code == 0:
        print("  ✅ 已推送到 GitHub")
    else:
        print(f"  ❌ 推送失败: {err.strip()}")
        print("  检查网络或代理设置后重试")
        return

    # ─── Step 2: Deploy to cloud server ──────────────
    step("Step 2/3: 部署到云服务器...")
    deploy_script = f"""
import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('{SERVER_IP}', port={SERVER_PORT}, username='{SERVER_USER}', password='{SERVER_PASS}', timeout=15)
stdin, stdout, stderr = c.exec_command('cd {PROJECT_DIR} && git pull 2>&1', timeout=20)
out = stdout.read().decode()
err = stderr.read().decode()
print(out.strip()[-200:] if out else '')
if err and 'Already up' not in err and 'Fast-forward' not in err:
    print('ERR:', err.strip()[-200:])
stdin2, stdout2, stderr2 = c.exec_command('systemctl restart astock-trader 2>&1 && sleep 2 && curl -s localhost:8000/health', timeout=15)
print('Status:', stdout2.read().decode().strip()[-100:])
c.close()
"""
    code, out, err = run(f'"{sys.executable}" -c "{deploy_script}"')
    if code == 0:
        print("  ✅ 云端已更新并重启")
    else:
        print(f"  ❌ 部署失败: {err[:200] if err else out[:200]}")
        print("  手动 SSH 检查: ssh root@{SERVER_IP}")
        return

    # ─── Step 3: Verify ──────────────────────────────
    step("Step 3/3: 验证部署...")
    import requests
    try:
        resp = requests.get(f"http://{SERVER_IP}:8000/health", timeout=5)
        if resp.status_code == 200:
            print(f"  ✅ 云端运行正常: {resp.json()}")
            print(f"\n  🌐 仪表盘: http://{SERVER_IP}:8000")
            print(f"  📊 Streamlit: https://riyue248-astock-trading.streamlit.app")
        else:
            print(f"  ⚠️ 云端返回: {resp.status_code}")
    except Exception as e:
        print(f"  ⚠️ 无法连接云端: {e}")
        print(f"  可能服务正在重启，等10秒后刷新 http://{SERVER_IP}:8000")

    print("\n" + "=" * 55)
    print("  ✅ 部署完成")
    print("=" * 55)


if __name__ == "__main__":
    main()

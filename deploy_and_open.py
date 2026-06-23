"""Deploy cache-buster + verify CSS + open browser."""
import paramiko, time, requests, webbrowser

HOST = "139.129.97.101"
USER = "root"
PASSWORD = "Msylbw2002@"
PROJECT = "/opt/astock-trading"

# 1. Deploy to server
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=15)

def run(cmd):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=30)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(out.strip())
    if err.strip(): print("[!]", err.strip())

print("=== Git pull ===")
run(f"cd {PROJECT} && git pull origin master")

print("\n=== Restart service ===")
run("systemctl restart astock-trader")
time.sleep(3)

c.close()

# 2. Verify CSS content on server
print("\n=== Server CSS (color lines) ===")
try:
    r = requests.get(f"http://{HOST}:8000/static/css/paper.css", timeout=15)
    for line in r.text.split("\n"):
        if any(kw in line for kw in ["text-up", "text-down", "--gain", "--loss", "--green", "--red"]):
            print(line.strip())
except Exception as e:
    print(f"Error: {e}")

# 3. Open browser
print("\n=== Opening dashboard ===")
webbrowser.open(f"http://{HOST}:8000")
print("Done! 如果颜色还是不对，请 Ctrl+F5 强制刷新浏览器缓存")

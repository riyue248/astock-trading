"""Verify latest code is actually deployed on server."""
import paramiko

HOST = "139.129.97.101"
USER = "root"
PASSWORD = "Msylbw2002@"
PROJECT = "/opt/astock-trading"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=15)

def run(cmd):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=30)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(out.strip())
    if err.strip(): print("[!]", err.strip())

print("=== Git log (last 3) ===")
run(f"cd {PROJECT} && git log --oneline -3")

print("\n=== MAX_POSITIONS in config ===")
run(f"cd {PROJECT} && grep MAX_POSITIONS config.py")

print("\n=== Color in paper.css ===")
run(f"cd {PROJECT} && grep -E 'text-up|text-down|--gain|--loss' web/static/css/paper.css")

print("\n=== Stash status ===")
run(f"cd {PROJECT} && git stash list")

c.close()

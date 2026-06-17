#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROJECT_DIR="${1:-.}"
JSON_MODE=false
if [ "${1:-}" = "--json" ]; then
  PROJECT_DIR="."
  JSON_MODE=true
elif [ "${2:-}" = "--json" ]; then
  JSON_MODE=true
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'
BOLD='\033[1m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }

ISSUES=0

if [ "$JSON_MODE" = "true" ]; then
  export PROJECT_DIR SCRIPT_DIR
  python3 - <<'PY'
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.environ.get("SCRIPT_DIR", "."))
try:
    from codex_support import count_claude_cli_processes
except Exception:  # pragma: no cover - fall back to inline detection
    count_claude_cli_processes = None


project_dir = os.environ.get("PROJECT_DIR", ".")
issues = []
SYSTEMD_MAIN_PIDS = set()


def run(args, timeout=5):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        return subprocess.CompletedProcess(args, 99, "", str(exc))


def add_issue(issue_code, severity, summary, blocks_completion=False, command_hint="", required_before="completion"):
    issue = {
        "issue_code": issue_code,
        "severity": severity,
        "summary": summary,
        "blocks_completion": bool(blocks_completion),
        "command_hint": command_hint,
        "required_before": required_before,
    }
    issues.append(issue)


def parent_pid(pid):
    result = run(["ps", "-p", str(pid), "-o", "ppid="])
    return result.stdout.strip() if result.returncode == 0 else ""


def collect_systemd_main_pids():
    for svc in ("edu-cloud", "llm-proxy", "edu-cloud-worker"):
        active = run(["systemctl", "is-active", svc]).stdout.strip()
        if active != "active":
            continue
        result = run(["systemctl", "show", svc, "-p", "MainPID", "--value"])
        pid = result.stdout.strip()
        if pid and pid != "0":
            SYSTEMD_MAIN_PIDS.add(pid)


def is_systemd_main_pid(pid):
    return str(pid) in SYSTEMD_MAIN_PIDS


def check_port(port, label):
    if not shutil.which("ss"):
        return
    result = run(["ss", "-tlnp", f"sport = :{port}"])
    holders = [line for line in result.stdout.splitlines() if "LISTEN" in line]
    if not holders:
        if port == 9000:
            add_issue(
                "BACKEND_DOWN",
                "red",
                f"port {port} ({label}) has nobody listening",
                True,
                "systemctl restart edu-cloud",
            )
        return
    if len(holders) > 1:
        add_issue(
            "PORT_CONFLICT",
            "red" if port == 9000 else "yellow",
            f"port {port} ({label}) has {len(holders)} listeners",
            port == 9000,
            f"ss -tlnp 'sport = :{port}'",
            "handoff",
        )

    for holder in holders:
        pid_match = re.search(r"pid=(\d+)", holder)
        bind_addr = holder.split()[3].rsplit(":", 1)[0] if len(holder.split()) >= 4 else ""
        if bind_addr in {"0.0.0.0", "*", "[::]"}:
            add_issue(
                "PORT_DANGER",
                "red",
                f"port {port} ({label}) is bound to {bind_addr}",
                port in {9000, 8080},
                f"bind {label} to 127.0.0.1 or stop the public listener",
            )
        if pid_match and parent_pid(pid_match.group(1)) == "1" and not is_systemd_main_pid(pid_match.group(1)):
            add_issue(
                "GHOST_PROCESS",
                "yellow",
                f"port {port} ({label}) listener PID={pid_match.group(1)} is an orphan",
                False,
                f"inspect or stop PID {pid_match.group(1)}",
                "session_end",
            )


def check_ghost_processes():
    result = run(["ps", "aux"])
    pattern = re.compile(r"vite.*--port|nuxt dev|uvicorn.*--reload|http\.server|arq.*worker")
    for line in result.stdout.splitlines():
        match = pattern.search(line)
        if not match or "grep" in line:
            continue
        parts = line.split(None, 10)
        if len(parts) < 11:
            continue
        pid = parts[1]
        if parent_pid(pid) == "1" and not is_systemd_main_pid(pid):
            cmd = parts[10][:120]
            add_issue(
                "GHOST_PROCESS",
                "yellow",
                f"ghost PID={pid} ({match.group(0)[:40]}): {cmd}",
                False,
                f"inspect or stop PID {pid}",
                "session_end",
            )


def check_dist():
    dist_dir = os.path.join(project_dir, "frontend", "dist")
    index = os.path.join(dist_dir, "index.html")
    version = os.path.join(dist_dir, "version.json")
    if not os.path.isdir(dist_dir):
        add_issue("BUILD_DRIFT", "red", "frontend/dist directory not found", True, "cd frontend && npm run build")
        return
    if not os.path.exists(index):
        add_issue("BUILD_DRIFT", "red", "frontend/dist/index.html not found", True, "cd frontend && npm run build")
    elif not os.access(index, os.R_OK):
        add_issue("BUILD_DRIFT", "red", "frontend/dist/index.html not readable", True, "fix dist permissions")
    if not os.path.exists(version):
        add_issue("BUILD_DRIFT", "yellow", "frontend/dist/version.json missing", True, "cd frontend && npm run build")


def check_systemd():
    for svc in ("edu-cloud", "llm-proxy"):
        state = run(["systemctl", "is-active", svc]).stdout.strip()
        if svc == "edu-cloud" and state != "active":
            uvicorn = run(["pgrep", "-f", "uvicorn.*9000"])
            if uvicorn.returncode == 0:
                add_issue(
                    "SERVICE_BYPASS",
                    "yellow",
                    "edu-cloud.service inactive while uvicorn :9000 is running manually",
                    False,
                    "restart edu-cloud through systemd or document manual debug mode",
                    "session_end",
                )


def _inline_is_claude_cli(command):
    command = (command or "").strip()
    if not command:
        return False
    parts = command.split()
    exe = os.path.basename(parts[0])
    if exe == "claude":
        return True
    if exe in {"node", "nodejs", "bun", "deno"}:
        for token in parts[1:]:
            if token.startswith("-"):
                continue
            base = os.path.basename(token)
            return base == "claude" or (token.endswith("cli.js") and "claude" in token)
    return False


def _inline_count_claude():
    result = run(["pgrep", "-af", "claude"])
    if result.returncode not in (0, 1):
        return 0
    count = 0
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid_text, _, command = stripped.partition(" ")
        if not pid_text.isdigit():
            continue
        if "--no-session-persistence" in command:
            continue
        if _inline_is_claude_cli(command):
            count += 1
    return count


def check_claude_processes():
    # Count only genuine Claude Code CLI sessions: a command that merely
    # references a `.claude` path, the claude-meta repo, or a `yuanshou-claude`
    # wrapper is not an active session and must not inflate the count.
    if count_claude_cli_processes is not None:
        count = count_claude_cli_processes()
    else:
        count = _inline_count_claude()
    if count > 5:
        add_issue(
            "CLAUDE_SESSION_RISK",
            "yellow",
            f"{count} Claude processes active",
            False,
            "close stale Claude sessions",
            "session_end",
        )


def check_db():
    py = os.path.join(project_dir, ".venv", "bin", "python")
    doctor = os.path.join(project_dir, "scripts", "db_doctor.py")
    if not os.path.exists(py) or not os.path.exists(doctor):
        return
    result = run([py, doctor, "--json"], timeout=20)
    if result.returncode != 0:
        add_issue("DB_SCHEMA_DRIFT", "red", "db_doctor failed to run", True, f"{py} scripts/db_doctor.py --strict")
        return
    try:
        data = json.loads(result.stdout)
    except Exception:
        add_issue("DB_SCHEMA_DRIFT", "red", "db_doctor output unreadable", True, f"{py} scripts/db_doctor.py --strict")
        return
    hard = int(data.get("hard", 0) or 0)
    warn = int(data.get("warn", 0) or 0)
    if hard > 0:
        add_issue("DB_SCHEMA_DRIFT", "red", f"ORM-DB drift has {hard} hard failure(s)", True, f"{py} scripts/db_doctor.py --strict")
    elif warn > 0:
        add_issue("DB_SCHEMA_DRIFT", "yellow", f"ORM-DB drift has {warn} warning(s)", False, f"{py} scripts/db_doctor.py --strict")


collect_systemd_main_pids()
for port, label in ((9000, "edu-cloud API"), (8080, "Vite dev server"), (8100, "llm-proxy")):
    check_port(port, label)
check_ghost_processes()
check_dist()
check_systemd()
check_claude_processes()
check_db()

overall = "green"
if any(issue["severity"] == "red" for issue in issues):
    overall = "red"
elif issues:
    overall = "yellow"

payload = {
    "schema": "guardian.doctor.v1",
    "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "overall": overall,
    "issue_count": len(issues),
    "red_count": sum(1 for issue in issues if issue["severity"] == "red"),
    "yellow_count": sum(1 for issue in issues if issue["severity"] == "yellow"),
    "issues": issues,
    "actions": [
        {
            "issue_code": issue["issue_code"],
            "required_before": issue["required_before"],
            "command_hint": issue["command_hint"],
            "blocks_completion": issue["blocks_completion"],
        }
        for issue in issues
        if issue["command_hint"]
    ],
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
PY
  exit 0
fi

echo -e "${BOLD}Truthline Doctor${NC}  $(date '+%H:%M:%S')"
echo ""

# ── 1. Port Check ──
echo -e "${BOLD}[Ports]${NC}"

check_port() {
  local port=$1 label=$2
  local holders count
  holders=$(ss -tlnp "sport = :$port" 2>/dev/null | grep LISTEN || true)
  if [ -z "$holders" ]; then
    warn "port $port ($label): nobody listening"
    return
  fi
  count=$(printf '%s\n' "$holders" | sed '/^$/d' | wc -l)
  if [ "$count" -gt 1 ]; then
    warn "port $port ($label): $count listeners detected (possible conflict)"
    ISSUES=$((ISSUES+1))
  fi

  while IFS= read -r holder; do
    [ -z "$holder" ] && continue
    local pid
    pid=$(echo "$holder" | grep -oP 'pid=\K[0-9]+' | head -1 || true)
    local bind_addr
    bind_addr=$(echo "$holder" | awk '{print $4}' | sed 's/:.*//')

    if [ -z "$pid" ]; then
      warn "port $port ($label): listening but PID unknown (no permission?)"
      continue
    fi

    if [ "$bind_addr" = "0.0.0.0" ] || [ "$bind_addr" = "*" ]; then
      fail "port $port ($label): PID=$pid bound to 0.0.0.0 (PUBLIC EXPOSURE)"
      ISSUES=$((ISSUES+1))
    else
      ok "port $port ($label): PID=$pid on $bind_addr"
    fi

    local ppid
    ppid=$(ps -p "$pid" -o ppid= 2>/dev/null | tr -d ' ' || true)
    systemd_main="no"
    for svc in edu-cloud llm-proxy edu-cloud-worker; do
      svc_pid=$(systemctl show "$svc" -p MainPID --value 2>/dev/null || true)
      if [ -n "$svc_pid" ] && [ "$svc_pid" != "0" ] && [ "$svc_pid" = "$pid" ]; then
        systemd_main="yes"
      fi
    done
    if [ "$ppid" = "1" ] && [ "$systemd_main" != "yes" ]; then
      warn "  PID=$pid is an orphan (PPID=1) — may be a ghost process"
      ISSUES=$((ISSUES+1))
    fi
  done <<< "$holders"
}

check_port 9000 "edu-cloud API"
check_port 8080 "Vite dev server"
check_port 8100 "llm-proxy"
echo ""

# ── 2. Ghost Process Check ──
echo -e "${BOLD}[Ghost Processes]${NC}"

GHOST_PATTERNS='vite.*--port|nuxt dev|uvicorn.*--reload|http\.server|arq.*worker'
GHOST_COUNT=0

while IFS= read -r line; do
  [ -z "$line" ] && continue
  pid=$(echo "$line" | awk '{print $2}')
  ppid=$(ps -p "$pid" -o ppid= 2>/dev/null | tr -d ' ')
  start=$(ps -p "$pid" -o lstart= 2>/dev/null | xargs)
  cmd=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s ",$i; print ""}' | head -c 80)
  match=$(echo "$line" | grep -oE "$GHOST_PATTERNS" | head -1 || true)

  systemd_main="no"
  for svc in edu-cloud llm-proxy edu-cloud-worker; do
    svc_pid=$(systemctl show "$svc" -p MainPID --value 2>/dev/null || true)
    if [ -n "$svc_pid" ] && [ "$svc_pid" != "0" ] && [ "$svc_pid" = "$pid" ]; then
      systemd_main="yes"
    fi
  done

  if [ "$ppid" = "1" ] && [ "$systemd_main" != "yes" ]; then
    warn "ghost PID=$pid (${match:-unknown}, since $start): $cmd"
    GHOST_COUNT=$((GHOST_COUNT+1))
  fi
done < <(ps aux | grep -E "$GHOST_PATTERNS" | grep -v grep || true)

if [ "$GHOST_COUNT" -eq 0 ]; then
  ok "no ghost dev processes found"
else
  fail "$GHOST_COUNT ghost process(es) detected (PPID=1 orphans)"
  ISSUES=$((ISSUES+GHOST_COUNT))
fi

MCP_COUNT=0
MCP_COUNT=$(pgrep -fc 'mcp-server-filesystem' 2>/dev/null) || MCP_COUNT=0
if [ "$MCP_COUNT" -gt 10 ]; then
  warn "MCP filesystem servers: $MCP_COUNT instances (likely Claude session residuals)"
  ISSUES=$((ISSUES+1))
elif [ "$MCP_COUNT" -gt 0 ]; then
  ok "MCP filesystem servers: $MCP_COUNT (normal)"
fi
echo ""

# ── 3. dist/ Permission Check ──
echo -e "${BOLD}[dist/ Permissions]${NC}"
DIST_DIR="$PROJECT_DIR/frontend/dist"
if [ -d "$DIST_DIR" ]; then
  if sudo -n -u www-data test -r "$DIST_DIR/index.html" 2>/dev/null; then
    ok "www-data can read dist/index.html"
  elif [ -r "$DIST_DIR/index.html" ]; then
    ok "dist/index.html readable (www-data check skipped — no sudo)"
  else
    fail "dist/index.html not readable"
    ISSUES=$((ISSUES+1))
  fi

  if [ -f "$DIST_DIR/version.json" ]; then
    ok "dist/version.json exists"
  else
    warn "dist/version.json missing (build without truthline fingerprint)"
    ISSUES=$((ISSUES+1))
  fi
else
  fail "dist/ directory not found"
  ISSUES=$((ISSUES+1))
fi
echo ""

# ── 4. systemd Service Check ──
echo -e "${BOLD}[systemd Services]${NC}"
for svc in edu-cloud llm-proxy edu-cloud-worker; do
  if systemctl is-active --quiet "$svc" 2>/dev/null; then
    ok "$svc.service: active"
  else
    STATE=$(systemctl is-active "$svc" 2>/dev/null || true)
    STATE=${STATE:-not-found}
    warn "$svc.service: $STATE"
    if [ "$svc" = "edu-cloud" ]; then
      if pgrep -f 'uvicorn.*9000' > /dev/null 2>&1; then
        warn "  → but uvicorn :9000 is running manually (systemd bypassed)"
        ISSUES=$((ISSUES+1))
      fi
    fi
  fi
done
echo ""

# ── 5. Claude Session Count ──
echo -e "${BOLD}[Claude Sessions]${NC}"
CLAUDE_COUNT=0
CLAUDE_COUNT=$(python3 -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); from codex_support import count_claude_cli_processes as c; print(c())" 2>/dev/null || echo 0)
if [ "$CLAUDE_COUNT" -le 5 ]; then
  ok "$CLAUDE_COUNT active Claude process(es)"
else
  warn "$CLAUDE_COUNT Claude processes active (risk of multi-session conflict)"
fi
echo ""

# ── 6. DB Schema Drift Check ──
echo -e "${BOLD}[DB Schema]${NC}"
DOCTOR_OUT=$("$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/scripts/db_doctor.py" --json 2>/dev/null || echo '{"hard":-1}')
HARD=$(echo "$DOCTOR_OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('hard',-1))" 2>/dev/null || echo -1)
WARNS=$(echo "$DOCTOR_OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('warn',0))" 2>/dev/null || echo 0)
ORM_T=$(echo "$DOCTOR_OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('orm_tables',0))" 2>/dev/null || echo 0)
DB_T=$(echo "$DOCTOR_OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('db_tables',0))" 2>/dev/null || echo 0)
ALVER=$(echo "$DOCTOR_OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('alembic_version','?'))" 2>/dev/null || echo "?")

if [ "$HARD" = "-1" ]; then
  fail "db_doctor failed to run"
  ISSUES=$((ISSUES+1))
elif [ "$HARD" -gt 0 ]; then
  fail "ORM-DB drift: $HARD HARD failures (will cause 500)"
  ISSUES=$((ISSUES+HARD))
elif [ "$WARNS" -gt 0 ]; then
  warn "ORM-DB: $WARNS warnings (orphan tables/columns)"
else
  ok "ORM-DB aligned: $ORM_T tables, alembic $ALVER"
fi
echo ""

# ── Summary ──
echo -e "${BOLD}[Summary]${NC}"
if [ "$ISSUES" -eq 0 ]; then
  echo -e "  ${GREEN}${BOLD}HEALTHY${NC} — no issues found"
else
  echo -e "  ${YELLOW}${BOLD}$ISSUES issue(s) found${NC}"
fi
echo ""

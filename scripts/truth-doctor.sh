#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIVE_FACT_COLLECTOR="${TRUTH_DOCTOR_LIVE_FACT_COLLECTOR:-$SCRIPT_DIR/governance/live_fact_collector.py}"
LIVE_FACT_PYTHON="${TRUTH_DOCTOR_PYTHON:-python3}"

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
  export PROJECT_DIR SCRIPT_DIR LIVE_FACT_COLLECTOR LIVE_FACT_PYTHON
  python3 - <<'PY'
import json
import os
import re
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.environ.get("SCRIPT_DIR", "."))
try:
    from codex_support import count_claude_cli_processes
except Exception:  # pragma: no cover - fall back to inline detection
    count_claude_cli_processes = None


project_dir = os.environ.get("PROJECT_DIR", ".")
live_fact_collector = os.environ.get("LIVE_FACT_COLLECTOR", "")
live_fact_python = os.environ.get("LIVE_FACT_PYTHON", "python3")
issues = []
LIVE_FACT_SCHEMA = "governance.live_facts.v1"
EXPECTED_PORTS = ((9000, "edu-cloud API"), (8080, "Vite dev server"), (8100, "llm-proxy"))
GHOST_PATTERN = re.compile(r"vite.*--port|nuxt dev|uvicorn.*--reload|http\.server|arq.*worker", re.I)


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


def load_live_facts():
    if not live_fact_collector or not os.path.exists(live_fact_collector):
        add_issue(
            "LIVE_FACT_COLLECTOR_FAILED",
            "red",
            "live_fact_collector.py not found",
            True,
            "scripts/governance/live_fact_collector.py --project-root .",
        )
        return {}
    result = run(
        [live_fact_python, live_fact_collector, "--project-root", project_dir, "--indent", "0"],
        timeout=30,
    )
    if result.returncode != 0:
        add_issue(
            "LIVE_FACT_COLLECTOR_FAILED",
            "red",
            "live_fact_collector failed to run",
            True,
            f"{live_fact_python} scripts/governance/live_fact_collector.py --project-root .",
        )
        return {}
    try:
        data = json.loads(result.stdout)
    except Exception:
        add_issue(
            "LIVE_FACT_COLLECTOR_FAILED",
            "red",
            "live_fact_collector output unreadable",
            True,
            f"{live_fact_python} scripts/governance/live_fact_collector.py --project-root .",
        )
        return {}
    if data.get("schema") != LIVE_FACT_SCHEMA:
        add_issue(
            "LIVE_FACT_COLLECTOR_FAILED",
            "red",
            "live_fact_collector schema mismatch",
            True,
            f"{live_fact_python} scripts/governance/live_fact_collector.py --project-root .",
        )
        return {}
    return data


def _port_listeners(facts, port):
    listeners = facts.get("ports", {}).get("listeners", [])
    result = []
    for listener in listeners:
        try:
            listener_port = int(listener.get("port"))
        except Exception:
            continue
        if listener_port == port:
            result.append(listener)
    return result


def _listener_pid(listener):
    pid = listener.get("pid")
    return "" if pid in (None, "") else str(pid)


def _listener_text(listener):
    return " ".join(
        str(listener.get(key) or "")
        for key in ("process", "command", "raw")
        if listener.get(key)
    )


def _is_public_listener(listener):
    if listener.get("public_bind"):
        return True
    return str(listener.get("bind") or "") in {"0.0.0.0", "*", "[::]", "::"}


def _is_orphan_listener(listener):
    return str(listener.get("ppid") or "") == "1" and not listener.get("service")


def _has_uvicorn_9000(facts):
    for listener in _port_listeners(facts, 9000):
        text = _listener_text(listener).lower()
        if "uvicorn" in text:
            return True
    ghost = facts.get("ghost_processes", {})
    for proc in ghost.get("suspects", []) + ghost.get("processes", []):
        text = " ".join(str(proc.get(key) or "") for key in ("command", "raw")).lower()
        if "uvicorn" in text and "9000" in text:
            return True
    return False


def _dist_version_invalid(dist):
    error = str(dist.get("version_error") or "").lower()
    missing_errors = {"", "missing", "not-found", "not_found", "enoent"}
    return dist.get("status") == "version_invalid" or bool(error and error not in missing_errors)


def _service_active(service):
    active = service.get("active")
    if isinstance(active, bool):
        return active
    if isinstance(active, str) and active.lower() == "active":
        return True
    state = service.get("is_active") or service.get("active_state")
    return str(state or "").lower() == "active"


def check_live_ports(facts):
    for port, label in EXPECTED_PORTS:
        holders = _port_listeners(facts, port)
        if not holders:
            if port == 9000:
                add_issue(
                    "BACKEND_DOWN",
                    "red",
                    f"port {port} ({label}) has nobody listening",
                    True,
                    "systemctl restart edu-cloud",
                )
            continue
        if len(holders) > 1:
            add_issue(
                "PORT_CONFLICT",
                "red" if port == 9000 else "yellow",
                f"port {port} ({label}) has {len(holders)} listeners",
                port == 9000,
                f"inspect port {port} listeners",
                "handoff",
            )
        for holder in holders:
            pid = _listener_pid(holder)
            bind_addr = str(holder.get("bind") or "")
            if _is_public_listener(holder):
                add_issue(
                    "PORT_DANGER",
                    "red",
                    f"port {port} ({label}) is bound to {bind_addr}",
                    port in {9000, 8080},
                    f"bind {label} to 127.0.0.1 or stop the public listener",
                )
            if pid and _is_orphan_listener(holder):
                add_issue(
                    "GHOST_PROCESS",
                    "yellow",
                    f"port {port} ({label}) listener PID={pid} is an orphan",
                    False,
                    f"inspect or stop PID {pid}",
                    "session_end",
                )


def check_live_ghost_processes(facts):
    for proc in facts.get("ghost_processes", {}).get("suspects", []):
        pid = proc.get("pid")
        command = str(proc.get("command") or proc.get("raw") or "")
        match = GHOST_PATTERN.search(command)
        add_issue(
            "GHOST_PROCESS",
            "yellow",
            f"ghost PID={pid} ({(match.group(0) if match else 'unknown')[:40]}): {command[:120]}",
            False,
            f"inspect or stop PID {pid}",
            "session_end",
        )


def check_live_dist(facts):
    dist = facts.get("dist", {})
    status = dist.get("status")
    if status == "missing":
        add_issue("BUILD_DRIFT", "red", "frontend/dist directory not found", True, "cd frontend && npm run build")
        return
    if status == "unreadable" or dist.get("index_readable") is False:
        add_issue("BUILD_DRIFT", "red", "frontend/dist/index.html not readable", True, "fix dist permissions")
        return
    if dist.get("index_exists") is False:
        add_issue("BUILD_DRIFT", "red", "frontend/dist/index.html not found", True, "cd frontend && npm run build")
        return
    if _dist_version_invalid(dist):
        add_issue("BUILD_DRIFT", "yellow", "frontend/dist/version.json invalid", True, "cd frontend && npm run build")
        return
    if dist.get("version") is None:
        add_issue("BUILD_DRIFT", "yellow", "frontend/dist/version.json missing", True, "cd frontend && npm run build")


def check_live_systemd(facts):
    services = facts.get("systemd", {}).get("services", {})
    edu_cloud = services.get("edu-cloud") or services.get("edu-cloud.service") or {}
    if not _service_active(edu_cloud) and _has_uvicorn_9000(facts):
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
    # references a `.claude` path, the claude-meta repo, or a `legacy_governance_claude`
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


live_facts = load_live_facts()
if live_facts:
    check_live_ports(live_facts)
    check_live_ghost_processes(live_facts)
    check_live_dist(live_facts)
    check_live_systemd(live_facts)
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

LIVE_FACT_JSON="$("$LIVE_FACT_PYTHON" "$LIVE_FACT_COLLECTOR" --project-root "$PROJECT_DIR" --indent 0 2>/dev/null || true)"

render_live_fact_phase() {
  local phase=$1 render_output phase_issues
  render_output=$(PHASE="$phase" LIVE_FACT_JSON="$LIVE_FACT_JSON" "$LIVE_FACT_PYTHON" - <<'PY'
import json
import os
import re

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
NC = "\033[0m"
BOLD = "\033[1m"
SCHEMA = "governance.live_facts.v1"
EXPECTED_PORTS = ((9000, "edu-cloud API"), (8080, "Vite dev server"), (8100, "llm-proxy"))
SYSTEMD_SERVICES = ("edu-cloud", "llm-proxy", "edu-cloud-worker")
GHOST_PATTERN = re.compile(r"vite.*--port|nuxt dev|uvicorn.*--reload|http\.server|arq.*worker", re.I)
issues = 0


def ok(msg):
    print(f"  {GREEN}✓{NC} {msg}")


def warn(msg):
    print(f"  {YELLOW}!{NC} {msg}")


def fail(msg):
    print(f"  {RED}✗{NC} {msg}")


def section(name):
    print(f"{BOLD}[{name}]{NC}")


def add_issue(count=1):
    global issues
    issues += count


def parse_facts():
    raw = os.environ.get("LIVE_FACT_JSON", "")
    if not raw.strip():
        return None, "live_fact_collector failed to run"
    try:
        data = json.loads(raw)
    except Exception:
        return None, "live_fact_collector output unreadable"
    if data.get("schema") != SCHEMA:
        return None, "live_fact_collector schema mismatch"
    return data, ""


def port_listeners(facts, port):
    listeners = facts.get("ports", {}).get("listeners", [])
    result = []
    for listener in listeners:
        try:
            listener_port = int(listener.get("port"))
        except Exception:
            continue
        if listener_port == port:
            result.append(listener)
    return result


def listener_pid(listener):
    pid = listener.get("pid")
    return "" if pid in (None, "") else str(pid)


def listener_text(listener):
    return " ".join(
        str(listener.get(key) or "")
        for key in ("process", "command", "raw")
        if listener.get(key)
    )


def is_public_listener(listener):
    if listener.get("public_bind"):
        return True
    return str(listener.get("bind") or "") in {"0.0.0.0", "*", "[::]", "::"}


def is_orphan_listener(listener):
    return str(listener.get("ppid") or "") == "1" and not listener.get("service")


def has_uvicorn_9000(facts):
    for listener in port_listeners(facts, 9000):
        if "uvicorn" in listener_text(listener).lower():
            return True
    ghost = facts.get("ghost_processes", {})
    for proc in ghost.get("suspects", []) + ghost.get("processes", []):
        text = " ".join(str(proc.get(key) or "") for key in ("command", "raw")).lower()
        if "uvicorn" in text and "9000" in text:
            return True
    return False


def dist_version_invalid(dist):
    error = str(dist.get("version_error") or "").lower()
    missing_errors = {"", "missing", "not-found", "not_found", "enoent"}
    return dist.get("status") == "version_invalid" or bool(error and error not in missing_errors)


def service_active(service):
    active = service.get("active")
    if isinstance(active, bool):
        return active
    if isinstance(active, str) and active.lower() == "active":
        return True
    state = service.get("is_active") or service.get("active_state")
    return str(state or "").lower() == "active"


def service_state(service):
    active = service.get("active")
    if isinstance(active, str):
        return active
    state = service.get("is_active") or service.get("active_state")
    if state:
        return str(state)
    if active is True:
        return "active"
    if active is False:
        return "inactive"
    return "not-found"


def render_ports(facts):
    section("Ports")
    for port, label in EXPECTED_PORTS:
        holders = port_listeners(facts, port)
        if not holders:
            warn(f"port {port} ({label}): nobody listening")
            continue
        if len(holders) > 1:
            warn(f"port {port} ({label}): {len(holders)} listeners detected (possible conflict)")
            add_issue()
        for holder in holders:
            pid = listener_pid(holder)
            bind_addr = str(holder.get("bind") or "")
            if not pid:
                warn(f"port {port} ({label}): listening but PID unknown (no permission?)")
                continue
            if is_public_listener(holder):
                fail(f"port {port} ({label}): PID={pid} bound to {bind_addr} (PUBLIC EXPOSURE)")
                add_issue()
            else:
                ok(f"port {port} ({label}): PID={pid} on {bind_addr}")
            if is_orphan_listener(holder):
                warn(f"  PID={pid} is an orphan (PPID=1) — may be a ghost process")
                add_issue()


def render_ghosts(facts):
    section("Ghost Processes")
    suspects = facts.get("ghost_processes", {}).get("suspects", [])
    if not suspects:
        ok("no ghost dev processes found")
        return
    for proc in suspects:
        pid = proc.get("pid")
        command = str(proc.get("command") or proc.get("raw") or "")
        match = GHOST_PATTERN.search(command)
        start = proc.get("start") or "unknown"
        warn(f"ghost PID={pid} ({(match.group(0) if match else 'unknown')[:40]}, since {start}): {command[:80]}")
    fail(f"{len(suspects)} ghost process(es) detected (PPID=1 orphans)")
    add_issue(len(suspects))


def render_dist(facts):
    section("dist/ Permissions")
    dist = facts.get("dist", {})
    status = dist.get("status")
    if status == "missing":
        fail("dist/ directory not found")
        add_issue()
        return
    if status == "unreadable" or dist.get("index_readable") is False:
        fail("dist/index.html not readable")
        add_issue()
    elif dist.get("index_exists") is False:
        fail("dist/index.html not found")
        add_issue()
    else:
        ok("dist/index.html readable")
    if dist_version_invalid(dist):
        warn("dist/version.json invalid (build truthline fingerprint unreadable)")
        add_issue()
    elif dist.get("version") is not None:
        ok("dist/version.json exists")
    else:
        warn("dist/version.json missing (build without truthline fingerprint)")
        add_issue()


def render_systemd(facts):
    section("systemd Services")
    services = facts.get("systemd", {}).get("services", {})
    for svc in SYSTEMD_SERVICES:
        data = services.get(svc) or services.get(f"{svc}.service") or {}
        state = service_state(data)
        if service_active(data):
            ok(f"{svc}.service: active")
        else:
            warn(f"{svc}.service: {state}")
            if svc == "edu-cloud" and has_uvicorn_9000(facts):
                warn("  → but uvicorn :9000 is running manually (systemd bypassed)")
                add_issue()


facts, error = parse_facts()
phase = os.environ.get("PHASE")
if error:
    if phase == "ports_ghost":
        section("Ports")
        fail(error)
        add_issue()
        print()
        section("Ghost Processes")
        warn("live facts unavailable")
    elif phase == "dist_systemd":
        section("dist/ Permissions")
        warn("live facts unavailable")
        print()
        section("systemd Services")
        warn("live facts unavailable")
else:
    if phase == "ports_ghost":
        render_ports(facts)
        print()
        render_ghosts(facts)
    elif phase == "dist_systemd":
        render_dist(facts)
        print()
        render_systemd(facts)
print(f"__TRUTH_DOCTOR_ISSUES__={issues}")
PY
)
  phase_issues=$(printf '%s\n' "$render_output" | sed -n 's/^__TRUTH_DOCTOR_ISSUES__=//p' | tail -1)
  printf '%s\n' "$render_output" | sed '/^__TRUTH_DOCTOR_ISSUES__=/d'
  if [[ "$phase_issues" =~ ^[0-9]+$ ]]; then
    ISSUES=$((ISSUES+phase_issues))
  fi
}

# ── 1-2. Shared live facts: ports and ghost processes ──
render_live_fact_phase ports_ghost

MCP_COUNT=0
MCP_COUNT=$(pgrep -fc 'mcp-server-filesystem' 2>/dev/null) || MCP_COUNT=0
if [ "$MCP_COUNT" -gt 10 ]; then
  warn "MCP filesystem servers: $MCP_COUNT instances (likely Claude session residuals)"
  ISSUES=$((ISSUES+1))
elif [ "$MCP_COUNT" -gt 0 ]; then
  ok "MCP filesystem servers: $MCP_COUNT (normal)"
fi
echo ""

# ── 3-4. Shared live facts: dist and systemd ──
render_live_fact_phase dist_systemd
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

#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-.}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'
BOLD='\033[1m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }

ISSUES=0

echo -e "${BOLD}Truthline Doctor${NC}  $(date '+%H:%M:%S')"
echo ""

# ── 1. Port Check ──
echo -e "${BOLD}[Ports]${NC}"

check_port() {
  local port=$1 label=$2
  local holder
  holder=$(ss -tlnp "sport = :$port" 2>/dev/null | grep LISTEN | head -1 || true)
  if [ -z "$holder" ]; then
    warn "port $port ($label): nobody listening"
    return
  fi

  local pid
  pid=$(echo "$holder" | grep -oP 'pid=\K[0-9]+' | head -1 || true)
  local bind_addr
  bind_addr=$(echo "$holder" | awk '{print $4}' | sed 's/:.*//')

  if [ -z "$pid" ]; then
    warn "port $port ($label): listening but PID unknown (no permission?)"
    return
  fi

  if [ "$bind_addr" = "0.0.0.0" ] || [ "$bind_addr" = "*" ]; then
    fail "port $port ($label): PID=$pid bound to 0.0.0.0 (PUBLIC EXPOSURE)"
    ISSUES=$((ISSUES+1))
  else
    ok "port $port ($label): PID=$pid on $bind_addr"
  fi

  local ppid
  ppid=$(ps -p "$pid" -o ppid= 2>/dev/null | tr -d ' ' || true)
  if [ "$ppid" = "1" ]; then
    warn "  PID=$pid is an orphan (PPID=1) — may be a ghost process"
    ISSUES=$((ISSUES+1))
  fi
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

  if [ "$ppid" = "1" ]; then
    warn "ghost PID=$pid (since $start): $cmd"
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
for svc in edu-cloud llm-proxy; do
  if systemctl is-active --quiet "$svc" 2>/dev/null; then
    ok "$svc.service: active"
  else
    STATE=$(systemctl is-active "$svc" 2>/dev/null || echo "not-found")
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
CLAUDE_COUNT=$(pgrep -fc 'claude' 2>/dev/null) || CLAUDE_COUNT=0
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

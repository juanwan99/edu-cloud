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
  holder=$(ss -tlnp "sport = :$port" 2>/dev/null | grep LISTEN | head -1)
  if [ -z "$holder" ]; then
    warn "port $port ($label): nobody listening"
    return
  fi

  local pid
  pid=$(echo "$holder" | grep -oP 'pid=\K[0-9]+' | head -1)
  local bind_addr
  bind_addr=$(echo "$holder" | awk '{print $4}' | sed 's/:.*//')

  if [ "$bind_addr" = "0.0.0.0" ] || [ "$bind_addr" = "*" ]; then
    fail "port $port ($label): PID=$pid bound to 0.0.0.0 (PUBLIC EXPOSURE)"
    ISSUES=$((ISSUES+1))
  else
    ok "port $port ($label): PID=$pid on $bind_addr"
  fi

  local ppid
  ppid=$(ps -p "$pid" -o ppid= 2>/dev/null | tr -d ' ')
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

MCP_COUNT=$(pgrep -fc 'mcp-server-filesystem' 2>/dev/null || echo 0)
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
CLAUDE_COUNT=$(pgrep -fc 'claude' 2>/dev/null || echo 0)
if [ "$CLAUDE_COUNT" -le 5 ]; then
  ok "$CLAUDE_COUNT active Claude process(es)"
else
  warn "$CLAUDE_COUNT Claude processes active (risk of multi-session conflict)"
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

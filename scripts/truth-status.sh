#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-.}"
FRONTEND_DIR="$PROJECT_DIR/frontend"
DIST_DIR="$FRONTEND_DIR/dist"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${CYAN}·${NC} $1"; }

# Path prefixes whose change between a deployed hash and HEAD is a real runtime
# drift (kept in sync with codex_support.RUNTIME_DRIFT_PREFIXES). Anything else
# is documentation / governance only and a deployed artifact that merely trails
# HEAD by such commits is still functionally current.
RUNTIME_PREFIXES=(
  "src/"
  "pyproject.toml"
  "uv.lock"
  "alembic.ini"
  "alembic/"
  "frontend/src/"
  "frontend/public/"
  "frontend/index.html"
  "frontend/package.json"
  "frontend/package-lock.json"
  "frontend/vite.config"
  "frontend/vitest.config"
  "deploy/"
  "scripts/run-arq-worker"
)

# classify_drift <deployed_hash> <head_hash>
# Echoes "runtime", "docs_only", or "unknown".
classify_drift() {
  local base="$1" head="$2"
  [ "$base" = "$head" ] && { echo "docs_only"; return; }
  git -C "$PROJECT_DIR" cat-file -e "${base}^{commit}" 2>/dev/null || { echo "unknown"; return; }
  git -C "$PROJECT_DIR" cat-file -e "${head}^{commit}" 2>/dev/null || { echo "unknown"; return; }
  local changed
  changed=$(git -C "$PROJECT_DIR" diff --name-only "${base}..${head}" 2>/dev/null) || { echo "unknown"; return; }
  local path pre
  while IFS= read -r path; do
    [ -z "$path" ] && continue
    for pre in "${RUNTIME_PREFIXES[@]}"; do
      case "$path" in
        "$pre"*) echo "runtime"; return ;;
      esac
    done
  done <<< "$changed"
  echo "docs_only"
}

BROKEN_AT=""
DOCS_ONLY_DRIFT=false

echo -e "${BOLD}Truthline Status${NC}  $(date '+%H:%M:%S')"
echo ""

# ── 1. Source ──
echo -e "${BOLD}[Source]${NC}"
GIT_HASH=$(git -C "$PROJECT_DIR" rev-parse --short HEAD 2>/dev/null || echo "unknown")
info "git HEAD: $GIT_HASH"

if git -C "$PROJECT_DIR" diff --quiet HEAD -- frontend/src/ frontend/vite.config.js frontend/package.json frontend/index.html 2>/dev/null; then
  FRONTEND_DIRTY=false
  ok "frontend/ build inputs clean (matches HEAD)"
else
  FRONTEND_DIRTY=true
  CHANGED=$(git -C "$PROJECT_DIR" diff --name-only HEAD -- frontend/src/ frontend/vite.config.js frontend/package.json frontend/index.html 2>/dev/null | wc -l)
  warn "frontend/ build inputs dirty ($CHANGED files changed since HEAD)"
fi

if git -C "$PROJECT_DIR" diff --quiet HEAD -- src/ 2>/dev/null; then
  ok "src/ (backend) clean"
else
  BACKEND_CHANGED=$(git -C "$PROJECT_DIR" diff --name-only HEAD -- src/ 2>/dev/null | wc -l)
  warn "src/ (backend) dirty ($BACKEND_CHANGED files — uvicorn --reload may serve uncommitted code)"
  [ -z "$BROKEN_AT" ] && BROKEN_AT="SOURCE (backend has uncommitted changes)"
fi
echo ""

# ── 2. Build ──
echo -e "${BOLD}[Build]${NC}"
VERSION_JSON="$DIST_DIR/version.json"
if [ -f "$VERSION_JSON" ]; then
  BUILD_HASH=$(python3 -c "import json; print(json.load(open('$VERSION_JSON'))['git_hash'])" 2>/dev/null || echo "unknown")
  BUILD_TIME=$(python3 -c "import json; print(json.load(open('$VERSION_JSON'))['build_time'])" 2>/dev/null || echo "unknown")
  BUILD_DIRTY=$(python3 -c "import json; print(json.load(open('$VERSION_JSON')).get('source_dirty','unknown'))" 2>/dev/null || echo "unknown")
  info "build git_hash: $BUILD_HASH"
  info "build time: $BUILD_TIME"

  if [ "$BUILD_DIRTY" = "True" ] || [ "$BUILD_DIRTY" = "true" ]; then
    warn "dist/ was built from dirty source (source_dirty=true in version.json)"
    [ -z "$BROKEN_AT" ] && BROKEN_AT="SOURCE → BUILD (built from dirty source)"
  elif [ "$BUILD_HASH" = "$GIT_HASH" ] && [ "$FRONTEND_DIRTY" = "false" ]; then
    ok "dist/ matches current source"
  elif [ "$BUILD_HASH" != "$GIT_HASH" ]; then
    BUILD_DRIFT_KIND=$(classify_drift "$BUILD_HASH" "$GIT_HASH")
    if [ "$BUILD_DRIFT_KIND" = "docs_only" ]; then
      warn "dist/ built from $BUILD_HASH; HEAD $GIT_HASH adds docs/governance-only commits (no build input changed)"
      DOCS_ONLY_DRIFT=true
    else
      fail "dist/ built from $BUILD_HASH, source is $GIT_HASH"
      [ -z "$BROKEN_AT" ] && BROKEN_AT="SOURCE → BUILD (git hash mismatch)"
    fi
  elif [ "$FRONTEND_DIRTY" = "true" ]; then
    fail "dist/ built from clean $BUILD_HASH, but frontend/ has uncommitted changes"
    [ -z "$BROKEN_AT" ] && BROKEN_AT="SOURCE → BUILD (uncommitted frontend changes)"
  fi
else
  fail "dist/version.json not found (build has no fingerprint)"
  [ -z "$BROKEN_AT" ] && BROKEN_AT="SOURCE → BUILD (no version.json — run: cd frontend && npm run build)"
fi
echo ""

# ── 3. Nginx / dist ──
echo -e "${BOLD}[Nginx]${NC}"
if [ -f "$DIST_DIR/index.html" ]; then
  DIST_MTIME=$(stat -c '%Y' "$DIST_DIR/index.html" 2>/dev/null || echo "0")
  DIST_READABLE=$(test -r "$DIST_DIR/index.html" && echo "yes" || echo "no")
  info "dist/index.html exists, mtime=$(date -d @"$DIST_MTIME" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "$DIST_MTIME")"

  if [ "$DIST_READABLE" = "yes" ]; then
    ok "dist/ readable"
  else
    fail "dist/ not readable by current user"
    [ -z "$BROKEN_AT" ] && BROKEN_AT="BUILD → NGINX (permission denied)"
  fi

  CURL_STATUS=$(curl -so /dev/null -w '%{http_code}' https://mcu.asia/ 2>/dev/null || echo "000")
  if [ "$CURL_STATUS" = "200" ]; then
    ok "https://mcu.asia/ returns 200"
  else
    fail "https://mcu.asia/ returns $CURL_STATUS"
    [ -z "$BROKEN_AT" ] && BROKEN_AT="NGINX → BROWSER (HTTP $CURL_STATUS)"
  fi

  REMOTE_HASH=$(curl -sf https://mcu.asia/version.json 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['git_hash'])" 2>/dev/null || echo "unreachable")
  if [ "$REMOTE_HASH" != "unreachable" ]; then
    info "nginx serves version.json: git_hash=$REMOTE_HASH"
    if [ "$REMOTE_HASH" = "$GIT_HASH" ] && [ "$FRONTEND_DIRTY" = "false" ]; then
      ok "nginx version matches source"
    elif [ "$REMOTE_HASH" != "$GIT_HASH" ]; then
      NGINX_DRIFT_KIND=$(classify_drift "$REMOTE_HASH" "$GIT_HASH")
      if [ "$NGINX_DRIFT_KIND" = "docs_only" ]; then
        warn "nginx serves $REMOTE_HASH; HEAD $GIT_HASH adds docs/governance-only commits (served bundle functionally current)"
        DOCS_ONLY_DRIFT=true
      else
        fail "nginx serves build $REMOTE_HASH, source is $GIT_HASH"
        [ -z "$BROKEN_AT" ] && BROKEN_AT="BUILD → NGINX (stale dist on nginx)"
      fi
    fi
  else
    warn "version.json not yet accessible via nginx (run build first)"
  fi
else
  fail "dist/index.html not found"
  [ -z "$BROKEN_AT" ] && BROKEN_AT="BUILD → NGINX (no dist/)"
fi
echo ""

# ── 4. Backend ──
echo -e "${BOLD}[Backend]${NC}"
BACKEND_JSON=$(curl -sf http://127.0.0.1:9000/api/v1/version 2>/dev/null || echo "")
if [ -n "$BACKEND_JSON" ]; then
  BE_HASH=$(echo "$BACKEND_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('git_hash','unknown'))" 2>/dev/null || echo "unknown")
  BE_BOOT=$(echo "$BACKEND_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('boot_time','unknown'))" 2>/dev/null || echo "unknown")
  BE_PID=$(echo "$BACKEND_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('pid','unknown'))" 2>/dev/null || echo "unknown")
  info "backend pid=$BE_PID boot=$BE_BOOT git=$BE_HASH"

  if [ "$BE_HASH" = "$GIT_HASH" ]; then
    ok "backend git hash matches source"
  elif [ "$BE_HASH" = "unknown" ]; then
    warn "backend /api/v1/version missing git_hash (upgrade needed)"
  else
    BACKEND_DRIFT_KIND=$(classify_drift "$BE_HASH" "$GIT_HASH")
    if [ "$BACKEND_DRIFT_KIND" = "docs_only" ]; then
      warn "backend running $BE_HASH; HEAD $GIT_HASH adds docs/governance-only commits (running backend functionally current)"
      DOCS_ONLY_DRIFT=true
    else
      fail "backend running $BE_HASH, source is $GIT_HASH"
      [ -z "$BROKEN_AT" ] && BROKEN_AT="SOURCE → BACKEND (stale uvicorn, restart needed)"
    fi
  fi
else
  fail "backend unreachable at :9000"
  [ -z "$BROKEN_AT" ] && BROKEN_AT="BACKEND (not running on port 9000)"
fi
echo ""

# -- 5. Worker --
echo -e "${BOLD}[Worker]${NC}"
WORKER_STATE_JSON="$PROJECT_DIR/logs/worker-runtime.json"
WORKER_UNIT_EXISTS=false
WORKER_UNIT_SKIP_REASON="not installed"
if systemctl list-unit-files edu-cloud-worker.service --no-legend 2>/dev/null | grep -q '^edu-cloud-worker\.service'; then
  WORKER_UNIT_EXISTS=true
  WORKER_UNIT_SKIP_REASON=""
  WORKER_UNIT_PROJECT=$(systemctl show edu-cloud-worker -p WorkingDirectory --value 2>/dev/null || echo "")
  if [ -n "$WORKER_UNIT_PROJECT" ]; then
    RESOLVED_PROJECT=$(cd "$PROJECT_DIR" 2>/dev/null && pwd -P || echo "$PROJECT_DIR")
    RESOLVED_WORKER_PROJECT=$(cd "$WORKER_UNIT_PROJECT" 2>/dev/null && pwd -P || echo "$WORKER_UNIT_PROJECT")
    if [ "$RESOLVED_WORKER_PROJECT" != "$RESOLVED_PROJECT" ]; then
      WORKER_UNIT_EXISTS=false
      WORKER_UNIT_SKIP_REASON="unit belongs to $RESOLVED_WORKER_PROJECT"
    fi
  fi
fi

if [ "$WORKER_UNIT_EXISTS" = "true" ]; then
  WORKER_ACTIVE=$(systemctl is-active edu-cloud-worker 2>/dev/null || true)
  WORKER_PID=$(systemctl show edu-cloud-worker -p MainPID --value 2>/dev/null || echo "0")
  if [ "$WORKER_ACTIVE" != "active" ] || [ -z "$WORKER_PID" ] || [ "$WORKER_PID" = "0" ]; then
    fail "edu-cloud-worker.service is $WORKER_ACTIVE"
    [ -z "$BROKEN_AT" ] && BROKEN_AT="WORKER (service not active)"
  elif [ ! -f "$WORKER_STATE_JSON" ]; then
    fail "worker runtime fingerprint missing: $WORKER_STATE_JSON"
    [ -z "$BROKEN_AT" ] && BROKEN_AT="WORKER (missing runtime fingerprint)"
  else
    WORKER_HASH=$(python3 -c "import json; print(json.load(open('$WORKER_STATE_JSON')).get('git_hash','unknown'))" 2>/dev/null || echo "unreadable")
    WORKER_BOOT=$(python3 -c "import json; print(json.load(open('$WORKER_STATE_JSON')).get('boot_time','unknown'))" 2>/dev/null || echo "unknown")
    WORKER_RECORDED=$(python3 -c "import json; print(json.load(open('$WORKER_STATE_JSON')).get('recorded_at','unknown'))" 2>/dev/null || echo "unknown")
    WORKER_STATE_PID=$(python3 -c "import json; print(json.load(open('$WORKER_STATE_JSON')).get('pid','unknown'))" 2>/dev/null || echo "unknown")
    WORKER_DIRTY=$(python3 -c "import json; print(json.load(open('$WORKER_STATE_JSON')).get('source_dirty','unknown'))" 2>/dev/null || echo "unknown")
    info "worker pid=$WORKER_STATE_PID service_pid=$WORKER_PID boot=$WORKER_BOOT recorded=$WORKER_RECORDED git=$WORKER_HASH"

    if [ "$WORKER_STATE_PID" != "$WORKER_PID" ]; then
      fail "worker fingerprint PID=$WORKER_STATE_PID does not match service PID=$WORKER_PID"
      [ -z "$BROKEN_AT" ] && BROKEN_AT="WORKER (stale runtime fingerprint)"
    elif [ "$WORKER_DIRTY" = "True" ] || [ "$WORKER_DIRTY" = "true" ]; then
      fail "worker runtime was fingerprinted from dirty source"
      [ -z "$BROKEN_AT" ] && BROKEN_AT="WORKER (source_dirty=true)"
    elif [ "$WORKER_HASH" = "$GIT_HASH" ]; then
      ok "worker git hash matches source"
    elif [ "$WORKER_HASH" = "unknown" ] || [ "$WORKER_HASH" = "unreadable" ]; then
      fail "worker runtime fingerprint missing git_hash"
      [ -z "$BROKEN_AT" ] && BROKEN_AT="WORKER (missing git_hash)"
    else
      WORKER_DRIFT_KIND=$(classify_drift "$WORKER_HASH" "$GIT_HASH")
      if [ "$WORKER_DRIFT_KIND" = "docs_only" ]; then
        warn "worker running $WORKER_HASH; HEAD $GIT_HASH adds docs/governance-only commits (running worker functionally current)"
        DOCS_ONLY_DRIFT=true
      else
        fail "worker running $WORKER_HASH, source is $GIT_HASH"
        [ -z "$BROKEN_AT" ] && BROKEN_AT="SOURCE -> WORKER (stale worker, restart needed)"
      fi
    fi
  fi
else
  warn "edu-cloud-worker.service skipped ($WORKER_UNIT_SKIP_REASON); skipping worker runtime fingerprint check"
fi
echo ""

# ── Diagnosis ──
echo -e "${BOLD}[Diagnosis]${NC}"
if [ -n "$BROKEN_AT" ]; then
  echo -e "  ${RED}${BOLD}BROKEN AT: $BROKEN_AT${NC}"
  exit 1
elif [ "$DOCS_ONLY_DRIFT" = "true" ]; then
  echo -e "  ${GREEN}${BOLD}FUNCTIONALLY ALIGNED${NC} — deployed runtime trails HEAD only by docs/governance/test/observability commits"
  exit 0
else
  echo -e "  ${GREEN}${BOLD}ALL ALIGNED${NC} - source, build, nginx, backend, worker versions match"
  exit 0
fi

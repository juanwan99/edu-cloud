# Truthline P0: 真相可见化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把"感觉 AI 改的和我看到的不一样"变成"明确断在源码→build→dist→nginx 的第几步"

**Architecture:** 在 vite build 时注入版本指纹（git hash + build time + source hash），生成 `dist/version.json`；后端 `/api/v1/version` 扩展返回 git 状态；`truth` CLI 对比全链路每一步的版本信息输出一行诊断；`truth doctor` 检查幽灵进程/端口/权限。全部是只读诊断，不改工作流。

**Tech Stack:** Vite (build plugin), Python FastAPI, Bash CLI, subprocess (git/ss/ps)

**Design doc:** `~/docs/truthline-design-consensus.md`

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `frontend/vite.config.js` | 注入 `__BUILD_TIME__` / `__GIT_HASH__` / `__SOURCE_DIRTY__` define + 生成 `dist/version.json` |
| Modify | `frontend/src/main.js` | 启动时 console.log 版本指纹 |
| Modify | `src/edu_cloud/api/app.py` | `/api/v1/version` 扩展返回 git_hash / source_dirty / pid |
| Modify | `tests/test_api/test_health.py` | 扩展 test_version 断言新字段 |
| Create | `frontend/src/__tests__/version-fingerprint.test.js` | 验证版本常量已注入 |
| Create | `scripts/truth` | CLI 入口脚本（bash），子命令分发 |
| Create | `scripts/truth-status.sh` | `truth status` 实现 |
| Create | `scripts/truth-doctor.sh` | `truth doctor` 实现 |

---

### Task 1: 前端 Build 版本指纹注入

**Files:**
- Modify: `frontend/vite.config.js`
- Test: `frontend/src/__tests__/version-fingerprint.test.js`

- [ ] **Step 1: 写失败测试 — 验证版本常量存在**

```js
// frontend/src/__tests__/version-fingerprint.test.js
import { describe, it, expect } from 'vitest'

describe('version fingerprint', () => {
  it('BUILD_TIME is defined and looks like ISO timestamp', () => {
    expect(typeof __BUILD_TIME__).toBe('string')
    expect(__BUILD_TIME__).toMatch(/^\d{4}-\d{2}-\d{2}T/)
  })

  it('GIT_HASH is defined and is 7+ char hex', () => {
    expect(typeof __GIT_HASH__).toBe('string')
    expect(__GIT_HASH__).toMatch(/^[0-9a-f]{7,}$/)
  })

  it('SOURCE_DIRTY is a boolean string', () => {
    expect(typeof __SOURCE_DIRTY__).toBe('string')
    expect(['true', 'false']).toContain(__SOURCE_DIRTY__)
  })

  it('BUILD_ID is defined and starts with build-', () => {
    expect(typeof __BUILD_ID__).toBe('string')
    expect(__BUILD_ID__).toMatch(/^build-\d+$/)
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npx vitest run src/__tests__/version-fingerprint.test.js`
Expected: FAIL — `__BUILD_TIME__ is not defined`

- [ ] **Step 3: 在 vite.config.js 中添加 define 和 version.json 生成**

在 `frontend/vite.config.js` 顶部的 `import { execSync }` 之后添加 helper 函数，并修改 `defineConfig`：

```js
function getBuildMeta() {
  const gitHash = execSync('git rev-parse --short HEAD', { encoding: 'utf-8' }).trim()
  const isDirty = (() => {
    try { execSync('git diff --quiet -- src/', { cwd: fileURLToPath(new URL('.', import.meta.url)) }); return false }
    catch { return true }
  })()
  const buildTime = new Date().toISOString()
  return { gitHash, isDirty, buildTime }
}

function generateVersionJson() {
  return {
    name: 'generate-version-json',
    closeBundle() {
      const fs = await import('node:fs')  // 不能用 top-level await，改用同步
      const { gitHash, isDirty, buildTime } = getBuildMeta()
      const versionData = {
        build_time: buildTime,
        git_hash: gitHash,
        source_dirty: isDirty,
        build_id: `build-${buildTime.replace(/[:.]/g, '-').slice(0, 19)}`
      }
      const fs2 = require !== undefined ? require('node:fs') : null // ESM 兼容
      // 实际使用 writeFileSync
      const { writeFileSync } = await import('node:fs')
      writeFileSync(
        fileURLToPath(new URL('./dist/version.json', import.meta.url)),
        JSON.stringify(versionData, null, 2) + '\n'
      )
    }
  }
}
```

等等——vite.config.js 是 ESM，`closeBundle` 不是 async。用同步写法：

```js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { execSync } from 'node:child_process'
import { writeFileSync } from 'node:fs'

function getGitHash() {
  try { return execSync('git rev-parse --short HEAD', { encoding: 'utf-8' }).trim() }
  catch { return 'unknown' }
}

function isSourceDirty() {
  try {
    execSync('git diff --quiet -- src/ vite.config.js package.json index.html', { cwd: fileURLToPath(new URL('.', import.meta.url)) })
    return false
  } catch { return true }
}

function fixDistPermissions() {
  return {
    name: 'fix-dist-permissions',
    closeBundle() {
      try {
        execSync('chmod -R o+rX dist/', { cwd: fileURLToPath(new URL('.', import.meta.url)) })
      } catch {}
    },
  }
}

function generateVersionJson() {
  return {
    name: 'generate-version-json',
    closeBundle() {
      const distDir = fileURLToPath(new URL('./dist', import.meta.url))
      const data = {
        build_time: new Date().toISOString(),
        git_hash: getGitHash(),
        source_dirty: isSourceDirty(),
        build_id: `build-${Date.now()}`
      }
      writeFileSync(`${distDir}/version.json`, JSON.stringify(data, null, 2) + '\n')
    }
  }
}

export default defineConfig({
  plugins: [vue(), generateVersionJson(), fixDistPermissions()],
  define: {
    __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
    __GIT_HASH__: JSON.stringify(getGitHash()),
    __SOURCE_DIRTY__: JSON.stringify(String(isSourceDirty())),
    __BUILD_ID__: JSON.stringify(`build-${Date.now()}`),
  },
  // ... rest unchanged
})
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npx vitest run src/__tests__/version-fingerprint.test.js`
Expected: PASS (3 tests)

- [ ] **Step 5: 运行全量前端测试确认无回归**

Run: `cd frontend && npx vitest run`
Expected: 2404+ tests passed, 0 failed

- [ ] **Step 6: Commit**

```bash
git add frontend/vite.config.js frontend/src/__tests__/version-fingerprint.test.js
git commit -m "feat(truthline): inject build fingerprint via vite define + generate dist/version.json"
```

---

### Task 2: 前端 main.js 启动时输出版本指纹

**Files:**
- Modify: `frontend/src/main.js`

- [ ] **Step 1: 在 main.js mount 之前添加 console.log**

在 `app.mount('#app')` 之前插入：

```js
if (typeof __BUILD_TIME__ !== 'undefined') {
  console.log(
    `[edu-cloud] id=${__BUILD_ID__} build=${__GIT_HASH__} time=${__BUILD_TIME__} dirty=${__SOURCE_DIRTY__}`
  )
}
```

- [ ] **Step 2: 运行前端测试确认无回归**

Run: `cd frontend && npx vitest run`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/main.js
git commit -m "feat(truthline): log build fingerprint on app startup"
```

---

### Task 3: 后端 /api/v1/version 扩展

**Files:**
- Modify: `src/edu_cloud/api/app.py:334-336`
- Modify: `tests/test_api/test_health.py:12-19`

- [ ] **Step 1: 写失败测试 — 断言新字段**

修改 `tests/test_api/test_health.py` 中的 `test_version`：

```python
@pytest.mark.asyncio
async def test_version(client):
    resp = await client.get("/api/v1/version")
    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data
    assert "boot_time" in data
    assert "git_hash" in data
    assert "source_dirty" in data
    assert isinstance(data["source_dirty"], bool)
    assert "pid" in data
    assert isinstance(data["pid"], int)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api/test_health.py::test_version -v`
Expected: FAIL — `KeyError: 'git_hash'`

- [ ] **Step 3: 扩展 app.py 中的 version 端点**

在 `app.py` 顶部 `_BOOT_TIME` 定义之后，添加 git 信息获取：

```python
import os
import subprocess

def _get_git_hash():
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'], text=True
        ).strip()
    except Exception:
        return 'unknown'

def _get_repo_root():
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', '--show-toplevel'], text=True
        ).strip()
    except Exception:
        return os.path.dirname(os.path.abspath(__file__))

def _is_source_dirty():
    try:
        subprocess.check_call(
            ['git', 'diff', '--quiet', '--', 'src/'],
            cwd=_get_repo_root()
        )
        return False
    except Exception:
        return True

_GIT_HASH = _get_git_hash()
_SOURCE_DIRTY = _is_source_dirty()
```

然后替换 version 端点（`app.py:334-336`）：

```python
@app.get("/api/v1/version")
async def version():
    return {
        "version": "0.1.0",
        "boot_time": _BOOT_TIME,
        "git_hash": _GIT_HASH,
        "source_dirty": _SOURCE_DIRTY,
        "pid": os.getpid(),
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_api/test_health.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: 运行后端全量测试确认无回归**

Run: `.venv/bin/python -m pytest --tb=short -q 2>&1 | tail -5`
Expected: 2199+ passed（既有 21 failed 为历史债，不新增）

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/api/app.py tests/test_api/test_health.py
git commit -m "feat(truthline): extend /api/v1/version with git_hash, source_dirty, pid"
```

---

### Task 4: truth CLI 入口脚本

**Files:**
- Create: `scripts/truth`

- [ ] **Step 1: 创建 CLI 入口脚本**

```bash
#!/usr/bin/env bash
# truth — Truthline CLI: AI 开发环境真相对齐系统
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
  cat <<'EOF'
truth — Truthline: AI 开发环境真相对齐系统

Usage:
  truth status    显示当前真相链状态（源码→build→dist→nginx→后端）
  truth doctor    诊断幽灵进程/端口占用/dist权限/systemd状态
  truth help      显示此帮助

EOF
}

case "${1:-help}" in
  status)  exec "$SCRIPT_DIR/truth-status.sh" "$PROJECT_DIR" ;;
  doctor)  exec "$SCRIPT_DIR/truth-doctor.sh" "$PROJECT_DIR" ;;
  help|-h|--help) usage ;;
  *)       echo "Unknown command: $1"; usage; exit 1 ;;
esac
```

- [ ] **Step 2: 设置可执行权限**

```bash
chmod +x scripts/truth
```

- [ ] **Step 3: Commit**

```bash
git add scripts/truth
git commit -m "feat(truthline): add truth CLI entry point"
```

---

### Task 5: truth status — 真相链诊断

**Files:**
- Create: `scripts/truth-status.sh`

- [ ] **Step 1: 实现 truth-status.sh**

```bash
#!/usr/bin/env bash
# truth status — 对比源码/build/dist/后端每一步的版本指纹
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

BROKEN_AT=""

echo -e "${BOLD}Truthline Status${NC}  $(date '+%H:%M:%S')"
echo ""

# ── 1. Source ──
echo -e "${BOLD}[Source]${NC}"
GIT_HASH=$(git -C "$PROJECT_DIR" rev-parse --short HEAD 2>/dev/null || echo "unknown")
info "git HEAD: $GIT_HASH"

if git -C "$PROJECT_DIR" diff --quiet -- frontend/src/ frontend/vite.config.js frontend/package.json frontend/index.html 2>/dev/null; then
  FRONTEND_DIRTY=false
  ok "frontend/ build inputs clean (matches HEAD)"
else
  FRONTEND_DIRTY=true
  CHANGED=$(git -C "$PROJECT_DIR" diff --name-only -- frontend/src/ frontend/vite.config.js frontend/package.json frontend/index.html 2>/dev/null | wc -l)
  warn "frontend/ build inputs dirty ($CHANGED files changed since HEAD)"
fi

if git -C "$PROJECT_DIR" diff --quiet -- src/ 2>/dev/null; then
  ok "src/ (backend) clean"
else
  BACKEND_CHANGED=$(git -C "$PROJECT_DIR" diff --name-only -- src/ 2>/dev/null | wc -l)
  warn "src/ (backend) dirty ($BACKEND_CHANGED files)"
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

  if [ "$BUILD_HASH" = "$GIT_HASH" ] && [ "$FRONTEND_DIRTY" = "false" ]; then
    ok "dist/ matches current source"
  elif [ "$BUILD_HASH" != "$GIT_HASH" ]; then
    fail "dist/ built from $BUILD_HASH, source is $GIT_HASH"
    [ -z "$BROKEN_AT" ] && BROKEN_AT="SOURCE → BUILD (git hash mismatch)"
  elif [ "$FRONTEND_DIRTY" = "true" ]; then
    fail "dist/ built from clean $BUILD_HASH, but frontend/src/ has uncommitted changes"
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
  info "dist/index.html exists, mtime=$(date -d @$DIST_MTIME '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo $DIST_MTIME)"

  if [ "$DIST_READABLE" = "yes" ]; then
    ok "dist/ readable"
  else
    fail "dist/ not readable by current user"
    [ -z "$BROKEN_AT" ] && BROKEN_AT="BUILD → NGINX (permission denied)"
  fi

  # 检查 nginx 能否访问
  CURL_STATUS=$(curl -so /dev/null -w '%{http_code}' https://mcu.asia/ 2>/dev/null || echo "000")
  if [ "$CURL_STATUS" = "200" ]; then
    ok "https://mcu.asia/ returns 200"
  else
    fail "https://mcu.asia/ returns $CURL_STATUS"
    [ -z "$BROKEN_AT" ] && BROKEN_AT="NGINX → BROWSER (HTTP $CURL_STATUS)"
  fi

  # 检查 version.json 是否可通过 nginx 访问
  REMOTE_HASH=$(curl -sf https://mcu.asia/version.json 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['git_hash'])" 2>/dev/null || echo "unreachable")
  if [ "$REMOTE_HASH" != "unreachable" ]; then
    info "nginx serves version.json: git_hash=$REMOTE_HASH"
    if [ "$REMOTE_HASH" = "$GIT_HASH" ] && [ "$FRONTEND_DIRTY" = "false" ]; then
      ok "nginx version matches source"
    elif [ "$REMOTE_HASH" != "$GIT_HASH" ]; then
      fail "nginx serves build $REMOTE_HASH, source is $GIT_HASH"
      [ -z "$BROKEN_AT" ] && BROKEN_AT="BUILD → NGINX (stale dist on nginx)"
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
    fail "backend running $BE_HASH, source is $GIT_HASH"
    [ -z "$BROKEN_AT" ] && BROKEN_AT="SOURCE → BACKEND (stale uvicorn, restart needed)"
  fi
else
  fail "backend unreachable at :9000"
  [ -z "$BROKEN_AT" ] && BROKEN_AT="BACKEND (not running on port 9000)"
fi
echo ""

# ── Diagnosis ──
echo -e "${BOLD}[Diagnosis]${NC}"
if [ -z "$BROKEN_AT" ]; then
  echo -e "  ${GREEN}${BOLD}ALL ALIGNED${NC} — source, build, nginx, backend versions match"
else
  echo -e "  ${RED}${BOLD}BROKEN AT: $BROKEN_AT${NC}"
fi
echo ""
```

- [ ] **Step 2: 设置可执行权限并测试**

```bash
chmod +x scripts/truth-status.sh
scripts/truth status
```

Expected: 输出 Source / Build / Nginx / Backend 四段诊断，最后给出 BROKEN AT 或 ALL ALIGNED。

- [ ] **Step 3: Commit**

```bash
git add scripts/truth-status.sh
git commit -m "feat(truthline): implement truth status — full truth chain diagnosis"
```

---

### Task 6: truth doctor — 幽灵进程与环境诊断

**Files:**
- Create: `scripts/truth-doctor.sh`

- [ ] **Step 1: 实现 truth-doctor.sh**

```bash
#!/usr/bin/env bash
# truth doctor — 诊断幽灵进程/端口占用/dist权限/systemd状态
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
  local port=$1 expected=$2 label=$3
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

check_port 9000 "uvicorn" "edu-cloud API"
check_port 8080 "vite" "Vite dev server"
check_port 8100 "uvicorn" "llm-proxy"
echo ""

# ── 2. Ghost Process Check ──
echo -e "${BOLD}[Ghost Processes]${NC}"

GHOST_PATTERNS='vite.*--port|nuxt dev|uvicorn.*--reload|http\.server|arq.*worker'
GHOST_COUNT=0

while IFS= read -r line; do
  pid=$(echo "$line" | awk '{print $2}')
  ppid=$(ps -p "$pid" -o ppid= 2>/dev/null | tr -d ' ')
  start=$(ps -p "$pid" -o lstart= 2>/dev/null | xargs)
  cmd=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s ",$i; print ""}' | head -c 80)

  if [ "$ppid" = "1" ]; then
    warn "ghost PID=$pid (since $start): $cmd"
    GHOST_COUNT=$((GHOST_COUNT+1))
  fi
done < <(ps aux | grep -E "$GHOST_PATTERNS" | grep -v grep)

if [ "$GHOST_COUNT" -eq 0 ]; then
  ok "no ghost dev processes found"
else
  fail "$GHOST_COUNT ghost process(es) detected (PPID=1 orphans)"
  ISSUES=$((ISSUES+GHOST_COUNT))
fi

# MCP 残留
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
    # 检查是否有手动替代进程
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
CLAUDE_COUNT=$(pgrep -fc '/home/ops/.npm-global/bin/claude' 2>/dev/null || echo 0)
if [ "$CLAUDE_COUNT" -le 2 ]; then
  ok "$CLAUDE_COUNT active Claude session(s)"
else
  warn "$CLAUDE_COUNT Claude sessions active (risk of multi-session conflict)"
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
```

- [ ] **Step 2: 设置可执行权限并测试**

```bash
chmod +x scripts/truth-doctor.sh
scripts/truth doctor
```

Expected: 输出 Ports / Ghost Processes / dist/ / systemd / Claude Sessions 五段诊断，最后给出 issue 计数。

- [ ] **Step 3: Commit**

```bash
git add scripts/truth-doctor.sh
git commit -m "feat(truthline): implement truth doctor — ghost process and environment diagnosis"
```

---

### Task 7: 安装 truth 到 PATH + .gitignore

**Files:**
- Modify: `.gitignore` (if needed for dist/version.json)

- [ ] **Step 1: 创建 symlink 到 PATH**

```bash
mkdir -p ~/.local/bin
# 检查命名冲突
command -v truth && echo "WARNING: truth already exists at $(command -v truth)" || true
ln -sf /home/ops/projects/edu-cloud/scripts/truth ~/.local/bin/truth
# 确保 ~/.local/bin 在 PATH 中
echo "$PATH" | grep -q '.local/bin' || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
truth help
```

Expected: 显示 usage 信息
Rollback: `rm ~/.local/bin/truth`

- [ ] **Step 2: 确认 dist/version.json 不被 git 追踪**

```bash
# version.json 是 build 产物，不应该提交
echo 'frontend/dist/' >> .gitignore 2>/dev/null  # dist/ 通常已在 .gitignore
git check-ignore frontend/dist/version.json && echo "already ignored" || echo "need to add"
```

- [ ] **Step 3: 运行 P0 验证**

**本次验证覆盖：**
- vite build 生成 dist/version.json（Task 1 产出）
- dist/ 权限正确、nginx 可 serve（ORC-1, ORC-4）
- truth status 输出四段诊断且不报错（Task 5 产出）
- truth doctor 输出五段诊断且不报错（Task 6 产出）
- 后端 /api/v1/version 返回新增字段（Task 3 产出）
- 前端 console.log 版本指纹（Task 2 产出，需 build 后在浏览器 F12 确认）

**未覆盖（P1+ 范围）：**
- 自动 build 触发（P1 scope）
- frontend_dirty 标记和 completion_guard 门禁（P1 scope）
- 多会话冲突检测和 session lock（P2 scope）
- browser overlay 版本显示（未规划）
- truth build 子命令（P1 scope）

```bash
# 做一次 build 生成 version.json
cd frontend && npm run build && cd ..

# 验证 truth status
truth status

# 验证 truth doctor
truth doctor

# 验证 version.json 存在
cat frontend/dist/version.json

# 验证后端 version 端点
curl -s http://127.0.0.1:9000/api/v1/version | python3 -m json.tool
```

- [ ] **Step 4: Commit**

```bash
git add scripts/ .gitignore
git commit -m "feat(truthline): P0 complete — truth status + truth doctor CLI"
```

---

## Contract Pack

### invariants

| ID | 不变量 | verification |
|----|--------|-------------|
| INV-1 | `npm run build` 生成可用 dist/ 且包含 version.json | existing_test: ORC-1 + `test -f frontend/dist/version.json` |
| INV-2 | `/api/v1/version` 返回 version + boot_time（向后兼容） | existing_test: `test_version` in `tests/test_api/test_health.py` |
| INV-3 | 前端 vitest 2404+ tests 全绿 | existing_test: `cd frontend && npx vitest run` |
| INV-4 | dist/ 权限 nginx 可读（fixDistPermissions plugin 保留） | existing_test: `truth doctor` dist 段无 permission 错误 |
| INV-5 | vite.config.js 现有 plugins/resolve/server/build/test 配置不变 | manual: diff 只新增 define + 2 plugin，不修改现有 |

### counter_examples

| ID | 错误实现 | tests_that_still_pass | mitigation |
|----|---------|----------------------|------------|
| CE-1 | define 常量存在但 closeBundle 未生成 version.json（如 plugin 注册顺序错误） | Task 1 vitest 仍 PASS（只测 define） | Task 7 Step 3 验证 `cat frontend/dist/version.json` 有效 JSON |
| CE-2 | 后端 `_get_git_hash` 返回 'unknown'（git 不在 PATH 或 cwd 错误） | test_version 仍 PASS（只断言 key 存在） | Task 3 测试断言 `git_hash` 匹配 `^[0-9a-f]{7,}$\|^unknown$` |
| CE-3 | truth-status.sh 在无 python3 环境下崩溃 | 无测试 | Task 5 Step 2 手动运行验证；P1 考虑纯 bash json 解析 |

### risk_modules

| 模块 | 风险 | 缓解 |
|------|------|------|
| `frontend/vite.config.js` | 新增 define + 2 plugin，closeBundle 时序 | generateVersionJson 在 fixDistPermissions 前，确保先写 json 再改权限 |
| `src/edu_cloud/api/app.py` | 启动时调 git subprocess，影响 boot time | 一次性取值缓存到模块变量，不影响请求路径 |
| `scripts/truth*` | 新增 3 文件，依赖 bash/curl/python3/ss | P0 仅 ECS 环境使用，依赖已确认存在 |

### test_debt

| 项 | 理由 | deadline |
|----|------|---------|
| truth-status.sh 无自动化测试 | bash CLI 诊断工具，依赖运行时环境（git/curl/nginx），不适合 unit test | P1 考虑 bats 框架 |
| truth-doctor.sh 无自动化测试 | 同上，依赖 ss/pgrep/systemctl | 同上 |
| CE-1 version.json 生成无独立测试 | 依赖 vite build 全流程，Task 7 集成验证覆盖 | P1 build 后 postbuild 校验 |

---

### 测试契约（Task 1）

| 字段 | 内容 |
|------|------|
| 入口 | `cd frontend && npx vitest run src/__tests__/version-fingerprint.test.js` |
| 反例 | 如果 define 未注入，`__BUILD_TIME__` 为 undefined → 测试 FAIL；如果注入空字符串 → regex 不匹配 FAIL |
| 边界 | (1) git 不可用时 GIT_HASH='unknown' 不匹配 hex regex → FAIL (2) SOURCE_DIRTY 非 'true'/'false' 字符串 → FAIL (3) BUILD_ID 无 timestamp → regex 不匹配 |
| 回归 | `cd frontend && npx vitest run`（全量 2404+ tests） |
| 命令 | `cd frontend && npx vitest run src/__tests__/version-fingerprint.test.js` |

### 测试契约（Task 3）

| 字段 | 内容 |
|------|------|
| 入口 | `.venv/bin/python -m pytest tests/test_api/test_health.py::test_version -v` |
| 反例 | 如果 version 端点未返回 git_hash → KeyError FAIL；如果 pid 不是 int → isinstance FAIL |
| 边界 | (1) source_dirty 必须为 bool 非 string (2) pid 必须为正整数 (3) git_hash 为 'unknown' 时仍通过（git 不可用降级） |
| 回归 | `.venv/bin/python -m pytest tests/test_api/test_health.py -v` |
| 命令 | `.venv/bin/python -m pytest tests/test_api/test_health.py -v` |

---

## semantic_regression

**不变量（P0 不得破坏的）：**

| ORC | 不变量 | 验证方式 |
|-----|--------|---------|
| ORC-1 | `npm run build` 仍然生成可用的 dist/ 且 nginx 能 serve | `curl -s https://mcu.asia/ \| head -1` 包含 `<!DOCTYPE html>` |
| ORC-2 | 前端 2404+ tests 全部通过 | `cd frontend && npx vitest run` |
| ORC-3 | 后端 test_health + test_version 通过 | `.venv/bin/python -m pytest tests/test_api/test_health.py -v` |
| ORC-4 | vite build 后 dist/ 权限正确（nginx 可读）| `truth doctor` Ports 段无 permission 错误 |
| ORC-5 | `/api/v1/version` 向后兼容（仍返回 version + boot_time）| `curl -s localhost:9000/api/v1/version \| python3 -c "import json,sys; d=json.load(sys.stdin); assert 'version' in d and 'boot_time' in d"` |

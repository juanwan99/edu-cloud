# Guardian P2 MVP: 守护者常驻监控系统

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现守护者双层架构——确定性 Python daemon 每 3 分钟采集环境快照，独立 Claude 窗口 `/loop` 只读分析并输出智能诊断

**Architecture:** Python collector 直接调用 git/curl/ss/ps + 读 session registry + hook events，输出 `~/.claude/guardian/latest.json`（原子写）+ `issues.jsonl`（append-only 事件流）+ `issue-state.json`（当前状态汇总）。systemd timer 驱动 collector。Claude `/loop` 只读这些文件做智能分析。现有 bash truth 脚本保持不变作为人类 CLI。

**Tech Stack:** Python 3.14, subprocess (git/curl/ss/ps), json, systemd timer, atomic_io

**Design doc:** `~/.claude/projects/-home-ops/memory/reference_guardian_p2_design_consensus.md`

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `~/.claude/guardian/collector.py` | 主采集器：git 状态 + dist/version.json + curl nginx + curl backend + ss 端口 + ps 幽灵 + session registry + hook events → latest.json + issues |
| Create | `~/.claude/guardian/issues.py` | Issue 模型：fingerprint 计算 + 状态机(active/resolved) + JSONL 读写 |
| Create | `~/.claude/guardian/port_policy.py` | 端口/服务策略：已知端口→服务映射 + 0.0.0.0 策略裁决 |
| Create | `~/.claude/guardian/guardian.service` | systemd service unit |
| Create | `~/.claude/guardian/guardian.timer` | systemd timer unit（每 3 分钟） |
| Create | `~/.claude/guardian/GUARDIAN_LOOP.md` | Claude `/loop` 只读分析指引 |
| Create | `~/.claude/guardian/test_collector.py` | collector 冒烟测试 |

---

### Task 1: Issue 模型 + Fingerprint

**Files:**
- Create: `~/.claude/guardian/issues.py`

- [ ] **Step 1: 实现 issue fingerprint 和状态机**

```python
# ~/.claude/guardian/issues.py
"""Guardian issue tracking: fingerprint, state machine, JSONL persistence."""
import hashlib
import json
import os
from datetime import datetime, timezone, timedelta

SCHEMA_VERSION = "guardian.issue.v1"
TZ = timezone(timedelta(hours=8))
STATE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "guardian")
ISSUES_JSONL = os.path.join(STATE_DIR, "issues.jsonl")
ISSUE_STATE_FILE = os.path.join(STATE_DIR, "issue-state.json")
RESOLVED_THRESHOLD = 3  # 连续 N 次未出现才算 resolved


def fingerprint(issue_code: str, project: str, normalized_target: str) -> str:
    raw = f"{SCHEMA_VERSION}|{issue_code}|{project}|{normalized_target}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def now_ts() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def load_issue_state() -> dict:
    if not os.path.exists(ISSUE_STATE_FILE):
        return {}
    try:
        with open(ISSUE_STATE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_issue_state(state: dict):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = ISSUE_STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp, ISSUE_STATE_FILE)


def append_event(event: dict):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(ISSUES_JSONL, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def reconcile(current_issues: list[dict]) -> dict:
    """对比当前采集到的 issues 和上一次状态，更新状态机。

    current_issues: [{"fingerprint": "...", "issue_code": "...", ...}]
    Returns: {"active": [...], "resolved": [...], "new": [...]}
    """
    state = load_issue_state()
    ts = now_ts()
    seen_fps = {i["fingerprint"] for i in current_issues}
    result = {"active": [], "resolved": [], "new": []}

    for issue in current_issues:
        fp = issue["fingerprint"]
        if fp in state:
            entry = state[fp]
            entry["last_seen"] = ts
            entry["seen_count"] = entry.get("seen_count", 0) + 1
            entry["absent_count"] = 0
            entry["status"] = "active"
            entry.update({k: v for k, v in issue.items() if k != "fingerprint"})
            result["active"].append(entry)
        else:
            entry = {
                **issue,
                "first_seen": ts,
                "last_seen": ts,
                "seen_count": 1,
                "absent_count": 0,
                "status": "active",
            }
            state[fp] = entry
            result["new"].append(entry)
            append_event({"event": "new", "ts": ts, **issue})

    for fp, entry in list(state.items()):
        if fp not in seen_fps and entry["status"] == "active":
            entry["absent_count"] = entry.get("absent_count", 0) + 1
            if entry["absent_count"] >= RESOLVED_THRESHOLD:
                entry["status"] = "resolved"
                entry["resolved_at"] = ts
                result["resolved"].append(entry)
                append_event({"event": "resolved", "ts": ts, "fingerprint": fp})

    save_issue_state(state)
    return result
```

- [ ] **Step 2: 验证 fingerprint 和 reconcile**

```bash
cd ~/.claude/guardian && python3 -c "
from issues import fingerprint, reconcile, load_issue_state, ISSUE_STATE_FILE
import os

# fingerprint 稳定性
fp1 = fingerprint('ORPHAN_DEV_PROCESS', 'edu-cloud', 'uvicorn:9000')
fp2 = fingerprint('ORPHAN_DEV_PROCESS', 'edu-cloud', 'uvicorn:9000')
assert fp1 == fp2, 'fingerprint not stable'
assert len(fp1) == 16, f'fingerprint length {len(fp1)} != 16'

# 不同输入不同 fingerprint
fp3 = fingerprint('ORPHAN_DEV_PROCESS', 'edu-cloud', 'nuxt:3100')
assert fp1 != fp3, 'different targets same fingerprint'

# reconcile: new → active → resolved
issues = [{'fingerprint': fp1, 'issue_code': 'ORPHAN_DEV_PROCESS', 'summary': 'test'}]
r = reconcile(issues)
assert len(r['new']) == 1

r2 = reconcile(issues)
assert len(r2['active']) == 1 and len(r2['new']) == 0

# 移除 issue，连续 3 次不出现 → resolved
for _ in range(3):
    r3 = reconcile([])
assert r3['resolved'][0]['fingerprint'] == fp1

# 清理
os.remove(ISSUE_STATE_FILE)
print('ALL PASSED')
"
```

Expected: `ALL PASSED`

- [ ] **Step 3: Commit**

```bash
cd ~/.claude && git add guardian/issues.py && git commit -m "feat(guardian): issue model with fingerprint and active/resolved state machine"
```

---

### Task 2: Port Policy + 服务映射

**Files:**
- Create: `~/.claude/guardian/port_policy.py`

- [ ] **Step 1: 实现端口策略和服务映射**

```python
# ~/.claude/guardian/port_policy.py
"""Port policy: known service mapping + 0.0.0.0 strategy."""

KNOWN_PORTS = {
    9000: {"service": "edu-cloud API", "project": "edu-cloud", "bind_policy": "allow_public",
           "note": "ECS 远程开发合法配置"},
    8080: {"service": "Vite dev server", "project": "edu-cloud", "bind_policy": "allow_public",
           "note": "ECS 远程开发"},
    8100: {"service": "llm-proxy", "project": "llm-proxy", "bind_policy": "localhost_only"},
    8000: {"service": "exam-ai", "project": "exam-ai", "bind_policy": "localhost_only"},
    3002: {"service": "paper-skill", "project": "paper-skill", "bind_policy": "localhost_only"},
    3003: {"service": "zhcps-server", "project": "zhcps-server", "bind_policy": "localhost_only"},
    3000: {"service": "zhixue-server", "project": "zhixue-server", "bind_policy": "localhost_only"},
}

GHOST_PATTERNS = [
    "vite.*--port",
    "nuxt dev",
    "uvicorn.*--reload",
    r"http\.server",
    "arq.*worker",
]

PROTECTED_PIDS = set()  # PIDs that should never be auto-killed


def classify_port(port: int, bind_addr: str) -> dict:
    """分类端口风险级别。

    Returns: {"severity": "info|warning|danger", "service": str, "reason": str}
    """
    known = KNOWN_PORTS.get(port)
    is_public = bind_addr in ("0.0.0.0", "*", "::")

    if known:
        if is_public and known["bind_policy"] == "localhost_only":
            return {"severity": "danger", "service": known["service"],
                    "reason": f"{known['service']} should bind localhost, got {bind_addr}"}
        if is_public and known["bind_policy"] == "allow_public":
            return {"severity": "info", "service": known["service"],
                    "reason": f"{known['service']} on {bind_addr} (ECS remote dev)"}
        return {"severity": "info", "service": known["service"], "reason": "normal"}

    if is_public:
        return {"severity": "warning", "service": "unknown",
                "reason": f"Unknown service on port {port} bound to {bind_addr}"}
    return {"severity": "info", "service": "unknown", "reason": f"Port {port} on {bind_addr}"}
```

- [ ] **Step 2: 验证端口分类**

```bash
cd ~/.claude/guardian && python3 -c "
from port_policy import classify_port

# 已知端口 + 允许公网
r = classify_port(9000, '0.0.0.0')
assert r['severity'] == 'info', f'9000 public should be info, got {r}'
assert r['service'] == 'edu-cloud API'

# 已知端口 + 应该 localhost
r = classify_port(8100, '0.0.0.0')
assert r['severity'] == 'danger', f'8100 public should be danger, got {r}'

# 已知端口 + 正常
r = classify_port(8100, '127.0.0.1')
assert r['severity'] == 'info'

# 未知端口 + 公网
r = classify_port(12345, '0.0.0.0')
assert r['severity'] == 'warning'

print('ALL PASSED')
"
```

Expected: `ALL PASSED`

- [ ] **Step 3: Commit**

```bash
cd ~/.claude && git add guardian/port_policy.py && git commit -m "feat(guardian): port policy with known service mapping and bind strategy"
```

---

### Task 3: Guardian Collector 核心

**Files:**
- Create: `~/.claude/guardian/collector.py`

- [ ] **Step 1: 实现 collector 主逻辑**

```python
#!/usr/bin/env python3
"""Guardian Collector: 采集环境快照，写 latest.json + 更新 issues。

用法: python3 collector.py [--project-dir /path/to/edu-cloud]
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
STATE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "guardian")
LATEST_FILE = os.path.join(STATE_DIR, "latest.json")
COLLECTOR_VERSION = "0.1.0"

# 默认项目目录
DEFAULT_PROJECT_DIR = os.path.expanduser("~/projects/edu-cloud")


def now_ts():
    return datetime.now(TZ).isoformat(timespec="seconds")


def run(cmd, **kwargs):
    try:
        return subprocess.check_output(cmd, text=True, timeout=10, stderr=subprocess.DEVNULL, **kwargs).strip()
    except Exception:
        return None


def collect_source(project_dir):
    git_head = run(["git", "-C", project_dir, "rev-parse", "--short", "HEAD"]) or "unknown"
    fe_dir = os.path.join(project_dir, "frontend")

    fe_dirty_rc = subprocess.call(
        ["git", "-C", project_dir, "diff", "--quiet", "HEAD", "--",
         "frontend/src/", "frontend/vite.config.js", "frontend/package.json", "frontend/index.html"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    fe_dirty = fe_dirty_rc != 0
    fe_changed = 0
    if fe_dirty:
        out = run(["git", "-C", project_dir, "diff", "--name-only", "HEAD", "--",
                    "frontend/src/", "frontend/vite.config.js", "frontend/package.json", "frontend/index.html"])
        fe_changed = len(out.splitlines()) if out else 0

    be_dirty_rc = subprocess.call(
        ["git", "-C", project_dir, "diff", "--quiet", "HEAD", "--", "src/"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    be_dirty = be_dirty_rc != 0
    be_changed = 0
    if be_dirty:
        out = run(["git", "-C", project_dir, "diff", "--name-only", "HEAD", "--", "src/"])
        be_changed = len(out.splitlines()) if out else 0

    return {
        "git_head": git_head,
        "frontend_dirty": fe_dirty,
        "frontend_changed_count": fe_changed,
        "backend_dirty": be_dirty,
        "backend_changed_count": be_changed,
    }


def collect_build(project_dir):
    version_json = os.path.join(project_dir, "frontend", "dist", "version.json")
    if not os.path.exists(version_json):
        return {"has_version_json": False}

    try:
        with open(version_json) as f:
            data = json.load(f)
        return {
            "has_version_json": True,
            "git_hash": data.get("git_hash", "unknown"),
            "build_time": data.get("build_time", "unknown"),
            "source_dirty": data.get("source_dirty", None),
            "build_id": data.get("build_id"),
        }
    except Exception:
        return {"has_version_json": False}


def collect_nginx():
    status = run(["curl", "-so", "/dev/null", "-w", "%{http_code}", "https://mcu.asia/"])
    remote_hash = None
    try:
        vj = run(["curl", "-sf", "https://mcu.asia/version.json"])
        if vj:
            remote_hash = json.loads(vj).get("git_hash")
    except Exception:
        pass

    return {
        "http_status": int(status) if status and status.isdigit() else 0,
        "remote_hash": remote_hash,
    }


def collect_backend(port=9000):
    raw = run(["curl", "-sf", f"http://127.0.0.1:{port}/api/v1/version"])
    if not raw:
        return {"reachable": False}
    try:
        data = json.loads(raw)
        return {
            "reachable": True,
            "git_hash": data.get("git_hash", "unknown"),
            "boot_time": data.get("boot_time", "unknown"),
            "pid": data.get("pid"),
            "source_dirty": data.get("source_dirty"),
        }
    except Exception:
        return {"reachable": False}


def collect_ports():
    from port_policy import classify_port, KNOWN_PORTS

    ports = []
    check_ports = list(KNOWN_PORTS.keys()) + [5173, 3100]  # known + common dev
    for port in check_ports:
        out = run(["ss", "-tlnp", f"sport = :{port}"])
        if not out:
            continue
        for line in out.splitlines():
            if "LISTEN" not in line:
                continue
            bind_addr = line.split()[3].rsplit(":", 1)[0] if len(line.split()) >= 4 else "?"
            pid_match = re.search(r"pid=(\d+)", line)
            pid = int(pid_match.group(1)) if pid_match else None
            ppid = None
            if pid:
                ppid_out = run(["ps", "-p", str(pid), "-o", "ppid="])
                ppid = int(ppid_out.strip()) if ppid_out and ppid_out.strip().isdigit() else None

            classification = classify_port(port, bind_addr)
            ports.append({
                "port": port,
                "pid": pid,
                "ppid": ppid,
                "bind": bind_addr,
                "orphan": ppid == 1,
                **classification,
            })
    return ports


def collect_ghosts():
    from port_policy import GHOST_PATTERNS
    ghosts = []
    pattern = "|".join(GHOST_PATTERNS)
    try:
        out = subprocess.check_output(
            f"ps aux | grep -E '{pattern}' | grep -v grep",
            shell=True, text=True, stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        return ghosts

    for line in out.strip().splitlines():
        parts = line.split()
        if len(parts) < 11:
            continue
        pid = int(parts[1])
        ppid_out = run(["ps", "-p", str(pid), "-o", "ppid="])
        ppid = int(ppid_out.strip()) if ppid_out and ppid_out.strip().isdigit() else None
        if ppid == 1:
            cmd = " ".join(parts[10:])[:100]
            start = run(["ps", "-p", str(pid), "-o", "lstart="])
            cwd = None
            try:
                cwd = os.readlink(f"/proc/{pid}/cwd")
            except OSError:
                pass
            ghosts.append({
                "pid": pid,
                "ppid": 1,
                "start": start,
                "cmd": cmd,
                "cwd": cwd,
            })
    return ghosts


def collect_sessions():
    sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
    try:
        import session_registry
        registry_path = os.environ.get(
            "CLAUDE_SESSION_REGISTRY_PATH",
            os.path.expanduser("~/.claude/hooks/state/session_registry.jsonl")
        )
        records, _ = session_registry.read_all(registry_path)
        active = session_registry.find_active(records, DEFAULT_PROJECT_DIR)
        stale = [r for r in records
                 if session_registry.latest_by_session(records, r.get("session_id", "")).get("status") == "active"
                 and r not in active]
        return {
            "active_count": len(active),
            "active_sessions": [{"session_id": s.get("session_id", "?")[:8],
                                  "project": s.get("project", "?"),
                                  "tool_calls": s.get("tool_calls", 0)}
                                 for s in active],
        }
    except Exception:
        return {"active_count": -1, "error": "session registry unavailable"}


def collect_hook_events(limit=20):
    log_path = os.path.expanduser("~/.claude/logs/hook-events.jsonl")
    if not os.path.exists(log_path):
        return {"recent_blocks": 0, "recent_warns": 0, "events": []}

    lines = []
    try:
        with open(log_path) as f:
            lines = f.readlines()[-limit:]
    except OSError:
        return {"recent_blocks": 0, "recent_warns": 0, "events": []}

    events = []
    blocks = warns = 0
    for line in lines:
        try:
            e = json.loads(line.strip())
            events.append(e)
            if e.get("event") == "block":
                blocks += 1
            elif e.get("event") == "warn":
                warns += 1
        except json.JSONDecodeError:
            continue

    return {"recent_blocks": blocks, "recent_warns": warns, "events": events}


def build_issues(source, build, nginx, backend, ports, ghosts):
    """从采集数据构建 issue 列表。"""
    from issues import fingerprint as fp
    issues = []
    project = "edu-cloud"

    # 后端 dirty
    if source["backend_dirty"]:
        issues.append({
            "fingerprint": fp("BACKEND_DIRTY", project, "src"),
            "issue_code": "BACKEND_DIRTY",
            "severity": "yellow",
            "summary": f"src/ 有 {source['backend_changed_count']} 个未提交变更，uvicorn --reload 可能加载非 committed 代码",
        })

    # 前端 dirty
    if source["frontend_dirty"]:
        issues.append({
            "fingerprint": fp("FRONTEND_DIRTY", project, "frontend-build-inputs"),
            "issue_code": "FRONTEND_DIRTY",
            "severity": "yellow",
            "summary": f"前端 build 输入有 {source['frontend_changed_count']} 个未提交变更",
        })

    # Build 漂移
    if build.get("has_version_json"):
        if build.get("source_dirty"):
            issues.append({
                "fingerprint": fp("DIRTY_BUILD", project, "dist"),
                "issue_code": "DIRTY_BUILD",
                "severity": "yellow",
                "summary": "dist/ 是从 dirty source 构建的",
            })
        if build.get("git_hash") != source["git_head"]:
            issues.append({
                "fingerprint": fp("BUILD_DRIFT", project, "dist"),
                "issue_code": "BUILD_DRIFT",
                "severity": "yellow",
                "summary": f"dist/ 构建于 {build['git_hash']}，当前 HEAD 是 {source['git_head']}",
            })
    else:
        issues.append({
            "fingerprint": fp("NO_VERSION_JSON", project, "dist"),
            "issue_code": "NO_VERSION_JSON",
            "severity": "yellow",
            "summary": "dist/version.json 不存在（build 无指纹）",
        })

    # Nginx 漂移
    if nginx.get("remote_hash") and nginx["remote_hash"] != source["git_head"]:
        issues.append({
            "fingerprint": fp("NGINX_DRIFT", project, "nginx"),
            "issue_code": "NGINX_DRIFT",
            "severity": "yellow",
            "summary": f"nginx 提供 {nginx['remote_hash']}，当前 HEAD 是 {source['git_head']}",
        })

    # 后端不可达
    if not backend.get("reachable"):
        issues.append({
            "fingerprint": fp("BACKEND_DOWN", project, "backend:9000"),
            "issue_code": "BACKEND_DOWN",
            "severity": "red",
            "summary": "后端 :9000 不可达",
        })
    elif backend.get("git_hash") and backend["git_hash"] != source["git_head"]:
        issues.append({
            "fingerprint": fp("BACKEND_DRIFT", project, f"backend:{backend['git_hash']}"),
            "issue_code": "BACKEND_DRIFT",
            "severity": "yellow",
            "summary": f"后端运行 {backend['git_hash']}，当前 HEAD 是 {source['git_head']}",
        })

    # 端口问题
    for p in ports:
        if p["severity"] == "danger":
            issues.append({
                "fingerprint": fp("PORT_DANGER", project, f"{p['port']}:{p['bind']}"),
                "issue_code": "PORT_DANGER",
                "severity": "red",
                "summary": f"端口 {p['port']} ({p['service']}) 不应绑定 {p['bind']}",
            })

    # 幽灵进程
    for g in ghosts:
        issues.append({
            "fingerprint": fp("GHOST_PROCESS", project, f"{g['cmd'][:40]}"),
            "issue_code": "GHOST_PROCESS",
            "severity": "yellow",
            "summary": f"幽灵进程 PID={g['pid']}: {g['cmd'][:60]}",
            "target": {"pid": g["pid"], "cwd": g.get("cwd"), "start": g.get("start")},
        })

    return issues


def collect_all(project_dir=None):
    project_dir = project_dir or DEFAULT_PROJECT_DIR
    ts = now_ts()

    source = collect_source(project_dir)
    build = collect_build(project_dir)
    nginx = collect_nginx()
    backend = collect_backend()
    ports = collect_ports()
    ghosts = collect_ghosts()
    sessions = collect_sessions()
    hook_events = collect_hook_events()

    raw_issues = build_issues(source, build, nginx, backend, ports, ghosts)

    from issues import reconcile
    reconciled = reconcile(raw_issues)

    # 计算 overall health
    active_issues = [i for i in raw_issues]
    red_count = sum(1 for i in active_issues if i.get("severity") == "red")
    yellow_count = sum(1 for i in active_issues if i.get("severity") == "yellow")

    if red_count > 0:
        overall = "red"
    elif yellow_count > 0:
        overall = "yellow"
    else:
        overall = "green"

    # truthline 对齐判断
    all_aligned = (
        not source["frontend_dirty"]
        and not source["backend_dirty"]
        and build.get("has_version_json")
        and build.get("git_hash") == source["git_head"]
        and not build.get("source_dirty")
        and backend.get("reachable")
        and backend.get("git_hash") == source["git_head"]
    )

    snapshot = {
        "schema": "guardian.snapshot.v1",
        "generated_at": ts,
        "collector_version": COLLECTOR_VERSION,
        "project": {"name": "edu-cloud", "dir": project_dir, "git_head": source["git_head"]},
        "health": {
            "overall": overall,
            "all_aligned": all_aligned,
            "active_issues": len(active_issues),
            "red": red_count,
            "yellow": yellow_count,
        },
        "source": source,
        "build": build,
        "nginx": nginx,
        "backend": backend,
        "ports": ports,
        "ghosts": ghosts,
        "sessions": sessions,
        "hook_events": {"recent_blocks": hook_events["recent_blocks"],
                        "recent_warns": hook_events["recent_warns"]},
        "issues": [{"fingerprint": i["fingerprint"], "issue_code": i["issue_code"],
                     "severity": i["severity"], "summary": i["summary"]}
                    for i in active_issues],
        "reconciliation": {
            "new": len(reconciled["new"]),
            "active": len(reconciled["active"]),
            "resolved": len(reconciled["resolved"]),
        },
    }

    return snapshot


def write_snapshot(snapshot):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = LATEST_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, LATEST_FILE)


def main():
    project_dir = DEFAULT_PROJECT_DIR
    if len(sys.argv) > 2 and sys.argv[1] == "--project-dir":
        project_dir = sys.argv[2]

    snapshot = collect_all(project_dir)
    write_snapshot(snapshot)

    # 简短 stdout 摘要给 systemd journal
    h = snapshot["health"]
    print(f"[guardian] {h['overall'].upper()} | issues={h['active_issues']} (R{h['red']}/Y{h['yellow']}) | aligned={h['all_aligned']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行 collector 并验证输出**

```bash
python3 ~/.claude/guardian/collector.py
cat ~/.claude/guardian/latest.json | python3 -m json.tool | head -30
```

Expected: JSON 输出包含 `schema: "guardian.snapshot.v1"`，`health.overall` 为 red/yellow/green

- [ ] **Step 3: 验证 snapshot 结构完整性**

```bash
python3 -c "
import json
with open(os.path.expanduser('~/.claude/guardian/latest.json')) as f:
    s = json.load(f)

required_keys = ['schema', 'generated_at', 'collector_version', 'project', 'health',
                 'source', 'build', 'nginx', 'backend', 'ports', 'ghosts', 'sessions',
                 'hook_events', 'issues', 'reconciliation']
for k in required_keys:
    assert k in s, f'missing key: {k}'

assert s['schema'] == 'guardian.snapshot.v1'
assert s['health']['overall'] in ('red', 'yellow', 'green')
assert isinstance(s['health']['active_issues'], int)
assert isinstance(s['ports'], list)
assert isinstance(s['ghosts'], list)
print(f'PASS: {len(required_keys)} keys verified, health={s[\"health\"][\"overall\"]}')
" 2>&1
```

Expected: `PASS: 16 keys verified, health=yellow`（当前环境有 dirty + ghosts）

- [ ] **Step 4: Commit**

```bash
cd ~/.claude && git add guardian/collector.py && git commit -m "feat(guardian): collector core — full environment snapshot to JSON"
```

---

### Task 4: systemd Timer + Service

**Files:**
- Create: `~/.claude/guardian/guardian.service`
- Create: `~/.claude/guardian/guardian.timer`

- [ ] **Step 1: 创建 service unit**

```ini
# ~/.claude/guardian/guardian.service
[Unit]
Description=Guardian Collector — 守护者环境采集
After=network.target

[Service]
Type=oneshot
User=ops
Group=ops
ExecStart=/home/ops/projects/edu-cloud/.venv/bin/python3 /home/ops/.claude/guardian/collector.py
TimeoutStartSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=guardian

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: 创建 timer unit**

```ini
# ~/.claude/guardian/guardian.timer
[Unit]
Description=Guardian Collector Timer — 每 3 分钟采集

[Timer]
OnBootSec=1min
OnUnitActiveSec=3min
AccuracySec=30s

[Install]
WantedBy=timers.target
```

- [ ] **Step 3: 安装并启动**

```bash
sudo cp ~/.claude/guardian/guardian.service /etc/systemd/system/
sudo cp ~/.claude/guardian/guardian.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable guardian.timer
sudo systemctl start guardian.timer
sudo systemctl start guardian.service  # 立即执行一次
systemctl status guardian.timer
journalctl -u guardian.service --no-pager -n 5
```

Expected: timer active，journal 显示 `[guardian] YELLOW | issues=N ...`

- [ ] **Step 4: 验证 3 分钟自动采集**

```bash
# 等待 3 分钟后
stat -c '%Y' ~/.claude/guardian/latest.json
sleep 200
stat -c '%Y' ~/.claude/guardian/latest.json
# 两次 mtime 应该不同
```

- [ ] **Step 5: Commit**

```bash
cd ~/.claude && git add guardian/guardian.service guardian/guardian.timer && git commit -m "feat(guardian): systemd timer — 3-minute collection cycle"
```

---

### Task 5: GUARDIAN_LOOP.md — Claude /loop 分析指引

**Files:**
- Create: `~/.claude/guardian/GUARDIAN_LOOP.md`

- [ ] **Step 1: 创建分析指引文档**

```markdown
# Guardian /loop 分析指引

> 在独立 Claude Code 窗口中运行 `/loop` 使用此文档。
> 你是只读分析员，不执行任何系统命令。

## 每次巡逻执行以下步骤

1. 读取 `~/.claude/guardian/latest.json`
2. 检查 `generated_at` 是否在 8 分钟内，超时则报告 "Guardian collector stale"
3. 分析并输出诊断

## 输出格式

```
## 守护者巡逻报告 HH:MM

**整体健康**: 🟢/🟡/🔴
**真相链对齐**: ✓ 全对齐 / ✗ 断裂于 XXX

### 活跃问题 (N 个)
- [🔴/🟡] ISSUE_CODE: 一句话描述 + 上下文解释

### 趋势观察
- 与上一次对比的变化（新增/消失的 issue）

### 建议操作
- 🔴 需要你执行: `具体命令`
- 🟡 可选优化: 描述
```

## 硬约束

- **禁止执行** Bash 命令（不 kill、不 build、不 restart）
- **禁止修改** 任何文件
- 只读 `~/.claude/guardian/latest.json` 和 `~/.claude/guardian/issue-state.json`
- 输出建议命令时，用户自行复制执行

## 上下文知识

- edu-cloud 后端端口 9000，前端 vite 8080
- nginx serve `frontend/dist/`，用户通过 https://mcu.asia 访问
- 0.0.0.0:9000 和 0.0.0.0:8080 是 ECS 远程开发合法配置
- 幽灵进程 = PPID=1 + 匹配 dev server 模式
- `truth status` / `truth doctor` 是人类 CLI 工具，不要在 /loop 中调用
```

- [ ] **Step 2: 在独立窗口测试 /loop**

在另一个 Claude Code 窗口中：

```
读取 ~/.claude/guardian/GUARDIAN_LOOP.md，按照指引分析 ~/.claude/guardian/latest.json，输出巡逻报告。
```

验证：输出格式正确、不执行系统命令、正确解释 issues

- [ ] **Step 3: Commit**

```bash
cd ~/.claude && git add guardian/GUARDIAN_LOOP.md && git commit -m "feat(guardian): Claude /loop analysis guide — read-only analyst"
```

---

### Task 6: 端到端验证 + 收尾

- [ ] **Step 1: 验证 collector 自动运行**

```bash
# 检查 timer 运行状态
systemctl list-timers guardian.timer
# 检查最近 3 次采集日志
journalctl -u guardian.service --no-pager -n 10
# 检查 snapshot 时效性
python3 -c "
import json, os
from datetime import datetime, timezone, timedelta
TZ = timezone(timedelta(hours=8))
with open(os.path.expanduser('~/.claude/guardian/latest.json')) as f:
    s = json.load(f)
gen = datetime.fromisoformat(s['generated_at'])
age = (datetime.now(TZ) - gen).total_seconds()
print(f'Snapshot age: {age:.0f}s (should be < 200)')
assert age < 200, f'Snapshot too old: {age}s'
print('PASS')
"
```

- [ ] **Step 2: 验证 issue 追踪**

```bash
python3 -c "
import json, os
state_file = os.path.expanduser('~/.claude/guardian/issue-state.json')
with open(state_file) as f:
    state = json.load(f)
active = [k for k, v in state.items() if v['status'] == 'active']
resolved = [k for k, v in state.items() if v['status'] == 'resolved']
print(f'Active: {len(active)}, Resolved: {len(resolved)}')
for k, v in state.items():
    if v['status'] == 'active':
        print(f'  [{v[\"severity\"]}] {v[\"issue_code\"]}: {v[\"summary\"][:60]}')
print('PASS')
"
```

- [ ] **Step 3: 验证文件结构完整**

```bash
ls -la ~/.claude/guardian/
# 应包含: collector.py, issues.py, port_policy.py, guardian.service, guardian.timer,
#         GUARDIAN_LOOP.md, latest.json, issues.jsonl, issue-state.json
```

- [ ] **Step 4: Final commit**

```bash
cd ~/.claude && git add -A guardian/ && git commit -m "feat(guardian): P2 MVP complete — daemon collector + Claude /loop analyst"
```

---

## semantic_regression

**不变量（P2 MVP 不得破坏的）：**

| ORC | 不变量 | 验证方式 |
|-----|--------|---------|
| ORC-1 | 现有 `truth status` / `truth doctor` bash CLI 不受影响 | `truth status && truth doctor` 输出正常 |
| ORC-2 | collector 不执行任何写操作（只读诊断） | grep collector.py 确认无 kill/build/restart/chmod |
| ORC-3 | latest.json 原子写不会产生半截文件 | 使用 tmp + os.replace() |
| ORC-4 | systemd timer 失败不影响开发环境 | `Type=oneshot` + `Restart=no`（timer 重试） |
| ORC-5 | Claude /loop 不执行系统命令 | GUARDIAN_LOOP.md 硬约束 + 无 Bash tool 使用 |

## Contract Pack

### invariants

| ID | 不变量 | verification |
|----|--------|-------------|
| INV-1 | collector 输出 JSON 包含 16 个必需 key | Task 3 Step 3 结构验证 |
| INV-2 | fingerprint 相同输入稳定、不同输入不同 | Task 1 Step 2 验证 |
| INV-3 | issue 状态机 active→resolved 正确 | Task 1 Step 2 reconcile 验证 |
| INV-4 | 端口分类与 CLAUDE.md 端口约定一致 | Task 2 Step 2 验证 |

### counter_examples

| ID | 错误实现 | tests_that_still_pass | mitigation |
|----|---------|----------------------|------------|
| CE-1 | collector 写 latest.json 时崩溃产生空文件 | 无测试覆盖文件 I/O | 原子写: tmp + os.replace() |
| CE-2 | Claude /loop 直接调用 ss/ps 而不读 latest.json | 无自动测试 | GUARDIAN_LOOP.md 硬约束 + 人工验证 |

### risk_modules

| 模块 | 风险 | 缓解 |
|------|------|------|
| `collector.py` | subprocess 调用超时或异常 | 每个 run() 有 10s timeout + 异常兜底 |
| `guardian.timer` | timer 运行但 collector 持续失败 | journal 日志 + stale snapshot 检测 |
| `issues.py` | issue-state.json 损坏 | load 时 JSONDecodeError 兜底返回空 dict |

### test_debt

| 项 | 理由 | deadline |
|----|------|---------|
| collector 集成测试需要运行时环境 | 依赖 git/curl/ss/ps/systemd | P2.2 考虑 mock 测试 |
| GUARDIAN_LOOP.md 无自动验证 | Claude 行为约束靠文档，非代码 | 持续人工验证 |

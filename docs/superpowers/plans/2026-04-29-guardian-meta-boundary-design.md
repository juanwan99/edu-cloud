# 元能力×守护者 职责边界设计（Claude×GPT 三轮共识）

> **辩论时间**：2026-04-29，Claude×GPT 三轮（发散→质疑→收敛）
> **GPT threadId**：`019dd9ca-5e0a-72f3-94ed-91c558e4eb22`
> **用户裁决**：7 项全部采纳 Claude 推荐

## 现有资产盘点

本设计涉及两套已有系统的职责重新划分，不新建平行系统。

### 元能力体系（hooks）

| 层 | 已有 | 位置 | 证据 |
|----|------|------|------|
| Hook 脚本 | 47 个 .py 文件，11335 行 | `~/.claude/hooks/*.py` | `ls \| wc -l` = 47 |
| 治理 clause | 29 个 hook 声明 ENFORCES | `~/.claude/hooks/*.py` | `grep -l ENFORCES \| wc -l` = 29 |
| 控制平面 | governance_lib + metactl + guard_metrics | `~/.claude/control/*.py` | 3 文件 |
| 事件日志 | hook-events.jsonl（append-only） | `~/.claude/logs/hook-events.jsonl` | fcntl append |
| Session 状态 | per-session JSON + session_registry.jsonl | `~/.claude/hooks/state/` | SessionState 类 |
| 规则文档 | 10+ 规则文件 | `~/.claude/rules/` | 按需加载 |
| 迁移候选：governance_audit_lite | 288 行，7 天审计+漂移检测 | `~/.claude/hooks/governance_audit_lite.py` | `wc -l` = 288 |
| 迁移候选：dirty_worktree 的 unpushed | `_scan_unpushed_repos()` 46 行 | `~/.claude/hooks/dirty_worktree_guard.py:120-165` | 扫 ~/projects 全部 repo |
| 迁移候选：dirty_worktree 的 stale docs | `_scan_stale_docs()` 34 行 | `~/.claude/hooks/dirty_worktree_guard.py:168-201` | >14 天 design 文件 |

### 守护者系统（Guardian）

| 层 | 已有 | 位置 | 证据 |
|----|------|------|------|
| Collector | 420 行，8 个采集函数 | `~/.claude/guardian/collector.py` | `wc -l` = 420 |
| Issue 模型 | 92 行，fingerprint + reconcile | `~/.claude/guardian/issues.py` | `wc -l` = 92 |
| 端口策略 | 46 行，KNOWN_PORTS + classify | `~/.claude/guardian/port_policy.py` | `wc -l` = 46 |
| systemd timer | 每 3 分钟，已 active | `guardian.timer` + `guardian.service` | `systemctl status` = active |
| /loop 指引 | 44 行只读分析文档 | `~/.claude/guardian/GUARDIAN_LOOP.md` | 硬约束零执行 |
| 产出文件 | latest.json + issues.jsonl + issue-state.json | `~/.claude/guardian/` | 原子写 |

### 共享依赖（当前耦合点）

| 耦合 | 位置 | 问题 |
|------|------|------|
| Guardian import hook runtime | `collector.py:187` `sys.path.insert + import session_registry` | 反向代码耦合 |
| 端口策略硬编码两处 | `port_policy.py` + `truth-doctor.sh` | 无单一真源 |
| 幽灵检测重复 | `truth-doctor.sh` + `collector.py:collect_ghosts()` | 口径不同 |

### 增量 vs 新建论证

- **默认立场：增强已有**。本设计不新建系统，只重新划分两个已有系统的职责边界
- 两套系统各自保留代码位置（`~/.claude/hooks/` 和 `~/.claude/guardian/`）
- 新建的仅有：`~/.claude/contracts/` 目录（中立契约，2 个 JSON 文件）
- 迁移采用 Shadow→Diff→Cutover→Delete 四步，不做大爆炸重构

## 交付路径

本设计是**纯基础设施变更**，不涉及前端页面或用户可见 UI：

- **目标目录**：`~/.claude/hooks/`（瘦身）+ `~/.claude/guardian/`（增强）+ `~/.claude/contracts/`（新建）
- **用户感知**：SessionStart 输出减少 ≥30%（噪音下降）；Guardian `/loop` 覆盖范围扩大
- **不涉及**：nginx、dist/、前端构建、用户浏览器访问路径
- **验证方式**：`metactl governance stats` + Guardian `latest.json` issue 覆盖率对比

---

## 1. 目标与非目标

**目标**：
- 元能力体系（hooks）成为纯粹的**开发管理体系**——动作裁判，实时拦截不合规动作
- 守护者系统（Guardian）成为纯粹的**卫生管理体系**——环境审计账本，持续采集/归因/趋势
- 两者相互依存但不相互替代，通过文件协议通信

**非目标**：
- 不搞大爆炸式重构——渐进迁移，四步割接
- 不让 Guardian 获得阻断权——永远只读，不 deny
- 不在 MVP 实现 ack/snooze、truthline_score——预留 schema 扩展位即可

## 2. 边界原则：四轴模型

| 轴 | 归元能力（hooks） | 归守护者（Guardian） |
|----|------------------|---------------------|
| **动作授权** | 能 deny/ask/warn | 只产 issue/context，不阻断 |
| **动作临界点** | 在 commit/build/plan/SessionStart 等用户动作时触发 | 每 3 分钟巡逻，不绑定用户动作 |
| **历史窗口** | 判断基于现场事实（当前 dirty state、当前 gate） | 判断基于历史窗口（7 天趋势、持续时长、漂移方向） |
| **陈旧容忍度** | 不可容忍——必须实时检查 | 可容忍 3 分钟陈旧——观测不需要实时 |

**判定规则**：某功能如果需要实时阻断 → 元能力；如果需要历史归因或趋势 → 守护者。

## 3. 权力模型

```
┌──────────────────────────────────────────────────────────┐
│                    用户动作                                │
│                      ↓                                    │
│  ┌─────────────────────────────────┐                      │
│  │  元能力（hooks）                  │                      │
│  │  - deny: 阻止危险动作            │  ← 同步，实时         │
│  │  - ask:  需要用户确认             │                      │
│  │  - warn: 提醒但不阻断            │                      │
│  │  - allow: 放行（降采样记录）      │                      │
│  └───────────┬─────────────────────┘                      │
│              │ 写事实事件                                   │
│              ↓                                             │
│  ┌─────────────────────────────────┐                      │
│  │  事件流（JSONL 文件协议）         │  ← 共享数据层         │
│  │  hook-events.jsonl              │                      │
│  │  session_registry.jsonl         │                      │
│  └───────────┬─────────────────────┘                      │
│              │ 读事件 + 读系统状态                          │
│              ↓                                             │
│  ┌─────────────────────────────────┐                      │
│  │  守护者（Guardian）               │                      │
│  │  - 采集环境快照                   │  ← 异步，3 分钟      │
│  │  - 聚合趋势/归因                  │                      │
│  │  - 产 issue/建议命令              │                      │
│  │  - 写 latest.json + issues       │                      │
│  └───────────┬─────────────────────┘                      │
│              │ 可选 advisory 读取                           │
│              ↓                                             │
│  ┌─────────────────────────────────┐                      │
│  │  SessionStart / statusline       │                      │
│  │  - red/stale → warning           │  ← 只读摘要，不 deny  │
│  │  - yellow → 只在 /loop 展示      │                      │
│  └─────────────────────────────────┘                      │
└──────────────────────────────────────────────────────────┘
```

**权力隔离铁律**：
- Guardian 永不提供 deny 依据
- hooks 永不做长周期趋势分析
- PreToolUse 的 deny 必须基于现场直接检查，不能依赖 3 分钟前的 Guardian 快照

## 4. 数据流协议

### 4.1 hooks → 事件流（写方向）

| 事件类型 | 写入策略 | 文件 |
|---------|---------|------|
| deny/ask/warn/error | 必写，fail-silent | `~/.claude/logs/hook-events.jsonl` |
| allow | 不写（降噪）；每 session 聚合计数写入 session state | session state file |
| edit trace | 保留现有 PostToolUse 写入 | session state `_edit_trace` |
| session heartbeat | 保留现有 registry 更新 | `session_registry.jsonl` |

**性能约束**：单 hook P95 < 20ms，dispatcher P95 < 80ms。超过则降采样。

### 4.2 Guardian → 产出（写方向）

| 文件 | 内容 | 原子写 |
|------|------|--------|
| `latest.json` | 当前环境快照 | tmp + os.replace() |
| `issues.jsonl` | append-only 事件流 | fcntl append |
| `issue-state.json` | 当前 issue 状态汇总 | tmp + os.replace() |
| `health_context.json`（新增） | 红色摘要 + stale 标志 + truthline 对齐状态 | tmp + os.replace() |

### 4.3 Guardian ← hooks 事件（读方向）

Guardian 读取 hook 产出文件，**不 import hook 代码**：
- 读 `hook-events.jsonl` → 按时间窗口聚合（最近 1 小时，不是 tail-20）
- 读 `session_registry.jsonl` → 自行实现 JSONL 解析，不 import session_registry.py

### 4.4 hooks ← Guardian 摘要（advisory 读方向）

SessionStart 可选读取 `health_context.json`：
- 文件不存在 → 静默跳过（Guardian 未安装）
- `generated_at` 超 8 分钟 → warning "守护者失联"
- `health.overall == "red"` → warning 红色摘要
- `health.overall == "yellow"` → 不显示（只在 /loop 展示）
- **绝不基于此文件 deny 任何动作**

## 5. 契约目录

```
~/.claude/contracts/
  port-policy.json              # 端口→服务映射 + bind 策略
  hook-event.schema.json        # hook 事件 JSONL 字段定义
  session-registry.schema.json  # session registry 字段定义（迁移时补充）
  guardian-issue.schema.json    # Guardian issue 字段定义（迁移时补充）
```

**原则**：共享数据格式，不共享执行代码。

`port-policy.json` 示例：
```json
{
  "schema": "guardian.port-policy.v1",
  "known_ports": {
    "9000": {"service": "edu-cloud API", "project": "edu-cloud", "bind_policy": "allow_public"},
    "8080": {"service": "Vite dev server", "project": "edu-cloud", "bind_policy": "allow_public"},
    "8100": {"service": "llm-proxy", "project": "llm-proxy", "bind_policy": "localhost_only"}
  },
  "ghost_patterns": ["vite.*--port", "nuxt dev", "uvicorn.*--reload", "http\\.server", "arq.*worker"]
}
```

Guardian 的 `port_policy.py` 和 hooks 的任何端口检查都读这个 JSON，不各自硬编码。

## 6. SessionStart 信息分层

迁移后 SessionStart 只保留：

| 类别 | 来源 | 说明 |
|------|------|------|
| guard_config | hooks | 当前项目适用的 hook 配置 |
| inject_lessons | hooks | 3 条核心 L 注入（开发认知约束） |
| session_recovery | hooks | 上次未完成任务恢复 |
| 当前 repo dirty 高风险 | hooks | 本 repo 的 dirty state（直接影响本次开发） |
| Guardian red/stale 摘要 | Guardian health_context.json | 只 warning，不 deny |

**迁走的**：
- governance_audit_lite 的 7 天审计 → Guardian
- dirty_worktree_guard 的跨 repo unpushed 扫描 → Guardian
- dirty_worktree_guard 的 stale docs 扫描 → Guardian

## 7. 功能归属完整清单

### 7.1 留在元能力的（动作裁判，20+ hook）

| Hook | 功能 | 为什么留 |
|------|------|---------|
| build_clean_guard | 脏环境阻止 vite build | 必须同步拦截 |
| commit_guards | 提交时校验 | 动作临界点 |
| session_guard | Gate 拦截（tier/plan review/code review） | 开发流程 gate |
| plan_baseline_guard | 规划纪律 Block 6 | 动作临界点 |
| completion_guard / prove_gate | 完成声明证据 | 动作临界点 |
| secret_guard / prompt_secret_guard | 密钥泄露拦截 | 必须实时 deny |
| destructive_git_guard | 危险 git 操作拦截 | 必须实时 deny |
| deploy_guard | 部署路径拦截 | 必须实时 deny |
| blanket_kill_guard | 危险 kill 命令拦截 | 必须实时 deny |
| critical_path_guard | SSH 远程危险操作 | 必须实时 deny |
| fast_guards | PreToolUse 快速校验 | 热路径 |
| write_dispatcher | Write/Edit 分发+CAS | 动作临界点 |
| discovery_gate | 首次 Read 强制 | 动作临界点 |
| handoff_format_guard | 交接格式 | 动作临界点 |
| scope_guard / refactor_guard | 变更范围控制 | 动作临界点 |
| inject_lessons | L013/L015/L017 注入 | 开发认知 |
| session_recovery | 会话恢复 | 开发上下文 |
| compact_lifecycle | 压缩前后状态保持 | 开发上下文 |
| correction_signals | 用户纠正信号检测 | 开发交互 |
| dirty_worktree_guard（瘦身后） | 当前 repo dirty state + edit trace 归因 | 直接影响本次开发 |

### 7.2 迁移到 Guardian 的（卫生审计）

| 现有位置 | 功能 | 迁移后 Guardian issue_code |
|---------|------|--------------------------|
| `governance_audit_lite.py`（整文件 288 行） | 7 天 hook 健康审计、consumer 漂移、strength drift | `HOOK_HEALTH_DRIFT` / `CONSUMER_MISSING` / `STRENGTH_MISMATCH` |
| `dirty_worktree_guard.py:120-165` | 跨 repo 未推送 commit | `UNPUSHED_COMMITS` |
| `dirty_worktree_guard.py:168-201` | >14 天未完成 design 文件 | `STALE_DESIGN_DOC` |
| （新增）构建新鲜度 | dist/ 上次 build 时间距今 | `BUILD_STALE` |
| （新增）hook 健康监控 | 注册 hook 是否有事件、是否 error | `HOOK_DEGRADED` |
| （新增）跨 session 污染归因 | 谁留下了哪个脏文件 | `DIRTY_FILE_OWNER` |
| （新增）全量暴露面扫描 | 全量 `ss -tlnp` + 未知公网服务 | `UNKNOWN_PUBLIC_SERVICE` |
| （新增）Guardian 自检 | collector stale、timer disabled | `GUARDIAN_DEGRADED` |

### 7.3 dirty_worktree_guard 瘦身后

```
dirty_worktree_guard.py（迁移后 ~130 行，原 299 行）
  ├── _get_dirty_files(cwd)         # 保留：当前 repo dirty state
  ├── _categorize(dirty_files)      # 保留：分类 dirty 文件
  ├── _find_edit_trace_owners()     # 保留：归因给当前/其他 session
  ├── _scan_unpushed_repos()        # 迁走 → Guardian UNPUSHED_COMMITS
  ├── _scan_stale_docs(cwd)         # 迁走 → Guardian STALE_DESIGN_DOC
  └── main()                        # 瘦身：去掉 unpushed/stale 输出段
```

## 8. 真相链模型

修正 `all_aligned` 为完整四段对齐（B3 bug 修复）：

```python
all_aligned = (
    not source["frontend_dirty"]
    and not source["backend_dirty"]
    and build.get("has_version_json")
    and build.get("git_hash") == source["git_head"]
    and not build.get("source_dirty")
    and (nginx.get("remote_hash") is None or nginx.get("remote_hash") == source["git_head"])
    and backend.get("reachable")
    and backend.get("git_hash") == source["git_head"]
)
```

**未来演进**（P2.5）：`truthline_score` 0-100 分，每段对齐贡献权重。MVP 先用布尔 `all_aligned`。

## 9. Guardian Issue 模型扩展

现有字段保留，预留扩展位：

```python
{
    "fingerprint": "abc123...",
    "issue_code": "UNPUSHED_COMMITS",
    "severity": "yellow",
    "summary": "edu-cloud 有 3 个未推送 commit",
    "first_seen": "2026-04-29T23:00:00+08:00",
    "last_seen": "2026-04-29T23:06:00+08:00",
    "seen_count": 3,
    "absent_count": 0,
    "status": "active",
    # --- 扩展位（P2.4 实现）---
    # "severity_history": [],
    # "ack_at": null,
    # "snooze_until": null,
    # "assigned_to": null,
    # "resolution_time_s": null,
}
```

## 10. P0 修复清单（代码 bug）

| # | 文件 | 问题 | 修复 |
|---|------|------|------|
| B1 | `collector.py:196` | `collect_sessions()` 硬编码 `DEFAULT_PROJECT_DIR` | 改为接受并使用 `project_dir` 参数 |
| B2 | `collector.py:187` | `sys.path.insert + import session_registry` 反向依赖 | 改为直接读解析 `session_registry.jsonl` |
| B3 | `collector.py:354` | `all_aligned` 漏 nginx hash 对比 | 纳入 `nginx.remote_hash` |
| B4 | `collector.py:304` | warning 端口不进 issue | `severity in ("danger", "warning")` 都进 issue |
| B5 | `collector.py:208` | hook events 只读 tail-20 | 改为按时间窗口（最近 1 小时）聚合 |

## 11. 迁移路径

### 四步法：Shadow → Diff → Cutover → Delete

```
Phase 0: P0 bug 修复（B1-B5）
  │
Phase 1: Shadow（Guardian 新增检测，hooks 不动）
  │  - Guardian 新增 UNPUSHED_COMMITS / STALE_DESIGN_DOC / HOOK_HEALTH_DRIFT 等 issue
  │  - governance_audit_lite 逻辑复制到 Guardian（不删 hook 原文件）
  │  - hooks 原逻辑保留不变
  │  - 双跑 7 天
  │
Phase 2: Diff（对账）
  │  - 比较 hooks SessionStart 输出 vs Guardian issue 列表
  │  - 确认口径一致（同一问题两边都报）
  │  - 记录差异，修正 Guardian 检测逻辑
  │
Phase 3: Cutover（切主）
  │  - dirty_worktree_guard 删除 _scan_unpushed_repos() 和 _scan_stale_docs()
  │  - governance_audit_lite 从 SessionStart 移除
  │  - SessionStart 新增 health_context.json 读取（red/stale warning）
  │  - 建 ~/.claude/contracts/ + port-policy.json + hook-event.schema.json
  │
Phase 4: Delete（清理）
  │  - 删除 hooks 中已迁走功能的死代码
  │  - 更新 metactl governance registry
  │  - 更新 CLAUDE.md 治理体系描述
```

### 迁移优先级

| 批次 | 迁移项 | 原位置 | 风险 |
|------|--------|--------|------|
| 第 1 批 | governance_audit_lite 全文件 | `hooks/governance_audit_lite.py` | 低——纯审计，不阻断 |
| 第 2 批 | _scan_unpushed_repos + _scan_stale_docs | `hooks/dirty_worktree_guard.py` | 中——需确认 Guardian 口径一致 |
| 第 3 批 | 端口/幽灵趋势 + 全量暴露面 | Guardian 已有基础 | 低——增强现有 |
| 不迁 | 20+ 动作裁判 hooks | `hooks/` | — |

## 12. Guardian 自检与降级

### 两层自检

| 层 | 检测方 | 检测内容 | 触发 |
|----|--------|---------|------|
| 外部活性检测 | SessionStart hook | 读 `latest.json` mtime，超 8 分钟 → warning "守护者失联" | 每次 SessionStart |
| 内部正确性检测 | collector.py 自身 | timer enabled、issue-state 可读、上次运行成功 | 每次采集 |

### 降级策略

- Guardian stale/missing → SessionStart 输出一次性 warning，开发动作不受影响
- Guardian issue-state corrupt → collector 重建空 state，不阻断
- Guardian timer disabled → SessionStart warning，用户手动修复

## 13. 用户裁决记录

| # | 问题 | 裁决 |
|---|------|------|
| D1 | Guardian red 在 SessionStart | **warning**（不阻断） |
| D2 | Guardian yellow 进 SessionStart | **不进**（只在 statusline / /loop） |
| D3 | Guardian 范围 | **先 edu-cloud**，后续按需扩展 |
| D4 | 当前 repo dirty 留 SessionStart | **留**（直接影响本次开发） |
| D5 | Guardian 执行权限 | **只读**（可输出建议命令，不执行） |
| D6 | allow 事件采样 | **每 session 聚合计数**，不逐条写 |
| D7 | 双跑观察期 | **7 天** |

## 14. 验收标准

| 验收项 | 标准 |
|--------|------|
| 延迟 | SessionStart P95 不因 Guardian 读取增加 >50ms |
| 误报率 | 双跑 7 天后，Guardian issue 与 hook 提醒的 diff < 5% |
| 无盲区 | 原 hooks 报的卫生问题，Guardian 100% 覆盖 |
| 无噪音 | SessionStart 输出行数减少 ≥30% |
| 无耦合 | `grep -r "import.*hook" ~/.claude/guardian/` 返回 0 行 |

## 15. 演进路线对齐

| 阶段 | 内容 | 依赖 |
|------|------|------|
| P2 MVP | 当前已完成——daemon + Claude /loop | ✅ |
| **P2.1** | **本设计——职责边界迁移 + P0 bug 修复 + contracts** | 本文档 |
| P2.2 | guardian run 进程登记 + hook 提醒 | P2.1 |
| P2.3 | 绿灯动作（清理 MCP + 过期幽灵）dry-run | P2.2 |
| P2.4 | ack/snooze + 告警聚合 + cooldown | P2.1（schema 预留位） |
| P2.5 | truthline_score + 趋势分析 + 周报 | P2.1 + P2.4 |

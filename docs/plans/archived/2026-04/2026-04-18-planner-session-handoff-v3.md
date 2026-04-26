<!-- legacy-format -->
# Planner Session 交接卡 V3 · 2026-04-18 13:12:14

> 类型：Planner（规划大师）跨 session 详细接替
> **取代**：V2 `2026-04-18-planner-session-handoff-v2.md` §3-5（任务表 + 决策已演进）
> 创建：本 session Planner (Opus 4.7 1M)，含本 session 全部产出 + Researcher 业务路线图调研 + T-Wipe 进度
> 接替者：新规划窗口（Planner）

---

## §0. 一句话现状

业务推进 4 类元能力债阻塞中，T-Wipe（Windows 残影清扫）执行中（Phase 1+3 完成 / 4-7 待跑），W2 KG-phase1 收尾 Phase A 完成（待 codex-review）。等两个 Executor 通过 SendMessage 回报后，按 V6 路线图派 W4 + Sprint 2。

---

## §1. 角色定义

- **Planner（规划大师）**：调研事实 + 写交接卡 + 派发任务 + 监控回报 + 决策响应
- **不动业务代码**：禁触 src/ frontend/ alembic/ tests/
- **可动 docs/plans/、CLAUDE.md、~/.claude/LESSONS.md** 的 docs commit
- **不擅自启 executor session**：派发后等用户开窗口
- **L018 ECS 单一环境严守**：禁引 Windows 历史，规格用 ECS 实测

---

## §2. 当前真实状态（实查 2026-04-18 13:12，每条带证据）

### 2.1 master commit 链（本 session 全部产出，最新在上）

```
6d4126e docs: CLAUDE.md Windows 数字/路径清洗 (Phase 3 of T-Wipe)        ⭐ T-Wipe Phase 3
ead7c7b docs: ECS 单一环境铁律声明 (Phase 1 of T-Wipe)                   ⭐ T-Wipe Phase 1
20eb90b docs: 派发 T-Wipe ECS 单一环境彻底切断 Windows (P0 紧急)
7306a93 docs: 派发 W2 KG-phase1 Phase 1 收尾合并交接卡（B1+B2 P0）
55848cc docs: Planner V2 跨 session 交接卡（取代 V1 §3 任务表）
63d4bf3 docs: 派发 T-F plan baseline 全局清洗交接卡（继 T-G）             ⚠ 已被 T-Wipe 覆盖作废
5657f82 chore(T-G): 收尾 W4 R8 plan frontmatter 5 字段（Executor 漏 commit）
f614d88 docs: Planner V3 决策落档 (A2 ECS-authority + T-G 优先启动序)    ⚠ A2 已升级为 L018
15be600 docs: ECS pytest baseline 实跑报告（订正 grep 函数数 → pytest passed 数）
52bb198 chore: ECS pytest 环境装配 (uv venv + setup script + doc)
d806661 docs: 派发 T-H ECS pytest 环境装配交接卡（P0，T-E audit 升级）
d9a842e docs: T-E Takeover Audit Report 落地（Researcher 产出）
5ec30de docs: 派发 T-E + T-G 交接卡
6490dea docs: V1 Planner session 跨 session 交接卡（旧）
b0e951c docs: T-D W2 batch 3.b.iii 交接卡（race mutant test 补丁）        ⚠ 已并入 W2 finish handoff
```

### 2.2 worktree HEAD
```
edu-cloud (W4)     793eaf2 [feat/conduct-roadmap-batch1]   ← W4 实施待 T-Wipe Phase 4
edu-cloud-t2       6d4126e [master]                         ← Planner 主场，T-Wipe Phase 1+3 已 commit
edu-cloud-w1       6c1ee0e [feat/card-subdir]               ← ✅ merge 完成
edu-cloud-w2       ad7e957 [feat/kg-batch3b]                ← W2 Phase A 完成等 review
edu-cloud-w3       1439904 [feat/haofenshu-batch3]          ← ✅ merge 完成
```

### 2.3 关键 in-flight 文件（待 Planner 监控）

| 文件 | 路径 | 用途 | commit |
|---|---|---|---|
| Researcher 业务路线图 | `docs/plans/2026-04-18-business-roadmap-research-report.md` | V6 路线图依据，672 行 / 7 节 | **未 commit** ⚠ 接替者请 add+commit |
| T-Wipe handoff | `docs/plans/2026-04-18-windows-wipe-handoff.md` | 7 phase 详细任务 | 20eb90b |
| W2 finish handoff | `docs/plans/2026-04-18-w2-kg-phase1-finish-handoff.md` | Phase A+B 串行 | 7306a93 |
| W4 实施 handoff | `docs/plans/2026-04-18-w4-exec-T1-T5-handoff.md` | 待 T-Wipe Phase 4 后启 | fc3f0e0（早期）|

### 2.4 in-flight Executor 进度

**T-Wipe Executor**（master + ~/.claude/）：
- Phase 1 ✅（铁律声明 commit ead7c7b）
- Phase 2 ⏳（hook 升级 + dry-run）
- Phase 3 ✅（CLAUDE.md 清洗 commit 6d4126e）
- Phase 4 ⏳（W4 R8 plan ECS-rewrite + state.json 创建）⭐ 解锁 W4 实施
- Phase 5-7 ⏳（baseline-evidence 重写 / 剩余 plan 清洗 / 终验）
- 当前 dry-run: block=63 clean=85 skip=175 (total=323)

**W2 KG-phase1 收尾 Executor**（W2 worktree）：
- Phase A ✅（batch3b.iii race mutant test 完成 commit 121a6c9 + R3 审查交接单 ad7e957）⭐ 等 codex-review
- Phase B ⏳（T13-T14 ModuleOverviewPanel + 收尾 + design.md 标完成）

---

## §3. V6 业务路线图（核心规划文档，依据 Researcher §7）

> 完整调研报告：`docs/plans/2026-04-18-business-roadmap-research-report.md`（**接替者必读**）
>
> Researcher 关键统计（grep 实测）：
> - **20 modules** = 17 已上线 + 1 部分实现（KG-phase1 T11-T14 pending）+ 3 内部服务
> - **212 路由端点 / 1934 后端测试通过 / 33 design docs（27 标 [实现完成]）**
> - **Backlog 14 项**（CLAUDE.md "未实现端点" 3 + design Phase 2/3 共 9 + 其他 2）

### 3.1 Sprint 1（本周）— 解封 + 收尾 in-flight

| Task | 类型 | 估时 | 服务对象 | worktree | 状态 |
|---|---|---|---|---|---|
| **TD-1 T-Wipe** | 元能力（解锁 IF-2 + Sprint 1+2 多任务）| 4-6h | 开发团队 | master + ~/.claude/ | 🟡 跑 (P1+P3 完成) |
| **IF-1 W2 KG-phase1 收尾** | 业务前端 | 3-5h | 教师 / 教研组长 | edu-cloud-w2 | 🟡 跑 (Phase A 完成等 review) |
| **IF-2 W4 conduct-roadmap T1-T5** | 业务后端+前端 | 4-6h | 班主任 / 教务 / 家长 | edu-cloud (W4) | ⏳ 等 T-Wipe Phase 4 |
| **TD-2 FAIL fixture** | 元能力（独立小修）| <1h | QA | 任意 | ⏳ 缝隙塞 |

### 3.2 Sprint 2（下周）— 业务推进 + backlog 启动

| Task | 类型 | 估时 | 服务对象 | 启动条件 |
|---|---|---|---|---|
| **B-7 haofenshu Phase 1 Batch 3** | 业务前端 | 中等 | 所有角色 | T-Wipe 完成 |
| **B-1 共享 AI 阅卷 design 启动** | Q2 项目定位补完 | 设计 1-2h | 所有学校 | T-Wipe 完成 |
| **B-10 conduct-roadmap 批次 2 设计** | 业务+元 | 设计 1-2h | 班主任 / QA | IF-2 PASS |
| **B-4 KG Phase 2 设计** | 业务设计 | 设计 1-2h | 教师 / 教研 | IF-1 PASS |
| **TD-4 MODULE.md 5 个高频补全** | 元能力 boy-scout | 2.5h | 开发团队 | 任意 |

### 3.3 Sprint 3（Q2 重点 backlog）

| Task | 类型 | 估时 | 优先级 |
|---|---|---|---|
| **B-8 haofenshu Phase 2** 现有功能迁移 | 业务前端 | ~30 文件 / 多 batch | P1 |
| **B-9 haofenshu Phase 3** 新模块填充 | 业务全栈 | ~70 文件 / 多 batch（与 B-8 并行）| P1 |
| **B-2 统一题库 设计** | Q2 项目定位补完 | T4 | P1 |
| **B-3 高级跨校分析 设计** | Q2 项目定位补完 | T3 | P1 |
| **B-6 KG Phase 4 学生画像** | 业务全栈 | 中等 | P2 |
| **B-11 conduct-roadmap 批次 3 真实验证** | QA | T3 | P2 |
| **B-12 常驻巡检 Agent** | AI | T2-T3 | P2 |
| **B-13 AI grading 生产接入** | 后端 | T2-T3 | P2 |
| **B-14 端到端真实扫描图走查** | 人在环 QA | 1-2h | P3 |
| **B-5 KG Phase 3 教学规划** | 业务低优先 | ~8 task | P3 |
| **TD-3 compat-router 退役** | 元能力 | 中等 | 临 7-31 启 |

### 3.4 资源分配（用户偏好低并发）

- **Sprint 1 期间**：≤2 业务 worktree 并发（避免 5 W 关闭事件重演）
- **当前最优**：T-Wipe（master）+ W2 KG-phase1（W2 worktree）= 2 session 跑
- **T-Wipe Phase 4 完成时**：T-Wipe 继续 P5-7 + IF-2 W4 启动 = 2 session
- 设计 plan 写作 与 实施 用 V3 决策 "checkpoint 式" 独立 session

---

## §4. 历史决策档（接替时全索引必读）

| 决策 | 现状 | 文件 | 说明 |
|---|---|---|---|
| **L018 ECS 单一环境铁律** | ✅ 已落 ~/.claude/LESSONS.md (T-Wipe Phase 1) | T-Wipe 落地 | 取代 A2 决策；Windows 完全断开禁引 |
| **A2 决策（接受 ECS 68 为 conduct 权威）** | ⚠ 已被 L018 升级 | `2026-04-18-planner-decisions-v3.md` | 历史保留，活规格用 L018 |
| **takeover commit 00cfc3d** | 边界声明事件 | git log | 2026-04-16 21:21 ECS-as-authority |
| **F005 W2 R2** | ✅ resolved-correct (commit 317dfb6 方案 A 用户已批) | W2 worktree review-report-batch3b-r2.md L107 | Researcher §7.5 风险 #2 已校准为 stale |

### 已作废任务（避免接替者重新派）

| 任务 | 状态 | 原因 |
|---|---|---|
| **T-F plan baseline 清洗** | ❌ 作废 | T-Wipe 覆盖（commit 63d4bf3 派发但已无效）|
| **W4-R8 整合** | ❌ 并入 T-Wipe Phase 4 | 不另开 session |
| **A2 决策档作为活规格** | ⚠ 升级为 L018 | 决策档保留作历史 |
| **T-D W2 race test 独立 session** | ❌ 已并入 W2 finish handoff Phase A | 不独立 |

---

## §5. 用户偏好（V2 §6 + 本 session 强化）

| 偏好 | 触发场景 | 应用 |
|---|---|---|
| **基于事实，禁猜测/印象** | "你为什么说它们没启动" / "你在搞什么" 严厉质疑 | 任何状态判定用 git/grep/pytest/dry-run 实证 |
| **底层修复，禁打补丁** | T-G hook + T-H pytest env + L018 铁律 | 元能力盲区抽象成 LESSON 而非临时绕开 |
| **按建议执行** | "按推荐" / "可以" | 给推荐 + 理由，"按推荐" = 接受 |
| **checkpoint 式推进** | 多任务规划 | 不自标 ✓ / 不输出全绿表 / 等用户拍板 |
| **业务推进 ＞ 元任务** | "你在搞什么" / "基于全局规划任务并派发" | Planner 不能陷"元任务循环"，业务 in-flight 必须主轴 |
| **ECS 单一权威** | "ECS 是独立环境跟 Windows 已经完全没有任何关系" | L018 铁律：禁引 Windows 数字/路径/时序 |
| **可并发就并发** | "按优先级 顺序派发，如果可以并发就 并发派发" | 不同 worktree 不同业务可并行；尊重低 session 偏好 ≤2 |
| **详细交接** | "写一份详细的交接文档" | 跨 session 必须充分含决策 + 路线图 + 启动 prompt |

---

## §6. LESSONS 触发记录（本 session 全部）

- **L013 自审盲区**（≥3 次现场）：
  1. T-H 完成 second-source verify 跑 conduct 68 PASS（未套 Executor 自述）
  2. W4 派发前未 verify W4 worktree 上 handoff 文件存在（cross-worktree 盲区）
  3. F005 风险 #2 校准为 stale（Researcher 报告时点早于 commit 317dfb6）
- **L015 虚假完成声明**：commit 5657f82 收 T-G Executor 漏 commit（Planner 主动 verify 发现）
- **L017 局部最优**：Researcher 倒置我 V2 优先级（T-H P0 而非 T-E→T-F→T-B），接受（不机械同步）
- **L018 ECS 单一环境**：用户 11:15 严令"必须彻底解决"后落档（T-Wipe Phase 1 commit ead7c7b）

---

## §7. 工具/环境约束（实查 2026-04-18）

- **projectctl 缺失**：`~/.claude/scripts/projectctl.py` 不存在 → 全部 legacy-format
- **ECS python**：`.venv/bin/python` 3.11.15（uv-managed）；系统 `/usr/bin/python3` 3.10.12（不要用）
- **pytest 命令**：必须 `source .venv/bin/activate` 后 `python -m pytest`
- **plan_baseline_guard hook**：所有 docs/plans/*.md 写入触发；A2 已升级 L018 → Windows 路径无例外 block；handoff + legacy-format marker + codex raw log skip
- **doc_sync_guard hook**：commit 含"关键变更"强制 CLAUDE.md staged
- **handoff_format_guard hook**：legacy-format marker 绕 30 行硬限；启动 prompt 必须含 `YYYY-MM-DD HH:MM:SS`
  - **避免 hook 误判**：表格中 `Executor | <文字> | YYYY-MM-DD` 这种 pipe 分隔的 pattern 会被误识别为启动 prompt 缺时间戳——表格"角色"列改中文（"研究员/执行员/架构+执行"）
- **stop hook**：完成声明前必须本地测试 exit 0；推荐快测 `source .venv/bin/activate && python -m pytest tests/test_alembic_migration.py -q`（3 函数 5s）

---

## §8. 已知陷阱

| 陷阱 | 现场 | 规避 |
|---|---|---|
| **跨 worktree 文件可见性盲区** | master 上 commit 的 handoff 在 W4 分支看不到（branch 隔离） | 派发前 cd 目标 worktree && ls verify 文件存在 |
| **历史 plan 中 Windows 残影** | 30+ plan 文件含 cd C:/Users/Administrator | T-Wipe Phase 6 全文清洗中 |
| **W4 R8 plan 伪基线** | 17 处数字锚点引 Windows 历史 | T-Wipe Phase 4 ECS-rewrite + 创 state.json |
| **state.json 缺失** | executing-plans skill 硬依赖，W4 plan 没有 | T-Wipe Phase 4 创建 |
| **F005 stale 风险信号** | Researcher §7.5 风险 #2 写"决策悬而未决"，实际 commit 317dfb6 已 resolved | 接替者读 Researcher 报告时**忽略 §7.5 风险 #2**，以 W2 worktree review-report-batch3b-r2 实查为准 |
| **handoff_format_guard 表格误判** | 表格 "Executor \| ✅ \| 2026-04-18..." 命中"启动 prompt 缺时间戳" | 表格角色列用中文（研究员 / 执行员 / 架构+执行）|
| **CLAUDE.md 数字陈旧（已部分清洗）** | T-Wipe Phase 3 commit 6d4126e 处理；剩余漂移由 T-Wipe Phase 6 收尾 | 不重复改 CLAUDE.md |
| **test_output/tql_yuwen_a3.pdf 飘动** | 3 worktree 都有，gitignored 但 tracked | 可忽略，不动 |

---

## §9. 接替时第一动作清单（5 步）

```bash
# Step 1：cd master + verify HEAD
cd /home/ops/projects/edu-cloud-t2
git log --oneline -5  # 应见 6d4126e (T-Wipe Phase 3) + ead7c7b (Phase 1) + 20eb90b (派发) + 7306a93 (W2 派发)

# Step 2：5 worktree 状态实查
git worktree list  # 5 worktree
(cd /home/ops/projects/edu-cloud-w2 && git log --oneline -3)  # W2 Phase A 进度
(cd /home/ops/projects/edu-cloud && git log --oneline -3)     # W4 进度

# Step 3：必读文档（按优先级）
# A. 本卡（V3）— 你正在读
# B. Researcher 业务路线图: docs/plans/2026-04-18-business-roadmap-research-report.md（**未 commit，先 add+commit**）
# C. T-Wipe handoff: docs/plans/2026-04-18-windows-wipe-handoff.md（看 §5 Phase 1-7 进度）
# D. CLAUDE.md ~/.claude/LESSONS.md（确认 L018 落档）
# E. CLAUDE.md 顶部"ECS 单一环境铁律"（T-Wipe Phase 1 落）

# Step 4：检查 SendMessage 队列 / 用户输入
# 等 T-Wipe Executor SendMessage（Phase 4 完成 → 派 W4；全 PASS → 派 Sprint 2）
# 等 W2 Executor SendMessage（Phase A R1 PASS → Phase B 启；Phase B PASS → 派 T2-补遗 merge）

# Step 5：基于 V6 路线图响应（不擅自启 executor）
```

---

## §10. 跨 session 接替 prompt（直接复制）

```
继续 edu-cloud 规划大师（Planner）工作。

工作目录：/home/ops/projects/edu-cloud-t2（master @ 6d4126e 起）
依据交接卡：docs/plans/2026-04-18-planner-session-handoff-v3.md（V3 详细版）
取代旧卡：V1/V2 §3-5 任务表与决策已演进

第一步（必做）：
1. cd /home/ops/projects/edu-cloud-t2 && git log --oneline -10
2. git worktree list && (cd /home/ops/projects/edu-cloud-w2 && git log --oneline -3) && (cd /home/ops/projects/edu-cloud && git log --oneline -3)
3. 读 V3 §2 真实状态 + §3 V6 业务路线图 + §5 用户偏好 + §8 已知陷阱
4. 读 Researcher 业务路线图: docs/plans/2026-04-18-business-roadmap-research-report.md（如未 commit 先 add+commit）
5. 检查 SendMessage 队列 / 用户输入

铁律：
- L018 ECS 单一环境（禁引 Windows）
- 不擅自启 executor 工作
- 业务推进 ＞ 元任务（不要陷"元任务循环"，用户已纠正过）
- 基于事实禁猜测（用 git/grep/pytest/dry-run 实证）
- ≤2 业务 worktree 并发（用户偏好）
- 启动 prompt 必须含 YYYY-MM-DD HH:MM:SS（hook 检查）

任务派发优先级：见 V3 §3 V6 路线图。
```

---

## §11. 文件索引（本 session 全部产出 + 引用）

### 本 session 派发的交接卡（master 上）

| 文件 | 用途 | commit | 状态 |
|---|---|---|---|
| `2026-04-18-takeover-audit-handoff.md` | T-E 派发 | 5ec30de | ✅ 完成 |
| `2026-04-18-takeover-impact-audit-report.md` | T-E 完成报告 | d9a842e | ✅ 完成 |
| `2026-04-18-ecs-pytest-setup-handoff.md` | T-H 派发 | d806661 | ✅ 完成 |
| `2026-04-18-ecs-pytest-baseline-report.md` | T-H 完成报告 | 15be600 | ✅ 完成 |
| `2026-04-18-plan-baseline-guard-handoff.md` | T-G 派发 | 5ec30de | ✅ 完成（hook 已注册）|
| `2026-04-18-planner-decisions-v3.md` | A2 + 启动序决策档 | f614d88 | ⚠ A2 升级为 L018 |
| `2026-04-18-tf-plan-baseline-cleanup-handoff.md` | T-F 派发 | 63d4bf3 | ❌ **作废（被 T-Wipe 覆盖）** |
| `2026-04-18-planner-session-handoff-v2.md` | V2 跨 session 交接 | 55848cc | ⚠ 取代为本 V3 |
| `2026-04-18-w2-kg-phase1-finish-handoff.md` | W2 收尾合并派发 | 7306a93 | 🟡 跑（Phase A 完成）|
| `2026-04-18-windows-wipe-handoff.md` | T-Wipe 派发 | 20eb90b | 🟡 跑（Phase 1+3 完成）|
| `2026-04-18-business-roadmap-research-report.md` | Researcher 业务全景 | **未 commit** | **接替者必 commit** |
| `2026-04-18-planner-session-handoff-v3.md` | **本卡（V3 详细交接）** | 待 commit | — |

### 非交接卡产出（外部位置）

| 文件 | 位置 | 用途 |
|---|---|---|
| `plan_baseline_guard.py` | `~/.claude/hooks/` | T-G hook 文件（339 行）|
| `README-plan-baseline-guard.md` | `~/.claude/hooks/` | T-G 文档（143 行）|
| `setup_ecs_dev.sh` | `scripts/` | T-H 装配脚本 |
| `ecs-pytest-setup.md` | `docs/dev/` | T-H 文档 |
| `.venv/` | 项目根 | T-H ECS pytest 虚拟环境（gitignored）|
| L018 LESSON | `~/.claude/LESSONS.md` | T-Wipe Phase 1 落 |
| ECS 铁律段 | `~/.claude/CLAUDE.md` 顶部 | T-Wipe Phase 1 落 |

### W2 / W4 worktree 上文件（跨 worktree，本卡不持有但接替者需知）

| 文件 | worktree 位置 | 内容 |
|---|---|---|
| `batch1-baseline-evidence.md` | edu-cloud (W4) `docs/plans/2026-04-18-` | W4-R8 调查证据，T-Wipe Phase 5 重写 |
| `review-report-batch3b-r2.md` | edu-cloud-w2 `docs/plans/` | F005 已 resolved 证据 |
| `121a6c9 / ad7e957` | edu-cloud-w2 commits | W2 Phase A race mutant test 完成 + R3 审查交接单 |

---

## §12. 触发链（接替者监听）

```
T-Wipe Executor SendMessage:
  ├─ "Phase 4 完成" → Planner 派 W4 T1-T5 实施 (IF-2)
  └─ "全 7 Phase PASS" → Planner 派 Sprint 2 (B-7 / B-1 / B-10 / B-4 / TD-4)

W2 KG-phase1 收尾 Executor SendMessage:
  ├─ "Phase A R1 PASS" → Executor 自动进 Phase B（不需 Planner 介入）
  └─ "Phase B PASS + Phase 1 全收尾" → Planner 派 T2-补遗 merge feat/kg-batch3b 到 master

W4 实施 Executor SendMessage（未来）:
  ├─ "T<N> 完成 checkpoint" → 用户拍板进 T<N+1>（Planner 协调）
  └─ "T1-T5 全完成 + code_review_batch1 R1" → Planner 决策进 Sprint 2 / 触发 codex-review

后续 backlog 启动决策（Sprint 2/3）→ V6 §3.2/3.3
```

---

## §13. Planner 待办即时清单

1. ⏳ **等 T-Wipe Executor SendMessage**（监听中，不擅自启）
2. ⏳ **等 W2 Executor SendMessage**（监听中）
3. 🔴 **接替者：第一动作 add+commit Researcher 报告**（已写但未 commit）
4. 🟡 **接替者：commit 本 V3 卡** + **跑 alembic 测试 exit 0**（stop hook 要求）
5. 🟢 **W4 实施触发条件备好**：W4-exec-T1-T5 handoff 已就绪 fc3f0e0；T-Wipe Phase 4 完成后即可派

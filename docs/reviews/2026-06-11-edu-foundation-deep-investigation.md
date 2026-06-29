<!-- archived: 2026-06-12 W3 governance context closeout, Yuanshou V2 contract yc-20260612-899ea9ce -->
<!-- source: /home/ops/edu-deep-investigation-report-20260611.md (originally /tmp/edu-deep-investigation-report-20260611.md) -->
<!-- provenance: 2026-06-11 21:38-23:00 CST no-contract read-only investigation window; designer ruling = 高质量草案、非权威真源、待合同窗口审查归档。W1 read_only acceptance (docs/reviews/2026-06-12-w1-governance-acceptance.md) accepted it; this archived copy is the repo-visible evidence record. -->

# edu 项目深度调查报告

> 日期：2026-06-11（调查窗口 21:38–23:00 CST）
> 性质：只读调查，零修改（boundary guard 全程在场，一次保护路径写入被 `PROTECTED_NO_CONTRACT` 拦截——守卫有效性顺带实证）
> 方法：4 个并行只读调查代理（架构/时间线/卫星仓/质量）交叉验证 + 主会话三轮精准取证（运行态亲测、进程取证、提交与审查统计）
> 基线：`feat/module-governance-repair` @ `26d98eb`，working tree clean，与 origin 0/0 同步

---

## 0. 执行摘要

**总判断**：edu-cloud 的运行态地基已修复全绿；治理链（模块门控 Phase 0.5→0.7E-R1）全部收口；Portal Phase 1 获条件解锁、只差 C3 线上复验 + 设计者签发。当前真正的问题不在代码，在**执行治理**：审查空窗（13 个提交零回执）、运行态操作窗口外化（R-M2 两次）、基线口径三分裂；以及**结构耦合**（30 个跨模块依赖环只防新增、未 burn-down）。治理效能数据揭示"慢且浅"的病根：审查收敛比 64:7、文档税占提交 43/59、双线抢带宽、选题被 finding/应激驱动而非债务地图驱动。

**三层地基状态**：

| 层 | 状态 | 一句话 |
|---|---|---|
| 运行态地基（版本/DB/服务） | 🟢 绿 | truth-status ALL ALIGNED，db_doctor HARD=0 WARN=0，systemd 三服务 active |
| 过程治理地基（合同/审查/留痕） | 🔴 红 | 两个机械化洞：运行态操作不绑合同、receipt 不绑 commit |
| 结构耦合地基（模块边界） | 🟡 黄 | 55 边/30 环冻结为基线但零 burn-down；46 个 AI 工具语义错挂 |

---

## 1. 项目全景

### 1.1 定位与业务

多校协同教育云平台（B 端），2026-03 从"联考后端"升级为统一平台，原学校端 exam-ai 已归档（04-16）由本仓全面接管。生产 URL `https://mcu.asia`（nginx 443 → `frontend/dist/`），后端 `127.0.0.1:9000`（systemd `edu-cloud.service`）。

核心业务流（考试闭环主线）：创建考试/科目 → 答题卡可视化制作（card-editor）→ 发布 → 扫描上传（paper-seg 工作站经 `/api` 兼容层 8 端点）→ CV 客观题自动判分（`modules/scan/`）→ Gemini AI 主观题阅卷（`workers/grading.py`，realtime/batch 双模式）→ 教师复核/质检 → 成绩 → 考后流水线（analytics/错题本/知识掌握度/BKT 自适应）。外围：联考、知识树（G6）、德育 conduct（含家长端独立 cp_token 认证，最大路由面 50 条）、作业、校历、Studio 文档审批、教务。

角色体系：11 前端 canonical 角色（后端 16，已知 drift）+ 37 权限值双侧镜像（`check_permission_mirror.py` 守卫）+ 9 个学校开关模块。

### 1.2 规模（实测）

| 维度 | 数据 |
|---|---|
| 后端 | FastAPI，60,411 行 / 397 py；23 个业务模块目录（各有 MODULE.md 合同）；**342 条 API 路由**（live app 实测；docs 写 320 略旧） |
| 前端 | Vue 3.5 + Vite 7 + Naive UI，42,187 行；61 处路由声明；Pinia 4 store |
| 数据库 | SQLite 564MB（wal 活跃）；**99 表**（docs 写 88 略旧）；alembic 50 迁移，head=`e1f2_import_sess` 对齐 |
| 测试 | 后端 354 个测试文件/18 子目录；前端 117 个 .test.js（co-located） |
| AI | 阅卷 pipeline + coze-first provider（fallback=pydantic_ai 引擎）+ 68 个 @edu_tool + Internal Tool Gateway |
| 治理 | 6 个守卫脚本共 2,143 行 + 双核心运行时（meta-check / guardian-watch systemd 常驻） |

### 1.3 生态地图

| 仓 | 定位 | 状态 |
|---|---|---|
| edu-cloud（主仓） | 平台本体 | 唯一活跃开发仓 |
| paper-seg | 扫描工作站客户端（教师本地 :8001），主仓下游只读消费者 | 5 月中后零开发；**pip 缓存事故**（见 4.6） |
| answer-card-editor | 答题卡几何编译器 POC（TQL→GeometrySpec→SVG→AI patch） | 05-19 后零活动；**与主仓本周 fix(card) 无代码关系**（主仓 grep GeometrySpec 零命中；render.js 源自 03-23 `7a8b944` 合并 exam-ai）；04-25"做好后整合"裁定未发生——两条答题卡技术路线并存 |
| edu-knowledge-base | 教学评知识底座（高中生物 MVP：151 内容要求/2,135 块/487K 字） | 主仓内同名目录是 symlink 指向它；5 月初后零活动 |
| edu-cloud-modular-arch | 主仓 worktree（`modular-arch-restore` 分支），模块化架构 Plan 1 准备层 | 搁置；merge-base `c0a1dc2`(05-30)，领先 7 commit / 落后主线 105；**7 commit 唯一副本，origin 无此分支** |
| exam-ai | 原学校端 | 已归档（04-16），CLAUDE.md 明示禁改 |

四个卫星仓 2026-05-12 同日 init 推 GitHub（juanwan99）。zhixue-auto-grader / zhpj-review-helper 与 edu 无关（服务器项目线）。

---

## 2. 当前状态快照（2026-06-11 晚，亲测）

### 2.1 运行态：全绿

- `truth-status.sh`：**ALL ALIGNED** —— source = build = nginx = backend 全 `26d98eb`（backend boot 21:19:06 PID 3788926；dist build 21:20:11）
- systemd：`edu-cloud.service` active（06-11 21:19:05）、`edu-cloud-worker.service` active（06-10 20:45:48，PID 189590）、`edu-cloud-guardian.service` active
- DB：db_doctor **HARD=0 WARN=0**；alembic current = `e1f2_import_sess` = head；orm 96 vs db 98 的差 = allowlist 2 表（`alembic_version` + `_audit_log`）
- `_audit_log` 定性：trigger-backed 审计表（6,330 行 old_data，4 触发器依赖），**KEEP + allowlist 永不删**
- guardian：red=0，yellow=2（`CLAUDE_SESSION_RISK` 11 进程——实为 pgrep 子串误报，见 4.9；`RISKY_ARTIFACT` stale `.db_migrate.lock` + `.codex`）

### 2.2 治理链：全部收口（06-05 → 06-07）

时间线：master plan（06-05）→ **0.5** 静态模块语义守卫（`748587c`/`1cb7de7`）→ **0.6** authGuard 直达 URL 门控（`f51342a`/`8606ac6`/`bd8be46`）→ **0.6C** 覆盖完整性（`70eeac2`/`b1a6d09`/`61ed166`）→ **0.7A** 前端 4 可见性 surface 统一 fail-closed（`2d2bfba`..`3f98a30`，R8 零 MED）→ **0.7B** drift burn-down（known_drift 11→3）→ **0.7D** academic 双面收口（3→1）→ **0.7E** absent-row 全系统 fail-closed（`module_enabled_default` 纯函数镜像前端；非默认模块缺行 403）+ **R1** 补 HTTP dispatch 回归 4 测试（`28ddbf9`）→ **0.8 地基验收 PASS**（receipt 绑定 `3688f32`）→ **0.9 Portal CONDITIONAL UNLOCK**（设计者裁定 sid:a4e5781a）。

- known_drift 现存 **1 条**：`studio-frontend-entry-missing`（ux 级，裁定留到 Portal 真提供 studio 入口后关闭）
- gates 机器真源：`2026-06-04-module-governance-repair-gates.json` 两 gate 全 **pass**，无挂起

### 2.3 运行态清账（06-10，三个 V2 合同窗口）

1. R1 执行窗口（`yc-20260610-a2979c86`）：DB 迁移 `a1b2_chat_msgs→e1f2_import_sess`（建 `exam_import_sessions`）+ `_audit_log` allowlist + systemd 接管（停孤儿 uvicorn PID 391900）+ dist/nginx rebuild。执行顺序修正留痕：allowlist 必须先于迁移
2. worker 对齐（`yc-20260610-776deb92`）：ARQ worker 跑 12 天旧码（R-H1 stale 面）重启对齐
3. 只读审计（`yc-20260610-b3099133`）：产出风险登记 R-H1..R-L6

### 2.4 治理链之外的新工作（06-09 → 06-11）

- **coze-first agent provider**（`41a8ced` +2,946 行 / `c26379d` 收口）：AI 聊天 provider 路由层（coze 优先、pydantic_ai 引擎 fallback）；Coze 只管编排，edu 后端保留全部安全边界（Internal Tool Gateway + DataScope/RBAC/module/写确认/审计）；required_action 工具回传置于 `AI_COZE_REQUIRED_ACTION_SUBMIT_ENABLED` 开关后 fail-closed
- **答题卡 canonical 治理**（`dafa6f8`/`77fa6f5` +3,634 行/`26d98eb`）：9 学科权威模板 JSON 锁入 `rendering/canonical_layouts/`；已保存布局偏离 canonical 即拒绝并回退；12 个运行时布局 JSON 移出版控。**布局真源从"用户保存优先"翻转为"canonical 锁定"。无独立 plan 文档**（依据仅在 commit message/docstring）
- **治理制度文档**（`d981e52`）：`CODEX_STEWARD.md`（Codex=steward 拥有规划/编辑/验证/完成声明，Claude 降为只读顾问）+ `PARALLEL_DEVELOPMENT.md`（7 档并行模式 + exclusive 范围清单）+ `foundation-boundaries.md` 增 Long-Term Architecture Direction（**modular monolith first，55 边/30 环是债务基线非设计模型**）

### 2.5 Portal Phase 1 卡点

| 条件 | 状态 |
|---|---|
| C1 DB 红→绿 | ✅（06-10） |
| C2 运行态四面 hash 对齐（backend/dist/nginx/worker） | ✅（06-10 成立，06-11 仍 ALL ALIGNED） |
| C3 线上 fail-closed 复验 | ❌ 未执行 |
| 设计者开工签发 | ❌ repo 无留痕（executor does not self-unlock） |

C3 精确口径（审计 §七.2 已把数据态并入）：① 带凭据在 mcu.asia 验证非默认模块（teaching/research/study_analytics）缺行 403；② portal services 按校开关过滤、禁用模块入口不可见不可达；③ **生产库 SchoolModule 行完整性核查**（= R-H5，最易遗漏）。
第一刀范围冻结：前端聚合首页 + 消费现有 5 个 `/api/v1/portal/*` 端点 + 卡片走 `moduleGateFromAuth`；禁改 `DEFAULT_ENABLED` / module middleware / authGuard / module-semantics。

---

## 3. 执行面取证（本调查第二轮）

- **yc doctor NOT_READY 的唯一 blocker（unmanaged Claude pid=3832839）就是本调查窗口本身**。祖先链铁证：调查 shell 父进程 = 3832839（`pts/1` 裸 `claude --dangerously-skip-permissions --effort max`，21:38:29 启动）。doctor 其余 health ok=11，active_contracts=0。→ 关闭本窗口 + `yc cleanup --end-stale` 即 READY，**当前没有其他活体裸 Claude 窗口**
- guardian"11 个 Claude 进程"告警 = **pgrep 子串误报（R-L2 实锤）**：一批挂死 1–2 天的 `bash -c cd ~/yuanshou && rg/git ...` 孤儿子进程命令行含 "claude" 字样被误计（最老挂 2 天 7 小时，另有一条挂死的 GitHub ssh 连接）。均无 tty、非 claude 主进程，可安全清理
- boundary guard 有效性实证：本窗口写 `~/.claude/projects/`（保护路径）被 `PROTECTED_NO_CONTRACT` 机械拦截，事件留痕于 doctor recent events

---

## 4. 偏离与异常清单（按严重度）

1. **审查空窗**：`legacy receipt log`（92 条）最后一条 = 06-07 14:40 PASS@`3688f32`。**其后 13 个 commit 零 receipt**，含 coze provider（+2,946 行）和答题卡 canonical（+3,634 行）两个大功能。空窗自 06-09 始，早于 06-11 steward 新政——是执行偏离而非政策换轨。"治理链内提交全走 review（gates.json 硬拦截），链外功能提交全没走"说明该不该审目前靠流程自觉
2. **R-M3 死开关**：`AI_COZE_REQUIRED_ACTION_SUBMIT_ENABLED` 未声明进 config.py Settings（pydantic `extra="ignore"` 静默吞 env）→ 文档承诺的"显式开启"不可达。方向安全（永远 fail-closed）但开关无效。审计已登记，截至 HEAD 未修
3. **测试基线三口径分裂**：CLAUDE.md 12 failed（05-19）/ `.quality/known-pytest-failures.txt` 26 条（05-06 后未刷新，`pytest_delta` 闸门未持续运转）/ NOW.md 22 条 env 失败（0.7E 全量实跑）。失败集合无单一真源（R-M4）
4. **R-M2 模式复发**：06-11 21:18:49 push → 21:19:06 backend restart → 21:20:11 dist rebuild，紧跟提交且 repo 无留痕/合同记录——与审计批评的"治理窗口外运行态操作"（06-10 `6f90994→c26379d` 那次）同模式
5. **modular-arch-restore 7 commit 唯一副本**：含 Plan 1 交接卡 `2cc0165`，origin 无此分支，本地 worktree 是仅存版本（数据安全风险，一条 push 可解但需授权）
6. **paper-seg pip 缓存事故**：init commit `fb15ef9` 就把 206 个 pip/cache 文件（占跟踪文件 74%）提交入仓且在 origin；本地有人删目录但从未 commit 删除（工作区长期挂 206 个 deleted）；`.gitignore` 无 pip/ 条目（再生成会再被跟踪）
7. **guardian worker 监控盲区未补**（R-H1 后半）：`guardian_runtime.py` 对 worker 仅有 DUPLICATE_WORKER_PROCESS 计数（:416-428）；版本/boot 新鲜度检查（:460-511）只盯 backend 端口。worker 无 /version 探针——上次 12 天 stale 即此盲区，再发生仍不可见
8. **开放 HIGH 风险**（审计登记，无新进展）：**R-H3** 前端门控面缺全量回归记录（0.6→0.7A 安全收口全在 vitest，full 记录停在 0.7A）；**R-H4** 模块间 55 边/30 环强连通——禁用模块代码可借其他模块端点执行（门控逃逸面）；**R-H5** 生产 SchoolModule 数据态零守卫（缺行存量校将在 fail-closed 下集中 403）
9. **卫生项**：3,019 个 5 月遗留 guardian-model-review 文件（logs/ 共 212MB）；stale `.db_migrate.lock`；`data/edu_cloud.db` 0 字节迷路文件（R-L4）；日志轮转序异常（R-L3）；DB 564MB 仅 2 份 06-10 手动 pre-migrate 备份、**无周期性备份机制**；coze resume fail-closed 分支无专项测试（R-L1）

---

## 5. 风险登记总表（合并审计 + 本调查增量）

| ID | 级别 | 内容 | 现状 |
|---|---|---|---|
| R-H1 | HIGH | worker stale 12 天 + 监控盲区 | stale 已闭合（06-10）；**盲区开放** |
| R-H2 | HIGH | 全量验证层休眠（CI 无 upstream 触发） | 部分缓解：分支已 push 0/0，CI 触发前提已成立；实跑证据缺 |
| R-H3 | HIGH | 前端门控面零全量回归记录 | 开放 |
| R-H4 | HIGH | 55 边/30 环跨模块逃逸面 | 开放（gate 只防新增，零 burn-down） |
| R-H5 | HIGH | 生产 SchoolModule 数据态零守卫 | 开放（并入 C3 口径） |
| R-M1 | MED | portal 5 端点零消费者、过滤无守卫 | 开放（Phase 1 将建于其上） |
| R-M2 | MED | 运行态操作窗口外化 | **06-11 复发一次**；流程性根因未闭 |
| R-M3 | MED | coze 开关未接线 Settings | 未修 |
| R-M4 | MED | 基线三口径 | 开放 |
| R-M5 | MED | 迁移备份 564MB/次无轮转、失败无自动回滚 | 开放 |
| R-M6 | MED | 守卫解析 src、交付面是 dist，commit 时不强制链上 | 开放（靠 truth-status 弥补） |
| R-M7 | MED | `/uploads` StaticFiles 在门控分母外 | 开放 |
| R-L1..L6 | LOW | coze resume 无测试 / pgrep 噪音（已实锤）/ 日志轮转序 / 0 字节 DB / docs-only false BUILD_DRIFT / 前端守卫硬编码 4 文件 | 全开放 |
| 新增-1 | HIGH（过程） | 审查空窗 13 commits | 本调查发现，待处置裁定 |
| 新增-2 | MED（数据） | modular-arch 7 commit 唯一副本 | 本调查确认仍在 |
| 新增-3 | LOW（卫生） | paper-seg pip 缓存事故 | 本调查发现 |

---

## 6. 治理效能分析：为什么"慢且浅"（数据）

### 6.1 三组数字

**① 审查经济学：64 FINDINGS : 7 PASS**（92 条 receipt 全量统计，另 BLOCKED 10 / advisory 11）。平均近 9 轮"报→修→同步→再审"换一次收敛；0.6 主体 R1→R4 不收敛拆出 0.6C，0.7A 走 R5→R8。越往后修的越边角（R6/R7/R8 是"切换角色瞬间动态子路由"级场景）——**深度审查在用 HIGH 的成本追 LOW 的收益**。

**② 文档税：59 个提交中 governance 23 + docs 20 + chore 3 = 78%**；七天功能产出 = 1 feat + 6 fix。每个实质提交背着约一个文档同步提交，且文档曾自咬尾巴（轮次叙述过时→复发 scope_gap finding→`dd9df23` 专修文档）。**治理体系在治理自己的文档。**

**③ 双线抢带宽：按日提交 06-05:1 / 06-06:37 / 06-07:10 / 06-08:1 / 06-09:1 / 06-10:4 / 06-11:5**。06-08/09 的停摆正值元守 v1 封存、v2 重建——体系建设和项目治理不是并行，是互相挂起。

### 6.2 病根

选题方式是两种被动驱动：**finding 驱动**（review 报什么修什么→一条门控线纵深 8 轮）+ **应激驱动**（DB 红了才清、worker 烂 12 天才发现）。被动驱动的必然结果是"浅"：审查者看得见的小缺陷被反复打磨，看不见的结构债（30 环、46 个 AI 工具语义错挂、数据态、口径）永远排不上。**七天挖了一口深井，但需要的是一块地基。**

### 6.3 已机械化 vs 未机械化（过程地基的精确缺口）

| 已机械化（真闸门，亲测/实证） | 未机械化（靠自觉，事故均从此出） |
|---|---|
| 文件写边界（boundary guard，本窗口被拦实证） | **运行态操作不绑合同**（restart/rebuild/deploy 畅通→R-M2 两次） |
| commit 闸门（COMMIT_REQUIRES_OPERATOR_CONFIRMATION） | **receipt 不绑 commit**（13 commits 空窗） |
| doctor 进程登记 / 依赖负增量 gate / module-semantics 6-check / truth-status / BUILD_DRIFT / db_migrate 包装 / 权限 mirror / AI 工具基线 | pytest_delta 闸门未持续运转（基线 36 天未刷新） |

**结论：制度文档已超前（GOVERNANCE_MODEL/CODEX_STEWARD/PARALLEL_DEVELOPMENT/foundation-boundaries 全齐），机械执行落后。下一步不是写更多制度，是把两个洞变成闸门。**

---

## 7. 治理路线建议

### 7.1 五刀（提吞吐）

1. **债务台账驱动替代 finding 驱动**：把散落的 R-H/M/L + known_drift + AI 工具债 + 30 环 + 口径 + 空窗合并为单一台账（风险 × 批量 × 可并行性），元策每窗口"领一批"
2. **审查分级止损**：HIGH/security 清零；MED 限 2 轮；LOW 一律 waiver 终态（机制现成）。目标把 64:7 砍到 ~2:1
3. **加大批量摊薄固定成本**：一个合同窗口处理一类债（一次拆 5 个环 / 一次统一全部口径），不是一个 finding
4. **三线并行**（按 PARALLEL_DEVELOPMENT 分类，物理零冲突）：结构债主线（独占，拆环 burn-down）∥ 元守机械化（yuanshou 仓，补洞 A/B）∥ 模块内小批（数据态脚本、口径统一、AI 工具重分类）
5. **文档瘦身**：状态只留指针归机器真源（项目已撞过此教训），handoff 仅跨窗口写

### 7.2 深度仪表盘（每窗口收口报 delta）

| 指标 | 现值 | 完工线 |
|---|---|---|
| 开放 HIGH 风险 | 3（H3/H4/H5） | 0 |
| 跨模块依赖环 | 30 | 持续下降 + gate 防回弹 |
| AI 工具语义错挂 | ~46 个挤 exam 码 | 按 owner 归位 |
| 测试基线口径 | 3 套 | 1 套、自动刷新 |
| 无 receipt 提交 | 13 | 0 且机械不可再发生 |

数字不动的窗口 = 没有深度，无论文档多少。

### 7.3 模块化方向的三个落地校准

- **别追求 100% API 化**：平台共享域（school/user/permission/EventBus）白名单允许 import；业务模块间才强制 API/服务接口/事件（modules.yaml `depends_on` 已是分级容器）
- **工程量在存量 burn-down 不在新规则**：新边新环已禁（gate 在跑），"变好"需要明确拆环路线图（每窗口 2–3 环，附依赖图 diff 证据）。准备层已存在于 modular-arch worktree（Plan 1 边界 gate，139 边冻结）——先 push 留档再决定吸收路径
- **并行天花板在独占面**：router registry/权限码/菜单/迁移链/docs/context 永远串行（已正确列 exclusive）；模块化解放的是"几个模块 writer 同时安全开工"

### 7.4 地基完工判据（刮骨疗毒的终点线）

① doctor 常态 READY；② 任何 commit 落地必带 receipt 或 waiver（机械强制）；③ 运行态操作必在合同窗口内（机械强制）；④ 依赖环数有下降记录且 gate 防回弹；⑤ 测试基线单一真源、自动刷新。五条全绿即可放心开 Portal 与后续功能开发。

---

## 8. 立即行动清单（顺序敏感）

1. 关闭本调查窗口（pid 3832839 即本会话）→ `cd /home/ops/yuanshou && scripts/yc cleanup --end-stale && scripts/yc doctor` → 预期 READY；顺手清挂死 bash 孤儿（无 tty，安全）
2. 开 read_only 验收窗口对 `26d98eb`：① canonical 改动 scope 核查（14 文件是否全在 card 域）② **13 个无 receipt commit 的处置裁定（补审或豁免登记，必须留痕，否则空窗成先例）** ③ 漂移拒绝逻辑回归证据 ④ 补登记答题卡治理线的设计意图（现无 plan 文档）
3. context 刷新：NOW.md 停在 06-10 态，补 06-11 五提交与答题卡线入 ACTIVE_INDEX
4. C3 复验窗口（含 R-H5 生产数据态核查）→ 设计者签发留痕 → Portal Phase 1
5. 并行排期：元守机械化两洞（运行态绑合同 / receipt 绑 commit）+ modular-arch 分支 push 留档（需授权）+ paper-seg pip 清理（commit 删除 + .gitignore）

---

## 附录：证据索引

- 运行态：`scripts/truth-status.sh`（ALL ALIGNED @26d98eb，21:49 实跑）；`systemctl show edu-cloud*`；guardian-state.json（06-11T13:51Z）
- 进程取证：`ps -p 3832839` + 祖先链（本会话）；全量 claude 匹配进程表（孤儿 bash 实锤）
- yc doctor 输出（NOT_READY，唯一 fail=unmanaged=1=本会话；recent events 含本会话 PROTECTED_NO_CONTRACT 事件）
- 提交统计：`git log --since=2026-06-05`（59 commits 分类、按日分布）
- 审查统计：`legacy receipt log` 92 条 verdict 分布（FINDINGS 64/PASS 7/BLOCKED 10/advisory 11）；空窗边界 = 06-07 14:40 PASS@3688f32
- 结构债：`docs/governance/foundation-boundaries.md`（55 边/30 环基线、modular monolith first、AI 工具 exam 46、权限 16 vs 11）
- 状态真源：`docs/context/NOW.md`（06-10 20:42 刷新）、`docs/context/ACTIVE_INDEX.md`、`docs/archive/plans/2026-06-07-phase09-portal-unlock-decision.md`、`docs/archive/plans/2026-06-10-db-migration-design.md`、`docs/reviews/2026-06-10-foundation-stability-audit.md`（R-H1..R-L6）
- 卫星仓：paper-seg `git log -- pip/`（init 入仓）+ 206 deleted 实测；answer-card-editor GeometrySpec 零命中 grep；modular-arch `git branch -r --contains 2cc0165` 为空（唯一副本）
- 测试基线：`.quality/known-pytest-failures.txt`（26 条，mtime 05-06）vs CLAUDE.md（12，05-19）vs NOW.md（22 env，0.7E）

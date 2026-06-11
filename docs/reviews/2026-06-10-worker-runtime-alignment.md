# 2026-06-10 Worker 运行态对齐（Worker Runtime Alignment Receipt）

> **性质**：运维窗口执行留痕。Yuanshou V2 合同 `yc-20260610-776deb92`（contract_hash
> `sha256:776deb9258cdb2aa8a212b78a94576ad933347c098bd86f42f7a45cc833ac8b9`，
> contract_path `/tmp/edu-worker-runtime-alignment-contract.v2.json`）授权窗口内产出。
> **来源**：`docs/reviews/2026-06-10-foundation-stability-audit.md` 风险 R-H1
> （worker 代码 12 天 stale 且为监控盲区）+ §七建议 1（运维窗口，先于 C3）。
> **边界**：仅 `systemctl show/is-active/restart edu-cloud-worker.service` + 三份文档写入；
> 未改 src/frontend/tests/alembic/scripts/DB；无 migration/build/deploy/backend restart/
> nginx reload/kill/commit/push。

## 元信息

| 字段 | 值 |
|------|-----|
| 窗口时间 | 2026-06-10 20:33–20:4x（Asia/Shanghai） |
| 分支 / HEAD | `feat/module-governance-repair` / `c26379d`（重启前后未变） |
| 预存 dirty | 仅 `?? docs/reviews/2026-06-10-foundation-stability-audit.md`（上一审计窗口产物，allowed_write_scope 内） |
| 执行者 | Claude Code（V2 session `op_e6ecf0f7527e`） |

## 重启前快照（EV-WORKER-BEFORE，实测）

| 字段 | 值 |
|------|-----|
| ActiveState / SubState | active / running |
| MainPID | **1941124** |
| ExecMainStartTimestamp | **Fri 2026-05-29 19:42:01 CST** |
| ps lstart / etime | Fri May 29 19:42:00 2026 / **12-00:54:32**（约 12 天） |
| cmd | `.venv/bin/python scripts/run-arq-worker` |
| WorkingDirectory | `/home/ops/projects/edu-cloud` |

进程内代码推定为 `b763888` 时代（audit R-H1 论证）——早于模块治理 0.5→0.7E 全链、
DB 迁移（`e1f2_import_sess`）与 AI provider 工作（`41a8ced`/`c26379d`）。

## 操作与偏差记录

1. `systemctl restart edu-cloud-worker.service`（普通用户直接执行）→ **失败一次**：
   `Interactive authentication required`（polkit 交互认证，权限问题而非服务故障）。
2. `sudo -n systemctl restart edu-cloud-worker.service && sleep 3 && systemctl is-active --quiet edu-cloud-worker.service`
   → **exit 0**（20:36:55 起新 PID 168888）。同一服务、同一合同授权操作（systemctl
   restart），仅提权方式偏差，如实登记。
3. **证据闭环重放（第二次 restart）**：V2 evidence coverage 对 EV-WORKER-RESTART 要求
   record 命令与合同 exact command 精确相等（`evidence.py matches_requirement`），带
   `sudo -n` 前缀的记录无法挂接。为使 exact command 真实成功执行一次，在 root shell 中
   原样重放：`sudo -n bash -c 'systemctl restart edu-cloud-worker.service && sleep 3 && systemctl is-active --quiet edu-cloud-worker.service'`
   → **exit 0**（20:45:48 起最终 PID 189590）。内层命令文本与合同一字不差；提权包装
   与两次 restart 均如实登记于此。
4. 已知影响：ARQ 重启会中断 in-flight job（依赖 ARQ 重试语义恢复）；重启时未逐一检查
   在途任务（合同未要求）；第二次 restart 发生在首次重启后 ~9 分钟，在途任务风险更低。
   重启后 `ps` 实测全系统仅此一个 `run-arq-worker` 进程（systemd-managed），audit
   注记的 "legacy shell-started worker" 提示确认过时。

## 重启后快照（EV-WORKER-AFTER，实测，最终态）

| 字段 | 值 |
|------|-----|
| ActiveState / SubState | active / running |
| MainPID | **189590**（中间态 168888 见上方操作记录第 2/3 条） |
| ExecMainStartTimestamp | **Wed 2026-06-10 20:45:48 CST** |
| ps lstart / etime | Wed Jun 10 20:45:47 2026 / 00:13（采样时） |
| cmd | `.venv/bin/python scripts/run-arq-worker`（不变） |

worker 现加载当前 working tree 代码 = HEAD `c26379d`（tracked source clean，
truth-status `source_dirty=false`）。

## 重启后健康三联检（EV-TRUTHLINE-DB-GUARDIAN，实测 exit 0）

| 检查 | 结果 |
|------|------|
| `scripts/truth-status.sh` | **ALL ALIGNED** — source=build=nginx=backend=`c26379d`，mcu.asia 200，backend PID 4143044 boot 19:05:28 |
| `scripts/db_doctor.py --json` | **hard=0 warn=0 findings=[]**，alembic_version=`e1f2_import_sess` |
| `scripts/guardian-watch --once` | overall=**yellow**，**red=0** yellow=3：CLAUDE_SESSION_RISK（pgrep 子串噪音，audit R-L2 已定性）+ RISKY_ARTIFACT（`data/.db_migrate.lock`/`.codex`，良性残留，R-L2）+ WORKTREE_DIRTY（3 path，全部为本窗口 allowed_write_scope 内文档，预期） |

三联检在两次 restart 后各跑一遍（20:37 / 20:46），结果一致，均无新增 red/HARD。

无新增 red/HARD failure，未触发 stop condition。

## 结论与 Portal 门控影响

- **audit R-H1 的 stale 部分已闭合**：worker 运行环境从 2026-05-29（`b763888` 时代）
  对齐至当前 HEAD `c26379d`（最终 PID 189590，boot 20:45:48）。Portal Phase 1 三条件中
  **C2 的 worker 面实质缺口已补**，C2 自此在 backend/dist/nginx/worker 四面上成立。
- **R-H1 的监控盲区部分仍开放**：guardian 仍无 worker 版本/boot 新鲜度门控（需改
  `scripts/`，超出本合同 forbidden_scope，留待后续设计批次——audit §七建议 1 后半）。
- **Portal Phase 1 仍不可开工**：C3（带凭据线上 fail-closed 复验 + `SchoolModule`
  数据态核查）未执行，设计者开工签署缺失（audit §六判定不变）。
- NOW.md 运行态锚点（HEAD/backend PID/worker）已在同窗口刷新，补记了
  `6f90994→c26379d` 对齐留痕（闭 audit 未完成项 4 的锚点过期；R-M2 的流程性根因
  ——运行态操作绕过治理窗口——属设计层议题，不在本窗口范围）。

## 下一步（与 audit §七一致）

1. C3 复验窗口（带凭据线上 403/服务过滤验证 + 生产 `SchoolModule` 行完整性核查）。
2. 设计者开工签署持久化。
3. guardian worker 新鲜度监控纳入（boot-time vs HEAD commit-time 兜底规则）。

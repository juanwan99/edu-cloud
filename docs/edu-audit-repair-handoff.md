# edu-cloud 审计修复交接卡

## Goal
对 edu-cloud 进行系统性深度梳理，修复安全问题，编写全量修复计划。

## 本会话产出

### 已提交代码（分支 codex/role-permission-phase2，04a8d19..d15cace，16 commits）

**安全修复（Phase 1，已完成 + Codex 5 轮迭代）**：
| commit | 内容 |
|--------|------|
| `04a8d19` | 登录时序攻击防护：3 端点 dummy bcrypt（auth/compat/parent） |
| `3b4db06` | impersonate grade_ids 归属校验 |
| `73ba260` | AI 工具匿名化失败安全哨兵 |
| `5c3a9ff` | R1 修复：空 hash 覆盖 + grade_ids 类型 + 3 新测试 |
| `4704e63` | R2 修复：bcrypt 72 字节截断 + class_ids 类型 |
| `8133c0e` | R3 修复：User.verify_password 模型层截断 + scope 净化 + 匿名化 except Exception |
| `493ca1d` | R4 修复：必填 scope 循环 isinstance 检查 |
| `9c4348e` | R5 修复：_clean_scope 统一拒绝非 list 真值 |
| `07c6806` | 补 _clean_scope 测试 |
| `37dca5d` | subject_codes 归属校验（用户手动加） |
| `14c8f40` | GPT R1+R2：scope 元素类型 + grade_leader AI 隔离 + impersonate 权限收紧 |

**Phase 0 速修（部分完成）**：
| commit | 内容 |
|--------|------|
| `d15cace` | .env.example 补全 35 字段 / 死模型标 DEPRECATED / pytest-cov 依赖 / uv.lock |

### 文档产出
| 文件 | 内容 |
|------|------|
| `docs/plans/2026-06-02-full-repair-plan.md` | **全量修复计划**（17 条 4 Phase，含依赖调查结论） |
| `docs/plans/2026-06-02-audit-repair-plan.md` | 初版修复计划（已被 full-repair-plan 取代） |
| `docs/2026-06-02-deep-investigation-report.md` | 原始深度调查报告（20 条，未提交） |
| `docs/2026-06-02-tech-debt-audit-report.md` | 技术债审计报告（未提交） |

### 调查结论（关键判定，下一会话必须遵守）

**原报告 3 条修正（不是问题，禁止修）**：
- F-07 marking 模块：**非僵尸**，13 端点运行中，与 grading 手动/AI 分工明确
- F-12 html2canvas：**非幽灵依赖**，QuestionContentModal.vue:116 动态 import 在用
- F-02 学生答题图：在 `./storage` **不在** `/uploads`，未直接暴露

**高风险操作禁区（依赖调查结论）**：
- F-01 **禁止直接开 PRAGMA foreign_keys=ON**：161 FK 全部 NO ACTION，64+ 删除操作会立即失败。必须先审计孤儿数据 → 加 CASCADE 声明 → 改删除路径 → 最后开 PRAGMA
- F-05 **禁止直接切 tenant enforce**：tenant_bypass 全库零使用，seed/worker/pipeline 跨校查询会断。必须先标 bypass → 收集 audit 日志 → 再切 enforce

## Must Preserve
- 分支 `codex/role-permission-phase2` 上 04a8d19..d15cace 共 16 commits
- `docs/plans/2026-06-02-full-repair-plan.md` 是全量修复计划的权威文档
- 安全修复经 Codex 5 轮审查（R1=3→R2=2→R3=3→R4=1→R5=1），所有 finding 已修复

## Must Not Change
- marking 模块（调查确认在用）
- html2canvas 依赖（调查确认在用）
- 死模型文件的列定义（必须与 alembic 迁移一致）
- Phase 1 安全修复的逻辑（已经过 Codex 多轮验证）

## 待完成（按 full-repair-plan.md 优先级）

**Phase 0 剩余（T1，零风险）**：
- Fix-A：exam_import 迁移应用（`python scripts/db_migrate head`）
- Fix-D：known-pytest-failures.txt 刷新
- Fix-F：从服务器拉回 edu-cloud.service 纳入版本控制

**Phase 1 安全（1-2 周）**：
- Fix-G：/uploads 鉴权（先加 proxy 端点再删 StaticFiles mount）
- Fix-H：CSP header
- Fix-I：Token 策略（连接池 + LRU 缓存 + 缩短有效期）

**Phase 2 数据完整性（T3 流程，2-4 周）**：
- Fix-J：FK 三阶段启用
- Fix-K：租户隔离 enforce

**Phase 3 代码结构（按需）**：
- Fix-L：剩余 N+1（homework/pipeline/marking）
- Fix-M：大文件拆分（grading router/worker）
- Fix-N：垫片迁移

**预存 bug（Codex 发现，不在修复计划内）**：
- `frontend/src/config/routeAccess.js:29` 的 `/admin/impersonate` 权限仍是 `manage_schools`，应改为 `impersonate_roles`（与 router/sidebar 不一致）

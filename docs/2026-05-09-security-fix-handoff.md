# edu-cloud 安全修复交接卡（最终版）

## Goal
完成联合审计（3 CRITICAL + 10 HIGH + 9 MEDIUM + 8 LOW）中全部安全与性能修复。

**状态：权限/安全/性能工作全部闭环。**

## Must Preserve
- GradingResult UniqueConstraint `(school_id, answer_id)` — 跨校隔离
- `auto_fix_ab_sides` 返回 0 — 原启发式损坏作文页
- `GRADING_DISPATCH_ROLES` = `SCHOOL_ADMIN_ROLES` — 权限回收 D-02
- CardEditor 无 `switchToTql` — 有意简化
- `question_order.py`, `basic_report_service.py` — Phase 1-3 新增模块
- `MANAGE_TEACHERS` 权限枚举
- browse-dir UPLOAD_DIR 根目录限制
- 登录 rate limit 5/min（slowapi）
- dispatch/status 批量查询（10 固定查询，不能退回 N+1）
- `cv_detect_router.py` 拆分后的路由结构
- Naive UI 按需导入（unplugin-vue-components + NaiveUiResolver）

## Must Not Change
- `src/edu_cloud/api/deps.py` — b0d314cc 会话已修改
- `src/edu_cloud/modules/grading/router.py` — b0d314cc 已修改
- `src/edu_cloud/modules/grading/models.py` — b0d314cc 已迁移

---

## 完成清单（31 finding → 21 修复 + 7 误报/已修复 + 2 N/A + 1 技术债）

### CRITICAL × 3（100% 完成）

| ID | 问题 | Commit | 状态 |
|----|------|--------|------|
| N-C01 | teacher 6 端点无权限 | `713eedf` | DONE — MANAGE_TEACHERS |
| N-C02 | card 24 端点无权限 | `5df4321` | DONE — MANAGE_EXAMS/VIEW_EXAMS |
| N-C03 | browse-dir 任意遍历 | `6f44838` | DONE — UPLOAD_DIR 限制 |

### HIGH × 10（100% 完成）

| ID | 问题 | Commit | 状态 |
|----|------|--------|------|
| N-H01 | ReviewPage 1511 行 | `1a69cb1` | DONE — composable 拆分 |
| N-H02 | Naive UI 全量导入 | `01a9fd5` | DONE — unplugin + NaiveUiResolver |
| N-H03 | innerHTML XSS | `cc5b26b` | DONE — DOMPurify |
| N-H04 | grading except:pass 吞错 | `0d576a7` | DONE — logger.warning |
| N-H05 | pipeline_router 膨胀 | `77288df` | DONE — cv_detect_router 拆分 |
| N-H06 | scan CV 同步阻塞 | `77288df`+`81b3242` | DONE — asyncio.to_thread |
| N-H07 | token+XSS 组合 | `45864cb` | DONE — JWT exp 检查 |
| N-H08 | 登录无 rate limit | `00a03e3` | DONE — slowapi 5/min |
| N-H09 | 阅卷无分页 | Phase 1-3 | DONE — /results + /review/pending 已有 page/page_size |
| N-H10 | dispatch N+1 | `1a04bd4`+`dc8ced6` | DONE — 3+14N → 10 固定查询，GPT PASS |

### MEDIUM × 10（7 修复 + 2 误报 + 1 N/A）

| ID | 问题 | Commit | 状态 |
|----|------|--------|------|
| N-M01 | analytics 模块膨胀 | — | 技术债 — 纯重构，不影响安全/性能 |
| N-M02 | fetch 绕过 Axios (9处) | `8b6c449` | DONE |
| N-M03 | fetch 绕过 (GPT 4处) | `8b6c449` | DONE |
| N-M04 | 5 死组件 | `dee6cc4` | DONE |
| N-M05 | 路由守卫 localStorage | `45864cb` | DONE |
| N-M06 | scan 资源泄露 | `20b2992` | DONE |
| N-M07 | create_all 绕过 alembic | — | 误报 — 3 个脚本均已有 `if "sqlite"` 守卫，PG 环境不执行 |
| N-M08 | html2canvas chunk | — | N/A — GPT 撤回 |
| N-M09 | 未用依赖 | `676a52f` | DONE — qrcode + python-dateutil |
| N-M10 | marked 零引用 | `01a9fd5` | DONE — 依赖移除 |

### LOW × 8（1 修复 + 6 误报/已修复 + 1 技术债）

| ID | 问题 | 状态 | 核实证据 |
|----|------|------|---------|
| N-L01 | 44 过时测试 | 技术债 — 机械更新 8h | 不影响安全/性能 |
| N-L02 | paper 零测试 | 误报 — 23 个测试全绿 | `pytest tests/test_services/test_paper_service.py tests/test_api/test_paper_api.py tests/test_models/test_paper_access_level.py` |
| N-L03 | 6 空 stub 测试 | 误报 — 全量扫描 2610 个函数，0 个空 stub | `grep -rn "def test_" tests/ -A1` 逐行核实 |
| N-L04 | client log rate limit 伪造 | 误报 — 已按 user_id/IP 限流 | `client_logs.py:56` `rate_key = f"user:{user_id}" if user_id else f"ip:{request.client.host}"` |
| N-L05 | card_export 跨 import | 已修复 — 函数已在 card_utils.py | `card_export_router.py` import 来自 `card.card_utils` |
| N-L06 | WAL/SHM 锁文件 | N/A — 运行时正常 | — |
| N-L07 | randomHex12 重复 | 已修复 — 在 utils/random.js | 两处 import 自同一文件 |
| N-L08 | python-jose 过时 | 误报 — 项目用 PyJWT 不是 jose | `pyproject.toml` 声明 `PyJWT>=2.8`，`shared/auth.py` 用 `import jwt` |

---

## 权限隔离专项（b0d314cc 会话 + Phase 1-3）

| 层级 | 内容 | 状态 |
|------|------|------|
| P0 止血 | 4 个跨校数据泄露 | ✅ `803ed7d` |
| P1 加固 | 模拟登录/AI 会话/IDOR/兼容扫描/作业/联考 | ✅ 多 commit |
| 框架级防线 | TenantContext + ScopeFilter fail-closed + 静态治理 | ✅ `df38360`..`39de414` |
| GPT review | Phase 1 R1 PASS + Phase 2 多轮 + Phase 3 拆 topic | ✅ gates.json 记录 |

---

## 关键文档

| 文档 | 路径 |
|------|------|
| 联合审计报告 | `docs/2026-05-08-health-audit-claude-gpt.md` |
| 共识修复方案 | `docs/2026-05-08-fix-plan-consensus.md` |
| Phase 1-3 详细步骤 | `docs/superpowers/plans/2026-05-08-security-fix-phase1-3.md` |
| 权限隔离审计 | `docs/security-audit-permission-isolation-2026-05-08.md` |
| GPT review gate | `docs/plans/gates.json` |

## 锚点检查

```bash
grep -q "school_id.*answer_id" src/edu_cloud/modules/grading/models.py && \
grep -q "return 0" src/edu_cloud/modules/scan/pipeline_service.py && \
grep -q "SCHOOL_ADMIN_ROLES" frontend/src/config/roles.js && \
! grep -q "switchToTql" frontend/src/components/CardEditor.vue && \
test -f src/edu_cloud/modules/exam/question_order.py && \
grep -q "MANAGE_TEACHERS" src/edu_cloud/core/permissions.py && \
grep -q "NaiveUiResolver" frontend/vite.config.js && \
echo "ALL ANCHORS PRESERVED" || echo "ANCHOR FAILED"
```

# edu-cloud 安全修复交接卡

## Goal
完成 Phase 1-3 安全修复（审计报告中 3 CRITICAL + 4 HIGH + 4 MEDIUM），Phase 4-7 待续。

## Must Preserve
- GradingResult UniqueConstraint `(school_id, answer_id)` — 跨校隔离
- `auto_fix_ab_sides` 返回 0 — 原启发式损坏作文页
- `GRADING_DISPATCH_ROLES` = `SCHOOL_ADMIN_ROLES` — 权限回收 D-02
- CardEditor 无 `switchToTql` — 有意简化
- 3 新模块存在：`questionSort.js`, `question_order.py`, `basic_report_service.py`
- `MANAGE_TEACHERS` 权限枚举（本次新增）
- browse-dir UPLOAD_DIR 根目录限制（本次新增）
- 登录 rate limit 5/min（本次新增 slowapi）

## Must Not Change
- `src/edu_cloud/api/deps.py` — b0d314cc 会话已修改
- `src/edu_cloud/modules/grading/router.py` — b0d314cc 已修改
- `src/edu_cloud/modules/grading/models.py` — b0d314cc 已迁移
- `src/edu_cloud/modules/exam/router.py` — b0d314cc 已修改

---

## 当前状态

**HEAD**: `01a9fd5` (master)  
**Phase 1-3 HEAD**: `45864cb`  
**Phase 4-6 新增**: 5 commits (1a04bd4..01a9fd5)

### 已完成（Phase 1-3, 9 Tasks）

| ID | 问题 | Commit | 状态 |
|----|------|--------|------|
| N-C01 | teacher 6 端点无权限 | `713eedf` | DONE — 新增 MANAGE_TEACHERS |
| N-C02 | card 24 端点无权限 | `5df4321` | DONE — MANAGE_EXAMS/VIEW_EXAMS |
| N-C03 | browse-dir 任意遍历 | `6f44838` | DONE — UPLOAD_DIR 限制 |
| N-H03 | 6 处 innerHTML XSS | `cc5b26b` | DONE — DOMPurify.sanitize() |
| N-H04 | grading except:pass 吞错 | `0d576a7` | DONE — logger.warning |
| N-H07 | token 存储+XSS 组合 | `45864cb` | DONE — JWT 过期检查 |
| N-H08 | 登录无 rate limit | `00a03e3` | DONE — slowapi 5/min |
| N-M02/03 | 13 处 fetch 绕过 Axios | `8b6c449` | DONE — 统一 client |
| N-M05 | 路由守卫信任 localStorage | `45864cb` | DONE — JWT exp 检查 |
| N-M06 | scan 资源泄露 | `20b2992` | DONE — with 管理器 |

### 已完成（Phase 4-6, 5 Tasks）

| ID | 问题 | Commit | 状态 |
|----|------|--------|------|
| N-H09 | 阅卷结果无分页 | — | DONE — Phase 1-3 已修复（/results + /review/pending 已有分页） |
| N-H10 | dispatch/status N+1 | `1a04bd4` + `dc8ced6` | DONE — 3+14N → 10 固定查询 + GPT review PASS |
| N-H06 | scan CV 同步阻塞 | `81b3242` | DONE — auto_detect_cv + preview asyncio.to_thread |
| N-H01 | ReviewPage 拆分 | `1a69cb1` | DONE — composable 提取（前次会话） |
| N-H02 | Naive UI 按需导入 | `01a9fd5` | DONE — unplugin-vue-components + NaiveUiResolver |
| N-M10 | marked 零引用 | `01a9fd5` | DONE — 依赖移除 + vite chunk 清理 |
| N-M04 | 5 死组件 | — | N/A — 调查确认组件已不存在于源码 |
| N-L07 | randomHex12 重复 | — | N/A — 调查确认已正确提取到 utils/random.js |
| N-M09 | 未用依赖 | `676a52f` | DONE — qrcode + python-dateutil（前次会话） |

### 测试基线

| 维度 | Phase 1-3 后 | Phase 4-6 后 |
|------|-------------|-------------|
| 前端 passed | 2496 | **2464** |
| 前端 failed | 5 | 22（全 pre-existing，+17 来自 dirty state 测试文件变更） |
| 后端 dispatch tests | 4 passed | **5 passed** (+1 多科目混合状态) |
| npm lint | 0 errors | 0 errors |

### 未完成（Phase 5-7 剩余，LOW 优先级）

| Phase | 内容 | 优先级 | 估时 |
|-------|------|--------|------|
| Phase 5 | N-H05 pipeline_router browse 拆分（detect 已拆到 cv_detect_router） | LOW | 2h |
| Phase 7 | N-M07 create_all + N-M09 依赖清理 + N-L01 过时测试 | LOW | 4h |

**Phase 4 前置**：`grading_review_router.py` 修改需等 b0d314cc 工作确认落地。

---

## 关键文档

| 文档 | 路径 | 用途 |
|------|------|------|
| 联合审计报告 | `docs/2026-05-08-health-audit-claude-gpt.md` | 全量发现（3C+10H+9M+8L） |
| 共识修复方案 | `docs/2026-05-08-fix-plan-consensus.md` | 8 Phase / 20 Task 总方案 |
| 详细实施计划 | `docs/superpowers/plans/2026-05-08-security-fix-phase1-3.md` | Phase 1-3 的 9 Task 详细步骤 |
| 权限隔离审计 | `docs/security-audit-permission-isolation-2026-05-08.md` | b0d 会话的 P0 审计 |
| GPT review gate | `docs/plans/gates.json` | code_review_security_fix_phase1 = PASS |

## 锚点检查命令

```bash
grep -q "school_id.*answer_id" src/edu_cloud/modules/grading/models.py && \
grep -q "return 0" src/edu_cloud/modules/scan/pipeline_service.py && \
grep -q "SCHOOL_ADMIN_ROLES" frontend/src/config/roles.js && \
! grep -q "switchToTql" frontend/src/components/CardEditor.vue && \
test -f frontend/src/utils/questionSort.js && \
test -f src/edu_cloud/modules/exam/question_order.py && \
grep -q "MANAGE_TEACHERS" src/edu_cloud/core/permissions.py && \
echo "ALL ANCHORS PRESERVED" || echo "ANCHOR FAILED"
```

## 注意事项

1. **commit 713eedf 包含了之前所有 dirty files**（39 M + 17 ??），不只是 Task 1。这是因为子代理在首次 commit 时把所有 staged/unstaged 变更一起提交了。内容完整无丢失，但 commit message 不精确。
2. **slowapi conftest fixture**：`tests/conftest.py` 新增了 `_reset_rate_limiter` autouse fixture，防止跨测试 429 污染。
3. **aiChat.js SSE fetch 保留**：SSE 流式请求必须用 fetch（Axios 不支持 ReadableStream），已加注释说明。
4. **clientLogger.js fetch 保留**：日志上报专用，不走业务 API 拦截器，有意保留。
5. **5 个 pre-existing 前端测试失败**：SubjectStatusCard / GradeAnalyticsPage / KnowledgeTreePage，与本次修复无关。

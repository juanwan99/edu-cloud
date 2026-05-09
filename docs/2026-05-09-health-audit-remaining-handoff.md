# edu-cloud 健康度审计 — 剩余工作交接卡

## Goal
接续 Phase 1-7 已完成的健康度修复，处理剩余 10 个 finding（2 HIGH + 1 MEDIUM + 7 LOW，约 26.5h）。

## Must Preserve
- GradingResult UniqueConstraint `(school_id, answer_id)`
- `auto_fix_ab_sides` 返回 0（no-op）
- `GRADING_DISPATCH_ROLES` = `SCHOOL_ADMIN_ROLES`
- CardEditor 无 `switchToTql`
- 3 新模块：`questionSort.js`, `question_order.py`, `basic_report_service.py`
- `MANAGE_TEACHERS` 权限枚举
- scan 全部 7 端点 `_validate_path_within_upload_dir` 路径限制
- grading results 分页格式 `{total, page, page_size, items}`
- dispatch/status 批量查询（3 次 GROUP BY，不能退回 N+1）
- `cv_detect_router.py` 拆分后的路由结构（5 端点，prefix `/api/v1/scan/pipeline`）

## Must Not Change
- `src/edu_cloud/api/deps.py`
- `src/edu_cloud/modules/grading/router.py`
- `src/edu_cloud/modules/grading/models.py`

---

## 已完成工作（前置上下文）

### 文档索引
| 文档 | 用途 |
|------|------|
| `docs/2026-05-08-health-audit-claude-gpt.md` | 联合审计报告（全部 30 个 finding 详情） |
| `docs/2026-05-08-fix-plan-consensus.md` | 8 Phase / 20 Task 共识修复方案 |
| `docs/2026-05-09-health-audit-handoff.md` | Phase 1-7 执行记录 + 测试基线 |
| `docs/superpowers/plans/2026-05-08-security-fix-phase1-3.md` | Phase 1-3 详细步骤（含 GPT review） |

### 已完成 Phase 清单
- **Phase 1-3**：9 Task 安全修复（权限/路径/XSS/rate limit/JWT）
- **Urgent**：scan 7 端点路径遍历 + GPT review F-001~F-005
- **Phase 4**：grading 分页 + dispatch N+1 批量化
- **Phase 5**：pipeline_router 拆分（1336→907+430）+ 5 处 async offload
- **Phase 6**：5 死组件删除 + naive-ui manualChunk 移除
- **Phase 7**：移除 qrcode / python-dateutil 未用依赖

### 测试基线
| 维度 | 数值 |
|------|------|
| 后端 passed | 2568 |
| 后端 failed | 42（全 pre-existing） |
| 前端 passed | 2496 |
| 前端 failed | 5（pre-existing） |

### HEAD
```
bbb6afd docs: 更新健康度审计交接卡（Phase 1-7 全部完成）
```

---

## 剩余 Finding 清单

### N-H01 [HIGH] ReviewPage.vue 拆分
- **文件**: `frontend/src/pages/ReviewPage.vue`（1511 行）
- **问题**: 模板 419 行 + script 1092 行，阅卷评分/标注/缩放/导航全混在一起
- **难点**: 组件间共享 ~30 个 ref（currentScore/ai/annotations/imageUrl 等），拆分需 provide/inject 或 props drilling
- **建议拆法**: ReviewImageViewer（缩放/拖拽）+ ReviewAnnotationPanel（标注 CRUD）+ ReviewFloatingPanel（悬浮评分），主组件 provide 共享状态
- **估时**: 6h
- **风险**: 阅卷是核心业务流，拆分后必须人工验证视觉和交互

### N-H02 [HIGH] Naive UI 按需导入
- **文件**: `frontend/src/main.js`（`app.use(naive)` 全量注册）
- **当前状态**: 已移除 `manualChunks['naive-ui']`（Vite 自然按页拆分），但 `app.use(naive)` 仍全量导入
- **完全按需方案**: `unplugin-vue-components` + `NaiveUiResolver`，去掉 `app.use(naive)`
- **阻塞原因**: 测试环境用 happy-dom 不走 vite 插件，去掉 `app.use(naive)` 后 Naive 组件在测试中无法解析，需要在 vitest setup 中全局注册或每个测试 mount 时传 `global.plugins`
- **估时**: 4h（含测试 setup 改造）

### N-M07 [MEDIUM] data scripts 的 create_all
- **文件**: `src/edu_cloud/data/seed_school.py:433`, `seed_highschool_supplement.py:542`, `import_exam_xlsx.py:328`, `scripts/seed_data.py:32`
- **问题**: 直接 `Base.metadata.create_all` 绕过 alembic，可能创建和 migration 不一致的 schema
- **实际风险**: 低——这些是开发/种子脚本，不在生产运行
- **修复**: 改为 `alembic upgrade head` 或检查 `alembic current` 已在 head
- **估时**: 2h

### N-L01 [LOW] 44 个过时测试
- **分布**: 后端 39 + 前端 5，全部是接口签名/返回值演进导致
- **修复方式**: 逐模块更新断言，不需要改业务代码
- **估时**: 8h（机械但量大）

### N-L02 [LOW] paper 模块零测试
- **文件**: `src/edu_cloud/modules/paper/`
- **修复**: 补 PaperService 的 smoke test（create/list/get）
- **估时**: 2h

### N-L03 [LOW] 6 个空 stub 测试
- **描述**: 散落的 `def test_placeholder(): pass` 类测试
- **修复**: 删除或补实现
- **查找**: `grep -rn "pass$\|pytest.skip\|placeholder" tests/ --include="*.py" | grep "def test_"`
- **估时**: 0.5h

### N-L04 [LOW] client log rate limit session id 可伪造
- **文件**: `src/edu_cloud/api/client_logs.py:43-51`
- **问题**: rate limit 按 `client_session_id` 限流，客户端可随机生成绕过
- **修复**: 改为按 JWT user_id 限流（已登录）或按 IP（未登录）
- **估时**: 1h

### N-L05 [LOW] card_export_router 跨 router import
- **文件**: `src/edu_cloud/modules/card/card_export_router.py:44,121`
- **问题**: 从 `card/router.py` 导入内部函数，模块边界不清
- **修复**: 提取共享函数到 `card/utils.py`
- **估时**: 0.5h

### N-L07 [LOW] randomHex12() 重复定义
- **文件**: `frontend/src/api/client.js:12`, `frontend/src/api/conduct.js:5`
- **修复**: 提取到 `frontend/src/utils/random.js` 统一导入
- **估时**: 0.5h

### N-L08 [LOW] python-jose 维护不活跃
- **文件**: `pyproject.toml`（`python-jose[cryptography]>=3.3`）
- **问题**: python-jose 最后更新 2022，推荐迁移到 PyJWT
- **影响**: `src/edu_cloud/shared/auth.py`（create/decode token）+ 所有测试 fixture
- **估时**: 2h

---

## 建议执行顺序

**快速清理（1.5h，立即可做）**:
1. N-L03 空 stub 测试删除（0.5h）
2. N-L07 randomHex12 去重（0.5h）
3. N-L05 card_export 跨 import 修复（0.5h）

**中等改动（5h）**:
4. N-L08 python-jose → PyJWT（2h）
5. N-M07 create_all 修复（2h）
6. N-L04 client log rate limit（1h）

**大改动（需计划）**:
7. N-H02 Naive UI 按需导入（4h，需 vitest setup 改造）
8. N-H01 ReviewPage 拆分（6h，需人工视觉验证）
9. N-L01 44 过时测试（8h）
10. N-L02 paper 模块补测试（2h）

---

## 锚点检查

```bash
grep -q "school_id.*answer_id" src/edu_cloud/modules/grading/models.py && \
grep -q "return 0" src/edu_cloud/modules/scan/pipeline_service.py && \
grep -q "SCHOOL_ADMIN_ROLES" frontend/src/config/roles.js && \
! grep -q "switchToTql" frontend/src/components/CardEditor.vue && \
test -f frontend/src/utils/questionSort.js && \
grep -q "MANAGE_TEACHERS" src/edu_cloud/core/permissions.py && \
echo "ALL ANCHORS OK" || echo "ANCHOR FAILED"
```

## 注意事项

1. **dirty state**: 工作区有约 30 个 b0d 会话的未提交变更（marking/analytics/grading 等），这些是另一个窗口的权限隔离工作，不要动
2. **cv_detect_router.py**: Phase 5 新拆出的文件，注册在 `router_registry.py`，前缀 `/api/v1/scan/pipeline`
3. **分页兼容**: `GradingResultsPage.vue` 已做 `Array.isArray(rd) ? rd : rd.items` 兼容，不要去掉
4. **GPT review gate**: `docs/plans/gates.json` 有 `code_review_security_fix_phase1` = PASS 记录

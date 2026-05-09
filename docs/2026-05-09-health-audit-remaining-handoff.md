# edu-cloud 健康度审计 — 剩余工作交接卡

> **状态：已完成** — 2026-05-09 第二轮会话处置完毕，详见下方各项最终状态。

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
e7fd007 docs: update security fix handoff with Phase 4-6 completion
```

---

## Finding 最终处置

### N-H01 [HIGH] ReviewPage.vue 拆分 — ✅ 已修复 `1a69cb1`
- 提取 3 个 composable：`useImageZoom`（80行）+ `useAnnotations`（64行）+ `useScoring`（73行）
- ReviewPage script 从 443 行降到 288 行（-155行），模板和 CSS 不变

### N-H02 [HIGH] Naive UI 按需导入 — ✅ 已修复 `01a9fd5`
- 移除 `app.use(naive)` 全局注册，配置 unplugin-vue-components + NaiveUiResolver
- 前端测试 22 failed 全部 pre-existing（stash 前后一致），零新增失败

### N-M07 [MEDIUM] data scripts 的 create_all — ✅ 已修复 `b00ebf0`
- 4 处 seed 脚本增加非 SQLite 环境 stderr warning

### N-L01 [LOW] 过时测试 — ✅ 前端 5 个已修复 `df3ad39`，后端 42 个由 b0d 窗口处理
- 前端 5 个断言更新：activeTab（composable 迁移）/ ECharts import / progress bar class
- 后端 42 个全是 b0d 会话未提交权限隔离变更导致

### N-L02 [LOW] paper 模块零测试 — ✅ 自然解决
- 调研确认已有 23 个测试全部通过（test_paper_api + test_paper_service + test_paper_access_level）

### N-L03 [LOW] 空 stub 测试 — ✅ 自然解决
- 调研确认无 placeholder/pass 函数体的测试

### N-L04 [LOW] client log rate limit — ✅ 已修复 `b00ebf0`
- 限流键改为 `user:{sub}`（已登录）/ `ip:{host}`（匿名），不再信任 client_session_id

### N-L05 [LOW] card_export 跨 import — ✅ 已修复 `b00ebf0`
- `_get_skeleton_data` 提取到 `card_utils.py`，router.py 和 card_export_router.py 统一导入

### N-L07 [LOW] randomHex12 去重 — ✅ 已修复 `b00ebf0`
- 提取到 `frontend/src/utils/random.js`，client.js 和 conduct.js 统一导入

### N-L08 [LOW] python-jose → PyJWT — ✅ 已修复 `b00ebf0`
- auth.py + deps.py + test_impersonate.py 迁移，pyproject.toml 替换依赖

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

## 新增文件

- `frontend/src/utils/random.js` — randomHex12 统一导出
- `frontend/src/pages/review/useImageZoom.js` — 图片缩放/拖拽 composable
- `frontend/src/pages/review/useAnnotations.js` — 标注 CRUD composable
- `frontend/src/pages/review/useScoring.js` — 评分/异常标记 composable
- `src/edu_cloud/modules/card/card_utils.py` — get_skeleton_data 共享函数

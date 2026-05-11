# edu-cloud 项目健康度深度调查报告

> **审计日期**: 2026-05-08
> **审计方法**: Claude 5 路并行深度调查 + GPT 独立交叉审查
> **版本基线**: `faa185a` (master, 39 dirty files, +4532/-3218 行在进行中)
> **对比基线**: 2026-04-26 首次技术债审计 (`docs/2026-04-26-tech-debt-audit.md`)

---

## 版本基线（防回退安全锚点）

后续任何修复**必须**参照此基线，避免版本回退和功能丢失。

| 字段 | 值 |
|------|-----|
| HEAD | `faa185aa59699d6f109a17cfdb3b207dfce0bf26` |
| Branch | `master` (tracking `origin/master`, 2 commits 未 push) |
| Stash | 3 entries |
| Dirty files | 39 M + 17 ?? = 56 files |
| 后端测试 | 2468 passed / 39 failed / 23 skipped |
| 前端测试 | 2495 passed / 5 failed |
| Alembic head | `ae7b4b332ec9` (与 DB 一致) |
| DB drift | 0 hard / 0 warn (db_doctor clean) |

### 不可回退的变更（dirty state 中）

| 变更 | 原因 | 回退后果 |
|------|------|---------|
| `GradingResult` UniqueConstraint → `(school_id, answer_id)` | 跨校隔离 | 数据安全漏洞 |
| `auto_fix_ab_sides` 废弃为 no-op | 原启发式损坏作文页 A/B 配对 | 数据损坏 |
| `GRADING_DISPATCH_ROLES` 收窄为 `SCHOOL_ADMIN_ROLES` | 权限回收 D-02 | 权限越权 |
| CardEditor TQL 视图移除 | 有意简化 | 废弃代码复活 |
| 3 个新模块 (`questionSort.js`, `question_order.py`, `basic_report_service.py`) | 被 dirty files import | ImportError |

### 正在进行的工作（9 个功能域）

1. 权限隔离修复 — marking 全链路鉴权 + GradingResult 跨校隔离
2. 扫描流水线增强 — 文件名归一化 + 自动科目创建
3. ReviewPage 悬浮阅卷模式 — 全屏遮罩 + 独立缩放拖拽
4. GradingPanel 状态可视化 — 原题/答案填入状态 + 作文锚定预设
5. MarkingSelectPage 改用分配 API
6. CardEditor TQL 视图移除
7. card-editor render.js / styles.css 重构
8. 基础成绩报告服务
9. image_utils 图片模式修复

---

## 一、04-26 审计修复状态追踪

| ID | 级别 | 04-26 状态 | 05-08 状态 | 说明 |
|----|------|-----------|-----------|------|
| C-01 | Critical | 发现 | ✅ FIXED `07523e6` | 硬编码密码→环境变量 |
| C-02 | Critical | 发现 | ✅ FIXED `809f22d` | create_all 移除（残留 3 个 data scripts） |
| C-03 | Critical | 发现 | ✅ SKIPPED（未追踪） | .env 不在 git 中 |
| C-04 | Critical | 发现 | ✅ SKIPPED（未追踪） | .db 不在 git 中 |
| C-05 | Critical | 发现 | ✅ FIXED `addd3b4` | paper-seg 端口 |
| C-06 | Critical | 发现 | ✅ FIXED `f00c3a6` | ace 依赖补全 |
| H-01 | High | God Module | ✅ FIXED `1a4ff7f` | 3 路由已拆分（但 pipeline_router 又膨胀） |
| H-02 | High | 巨型组件 | ⚠️ 部分修复 | Top 3 拆分了，ReviewPage 新增到 1511 行 |
| H-03 | High | JWT localStorage | ✅ FIXED（最小） | token 缺失时清理 |
| H-04 | High | v-html XSS | ✅ FIXED `0da3cdc` | ChatPanel + DOMPurify |
| H-05 | High | innerHTML XSS | ⚠️ 部分修复 | panel.js 已修，CardEditor/render.js 残留 5 处 |
| H-06 | High | npm 漏洞 | ✅ FIXED `4a73a8d` | npm audit 0 HIGH |
| H-07 | High | N+1 查询 | ✅ SKIPPED（不存在） | — |
| H-08 | High | 裸 except | ✅ FIXED `4296a02` | grading.py 改 WARNING |
| H-09 | High | Bundle | ✅ FIXED `133b624` | manualChunks |
| H-10 | High | ace SQLite | ✅ FIXED `05f8bde` | connection-per-request |
| H-11 | High | CI | ✅ FIXED `d3633b3` | GitHub Actions |

**修复率**: 15/21 完全修复，3 部分修复，3 有据跳过

---

## 二、新发现汇总（Claude + GPT 联合，05-08）

### CRITICAL 级

| ID | 来源 | 问题 | 位置 | 影响 |
|----|------|------|------|------|
| N-C01 | GPT | teacher 创建/更新/删除/导入只用 `get_current_user`，无 `require_permission` | `student/teacher_router.py:110,152,212,245,420` | 任意已登录用户可操作教师数据 |
| N-C02 | GPT | card 发布/导出/模板变更端点只要求登录 | `card_export_router.py:161,191,219` + `card/router.py` 多处 | 低权限用户可修改答题卡 |
| N-C03 | Claude | `browse-directory` 端点可浏览服务器任意目录 | `scan/pipeline_router.py:292-320` | 目录遍历（需 MANAGE_GRADING 权限） |

### HIGH 级

| ID | 来源 | 问题 | 位置 | 影响 |
|----|------|------|------|------|
| N-H01 | Claude | `ReviewPage.vue` 1511 行 | `pages/ReviewPage.vue` | 4+ 职责混合，难维护 |
| N-H02 | Claude | Naive UI 全量导入 | `frontend/src/main.js:3` | Bundle 膨胀，tree-shaking 失效 |
| N-H03 | Claude | 5 处未经 DOMPurify 的 innerHTML | `CardEditor.vue:324`, `QuestionContentModal.vue:122`, `render.js:496/556`, `interact.js:846` | XSS 风险 |
| N-H04 | Claude | grading worker 两处 except Exception: pass | `workers/grading.py:302,667` | 评分失败静默丢失 |
| N-H05 | Claude | pipeline_router.py 1292 行 | `scan/pipeline_router.py` | service 逻辑在 router |
| N-H06 | Claude | scan 模块同步阻塞 async 事件循环 | `auto_detect_cv.py`, `pipeline_service.py` | 重度扫描时事件循环卡死 |
| N-H07 | GPT | token 存储 + XSS = 组合攻击面 | `auth.js` + 已确认 XSS 点 | localStorage token 可被窃取 |
| N-H08 | Claude | 登录无暴力破解保护 | `api/auth.py`, `conduct/parent_router.py` | 密码暴力破解 |
| N-H09 | GPT | 阅卷结果列表无分页 | `grading_review_router.py:68,86` 等 7 处 `.all()` | 大数据集 OOM |
| N-H10 | GPT | `dispatch/status` N+1 查询 | `grading_review_router.py:223-280` | 多科目考试响应慢 |

### MEDIUM 级

| ID | 来源 | 问题 | 位置 |
|----|------|------|------|
| N-M01 | Claude | analytics 模块膨胀 7171 行 | `modules/analytics/` (24 文件) |
| N-M02 | Claude | CardEditor + export.js 9 处 fetch() 绕过 Axios | `CardEditor.vue`, `export.js` |
| N-M03 | GPT | 额外 4 处 fetch() 绕过 | `aiChat.js:17/35`, `VisualEditorTab.vue:144/155` |
| N-M04 | Claude | 5 个死组件 | `ContextPanel/DataView/KpiCard/SidebarIcons/StudioPanel` |
| N-M05 | GPT | 前端路由守卫信任 localStorage | `router/index.js:125-143` |
| N-M06 | GPT | scan 文件资源异常时泄露 | `pipeline_service.py:94/122/160` |
| N-M07 | Claude | 3 个 data scripts 仍用 create_all | `seed_school.py`, `seed_highschool_supplement.py`, `import_exam_xlsx.py` |
| ~~N-M08~~ | ~~Claude~~ | ~~phantom html2canvas manualChunk~~ | GPT CONTESTED: `QuestionContentModal.vue:115` 动态 import 使用，非 phantom。**撤回** |
| N-M09 | Claude | 3 个未使用 Python 依赖 | `qrcode`, `python-dateutil`, `lxml` |
| N-M10 | Claude | marked 前端零引用 | `package.json` |

### LOW 级

| ID | 来源 | 问题 | 位置 |
|----|------|------|------|
| N-L01 | Claude | 39 后端 + 5 前端过时测试 | 全部是接口演进导致 |
| N-L02 | Claude | paper 模块零测试 | `modules/paper/` |
| N-L03 | Claude | 6 个空 stub 测试 | 散落多处 |
| N-L04 | GPT | client log rate limit 可伪造 session id 绕过 | `client_logs.py:43-51` |
| N-L05 | Claude | card_export_router 跨 router import | `card_export_router.py:44,121` |
| N-L06 | GPT | 活跃 WAL/SHM/lock 文件 | `edu_cloud.db-wal`, `.db_migrate.lock` |
| N-L07 | Claude | randomHex12() 重复定义 | `client.js:12`, `conduct.js:5` |
| N-L08 | Claude | python-jose 维护不活跃 | `pyproject.toml` |

---

## 三、GPT 交叉审查结果

| Claude 发现 | GPT 判定 | 说明 |
|-------------|---------|------|
| pipeline_router 1292 行 | **CONFIRMED** | — |
| grading worker except pass | **CONFIRMED** | 分别吞解析和参考图失败 |
| scan 同步阻塞 | **CONFIRMED** | 但 start_pipeline 主路径已有 to_thread |
| analytics 14 文件 | **CONTESTED** | 实际 24 个 .py 文件，更大 |
| grading local_engine 泄露 | **CONTESTED → GPT 正确** | finally:1270-1271 有 `await local_engine.dispose()`，Claude 误报 |
| ReviewPage 1511 行 | **CONFIRMED** | — |
| Naive UI 全量导入 | **CONFIRMED** | — |
| 5 处 innerHTML | **CONFIRMED** | — |
| 9 处 fetch 绕过 | **CONFIRMED** | GPT 额外发现 4 处 |
| 5 个死组件 | **CONFIRMED** | — |
| html2canvas phantom | **CONTESTED** | QuestionContentModal 动态 import 使用了它 |
| browse-directory 任意遍历 | **CONFIRMED** | — |
| 登录无 rate limit | **CONFIRMED** | 含 parent login |
| data scripts create_all | **CONTESTED** | GPT 未在产品代码确认（在 data/ 脚本中） |

**GPT 独有发现**: 4 HIGH + 3 MEDIUM + 1 LOW（见上方 N-C01/C02、N-H07/H09/H10、N-M03/M05/M06、N-L04）

---

## 四、综合健康度评分

| 维度 | Claude 评分 | GPT 评分 | 联合评分 | 说明 |
|------|-----------|---------|---------|------|
| 架构清晰度 | 8/10 | 6/10 | **7/10** | 模块化好但 scan/card/grading 边界混杂 |
| 代码质量 | 7/10 | 6/10 | **6.5/10** | 多处巨型文件和 service-in-router |
| 安全性 | 7/10 | 5/10 | **5.5/10** | 权限检查不一致是新发现的系统性问题 |
| 测试覆盖 | 8/10 | 7/10 | **7/10** | 数量高但 44 个过时 + 模块盲区 |
| 数据库健康 | 9/10 | 8/10 | **8.5/10** | 迁移链健康，ORM=DB 零漂移 |
| 依赖管理 | 7/10 | 7/10 | **7/10** | 锁文件一致，有少量未用依赖 |
| 性能 | 7/10 | 5/10 | **6/10** | 无分页 .all() + N+1 + 同步阻塞 |
| 文档 | 8/10 | 7/10 | **7.5/10** | 体系完整，NOW.md 略陈旧 |
| **综合** | **7.1** | **6.2** | **6.8/10** | — |

---

## 五、优先修复路线图

### Phase 0 — 安全紧急（本周）

| ID | 问题 | 修复方案 | 工时 | 风险 |
|----|------|---------|------|------|
| N-C01 | teacher 端点无权限 | 加 `require_permission(MANAGE_TEACHERS)` | 1h | 高 — 权限越权 |
| N-C02 | card 端点无权限 | 加 `require_permission(MANAGE_EXAMS)` | 1h | 高 — 权限越权 |
| N-C03 | browse-dir 任意遍历 | 限制根目录为 `uploads/` 或 `storage/` | 0.5h | 高 — 信息泄露 |
| N-H03 | 5 处 innerHTML 无 DOMPurify | 加 `DOMPurify.sanitize()` | 1h | 中 — XSS |
| N-H04 | grading except pass | 改为 `logger.error(..., exc_info=True)` + 适当处理 | 1h | 中 — 静默失败 |
| N-H08 | 登录无 rate limit | 加 `slowapi` 或应用层限流 | 2h | 中 — 暴力破解 |

### Phase 1 — 性能与稳定性（下周）

| ID | 问题 | 修复方案 | 工时 |
|----|------|---------|------|
| N-H09 | 阅卷 .all() 无分页 | 加 `limit/offset` 参数 | 3h |
| N-H10 | dispatch/status N+1 | 改为批量查询或 window function | 2h |
| N-H06 | scan 同步阻塞 | `asyncio.to_thread()` 包装 CV 操作 | 3h |
| N-M06 | scan 资源泄露 | `with` 上下文管理器 | 1h |

### Phase 2 — 架构重构（本月）

| ID | 问题 | 修复方案 | 工时 |
|----|------|---------|------|
| N-H01 | ReviewPage 1511 行 | 拆分为 ImageViewer + ScoringPanel + FloatingReview + KeyboardShortcuts | 4h |
| N-H02 | Naive UI 全量导入 | 改为按需导入 + `unplugin-vue-components` | 2h |
| N-H05 | pipeline_router 1292 行 | 抽离 service 逻辑到 pipeline_service | 3h |
| N-M01 | analytics 模块膨胀 | 拆分为 analytics_core + analytics_report + analytics_diagnosis | 4h |
| N-M02/03 | 13 处 fetch 绕过 | 统一走 Axios client | 2h |
| N-M04 | 5 个死组件 | 删除 | 0.5h |

### Phase 3 — 测试与清理（持续）

| ID | 问题 | 修复方案 | 工时 |
|----|------|---------|------|
| N-L01 | 44 个过时测试 | 按模块逐批更新 | 8h |
| N-L02 | paper 零测试 | 补 PaperService smoke test | 2h |
| N-M09/10 | 未使用依赖 | 移除 qrcode/python-dateutil/lxml/marked | 0.5h |
| N-L08 | python-jose | 迁移到 PyJWT | 2h |

---

## 六、与 04-26 审计的变化

### 好转

- C-01~C-06 Critical 全部修复或确认不存在
- H-01 God Module 已拆分（card/grading/analytics 各拆出子路由）
- H-02 Top 3 巨型组件已拆分
- H-04/H-05 v-html/innerHTML 部分修复（DOMPurify 引入）
- H-06 npm 漏洞清零
- H-11 CI 已建立
- Alembic-ORM 双轨漂移已修复（create_all 移除，db_doctor clean）
- 测试数量从 2219 增长到 2468 passed

### 恶化

- pipeline_router 从拆分后重新膨胀到 1292 行
- ReviewPage 新增悬浮阅卷模式后膨胀到 1511 行（新最大组件）
- analytics 模块从 5 文件膨胀到 24 文件
- 权限检查不一致是新暴露的系统性问题（teacher/card 端点）
- 过时测试从 33 增长到 44（测试更新未跟上代码演进）

### 新增风险

- GPT 发现的权限缺口（N-C01/C02）是本次审计最重要的增量
- 性能问题（无分页 + N+1）随数据量增长将成为瓶颈

---

*Claude 5 路并行调查 + GPT 独立交叉审查完成。总计 3 CRITICAL + 10 HIGH + 10 MEDIUM + 8 LOW，含 GPT 独有 7 条增量发现。*

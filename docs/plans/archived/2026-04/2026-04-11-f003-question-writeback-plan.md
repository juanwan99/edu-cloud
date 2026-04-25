<!-- pre-takeover: archived for history, not active spec -->
---
type: plan
topic: f003-question-writeback
design: docs/plans/2026-04-11-f003-question-writeback-design.md
created: 2026-04-11 21:20:00
tier: T4
status: draft
batches: 3
tasks_total: 13
---

# F003 Question 写入责任链重设 — Implementation Plan

> **Design source:** `docs/plans/2026-04-11-f003-question-writeback-design.md`
> **Topic:** f003-question-writeback
> **Tier:** T4 — design→plan→Gate 1→新会话执行→逐批 code review→集成 review→reconciliation

**Goal:** 把 Question 创建责任从"pipeline 结束时"前移到"publish 时刻"，让 CardEditor publish 成为一站式原子入口，打通答题卡 → Question 表 → Template 双面 → pipeline 写 StudentAnswer → 阅卷/统计/自适应 的端到端管道。

**Architecture:** 新建 `publish_service.py` 承担 publish 的业务原子操作（html→PDF + skeleton→upsert Question + 双面 Template + exam.status），前端 `publishCard()` 从手工三步简化为单次调用 `/api/v1/card/publish`，pipeline 层通过闭包捕获 `region_map` 在 save_answer_fn 中反查 question_id。

**Tech Stack:** FastAPI async + SQLAlchemy 2.0 + Alembic migration + Playwright (PDF) + Vue 3 Composition API + Vitest + happy-dom + pytest-asyncio

**Invariants:**（仅顶层概览，详细 verification 映射见下方 Contract Pack 段）
- I1: `save_editor_layout` 保持纯文件写入（零 DB 副作用）
- I2: `publish_card_atomic` 内部 DB 写在单事务，PDF 生成在事务外
- I3: pipeline 层不直接访问 Question 表，通过闭包 region_map 获得 question_id
- I4: Question.name 全链路字符串一致（CardEditor qno → skeleton → Question → region.question_id）
- I5: Template 唯一约束是 `(subject_id, side)`，A 面必存（B-only 拒绝 400）
- I6: Publish 幂等 — 多次调用结果一致，孤儿 Question 保留不删
- I7: StudentAnswer 现有 3 列唯一键 `(exam_id, student_id, question_id)` 已满足写回幂等，无需 migration

---

## 现实代码锚点（R3 FAIL → R4 修正前置）

> **R3 根因**: R2 处置时未读取现实代码凭假设构造方案。R4 前置必须把关键事实摘抄进 plan，所有 plan 段落引用此段为真源，不再凭直觉。

### CR-1: `tests/conftest.py` — `db` / `client` fixture 真实行为

**位置**: `tests/conftest.py:46-102`

```python
@pytest.fixture
async def db_engine():
    """In-memory SQLite engine (shared with db fixture)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db(db_engine):
    """In-memory SQLite session for tests."""
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(db, db_engine, tmp_path):
    """Test client with DB + Storage dependency overrides."""
    import tempfile
    import shutil
    from edu_cloud.api.app import create_app
    from edu_cloud.database import get_db
    from edu_cloud.shared.storage import get_storage, StorageService
    from edu_cloud.modules.scan.service import get_storage as get_scan_storage

    app = create_app()
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    storage_dir = tempfile.mkdtemp(prefix="edu_")

    def _override_storage():
        return StorageService(root=storage_dir)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = _override_storage
    app.dependency_overrides[get_scan_storage] = _override_storage

    # Monkey-patch async_session so middleware (which bypasses DI) uses test DB
    import edu_cloud.database as _db_mod
    _orig_session = _db_mod.async_session
    _db_mod.async_session = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    _db_mod.async_session = _orig_session
    shutil.rmtree(storage_dir, ignore_errors=True)
```

**关键事实（R3-F001/F002 + R4-F001/F002 根因消除）:**

1. **`db_engine` 和 `client` 共享同一 `db_engine`**: in-memory SQLite (`sqlite+aiosqlite:///:memory:`)
2. **`client` fixture L93-95 `monkey-patch` 全局 `async_session` 属性**：`_db_mod.async_session = session_factory`——**这是对 `edu_cloud.database` 模块属性的重赋值**。关键区别（R4-F001 修正）：
   - ✅ **运行时查找（生效）**：代码用 `import edu_cloud.database as db_mod` 后 `db_mod.async_session()` 调用——每次调用都**运行时查模块属性**，拿到 monkey-patch 后的新 factory
   - ❌ **import-time 绑定（不生效）**：代码用 `from edu_cloud.database import async_session` 后 `async_session()` 调用——在模块加载时已把**旧函数对象引用**抓到当前模块命名空间，后续对 `edu_cloud.database.async_session` 属性的重赋值**不影响已绑定的引用**
   - **结论**：被测模块（如 `pipeline_router.py`）必须用 `import ... as db_mod` 形式，才能让 `client` fixture 的 monkey-patch 在测试期间生效
3. monkey-patch **只在 `async with AsyncClient:` 期间生效**，上下文退出后恢复
4. `db` fixture 返回**单个 session**（从 session_factory 创建），生命周期贯穿整个测试函数
5. 同一 engine 下的跨 session 可见性：session A commit 后，session B 需要新事务 SELECT 或 **同步** `db.expire_all()` 才能看到（SQLAlchemy identity map）
6. **`AsyncSession.expire_all()` 是同步方法，不是 coroutine（R4-F002 修正）**：源码 `sqlalchemy/ext/asyncio/session.py` 中 `expire_all` 直接 `self.sync_session.expire_all()`，不返回 `Awaitable`。测试中必须写 `db.expire_all()` 不带 `await`，否则 `TypeError: object NoneType can't be used in 'await' expression`

**S7 / S8 / S9b 的选型结论:**

- **S7 (publish_service.upsert_questions_from_skeleton 测试)** — 可以**只用 `db` fixture**（被测函数接受 `db` 参数，外层事务在同一 session 内），**不需要** `client` fixture
- **S8a/b/c (工厂函数 + 闭包测试)** — **必须用 `client + db` 组合 fixture + 被测模块采用 `import ... as db_mod` 形式**。`client` fixture 的 monkey-patch 生效期间，工厂闭包内 `db_mod.async_session()` 运行时查找到新 factory，写入打到 in-memory test DB；断言查询用 `db` fixture（跨 session 可见性通过同步 `db.expire_all()` 或新 SELECT 事务刷新）
- **S9b** — 已经用 `client + db`，同理生效
- **工厂函数签名**：接 `regions: list[dict]`（兼容 `tpl_path` 分支），**不接 Template ORM 对象**；session factory 从 `db_mod.async_session()` 运行时查找

---

### CR-2: `pipeline_router.py` `start_pipeline` 真实结构

**位置**: `src/edu_cloud/modules/scan/pipeline_router.py:25-29, 90-160`

```python
class StartPipelineRequest(BaseModel):
    subject_id: str
    side: str = "A"
    image_dir: str
    tpl_path: str | None = None  # 可选：.tpl 文件路径（替代 Template 表）

@router.post("/start")
async def start_pipeline(
    req: StartPipelineRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
    storage: StorageService = Depends(get_storage),
):
    """启动扫描切割流水线。"""
    school_id = current["current_role"].school_id

    if pipeline_service.is_running():
        raise HTTPException(409, "流水线正在运行")

    # 验证目录
    if not os.path.isdir(req.image_dir):
        raise HTTPException(400, f"目录不存在: {req.image_dir}")

    # 获取 subject
    subject = (await db.execute(
        select(Subject).where(Subject.id == req.subject_id, Subject.school_id == school_id)
    )).scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "科目不存在")

    # 加载模板
    if req.tpl_path:
        if not os.path.isfile(req.tpl_path):
            raise HTTPException(400, f"tpl 文件不存在: {req.tpl_path}")
        template = parse_tpl_file(req.tpl_path)
    else:
        tpl = (await db.execute(
            select(Template).where(
                Template.subject_id == req.subject_id,
                Template.side == req.side,
            )
        )).scalar_one_or_none()
        if not tpl:
            raise HTTPException(404, "模板不存在，请先发布答题卡或导入 .tpl 文件")
        template = {
            "image_size": {"width": tpl.image_width, "height": tpl.image_height},
            "anchors": tpl.anchors or [],
            "regions": tpl.regions or [],
            "barcode_region": None,
        }

    # 列出文件
    try:
        files = pipeline_service.list_scan_images(req.image_dir, req.side)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))

    if not files:
        raise HTTPException(400, f"目录下没有 {req.side} 面的 PNG 文件")

    # 按 school/exam/subject 隔离的输出目录
    output_dir = os.path.join(storage.root, school_id, subject.exam_id, req.subject_id)

    # 后台启动（只切图存储，不写 StudentAnswer — 入库由后续阅卷流程负责）
    asyncio.create_task(pipeline_service.run_pipeline(
        image_dir=req.image_dir,
        template=template,
        output_dir=output_dir,
        exam_id=subject.exam_id,
        subject_id=req.subject_id,
        school_id=school_id,
        side=req.side,
    ))

    logger.info("Pipeline started: subject=%s, dir=%s, files=%d",
                subject.name, req.image_dir, len(files))
    return {"status": "started", "total_files": len(files)}
```

**关键事实（R3-F005 根因消除）:**

1. **两条模板加载分支都没有统一的 `tpl` 变量**:
   - `tpl_path` 分支：只有 `template = parse_tpl_file(...)` 一个 dict，**无 `tpl` Template 对象**
   - DB 分支：`tpl` 是 Template ORM 对象 + `template` 是手工构造的 dict，**两个不同变量**
2. **统一装配点**: 两条分支的共同产物是 `template` dict，它的 `"regions"` key 是 `list[dict]`（每条 region 可能有 `question_id` 字段）
3. **修复策略**: 工厂函数接 **`regions: list[dict]`** 参数（从 `template["regions"]` 提取），两条分支都能调；**不接 Template ORM 对象**，避免 tpl_path 分支的 NameError
4. **`exam_id` 来源锁定**: `subject.exam_id`（L145/L152 已有派生，`StartPipelineRequest` 保持 4 字段契约不变）

---

### CR-3: `ExamDetailPage.vue` 发布按钮 + `handlePublishCard` 真实结构

**位置**: `frontend/src/pages/ExamDetailPage.vue` — 按源文件行号顺序摘抄 4 段原文：
- L242-263（template 段：发布按钮 + CardEditor props）
- L446-471（script setup：imports + saveBlob + route/message/dialog/examId 声明）
- L652-662（script setup：loadExam 函数）
- L848-881（script setup：handlePublishCard 函数）

> 代码块内为 4 段字节级原文拼接，段与段之间用单个空行分隔。禁止插入 HTML 说明标签或 `...` 省略符。

```vue
            <n-button
              size="small"
              class="btn-pill toolbar-btn"
              :disabled="!visualEditorSubjectId || exam?.status !== 'draft'"
              @click="handlePublishCard"
            >
              发布答题卡
            </n-button>
          </div>
          <div v-if="visualEditorSubjectId" style="min-height: 600px;">
            <CardEditor
              ref="cardEditorRef"
              :key="visualEditorSubjectId + (pendingQuestionsForEditor ? '-pq' : '')"
              :exam-id="examId"
              :subject-id="visualEditorSubjectId"
              :subject-name="visualEditorSubjectName"
              :card-title="exam?.card_title || ''"
              :readonly="exam?.status !== 'draft'"
              :pending-questions="pendingQuestionsForEditor"
              @publish="handlePublishCard"
            />
          </div>

import { getExam, updateExam } from '../api/exams'
import { listSubjects, createSubject } from '../api/subjects'
import { getRubric, upsertRubric } from '../api/rubrics'
import { generateBarcode, parseAnswers, previewByWeights, generateCardV2 } from '../api/cards'
import { scanDirectory, startPipeline, getPipelineProgress, stopPipeline, previewScan, importTpl } from '../api/scan'
import CardEditor from '../components/CardEditor.vue'
import katex from 'katex'
import 'katex/dist/katex.min.css'

/** 可靠的 blob 下载：用 File 构造器强制文件名（绕过 Chrome blob UUID 问题） */
function saveBlob(blob, filename) {
  const file = new File([blob], filename, { type: blob.type })
  const url = URL.createObjectURL(file)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}

const route = useRoute()
const message = useMessage()
const dialog = useDialog()
const examId = route.params.id

async function loadExam() {
  loading.value = true
  try {
    const [examRes, subjRes] = await Promise.all([getExam(examId), listSubjects(examId)])
    exam.value = examRes.data
    cardForm.cardTitle = examRes.data.card_title || ''
    subjects.value = subjRes.data
  } catch { /* interceptor */ } finally {
    loading.value = false
  }
}

async function handlePublishCard() {
  if (!visualEditorSubjectId.value) {
    message.warning('请先选择科目')
    return
  }
  const subjectId = visualEditorSubjectId.value
  const subj = subjects.value.find(s => s.id === subjectId)
  const filename = `答题卡_${subj?.name || '未知'}.pdf`

  dialog.warning({
    title: '确认发布',
    content: '发布后答题卡将锁定为只读，扫描端可开始拉取模板。确定发布？',
    positiveText: '发布',
    negativeText: '取消',
    positiveButtonProps: { class: 'btn-pill' },
    negativeButtonProps: { class: 'btn-pill' },
    onPositiveClick: async () => {
      try {
        // Step 1-3: PDF + skeleton + Template (via export.js publishCard)
        const exportModule = await import('@/card-editor/export.js')
        await exportModule.publishCard(subjectId, filename)

        // Step 4: Update exam status to scanning
        await updateExam(examId, { status: 'scanning' })

        // Refresh exam data (updates readonly state)
        await loadExam()
        message.success('答题卡已发布，扫描端可拉取模板')
      } catch (e) {
        message.error('发布失败: ' + (e.message || '未知错误'))
      }
    },
  })
}
```

**关键事实（R3-F004 根因消除）:**

1. **import 路径**：`api/exams` 导出 `getExam, updateExam`；**`api/subjects` 导出 `listSubjects, createSubject`**（V3 mock 必须分两个模块 mock）
2. **axios shape**: `api/subjects.js` 第 3 行 `listSubjects = (examId) => client.get(...)` 返回 axios 响应——`loadExam` 读 `subjRes.data`，V3 的 mock 返回值必须是 `{ data: [...] }` 包装
3. **发布按钮 disabled 双条件**：`!visualEditorSubjectId || exam?.status !== 'draft'`——V3 测试必须同时满足：
   - `visualEditorSubjectId.value` 非空（选择了具体科目）
   - `exam.value.status === 'draft'`（考试处于草稿状态）
4. **当前**：发布按钮**无 `data-testid` 属性**——Task 10 Step 2 必须显式添加 `data-testid="publish-card-btn"`（plan 强制要求）
5. **`handlePublishCard` 通过 `dialog.warning` 中转**：
   - 触发 flow: 按钮 click → `handlePublishCard()` → `dialog.warning({onPositiveClick: async () => {...publishCard...}})` → 弹窗
   - 真正的 `publishCard` 调用**在 dialog 的 `onPositiveClick` 回调里**
   - **V3 测试方案**: mock `useDialog`/`dialog` 让 `warning({onPositiveClick})` **立即同步调用 `onPositiveClick`**，跳过真实弹窗渲染
6. **L471 `const examId = route.params.id`** 组件顶层常量——L868 改签名时直接引用 `examId`，不需要新增 ref
7. **当前 publishCard 签名**: L868 是 `publishCard(subjectId, filename)` 2 参——T10 Step 2 改为 `publishCard(subjectId, examId, filename)` 3 参

---

### CR-4: `api/subjects.js` 真实导出

**位置**: `frontend/src/api/subjects.js:1-5`

```js
import client from './client'

export const listSubjects = (examId) => client.get(`/exams/${examId}/subjects`)
export const createSubject = (examId, data) => client.post(`/exams/${examId}/subjects`, data)
```

**关键事实**: `listSubjects` 直接返回 axios Promise，**无额外包装**；响应是 axios 标准格式 `{ data, status, headers, ... }`。

---

## Contract Pack（Plan Review R1 F001 补齐）

> 符合 `~/.claude/config/contract-pack-schema.md` 规范。Plan Review / Code Review 按此作为机审语义护栏。

```yaml
contract_pack:

  invariants:
    - id: INV-001
      statement: upsert_questions_from_skeleton 对空 skeleton 返回空字典 {}，不抛异常
      verification: pending_test
      test_ref: tests/test_services_exam/test_publish_service.py::test_S2_upsert_questions_from_skeleton_new_subject
      note: S2 覆盖新 subject 14 题场景，边界条件段另外覆盖空 skeleton

    - id: INV-002
      statement: upsert_questions_from_skeleton 同一 (subject_id, name) 重复调用，Question 表记录数不变、max_score 更新到最新值
      verification: pending_test
      test_ref: tests/test_services_exam/test_publish_service.py::test_S3_upsert_questions_idempotent

    - id: INV-003
      statement: upsert_questions_from_skeleton 第二次 skeleton 删除题目时，原 Question 在 DB 保留（孤儿策略 D4）
      verification: pending_test
      test_ref: tests/test_services_exam/test_publish_service.py::test_S4_upsert_preserves_orphan

    - id: INV-004
      statement: upsert_template_both_sides 在 regions 仅含 B 面时必须 raise HTTPException(400)，A 面必存（design §5.1）
      verification: pending_test
      test_ref: tests/test_services_exam/test_publish_service.py::test_S5c_only_B_side_raises_400

    - id: INV-005
      statement: publish_card_atomic 事务内任一步失败（Question/Template/exam.status）→ 全部 rollback，DB 保持原状
      verification: pending_test
      test_ref: tests/test_services_exam/test_publish_service.py::test_S6_publish_card_atomic_rollback_on_template_fail

    - id: INV-006
      statement: pipeline_router 的 save_answer_fn 闭包收到 orphan region_id（不在 region_map）时 skip + log warning，不中断 pipeline
      verification: pending_test
      test_ref: tests/test_api_exam/test_pipeline_save_answer.py::test_S8a_factory_skips_orphan_region_with_warning
      note: S8a 直接通过 build_pipeline_save_answer_fn 工厂函数拿闭包 + 手动驱动，不依赖 async background run_pipeline（R2-F005 修正：移除原 pytest.skip/TODO 占位）

    - id: INV-007
      statement: StudentAnswer 唯一约束是 3 列 (exam_id, student_id, question_id)，重跑 pipeline 对同一学生同一题二次 INSERT 触发 IntegrityError 被捕获 skip
      verification: existing_test
      test_ref: src/edu_cloud/modules/scan/models.py:23
      note: schema 层已存在约束，代码层 try/except 在 T11 save_answer_fn 闭包实现

    - id: INV-008
      statement: publish_card_atomic 前置校验失败（Exam/Subject 归属/HTML 空/status completed）→ 400 快速失败，事务未开启
      verification: pending_test
      test_ref: tests/test_services_exam/test_publish_service.py::test_S6b_publish_card_atomic_success_path
      note: success path 测试覆盖；单独的 400 路径测试在 T6 Step 1 追加

    - id: INV-009
      statement: start_pipeline HTTP 入口必须调用 build_pipeline_save_answer_fn 工厂并把闭包传给 run_pipeline；两条分支（DB Template / .tpl 文件）都统一装配
      verification: pending_test
      test_ref: tests/test_api_exam/test_pipeline_router_wiring.py::test_S8d_start_pipeline_tracks_factory_and_asserts_identity
      note: |
        R3-F003 → R4-F004 → R5-F002 演化修正——工厂单元测试 PASS 不等于 wiring 正确。
        S8d-a 通过 `patch.object(..., side_effect=tracked_factory)` + 外部 `factory_returns` 列表
        捕获真工厂返回闭包（Python 3.11.9 `unittest.mock.MagicMock` 无 `spy_return` 属性，R5-F002），
        再用 `captured_kwargs["save_answer_fn"] is factory_returns[0]` identity 断言验证真实装配路径。
        S8d-b 同 `tracked_factory` 策略覆盖 tpl_path 分支（R3-F005 + R4-F004 + R5-F002 三重守卫）。

    - id: INV-010
      statement: upsert_questions_from_skeleton 采用 SELECT-first existing fast path + SAVEPOINT retry 并发防御；SAVEPOINT 子事务 rollback 不破坏外层 publish 事务
      verification: pending_test
      test_ref: tests/test_services_exam/test_publish_service.py::test_S7a_savepoint_semantics_preserves_outer_tx
      note: S7a 纯 SAVEPOINT 语义 + S7b SELECT-first 主路径 + 代码审查作为 SAVEPOINT retry 分支护栏（R4-F003 修正后 S7c 不再写伪实现，延期到 PostgreSQL CI；见 test_debt）。

  counter_examples:
    - id: CE-001
      scenario: publish 后 publishCard 前端手工三步未改造（T9 跳过），后端 /card/publish 被调用但前端仍走旧 PUT /templates/{subject_id}/A
      tests_that_still_pass: test_S2/S3/S4/S5/S6/S6b/S7（所有纯函数单元测试）、test_R3（只测 publish 幂等）
      mitigation: V2 vitest test_publishCard_single_api_call 断言 fetch 调用 1 次且目标 /card/publish；S9a 通过 HTTP client 调 /card/publish 端点而非模拟前端

    - id: CE-002
      scenario: pipeline_router 构建 region_map 但 save_answer_fn 闭包内 INSERT 失败被吞（无 log）+ 无 IntegrityError 捕获；或测试绕开 pipeline_router 装配路径手工 db.add(StudentAnswer) 伪装验证
      tests_that_still_pass: S9a publish 可见性测试（只查 marking/subjects.questions，不查 total_answers）；S8a orphan 测试（主要测 skip 不中断）
      mitigation: |
        S8b + S8c + S9b 统一通过 `build_pipeline_save_answer_fn` 工厂函数获取闭包，与 `start_pipeline` 装配路径完全一致：
        - S8b 断言闭包合法 region_id → 真实 Question.id 反查 + INSERT StudentAnswer 成功
        - S8c 断言重复 INSERT 触发 3 列 UniqueConstraint → IntegrityError 被捕获 rollback 幂等
        - S9b 驱动工厂闭包后查 marking/subjects.total_answers == 2，同时断言 StudentAnswer.question_id == Question.id（证明经过反查路径）
        工厂函数是 pipeline_router 和测试的共享装配路径，无法被伪验证绕过（R2-F003 修正）

    - id: CE-003
      scenario: upsert_questions_from_skeleton 实现用 hard-delete 策略（每次 publish 先 DELETE 再 INSERT）
      tests_that_still_pass: S2 新 subject 场景、S3 幂等场景（单次更新也能过）
      mitigation: S4 test_S4_upsert_preserves_orphan 断言第二次 publish 删除题 15 后 DB 仍 3 条记录

    - id: CE-004
      scenario: Task 4 允许 tpl_a=None（B-only publish 合法），但下游 pipeline_router 默认按 side="A" 查 Template 查不到
      tests_that_still_pass: S5 双面 Template 测试、S8 orphan 测试（因为它们显式构造 A 面 region）
      mitigation: S5c test_S5c_only_B_side_raises_400 断言 HTTPException(400)

  risk_modules:
    - module: src/edu_cloud/modules/card/publish_service.py
      reason: 新建模块，包含 upsert_questions_from_skeleton / upsert_template_both_sides / publish_card_atomic 三个核心函数，是 F003 的业务原子入口；事务边界在此模块内定义；一旦实现偏离 CE-003 的孤儿保留或 CE-004 的 A-only 契约会产生全链路隐藏故障

    - module: src/edu_cloud/modules/card/router.py (L1189 publish_card)
      reason: 唯一的公开 HTTP 入口 `/api/v1/card/publish`，从当前僵尸端点复活为主路径，前端所有 publish 调用收敛于此；错误的前置校验或错误的 service 调用会直接暴露给客户端

    - module: src/edu_cloud/modules/scan/pipeline_router.py (start_pipeline)
      reason: pipeline 启动端点要读 Template → 构建 region_map → 注入 save_answer_fn 闭包，如果闭包构建错误（如缺 region_map 参数、闭包捕获错误 session scope）→ StudentAnswer 写入全失败或写错数据，F003 修复形同虚设

    - module: src/edu_cloud/modules/exam/models.py (Question UniqueConstraint)
      reason: Alembic migration 加 UniqueConstraint (subject_id, name)，现有 5 科种子数据必须满足唯一性，migration 失败会阻塞整个 B1 执行

    - module: frontend/src/card-editor/render.js (data-side attribute)
      reason: F001 前置修复点，同文件与小微排版 v2 WIP 冲突区，diff 混入风险高；数据-side 属性错误会导致 skeleton.side 字段全 A，B 面 Template 空

    - module: frontend/src/card-editor/export.js (publishCard)
      reason: 前端唯一的 publish 入口，重写时若 examId 参数名或来源错误 → 后端 400 不可见于用户

  test_debt:
    - item: SAVEPOINT retry 分支的 flush-time race 确定性测试（跨 session 真实 IntegrityError 场景）
      reason: |
        SQLite in-memory 下任何 "同 session monkeypatch flush 拦截 + 偷插 rival" 方案都逻辑不可证：
        同一 SAVEPOINT 子事务内偷插的 rival 会随 SAVEPOINT rollback 一并回滚，re-SELECT 永远找不到
        （R4-F003 证实）。测试必须在 PostgreSQL CI 环境用独立 session/独立 connection 预插 rival
        + commit（跨 session 可见），才能真正触发被测函数的 SAVEPOINT retry 分支。
        S7a（纯 SAVEPOINT 语义）+ S7b（SELECT-first existing fast path）+ 代码审查作为
        Gate 1 PASS 充分条件。本 test_debt 条目延期到 PostgreSQL CI 激活时实现。
      deadline: 2026-06-30
      note: |
        R4-F003 修正历史：R3 阶段尝试用 monkeypatch flush 在 SAVEPOINT 上下文内注入 rival 的草稿
        被 R4 审查证明为逻辑矛盾（rival 与 rollback 同 scope），草稿已删除。PostgreSQL CI 延期方案：
        用 testcontainers-python 或 GHA postgres service + 独立 asyncpg.connect() 预 commit rival，
        Session A 调被测函数触发真实 UniqueConstraint 冲突 + SAVEPOINT retry 分支。

    - item: 真正 PostgreSQL 并发 session 的 IntegrityError retry 压测（多 asyncio task 并发调 upsert_questions_from_skeleton，跨 session 真实 race）
      reason: SQLite in-memory 单 connection 模型无法模拟真实并发 session 的 race condition；PostgreSQL 需要完整部署测试环境，超出本批次 scope
      deadline: 2026-06-30

    - item: Playwright 真实 PDF 生成 + 真实 extract_skeleton 的 E2E 烟雾测试（S9a/S9b 都 mock 掉了 html_to_pdf 和 extract_skeleton）
      reason: Playwright Chromium 在 CI 环境配置成本高，且本轮重点在业务逻辑正确性（不是 PDF 渲染质量）
      deadline: 2026-05-31
      note: 当前通过 Task 12 的手动 smoke test（浏览器点发布按钮）覆盖这条路径
```

### Contract Pack 解读

**invariants** 聚焦 publish_service 和 pipeline save_answer_fn 的核心不变量——8 条全部可验证（7 条 pending_test + 1 条 existing_test 对应 schema 层约束）。

**counter_examples** 4 个覆盖最可能的错误实现：
- CE-001 前端未切换到 /card/publish（mitigation: V2 vitest）
- CE-002 pipeline save_answer_fn 静默失败（mitigation: S9b）
- CE-003 hard-delete 破坏孤儿策略（mitigation: S4）
- CE-004 B-only 违反 A 面必存（mitigation: S5c）

**risk_modules** 5 个模块：3 个新建/重写（publish_service / card/router:1189 / pipeline_router）+ 1 个 schema migration (Question UniqueConstraint) + 2 个前端核心入口（render.js 冲突区 + export.js publishCard）。

**test_debt** 2 条，都有具体理由 + deadline，无空占位。

---

## Pre-flight checklist（启动执行前）

- [ ] **小微排版 v2 视觉验收已回主线**（card 模块 WIP 不再有未 commit 修改）
- [ ] `git status` 显示 card/ 目录 clean
- [ ] 确认当前 branch 是 master 且基线为 design commit `7ad6416`
- [ ] 后端 :9000 + 前端 :5273 服务可运行（批次间 smoke 验证用）
- [ ] 已读完 design.md（至少 §3 决策 / §4 数据流 / §6 错误处理）

---

## Batch 1: 前置修复 + 纯函数（Slice A + B + C）

**目标：** 零风险的纯函数 + 一行前端属性修复，为事务层做准备。无 schema 改动，无对外接口变更。

### Task 0: StudentAnswer 唯一约束核验（decision locked by Plan Review R1 F003）

**Files:**
- Read only: `src/edu_cloud/modules/scan/models.py`

**背景**：Plan Review R1 F003 已核实 StudentAnswer 现有 schema 约束为 **3 列** `(exam_id, student_id, question_id)`（`scan/models.py:23`），不是早期设计稿误写的 4 列。本 Task 仅做最终锚定验证，不改代码不加 migration。

**决策结果（已锁定）**：
- **StudentAnswer 现有约束**: `UniqueConstraint("exam_id", "student_id", "question_id")` — 3 列
- **本批次是否新增 migration**: **否**
- **save_answer_fn 写入策略**: `INSERT` + `try/except IntegrityError` 捕获后 `rollback` 并 log warning（天然幂等）

**原因**：同一 exam + 同一 student + 同一 question 全局唯一一条 StudentAnswer；subject_id 由 question_id 的外键归属间接确定，无需加入唯一键。重跑 pipeline 对同一学生同一题的二次 INSERT 会自然触发 IntegrityError，被 save_answer_fn 的 try/except 捕获并跳过。

- [ ] **Step 1: 最终事实验证**

```bash
grep -n "UniqueConstraint\|__table_args__" src/edu_cloud/modules/scan/models.py
```

Expected: L23 输出 `__table_args__ = (UniqueConstraint("exam_id", "student_id", "question_id"),)`

若输出不符（schema 被改了）→ 进入未预期分支：必须停下 + 重写 Task 0；不能盲目 migration。

- [ ] **Step 2: 无改动 commit 通过 Task 0**

```bash
# Task 0 本身无文件修改，直接进入 Task 1
echo "Task 0 锚定验证通过，现有 3 列约束满足写回语义"
```

**审查清单:**
- ✓ 正向：grep 输出匹配 L23 的 3 列 UniqueConstraint
- ✗ 反向：试图加 alembic migration 追加第 4 列（subject_id）——已被 R1 F003 证伪，不要做
- 关键行为：本 Task 是 R1 F003 修正后的文档锚点，确保 T6/T11 的 save_answer_fn 实现策略基于真实 schema

---

### Task 1: F001 — render.js 4 处 `.page` 加 `data-side` 属性

**Files:**
- Modify: `frontend/src/card-editor/render.js:641,643,689,701`
- Test: `frontend/src/card-editor/__tests__/render.test.js` 新增 data-side 断言

**背景：** `html_export.py:101` 的 `el.closest('[data-side]')?.dataset.side || 'A'` 需要 DOM 有 data-side 属性，否则全部 fallback 到 "A"。当前 render.js 生成的 `.page` DOM 无此属性（F001）。

- [ ] **Step 1: 写失败的 Vitest 测试（Red）**

编辑 `frontend/src/card-editor/__tests__/render.test.js`，追加：

```js
import { describe, it, expect } from 'vitest'
import { renderFromLayout } from '../render.js'

describe('F001: .page DOM 必须有 data-side 属性', () => {
  it('A3 双面布局: pageA data-side="A", pageB data-side="B"', () => {
    const container = document.createElement('div')
    const layout = {
      paper: 'A3',
      sides: [
        { side: 'A', columns: [{ col: 0, regions: [] }, { col: 1, regions: [] }, { col: 2, regions: [] }] },
        { side: 'B', columns: [{ col: 0, regions: [] }, { col: 1, regions: [] }, { col: 2, regions: [] }] },
      ],
    }
    const config = { paperSize: 'A3', examTitle: 'T', subjectTitle: 'S' }

    renderFromLayout(container, layout, config)

    const pageA = container.querySelector('#pageA')
    const pageB = container.querySelector('#pageB')
    expect(pageA).not.toBeNull()
    expect(pageB).not.toBeNull()
    expect(pageA.getAttribute('data-side')).toBe('A')
    expect(pageB.getAttribute('data-side')).toBe('B')
  })

  it('A4 双面布局: pageA data-side="A", pageB data-side="B"', () => {
    const container = document.createElement('div')
    const layout = {
      paper: 'A4',
      sides: [
        { side: 'A', columns: [{ col: 0, regions: [] }] },
        { side: 'B', columns: [{ col: 0, regions: [{ type: 'essay', subs: [] }] }] },
      ],
    }
    const config = { paperSize: 'A4', examTitle: 'T', subjectTitle: 'S' }

    renderFromLayout(container, layout, config)

    const pageA = container.querySelector('#pageA')
    const pageB = container.querySelector('#pageB')
    expect(pageA.getAttribute('data-side')).toBe('A')
    expect(pageB?.getAttribute('data-side')).toBe('B')
  })
})
```

- [ ] **Step 2: 运行测试，确认 Red（失败）**

```bash
cd frontend && npx vitest run src/card-editor/__tests__/render.test.js
```

Expected: FAIL — `Expected "A" but got null`（当前 render.js 没有 data-side 属性）

- [ ] **Step 3: 修 render.js 4 处 `.page` 加 data-side**

在 `frontend/src/card-editor/render.js` 做 4 处改动：

L641-643（A3 双面）:
```js
// 原：
<div class="page" data-paper="A3" id="pageA">${pageA}</div>
<div class="page-label">B 面（背面）</div>
<div class="page" data-paper="A3" id="pageB">${pageB}</div>

// 改为：
<div class="page" data-paper="A3" data-side="A" id="pageA">${pageA}</div>
<div class="page-label">B 面（背面）</div>
<div class="page" data-paper="A3" data-side="B" id="pageB">${pageB}</div>
```

L689（A4 B 面）:
```js
// 原：
<div class="page" data-paper="A4" id="pageB">

// 改为：
<div class="page" data-paper="A4" data-side="B" id="pageB">
```

L701（A4 A 面）:
```js
// 原：
<div class="page" data-paper="A4" id="pageA">${pageAContent}</div>

// 改为：
<div class="page" data-paper="A4" data-side="A" id="pageA">${pageAContent}</div>
```

- [ ] **Step 4: 运行测试，确认 Green**

```bash
cd frontend && npx vitest run src/card-editor/__tests__/render.test.js
```

Expected: PASS — 2 new tests + all existing render tests still pass

- [ ] **Step 5: 跑前端全量 vitest 确认无回归**

```bash
cd frontend && npx vitest run
```

Expected: 182+ tests pass（预期前 182 维持 + 2 新增 = 184 通过）

- [ ] **Step 6: Commit**

```bash
git add frontend/src/card-editor/render.js frontend/src/card-editor/__tests__/render.test.js
git commit -m "fix(card-editor): F001 render.js .page DOM 加 data-side 属性 (T1)"
```

**测试契约（S1 + V1）:**

| slice | 入口 | 反例 | 边界 | 回归 | 命令 |
|-------|------|------|------|------|------|
| S1 | `renderFromLayout(container, layout, config)` 渲染后查询 `container.querySelector('#pageB')` | 错误实现不加 data-side → `getAttribute('data-side')` 返回 null，测试断言 expect.toBe('B') 失败 | 单面考试（无 pageB）→ querySelector 返回 null 不断言 | F001（skeleton side 全 A 的根源）| `npx vitest run src/card-editor/__tests__/render.test.js` |

**边界条件:**
- 仅 A 面（sideB 为空 / 无 regions）→ pageA 有 data-side="A"，无 pageB 节点
- A3 横向双面 → pageA + pageB 都有 data-side
- A4 纵向双面 → pageA + pageB 都有 data-side
- sideB.columns 为空数组 → A4 分支走 pageBHTML=''，不生成 pageB

**审查清单:**
- ✓ 正向：render.js 4 处 `.page` 都有 data-side 属性
- ✓ 正向：vitest 2 个新测试 pass
- ✓ 正向：前端全量 vitest 不低于 184 tests pass
- ✗ 反向：render.js 其他 .page 引用（如果有）未加 data-side
- ✗ 反向：data-side 值不是 'A'/'B' 而是其他字符串
- 关键行为：data-side 属性必须在 page 根节点，而不是嵌套在 .a3-layout / .a4-content 内部

---

### Task 2: extract_skeleton 输出 side 字段验证（integration）

**Files:**
- Test: `tests/test_api_exam/test_card_publish.py`（新建，Task 2 首次 touch）

**背景：** Task 1 改了前端 DOM 的 data-side 属性，但验证链路（前端 → Playwright 渲染 → `html_export.py:_extract_skeleton_sync` → JS 闭包 `el.closest('[data-side]')`）是否真正穿透到 skeleton JSON 输出，需要 integration 测试。

- [ ] **Step 1: 新建测试文件 + 写失败的测试（Red）**

创建 `tests/test_api_exam/test_card_publish.py`:

```python
"""F003 Question 写入责任链 — integration tests for /api/v1/card/publish."""
import pytest


@pytest.fixture
def minimal_html_with_data_side():
    """构造含 data-side="A" 和 data-side="B" 的 .page DOM 的 HTML。"""
    return """<!DOCTYPE html>
<html><body>
  <div class="page" data-paper="A3" data-side="A" id="pageA">
    <div data-region-id="essay-Q12" data-region-type="subjective" data-qno="12">Q12</div>
  </div>
  <div class="page" data-paper="A3" data-side="B" id="pageB">
    <div data-region-id="essay-Q17" data-region-type="subjective" data-qno="17">Q17</div>
  </div>
</body></html>"""


@pytest.mark.asyncio
async def test_extract_skeleton_preserves_data_side(minimal_html_with_data_side):
    """Slice A2: extract_skeleton 的 JS eval 必须正确读取 data-side 并写入 skeleton.regions[].side。

    反例：render.js 未修时 closest('[data-side]') 返回 null，所有 region side fallback 'A'。
    本测试构造 B 面 region 并断言 side='B'。
    """
    from edu_cloud.modules.card.html_export import extract_skeleton

    skeleton = await extract_skeleton(minimal_html_with_data_side)

    regions = skeleton.get("regions", [])
    assert len(regions) == 2, f"应有 2 个 region，实际 {len(regions)}"

    by_id = {r["id"]: r for r in regions}
    assert "essay-Q12" in by_id and by_id["essay-Q12"]["side"] == "A"
    assert "essay-Q17" in by_id and by_id["essay-Q17"]["side"] == "B", (
        f"Q17 应在 B 面，实际 side={by_id['essay-Q17']['side']}"
    )
```

- [ ] **Step 2: 运行 Red verification**

```bash
python -m pytest tests/test_api_exam/test_card_publish.py::test_extract_skeleton_preserves_data_side -v
```

Expected:
- 如果 Task 1 已 commit：PASS（data-side 已写入 DOM，Playwright 应正确提取）
- 如果未做 Task 1：FAIL（Q17 side='A'，预期 'B'）

**注意：** 本 Task 是**事后验证测试**，不是 Red-Green-Refactor 的 Red 阶段。Task 1 修的是 render.js，Task 2 是 integration 级别确认修复穿透。

- [ ] **Step 3: 跑 pytest test_card_publish 确认 PASS**

```bash
python -m pytest tests/test_api_exam/test_card_publish.py -v
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_api_exam/test_card_publish.py
git commit -m "test(card): F001 integration 验证 extract_skeleton 穿透 data-side (T2)"
```

**测试契约:**

| slice | 入口 | 反例 | 边界 | 回归 | 命令 |
|-------|------|------|------|------|------|
| A2 | `await extract_skeleton(html)` | 错误实现（render.js 未修）→ side 全 'A'，Q17 断言失败 | 单面 HTML（只有 pageA）→ 测试单独覆盖（future）| F001 穿透链路 | `pytest tests/test_api_exam/test_card_publish.py::test_extract_skeleton_preserves_data_side -v` |

**边界条件:**
- HTML 无 data-side 属性 → skeleton.regions[].side 全 'A'（当前 bug 行为，作为反例参考）
- HTML 只有 pageA → regions 只有 A 面
- HTML 嵌套 data-side（祖先节点）→ closest 正确走祖先链

**审查清单:**
- ✓ 正向：test_extract_skeleton_preserves_data_side PASS
- ✓ 正向：Q17 side 值为 'B'
- ✗ 反向：Playwright 未启动时跑不过（需要确保 playwright chromium 已安装）
- 关键行为：integration 测试使用真实 Playwright sync API（test runtime 有 playwright.chromium.launch 能力）

---

### Task 3: `publish_service.upsert_questions_from_skeleton` 纯函数 + unit tests (S2/S3/S4)

**Files:**
- Create: `src/edu_cloud/modules/card/publish_service.py`
- Create: `tests/test_services_exam/test_publish_service.py`

**背景：** design.md §5.1 B1 新模块的第一个函数。纯数据层，无 HTTP 依赖，可单元测试。

- [ ] **Step 1: 写失败测试（Red） — S2 新 subject 全量创建**

创建 `tests/test_services_exam/test_publish_service.py`:

```python
"""F003 publish_service 单元测试 — upsert_questions / upsert_template / publish_card_atomic."""
import pytest
from sqlalchemy import select

from edu_cloud.models.school import School
from edu_cloud.modules.exam.models import Exam, Subject, Question


@pytest.fixture
async def empty_subject(db):
    """创建空 subject（无任何 Question），返回 school/exam/subject ids。"""
    school = School(name="PSTest", code="PS01")
    db.add(school)
    await db.commit()
    exam = Exam(name="PSExam", school_id=school.id, status="draft")
    db.add(exam)
    await db.commit()
    subject = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subject)
    await db.commit()
    return {"school_id": school.id, "exam_id": exam.id, "subject_id": subject.id}


def _build_skeleton(objective_groups=None, slots=None):
    """构造最小 skeleton dict（模拟 extract_skeleton 的输出形状）。"""
    return {
        "objective_groups": objective_groups or [],
        "slots": slots or [],
        "image_width": 1587,
        "image_height": 1123,
        "anchors": [],
    }


async def test_S2_upsert_questions_from_skeleton_new_subject(db, empty_subject):
    """S2: 空 Subject 首次 publish，skeleton 含 12 选择题 + 3 主观题 → 创建 15 条 Question。

    反例：错误实现只创建 subjective 或只创建 objective group 合并为 1 条。
    """
    from edu_cloud.modules.card.publish_service import upsert_questions_from_skeleton

    skeleton = _build_skeleton(
        objective_groups=[
            {"group_id": "obj1", "start_no": 1, "count": 12, "options": 4,
             "symbols": "A,B,C,D", "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}}
        ],
        slots=[
            {"sub_regions": [
                {"id": "essay-13", "name": "13", "score": 10, "rect": {"x1": 0, "y1": 100, "x2": 100, "y2": 200}},
                {"id": "essay-14", "name": "14", "score": 15, "rect": {"x1": 0, "y1": 200, "x2": 100, "y2": 300}},
                {"id": "essay-15", "name": "15", "score": 20, "rect": {"x1": 0, "y1": 300, "x2": 100, "y2": 400}},
            ]}
        ],
    )

    q_map = await upsert_questions_from_skeleton(
        db,
        subject_id=empty_subject["subject_id"],
        school_id=empty_subject["school_id"],
        skeleton=skeleton,
    )
    await db.commit()

    # 预期 15 条 Question
    qs = (await db.execute(select(Question).where(Question.subject_id == empty_subject["subject_id"]))).scalars().all()
    names = sorted([q.name for q in qs], key=lambda s: int(s) if s.isdigit() else 999)
    assert len(qs) == 15
    assert names[:12] == [str(i) for i in range(1, 13)]  # "1".."12" 选择题
    assert names[12:] == ["13", "14", "15"]  # 主观题

    # q_map 包含全部 name → id
    assert set(q_map.keys()) == set(names)
    assert all(q_map[q.name] == q.id for q in qs)

    # 类型正确
    types = {q.name: q.question_type for q in qs}
    for i in range(1, 13):
        assert types[str(i)] == "objective"
    for n in ["13", "14", "15"]:
        assert types[n] == "subjective"


async def test_S3_upsert_questions_idempotent(db, empty_subject):
    """S3: 同 skeleton 连续调用两次，Question 数量不变（幂等）。"""
    from edu_cloud.modules.card.publish_service import upsert_questions_from_skeleton

    skeleton = _build_skeleton(
        slots=[{"sub_regions": [
            {"id": "essay-13", "name": "13", "score": 10, "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
        ]}],
    )

    await upsert_questions_from_skeleton(db, **{
        "subject_id": empty_subject["subject_id"],
        "school_id": empty_subject["school_id"],
        "skeleton": skeleton,
    })
    await db.commit()

    # 再跑一次，更新分值
    skeleton["slots"][0]["sub_regions"][0]["score"] = 12
    q_map2 = await upsert_questions_from_skeleton(db, **{
        "subject_id": empty_subject["subject_id"],
        "school_id": empty_subject["school_id"],
        "skeleton": skeleton,
    })
    await db.commit()

    qs = (await db.execute(select(Question).where(Question.subject_id == empty_subject["subject_id"]))).scalars().all()
    assert len(qs) == 1, f"幂等失败，Question 数量 {len(qs)} != 1"
    assert qs[0].max_score == 12.0, f"分值未更新，实际 {qs[0].max_score}"


async def test_S4_upsert_preserves_orphan(db, empty_subject):
    """S4: 首次 publish 有题目 13/14/15，二次 publish 只有 13/14（老师删了 15）→ DB 仍 3 条。"""
    from edu_cloud.modules.card.publish_service import upsert_questions_from_skeleton

    skel1 = _build_skeleton(slots=[{"sub_regions": [
        {"id": "essay-13", "name": "13", "score": 10, "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
        {"id": "essay-14", "name": "14", "score": 10, "rect": {"x1": 0, "y1": 100, "x2": 100, "y2": 200}},
        {"id": "essay-15", "name": "15", "score": 10, "rect": {"x1": 0, "y1": 200, "x2": 100, "y2": 300}},
    ]}])
    await upsert_questions_from_skeleton(db, subject_id=empty_subject["subject_id"],
                                          school_id=empty_subject["school_id"], skeleton=skel1)
    await db.commit()

    # 二次 publish 只有 13/14
    skel2 = _build_skeleton(slots=[{"sub_regions": [
        {"id": "essay-13", "name": "13", "score": 10, "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
        {"id": "essay-14", "name": "14", "score": 10, "rect": {"x1": 0, "y1": 100, "x2": 100, "y2": 200}},
    ]}])
    await upsert_questions_from_skeleton(db, subject_id=empty_subject["subject_id"],
                                          school_id=empty_subject["school_id"], skeleton=skel2)
    await db.commit()

    qs = (await db.execute(select(Question).where(Question.subject_id == empty_subject["subject_id"]))).scalars().all()
    assert len(qs) == 3, f"孤儿保留失败，Question 数量 {len(qs)} != 3"
    names = {q.name for q in qs}
    assert names == {"13", "14", "15"}
```

- [ ] **Step 2: 运行 Red verification**

```bash
python -m pytest tests/test_services_exam/test_publish_service.py::test_S2_upsert_questions_from_skeleton_new_subject -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'edu_cloud.modules.card.publish_service'`

- [ ] **Step 3: 创建 publish_service.py 最小实现**

创建 `src/edu_cloud/modules/card/publish_service.py`:

```python
"""F003 B1 新模块：publish 一站式原子操作的业务逻辑层。

职责边界：
- 纯业务层，不做 HTTP 层校验（router 负责）
- DB 写入在单事务内（调用方传入 db session）
- PDF 生成不在本模块（调用方在事务外完成）
"""
from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from edu_cloud.modules.exam.models import Question

logger = logging.getLogger(__name__)


async def upsert_questions_from_skeleton(
    db: AsyncSession,
    subject_id: str,
    school_id: str,
    skeleton: dict,
) -> dict[str, str]:
    """从 skeleton 扫描 regions + objective_groups，upsert Question 表，返回 {name: question_id} map。

    upsert 语义（决策 D4）:
      - 匹配 (subject_id, name)：存在 → UPDATE max_score/question_type；不存在 → INSERT
      - 孤儿（DB 有但 skeleton 没）→ 保留不动

    命名约定（决策 D3）:
      - 选择题组 → 按 start_no + i 展开为 N 条 Question.name = str(qno)
      - 主观题 slot → Question.name = slot["name"]（字符串形式的题号）

    返回：{name: question_id} 映射表，供后续 skeleton_to_paperseg_json 构建 Template.regions。
    """
    # 1. 从 skeleton 提取题目清单 [(name, question_type, max_score)]
    items: list[tuple[str, str, float]] = []

    for group in skeleton.get("objective_groups", []) or []:
        start_no = group.get("start_no", 1)
        count = group.get("count", 0)
        per_score = group.get("per_score", 0) or 0
        for i in range(count):
            qno = str(start_no + i)
            items.append((qno, "objective", float(per_score)))

    for slot in skeleton.get("slots", []) or []:
        for sr in slot.get("sub_regions", []) or []:
            name = sr.get("name")
            if not name:
                logger.warning(
                    "publish_service: skip anonymous slot sub_region id=%s",
                    sr.get("id"),
                )
                continue
            score = float(sr.get("score", 0) or 0)
            items.append((str(name), "subjective", score))

    if not items:
        logger.info("upsert_questions: empty skeleton, nothing to upsert")
        return {}

    # 2. 读取现有 Question（subject_id 范围）
    existing = (await db.execute(
        select(Question).where(
            Question.subject_id == subject_id,
            Question.school_id == school_id,
        )
    )).scalars().all()
    existing_by_name = {q.name: q for q in existing}

    # 3. upsert 循环
    name_to_id: dict[str, str] = {}
    for name, qtype, max_score in items:
        if name in existing_by_name:
            q = existing_by_name[name]
            q.question_type = qtype
            q.max_score = max_score
            name_to_id[name] = q.id
        else:
            q = Question(
                subject_id=subject_id,
                school_id=school_id,
                name=name,
                question_type=qtype,
                max_score=max_score,
            )
            db.add(q)
            await db.flush()  # 拿到 q.id 供 question_map 返回
            name_to_id[name] = q.id

    # 孤儿保留：existing 中不在 items 里的 Question 不动

    logger.info(
        "upsert_questions: subject=%s upserted=%d orphans=%d",
        subject_id, len(items),
        len(existing) - len([q for q in existing if q.name in name_to_id]),
    )
    return name_to_id
```

- [ ] **Step 4: 运行所有 3 个单元测试，确认 Green**

```bash
python -m pytest tests/test_services_exam/test_publish_service.py -v
```

Expected: 3 passed (S2 / S3 / S4)

- [ ] **Step 5: 跑 exam 广域回归确认无干扰**

```bash
python -m pytest tests/test_services_exam/ tests/test_api_exam/test_marking.py tests/test_api_exam/test_grading_task.py -q
```

Expected: 全部 pass（含前面批次的 B2 / B3a 测试）

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/modules/card/publish_service.py tests/test_services_exam/test_publish_service.py
git commit -m "feat(card): F003 B1 publish_service.upsert_questions_from_skeleton + S2/S3/S4 (T3)"
```

**测试契约（S2/S3/S4）:**

| slice | 入口 | 反例 | 边界 | 回归 | 命令 |
|-------|------|------|------|------|------|
| S2 | `upsert_questions_from_skeleton(db, subject_id, school_id, skeleton)` 空 subject + 15 题 skeleton | 错误实现只创建 subjective 或只创建 objective group 合并为 1 条 → 数量 ≠ 15 | 空 skeleton → 返回 `{}` 不抛异常 | F003 Question 创建入口 | `pytest tests/test_services_exam/test_publish_service.py::test_S2_upsert_questions_from_skeleton_new_subject -v` |
| S3 | 同 skeleton 连续调用 2 次 | 错误实现第二次插入新 Question → 数量 ×2 | 第二次 score 变更 → UPDATE 而非 INSERT | 幂等性 | `pytest tests/test_services_exam/test_publish_service.py::test_S3_upsert_questions_idempotent -v` |
| S4 | 首次 3 题 → 再次 2 题（删一题） | 错误实现 hard-delete → DB 剩 2 条 | 孤儿 Question 保留 → DB 仍 3 条 | 决策 D4 孤儿保留 | `pytest tests/test_services_exam/test_publish_service.py::test_S4_upsert_preserves_orphan -v` |

**边界条件:**
- 空 skeleton（无 objective_groups 无 slots）→ 返回 `{}`，不抛异常
- slot 的 sub_region 缺 name → log warning 并 skip（不崩）
- objective_group count=0 → 不展开任何 Question
- 同一 name 重复出现在 skeleton（数据脏）→ 幂等语义自动去重（后一次覆盖前一次）

**审查清单:**
- ✓ 正向：3 个测试 PASS
- ✓ 正向：返回 `{name: question_id}` 映射完整
- ✓ 正向：广域 exam 测试无回归
- ✓ 正向：孤儿 Question 不被删
- ✗ 反向：使用 hard-delete 策略（违反 D4）
- ✗ 反向：尝试做 UniqueConstraint 检查（Task 5 才加约束）
- 关键行为：`flush()` 调用获取新 Question.id，不 commit（事务由调用方管理）

---

### Task 4: `publish_service.upsert_template_both_sides` + S5 unit test

**Files:**
- Modify: `src/edu_cloud/modules/card/publish_service.py`（追加函数）
- Modify: `tests/test_services_exam/test_publish_service.py`（追加 S5）

- [ ] **Step 1: 写失败测试（Red） — S5**

在 `tests/test_services_exam/test_publish_service.py` 追加：

```python
async def test_S5_upsert_template_both_sides(db, empty_subject):
    """S5: skeleton 含 A/B 双面 region → upsert 后 Template 表有 2 条记录 (A 面 + B 面)。"""
    from edu_cloud.modules.card.publish_service import (
        upsert_questions_from_skeleton, upsert_template_both_sides,
    )
    from edu_cloud.modules.card.models import Template

    # 构造含双面 region 的 skeleton（模拟 extract_skeleton 输出）
    skeleton = {
        "image_width": 1587,
        "image_height": 1123,
        "anchors": [],
        "objective_groups": [],
        "slots": [{"sub_regions": [
            {"id": "essay-13", "name": "13", "score": 10, "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
            {"id": "essay-14", "name": "14", "score": 10, "rect": {"x1": 0, "y1": 100, "x2": 100, "y2": 200}},
        ]}],
        # regions 字段：extract_skeleton 输出的 DOM region 列表，含 side 字段
        "regions": [
            {"id": "essay-13", "type": "subjective", "qno": 13, "side": "A",
             "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
            {"id": "essay-14", "type": "subjective", "qno": 14, "side": "B",
             "rect": {"x1": 0, "y1": 100, "x2": 100, "y2": 200}},
        ],
    }

    q_map = await upsert_questions_from_skeleton(
        db, subject_id=empty_subject["subject_id"],
        school_id=empty_subject["school_id"], skeleton=skeleton,
    )

    tpl_a, tpl_b = await upsert_template_both_sides(
        db,
        subject_id=empty_subject["subject_id"],
        school_id=empty_subject["school_id"],
        skeleton=skeleton,
        question_map=q_map,
    )
    await db.commit()

    assert tpl_a is not None and tpl_a.side == "A"
    assert tpl_b is not None and tpl_b.side == "B"

    templates = (await db.execute(
        select(Template).where(Template.subject_id == empty_subject["subject_id"])
    )).scalars().all()
    assert len(templates) == 2
    sides = {t.side for t in templates}
    assert sides == {"A", "B"}


async def test_S5b_single_side_only_A(db, empty_subject):
    """S5b: skeleton 只有 A 面 region → 仅 A 面 Template，B 面返回 None (合法)。

    单面答题卡 A-only 是合法的 publish 状态。
    """
    from edu_cloud.modules.card.publish_service import (
        upsert_questions_from_skeleton, upsert_template_both_sides,
    )
    from edu_cloud.modules.card.models import Template

    skeleton = {
        "image_width": 1587, "image_height": 1123, "anchors": [],
        "objective_groups": [], "slots": [],
        "regions": [
            {"id": "essay-13", "type": "subjective", "qno": 13, "side": "A",
             "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
        ],
    }
    q_map = await upsert_questions_from_skeleton(
        db, subject_id=empty_subject["subject_id"],
        school_id=empty_subject["school_id"], skeleton=skeleton,
    )
    tpl_a, tpl_b = await upsert_template_both_sides(
        db, subject_id=empty_subject["subject_id"],
        school_id=empty_subject["school_id"], skeleton=skeleton, question_map=q_map,
    )
    await db.commit()
    assert tpl_a is not None and tpl_a.side == "A"
    assert tpl_b is None


async def test_S5c_only_B_side_raises_400(db, empty_subject):
    """S5c (Plan Review R1 F002 修正): B-only publish 违反 design §5.1 'A 面必存' 契约 → 必须 raise HTTPException(400)。

    反例：错误实现允许 tpl_a=None + tpl_b=Template → 下游按 A 面查 Template 查不到
    pipeline_router.py 默认 side="A" 读取，B-only 会造成隐藏运行时故障。
    """
    from fastapi import HTTPException
    from edu_cloud.modules.card.publish_service import (
        upsert_questions_from_skeleton, upsert_template_both_sides,
    )

    skeleton = {
        "image_width": 1587, "image_height": 1123, "anchors": [],
        "objective_groups": [], "slots": [],
        "regions": [
            {"id": "essay-13", "type": "subjective", "qno": 13, "side": "B",
             "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
        ],
    }
    q_map = await upsert_questions_from_skeleton(
        db, subject_id=empty_subject["subject_id"],
        school_id=empty_subject["school_id"], skeleton=skeleton,
    )

    with pytest.raises(HTTPException) as exc_info:
        await upsert_template_both_sides(
            db, subject_id=empty_subject["subject_id"],
            school_id=empty_subject["school_id"], skeleton=skeleton, question_map=q_map,
        )
    assert exc_info.value.status_code == 400
    assert "A 面" in exc_info.value.detail
```

- [ ] **Step 2: Red verify**

```bash
python -m pytest tests/test_services_exam/test_publish_service.py::test_S5_upsert_template_both_sides -v
```

Expected: FAIL — `ImportError: cannot import name 'upsert_template_both_sides'`

- [ ] **Step 3: 在 publish_service.py 追加 upsert_template_both_sides**

追加：

```python
from edu_cloud.modules.card.models import Template


async def upsert_template_both_sides(
    db: AsyncSession,
    subject_id: str,
    school_id: str,
    skeleton: dict,
    question_map: dict[str, str],
) -> tuple[Template, Template | None]:
    """按 skeleton.regions[].side 分组，构建 A 面 + B 面 Template，upsert 走 UniqueConstraint(subject_id, side)。

    返回 (tpl_a, tpl_b)，A 面必存（tpl_a 不为 None），B 面可选（单面考试时 tpl_b=None）。

    契约（Plan Review R1 F002）: design §5.1 明确 "A 面必存，B 面可选"。
    - A-only publish (常见单面答题卡) → 返回 (tpl_a, None)
    - A+B publish (双面答题卡) → 返回 (tpl_a, tpl_b)
    - B-only publish → raise HTTPException(400, "发布失败：答题卡必须包含 A 面内容")
      （下游 pipeline_router / export.py 默认按 side="A" 查 Template，B-only 会产生隐藏故障）

    依赖：skeleton["regions"] 含 side 字段（F001 修复后）。
    """
    from fastapi import HTTPException
    from edu_cloud.modules.card.export import skeleton_to_paperseg_json

    # 按 side 分组 regions
    regions_by_side: dict[str, list[dict]] = {"A": [], "B": []}
    for r in skeleton.get("regions", []) or []:
        side = r.get("side", "A")
        if side not in regions_by_side:
            side = "A"  # 异常值降级到 A 面
        regions_by_side[side].append(r)

    # F002 契约硬校验：A 面必存
    if not regions_by_side["A"]:
        if regions_by_side["B"]:
            raise HTTPException(
                400,
                "发布失败：答题卡必须包含 A 面内容（B-only 不支持，"
                "下游扫描/阅卷默认按 A 面查 Template）",
            )
        raise HTTPException(400, "发布失败：答题卡为空（skeleton.regions 无内容）")

    result: list[Template | None] = [None, None]  # [A, B]

    for idx, side in enumerate(("A", "B")):
        side_regions = regions_by_side[side]
        if not side_regions:
            continue

        # 构造 side 专属的 skeleton subset
        side_skeleton = {
            **skeleton,
            "regions": side_regions,
            # slots / objective_groups 不按 side 拆分，这里保留原 skeleton 数据（export.py 只读 regions）
        }
        tpl_data = skeleton_to_paperseg_json(
            side_skeleton,
            {"slots": skeleton.get("slots", [])},
            exam_id="",  # 本函数不处理 exam_id
            subject="",
            side=side,
            question_map=question_map,
        )

        # upsert Template by (subject_id, side)
        existing_tpl = (await db.execute(
            select(Template).where(
                Template.subject_id == subject_id,
                Template.side == side,
            )
        )).scalar_one_or_none()

        values = {
            "image_width": tpl_data["image_size"]["width"],
            "image_height": tpl_data["image_size"]["height"],
            "anchors": tpl_data["anchors"],
            "regions": tpl_data["regions"],
        }

        if existing_tpl:
            for k, v in values.items():
                setattr(existing_tpl, k, v)
            result[idx] = existing_tpl
        else:
            tpl = Template(
                subject_id=subject_id,
                side=side,
                school_id=school_id,
                **values,
            )
            db.add(tpl)
            await db.flush()
            result[idx] = tpl

    return result[0], result[1]
```

- [ ] **Step 4: Green verify + 回归**

```bash
python -m pytest tests/test_services_exam/test_publish_service.py -v
```

Expected: 6 passed（S2/S3/S4 + S5 + S5b + S5c）

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/card/publish_service.py tests/test_services_exam/test_publish_service.py
git commit -m "feat(card): F003 B1 publish_service.upsert_template_both_sides + S5/S5b (T4)"
```

**测试契约（S5 / S5b / S5c）:**

| slice | 入口 | 反例 | 边界 | 回归 | 命令 |
|-------|------|------|------|------|------|
| S5 | `upsert_template_both_sides(db, ..., double_side_skeleton)` | 错误实现只写 A 面 → Template 表只 1 条 | A+B region → 2 条 Template 分别 side A 和 B | F003a 双面 Template | `pytest tests/test_services_exam/test_publish_service.py::test_S5_upsert_template_both_sides -v` |
| S5b | `upsert_template_both_sides(db, ..., A_only_skeleton)` | 错误实现 raise 或返回 tpl_a=None | 单面 A skeleton → tpl_a 有值 + tpl_b=None | D6 单面合法 | `pytest test_S5b_single_side_only_A -v` |
| S5c | `upsert_template_both_sides(db, ..., B_only_skeleton)` | 错误实现允许 tpl_a=None + tpl_b=有值 → 下游运行时 404 | B-only skeleton → raise HTTPException(400) 含"A 面" | F002 契约冲突防御 | `pytest test_S5c_only_B_side_raises_400 -v` |

**边界条件:**
- A+B 双面 region → Template 表 2 条（side A + side B）
- 仅 A 面 region → 1 条 (side A) + tpl_b=None（合法单面答题卡）
- 仅 B 面 region → **raise HTTPException(400)**（违反 design §5.1 "A 面必存"契约）
- 空 skeleton.regions → raise HTTPException(400, "skeleton.regions 无内容")
- region.side 值非 'A'/'B'（异常）→ 降级到 A 面
- 重复 publish → 按 (subject_id, side) 唯一约束 upsert，不产生重复

**审查清单:**
- ✓ 正向：双面 skeleton → 2 条 Template
- ✓ 正向：A-only skeleton → 1 条 Template (side A) + tpl_b=None
- ✓ 正向：B-only skeleton → raise HTTPException(400)
- ✓ 正向：重复 upsert 幂等
- ✗ 反向：硬编码 side="A"（违反 D6）
- ✗ 反向：允许 tpl_a=None（违反 F002 契约防御）
- ✗ 反向：破坏 Template 唯一约束（`(subject_id, side)`）
- 关键行为：调用 `export.skeleton_to_paperseg_json` 零改动复用 + **A 面必存硬校验在 regions 分组之后立即执行**

---

**Batch 1 结束 checkpoint：**
- Task 0-4 全部完成
- 测试：11+ 个新 unit + vitest + integration pass
- 无事务/并发/router 接入（留给 Batch 2）
- 前端 render.js 改动已回主线，F001 修复
- **预计耗时：** 4-6 小时 / 1 个 code review batch

---

## Batch 2: 事务层 + schema migration + router 接入（Slice D + E + F）

**目标：** 把 Batch 1 的两个纯函数组装成事务原子操作，加入并发保护，router 层切换到新 service。

### Task 5: Alembic migration — Question 加 UniqueConstraint(subject_id, name)

**Files:**
- Create: `alembic/versions/XXXXX_question_unique_subject_name.py`
- Modify: `src/edu_cloud/modules/exam/models.py:50 class Question` 加 `__table_args__`

**背景：** design.md §5.4 唯一的 schema migration。支持并发 publish 的 IntegrityError 重试策略。

- [ ] **Step 1: 先校验现有数据无冲突**

```bash
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
async def check():
    engine = create_async_engine('postgresql+asyncpg://postgres:password@localhost:5432/edu_cloud')
    async with engine.connect() as conn:
        result = await conn.execute(text('''
            SELECT subject_id, name, COUNT(*) as cnt FROM questions
            GROUP BY subject_id, name HAVING COUNT(*) > 1
        '''))
        rows = result.fetchall()
        print(f'duplicates: {len(rows)}')
        for r in rows[:5]:
            print(r)
asyncio.run(check())
"
```

Expected: `duplicates: 0`（若 > 0 需先清理重复）

- [ ] **Step 2: 生成 alembic migration**

```bash
alembic revision -m "add unique constraint on questions subject_id name"
```

编辑生成的文件（替换 XXXXX 为实际 revision id）:

```python
"""add unique constraint on questions subject_id name

Revision ID: XXXXX
Revises: <prev_head>
Create Date: 2026-04-11 ...

B1 F003: 支持并发 publish 的 IntegrityError 重试策略，防止同一 subject 下重复 Question.name
"""
from alembic import op
import sqlalchemy as sa

revision = 'XXXXX'
down_revision = '<previous>'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_question_subject_name",
        "questions",
        ["subject_id", "name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_question_subject_name", "questions", type_="unique")
```

- [ ] **Step 3: 在 models.py 同步声明 __table_args__**

```python
# 原 class Question:
class Question(Base, IdMixin, TimestampMixin):
    __tablename__ = "questions"

    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id"))
    name: Mapped[str] = mapped_column(String(200))
    ...

# 改为：
class Question(Base, IdMixin, TimestampMixin):
    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("subject_id", "name", name="uq_question_subject_name"),
    )

    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id"))
    ...
```

（注：如果 models.py 顶部已导入 `UniqueConstraint`，跳过 import；否则加 `from sqlalchemy import ..., UniqueConstraint`）

- [ ] **Step 4: 本地跑测试套件，验证 migration 不破坏 in-memory SQLite fixture**

```bash
python -m pytest tests/test_api_exam/test_marking.py tests/test_services_exam/test_publish_service.py -q
```

Expected: 全部 pass（in-memory SQLite 也能识别 UniqueConstraint）

- [ ] **Step 5: 跑 alembic smoke test 验证 upgrade/downgrade**

```bash
python -m pytest tests/test_alembic_migration.py -v
```

Expected: PASS（已有的 alembic smoke test 会自动覆盖新 migration）

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/*_question_unique_subject_name.py src/edu_cloud/modules/exam/models.py
git commit -m "feat(db): F003 Question add UniqueConstraint(subject_id, name) (T5)"
```

**测试契约:**

| slice | 入口 | 反例 | 边界 | 回归 | 命令 |
|-------|------|------|------|------|------|
| E1 | alembic upgrade 新增 migration | 已有重复数据 → migration 失败需先清理 | 空表 / 15 条种子数据 | 并发 publish 保护 | `pytest tests/test_alembic_migration.py -v` |

**边界条件:**
- 空 questions 表 → migration 成功，无数据操作
- 现有 5 科种子数据（地理/化学/历史/生物/政治）已满足唯一性 → 成功
- 下线：downgrade 能正确 drop constraint

**审查清单:**
- ✓ 正向：alembic revision 文件含 upgrade + downgrade 两个函数
- ✓ 正向：models.py `__table_args__` 声明一致
- ✓ 正向：所有既有测试（含 B2 marking tests）仍 PASS
- ✗ 反向：migration 文件用硬编码 revision id 和错误的 down_revision
- ✗ 反向：migration 用 CASCADE DELETE 副作用

---

### Task 6: `publish_card_atomic` 事务原子性（Slice D）+ S6

**Files:**
- Modify: `src/edu_cloud/modules/card/publish_service.py`（追加 `publish_card_atomic`）
- Modify: `tests/test_services_exam/test_publish_service.py`（追加 S6）

- [ ] **Step 1: 写失败测试 S6（Red）**

追加：

```python
from unittest.mock import patch, AsyncMock


async def test_S6_publish_card_atomic_rollback_on_template_fail(db, empty_subject):
    """S6: publish_card_atomic 内 Template upsert 失败 → Question 和 exam.status 都回滚。

    反例：错误实现独立 commit 每一步 → Question 已落库但 Template 失败，状态不一致
    """
    from edu_cloud.modules.card.publish_service import publish_card_atomic
    from edu_cloud.modules.exam.models import Exam, Question
    from edu_cloud.modules.card.models import Template

    # mock html_to_pdf 返回假 bytes
    async def fake_pdf(html, paper_size):
        return b"%PDF-fake"

    async def fake_extract(html):
        return {
            "image_width": 1587, "image_height": 1123, "anchors": [],
            "objective_groups": [], "slots": [],
            "regions": [
                {"id": "essay-13", "type": "subjective", "qno": 13, "side": "A",
                 "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
            ],
        }

    async def boom(*args, **kwargs):
        raise RuntimeError("Template upsert simulation failure")

    with patch("edu_cloud.modules.card.publish_service.html_to_pdf", side_effect=fake_pdf), \
         patch("edu_cloud.modules.card.publish_service.extract_skeleton", side_effect=fake_extract), \
         patch("edu_cloud.modules.card.publish_service.upsert_template_both_sides", side_effect=boom):
        with pytest.raises(RuntimeError, match="Template upsert"):
            await publish_card_atomic(
                db,
                html="<html/>",
                subject_id=empty_subject["subject_id"],
                exam_id=empty_subject["exam_id"],
                school_id=empty_subject["school_id"],
                paper_size="A3",
            )

    # 验证 Question 未落库
    qs = (await db.execute(select(Question).where(Question.subject_id == empty_subject["subject_id"]))).scalars().all()
    assert len(qs) == 0, f"Question 应回滚，实际残留 {len(qs)} 条"

    # 验证 exam.status 仍为 draft
    exam = (await db.execute(select(Exam).where(Exam.id == empty_subject["exam_id"]))).scalar_one()
    assert exam.status == "draft", f"exam.status 应保持 draft，实际 {exam.status}"

    # 验证 Template 未创建
    tpls = (await db.execute(select(Template).where(Template.subject_id == empty_subject["subject_id"]))).scalars().all()
    assert len(tpls) == 0


async def test_S6b_publish_card_atomic_success_path(db, empty_subject):
    """S6b: publish_card_atomic 正常走完全链路 → PDF + Question + Template + exam.status=scanning。"""
    from edu_cloud.modules.card.publish_service import publish_card_atomic
    from edu_cloud.modules.exam.models import Exam, Question
    from edu_cloud.modules.card.models import Template

    async def fake_pdf(html, paper_size):
        return b"%PDF-fake-success"

    async def fake_extract(html):
        return {
            "image_width": 1587, "image_height": 1123, "anchors": [],
            "objective_groups": [], "slots": [{"sub_regions": [
                {"id": "essay-13", "name": "13", "score": 10, "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
            ]}],
            "regions": [
                {"id": "essay-13", "type": "subjective", "qno": 13, "side": "A",
                 "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
            ],
        }

    with patch("edu_cloud.modules.card.publish_service.html_to_pdf", side_effect=fake_pdf), \
         patch("edu_cloud.modules.card.publish_service.extract_skeleton", side_effect=fake_extract):
        pdf_bytes = await publish_card_atomic(
            db,
            html="<html/>",
            subject_id=empty_subject["subject_id"],
            exam_id=empty_subject["exam_id"],
            school_id=empty_subject["school_id"],
            paper_size="A3",
        )

    assert pdf_bytes == b"%PDF-fake-success"

    qs = (await db.execute(select(Question).where(Question.subject_id == empty_subject["subject_id"]))).scalars().all()
    assert len(qs) == 1
    assert qs[0].name == "13"

    tpls = (await db.execute(select(Template).where(Template.subject_id == empty_subject["subject_id"]))).scalars().all()
    assert len(tpls) == 1 and tpls[0].side == "A"

    exam = (await db.execute(select(Exam).where(Exam.id == empty_subject["exam_id"]))).scalar_one()
    assert exam.status == "scanning"
```

- [ ] **Step 2: Red verify**

```bash
python -m pytest tests/test_services_exam/test_publish_service.py::test_S6_publish_card_atomic_rollback_on_template_fail -v
```

Expected: FAIL — `ImportError: cannot import name 'publish_card_atomic'`

- [ ] **Step 3: 实现 publish_card_atomic**

在 publish_service.py 追加：

```python
from sqlalchemy import select
from edu_cloud.modules.card.html_export import html_to_pdf, extract_skeleton
from edu_cloud.modules.exam.models import Exam, Subject


async def publish_card_atomic(
    db: AsyncSession,
    html: str,
    subject_id: str,
    exam_id: str,
    school_id: str,
    paper_size: str,
) -> bytes:
    """publish 一站式原子操作。

    顺序（PDF 生成在事务外，DB 写在事务内）：
      1. 校验 Exam 归属 + Subject 归属 + Exam.status ∈ {draft, scanning}
      2. html_to_pdf → pdf_bytes（事务外，失败直接 raise）
      3. extract_skeleton → skeleton_data（事务外）
      4. [BEGIN] upsert_questions + upsert_template + exam.status [COMMIT]
      5. 返回 pdf_bytes

    任一 DB 步失败 → rollback → raise（调用方决定如何响应）
    """
    from fastapi import HTTPException

    # 1. 校验
    exam = (await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
    )).scalar_one_or_none()
    if not exam:
        raise HTTPException(404, "考试不存在")
    if exam.status not in ("draft", "scanning"):
        raise HTTPException(400, f"考试状态为 {exam.status}，仅 draft/scanning 可发布")

    subject = (await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.school_id == school_id)
    )).scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "科目不存在")
    if subject.exam_id != exam_id:
        raise HTTPException(400, "科目不属于该考试")

    if not html or not html.strip():
        raise HTTPException(400, "HTML 不能为空")

    # 2. PDF 生成（事务外）
    pdf_bytes = await html_to_pdf(html, paper_size)

    # 3. Skeleton 提取（事务外）
    skeleton = await extract_skeleton(html)

    # 4. 事务内：Question upsert + Template upsert + exam.status
    try:
        question_map = await upsert_questions_from_skeleton(
            db, subject_id=subject_id, school_id=school_id, skeleton=skeleton,
        )
        await upsert_template_both_sides(
            db, subject_id=subject_id, school_id=school_id,
            skeleton=skeleton, question_map=question_map,
        )
        if exam.status == "draft":
            exam.status = "scanning"
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    logger.info(
        "publish_card_atomic: exam=%s subject=%s questions=%d success",
        exam_id, subject_id, len(question_map),
    )
    return pdf_bytes
```

- [ ] **Step 4: Green verify**

```bash
python -m pytest tests/test_services_exam/test_publish_service.py -v
```

Expected: 7 tests pass（含 S6 + S6b + 前 5 个）

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/card/publish_service.py tests/test_services_exam/test_publish_service.py
git commit -m "feat(card): F003 B1 publish_card_atomic + S6/S6b 事务原子性 (T6)"
```

**测试契约（S6/S6b）:**

| slice | 入口 | 反例 | 边界 | 回归 | 命令 |
|-------|------|------|------|------|------|
| S6 | `publish_card_atomic(db, html, ...)` Template 失败 mock | 错误实现独立 commit 每步 → 失败时 Question 已落库 | Template 失败时 Question 也回滚 | 事务原子性 | `pytest test_S6_publish_card_atomic_rollback_on_template_fail -v` |
| S6b | 正常走完全流程 | 错误实现漏写 exam.status 或漏 commit | PDF bytes + Question + Template + status 切换全部完成 | 完整路径 | `pytest test_S6b_publish_card_atomic_success_path -v` |

**边界条件:**
- Exam 不存在 → 404
- Subject 不属于当前 exam → 400
- Exam.status = completed → 400
- HTML 空 → 400
- html_to_pdf 失败 → 500 事务外，DB 无变化
- upsert_questions 失败 → rollback，Template 未写入
- upsert_template 失败 → rollback，Question 回滚，exam.status 回滚
- exam.status 从 scanning 再次 publish → 保持 scanning（幂等）

**审查清单:**
- ✓ 正向：S6/S6b 两个 test pass
- ✓ 正向：事务边界清晰——PDF 生成在事务外，DB 写入在事务内
- ✓ 正向：异常必定 rollback
- ✓ 正向：exam.status 从 draft → scanning 的升级只触发一次（幂等）
- ✗ 反向：任何 `await db.commit()` 出现在事务块之外（PDF 生成之前）
- ✗ 反向：catch Exception 后没有 rollback
- 关键行为：函数签名稳定，下一 Task (T7) 只在内部加 IntegrityError retry 不改签名

---

### Task 7: 并发 IntegrityError retry（Slice D 扩展）+ S7a/S7b/S7c（R2-F001 + R3-F001 修正）

**Files:**
- Modify: `src/edu_cloud/modules/card/publish_service.py upsert_questions_from_skeleton`
- Modify: `tests/test_services_exam/test_publish_service.py`（追加 S7a/S7b/S7c）

**背景：** T5 加了 UniqueConstraint 后，并发 publish 会产生 IntegrityError。需要捕获+重试一次。

**R2-F001 修正（事务边界重设）：** `upsert_questions_from_skeleton` 被 T6 的 `publish_card_atomic` 包在**同一事务内**（见 design §6.1 / plan invariant I2）。如果单题冲突时直接 `await db.rollback()` 会连带回滚同事务中前面**已成功 upsert 的其他 Question**，但循环只补救当前冲突题——造成"部分 Question 丢失 + Template 仍引用"的半提交状态，破坏 INV-002 / INV-005。

**正确方案**：用 SQLAlchemy `async with db.begin_nested():` SAVEPOINT 让单题 retry 只回滚子事务，外层 publish 事务继续推进。SAVEPOINT 与 SQLite + PostgreSQL 都兼容（SQLite 自 3.6.8 支持，SQLAlchemy 原生封装）。

**R3-F001 修正（S7 测试设计重构）**：R3 审查发现原 S7 有 3 个问题：
1. rival `"14"` 预 commit 后，被测代码首次 `SELECT` 就会直接找到 rival，**走 existing fast path 而不是 SAVEPOINT retry 分支**
2. 使用未绑定到 `db` fixture 的全局 `async_session`（会打到生产配置 DB，与断言查询的 in-memory SQLite 脱节）
3. flush-time race 的确定性触发需要精确时序控制，SQLite in-memory 下难以实现

**R3-F001 后的测试策略（S7 拆成 3 个独立测试）：**

- **S7a** — **纯 SAVEPOINT 语义单元测试**（不涉及被测函数）：手动构造 3 个 Question，其中一个在 `async with db.begin_nested():` 内 `raise IntegrityError`，断言外层事务 commit 后另外 2 个 Question 仍落库。这证明 SAVEPOINT 语义是正确的——错误实现（全局 `db.rollback()`）会让 3 个 Question 全部丢失。
- **S7b** — **被测函数的 SELECT-first existing fast path 测试**：`db` fixture 预插入 rival `"14"` 并 commit；调用 `upsert_questions_from_skeleton` 处理 skeleton `[13, 14, 15]`；断言 3 题都在，`"14"` 指向 rival_id，`max_score` 已更新到新值。这证明**先 SELECT 后 INSERT 的 upsert 策略正确**——也是被测函数的主路径。
- **S7c** — **被测函数用 SAVEPOINT retry 分支的 monkeypatch 测试**：用 `monkeypatch.setattr(AsyncSession, 'flush', ...)` 让 `"14"` 处理时的 `db.flush()` 首次抛 `IntegrityError`（配合预插入 rival 在 re-SELECT 时可见），验证 retry 分支被命中且外层事务前序 Question 保留。**若 fixture 无法稳定触发**，S7c 标为 `test_debt` 延期到 PostgreSQL CI，但仍在 plan 留具体实现草稿供 R4 审查；S7a + S7b + 代码审查作为 Gate 1 PASS 的充分条件。

**禁止模式（R2-F001 + R3-F001 forbidden）**：
- ❌ 在循环内全局 `await db.rollback()` 后继续跑剩余题目
- ❌ 吞 IntegrityError 不重建 state
- ❌ 无限重试 / 嵌套重试
- ❌ （R3-F001）使用未绑定 `db` fixture 的全局 `async_session` 进行跨 session rival 预插
- ❌ （R3-F001）在 `async_session` monkey-patch 未生效的情况下调用 factory 函数（工厂调用必须在 `client` fixture 上下文内，否则打到生产 DB）

- [ ] **Step 1: 写 S7a 纯 SAVEPOINT 语义测试（R3-F001 修正，不涉及被测函数）**

S7a 目的：证明 `async with db.begin_nested(): ... raise IntegrityError` 退出时只回滚 SAVEPOINT 子事务，**外层事务中前面已 `db.flush()` 的对象保留**。本测试不涉及被测函数，只验证 SQLAlchemy async SAVEPOINT 语义是 SAVEPOINT 修复方向的基础。

```python
async def test_S7a_savepoint_semantics_preserves_outer_tx(db, empty_subject):
    """S7a (R3-F001): 纯 SAVEPOINT 语义——子事务 rollback 不破坏外层事务中其他对象。

    本测试不涉及被测函数 upsert_questions_from_skeleton，
    直接用 db session 构造场景：三题 [13, 14, 15]，中间用 begin_nested + raise 模拟 '14' 冲突。
    断言：外层 commit 后 DB 有 '13' 和 '15'（外层事务保留），'14' 被 SAVEPOINT 回滚消失。

    反例: 错误实现用外层 db.rollback() → 外层事务整体回滚 → '13' 也消失 → names != ['13','15']
    """
    from sqlalchemy.exc import IntegrityError
    subject_id = empty_subject["subject_id"]
    school_id = empty_subject["school_id"]

    # Step A: 外层事务内先 add + flush q_13（模拟 upsert_questions 循环第一题成功）
    q_13 = Question(
        subject_id=subject_id, school_id=school_id,
        name="13", question_type="subjective", max_score=10.0,
    )
    db.add(q_13)
    await db.flush()  # q_13 在外层事务中 pending

    # Step B: 进入 SAVEPOINT 子事务模拟 q_14 冲突
    try:
        async with db.begin_nested():  # SAVEPOINT
            q_14 = Question(
                subject_id=subject_id, school_id=school_id,
                name="14", question_type="subjective", max_score=12.0,
            )
            db.add(q_14)
            # 模拟 flush 时 UniqueConstraint 冲突（不需要真实 race，直接 raise）
            raise IntegrityError("simulated flush race", params=None, orig=Exception("race"))
    except IntegrityError:
        # SAVEPOINT 自动 rollback（async with 退出），q_14 被抛弃
        pass

    # Step C: 继续 add q_15（模拟循环第三题）
    q_15 = Question(
        subject_id=subject_id, school_id=school_id,
        name="15", question_type="subjective", max_score=15.0,
    )
    db.add(q_15)
    await db.flush()

    # Step D: 外层事务 commit
    await db.commit()

    # 断言: DB 有 q_13 和 q_15（外层保留），没有 q_14（SAVEPOINT 回滚）
    qs = (await db.execute(
        select(Question).where(Question.subject_id == subject_id).order_by(Question.name)
    )).scalars().all()
    names = [q.name for q in qs]
    assert names == ["13", "15"], (
        f"外层事务应保留 '13' 和 '15'（SAVEPOINT 回滚 '14'），实际 {names}"
        " —— 错误实现用外层 rollback 会让 '13'/'15' 全部消失"
    )
```

- [ ] **Step 1b: 写 S7b 被测函数 SELECT-first existing fast path 测试（Red → Green，R3-F001 修正）**

S7b 目的：验证被测函数 `upsert_questions_from_skeleton` 的 **SELECT-first existing update** 主路径——预插入 rival "14"，调被测函数处理 `[13, 14, 15]`，断言被测函数**不走 SAVEPOINT retry 分支**（因为 SELECT 已经找到 existing），而是走 update 分支。这是主路径，也是 R3 审查确认 "rival 预插就走 fast path" 后的正确测试定位。

```python
async def test_S7b_upsert_questions_existing_fast_path(db, empty_subject):
    """S7b (R3-F001 修正): 预插入 rival "14" → 被测函数 SELECT 命中 → existing update 分支。

    这不是 retry 分支测试，而是被测函数的主路径测试：
    - SELECT first: 先查 (subject_id, name) 是否已存在
    - existing → update (question_type + max_score)
    - no match → INSERT path (可能触发 SAVEPOINT retry，见 S7c)

    反例: 错误实现不先 SELECT 直接 INSERT → DB 最终有 2 条 "14"（rival + 新插）或 IntegrityError
          → names 长度 != 3 或 q14.id != rival_id
    """
    from edu_cloud.modules.card.publish_service import upsert_questions_from_skeleton

    subject_id = empty_subject["subject_id"]
    school_id = empty_subject["school_id"]

    # 同 db session 预插入 rival "14" 并 commit → 被测代码 SELECT 能立即看到
    rival = Question(
        subject_id=subject_id, school_id=school_id,
        name="14", question_type="subjective", max_score=5.0,
    )
    db.add(rival)
    await db.commit()
    rival_id = rival.id

    skeleton = _build_skeleton(slots=[{"sub_regions": [
        {"id": "essay-13", "name": "13", "score": 10, "rect": {"x1": 0, "y1": 0, "x2": 50, "y2": 50}},
        {"id": "essay-14", "name": "14", "score": 12, "rect": {"x1": 0, "y1": 50, "x2": 50, "y2": 100}},
        {"id": "essay-15", "name": "15", "score": 15, "rect": {"x1": 0, "y1": 100, "x2": 50, "y2": 150}},
    ]}])

    q_map = await upsert_questions_from_skeleton(
        db, subject_id=subject_id, school_id=school_id, skeleton=skeleton,
    )
    await db.commit()

    qs = (await db.execute(
        select(Question).where(Question.subject_id == subject_id).order_by(Question.name)
    )).scalars().all()
    names = [q.name for q in qs]
    assert names == ["13", "14", "15"], f"应有 3 题（13/14/15），实际 {names}"

    q14 = next(q for q in qs if q.name == "14")
    assert q14.id == rival_id, "'14' 应命中 rival existing 记录（走 SELECT-first fast path）"
    assert q14.max_score == 12.0, f"existing update: max_score 应更新为 12，实际 {q14.max_score}"

    assert set(q_map.keys()) == {"13", "14", "15"}
    assert q_map["14"] == rival_id, "q_map['14'] 应指向 rival_id"
```

- [ ] **Step 1c: S7c 不写实现代码 → 纯 test_debt 延期（R4-F003 修正）**

**R4-F003 修正**：R3 阶段曾给 S7c 写 monkeypatch flush 拦截实现草稿，但 R4 审查发现该实现**逻辑上不可证**：在同一 SAVEPOINT 子事务内偷插 rival 后 `raise IntegrityError`，SAVEPOINT rollback 会把 rival 一并回滚，后续 re-SELECT 永远找不到 rival，retry 分支无法触达。

**决策**：本 Task **不写 S7c 实现代码**。SAVEPOINT retry 分支的 flush-time race 测试改为纯 `test_debt` 条目，延期到 PostgreSQL CI 激活时通过独立 session / 独立 connection 设计。

**禁止模式（R4-F003 forbidden）**:
- ❌ 在同一 SAVEPOINT 子事务内 "偷插 rival + raise IntegrityError"（rollback 会一并回滚 rival，逻辑矛盾）
- ❌ 用 monkeypatch flush 拦截模拟 race（拦截时序在 SQLite in-memory 下不稳定，且 rival 注入点无论放哪都会与 SAVEPOINT 回滚冲突）
- ❌ 把 "可能的实现草稿" 保留在 plan 里作为 best-effort——要么写完整可证代码，要么完全删除

**Gate 1 PASS 的 SAVEPOINT retry 分支护栏**（不依赖 S7c）:
1. **S7a**（纯 SAVEPOINT 语义）— 直接用 `db` fixture 手动构造 `async with db.begin_nested(): raise IntegrityError`，断言外层事务前序保留（已在 Step 1 写完整实现）
2. **S7b**（SELECT-first existing fast path）— 被测函数主路径（已在 Step 1b 写完整实现）
3. **代码审查**（Gate 2 Code Review 任务）— reviewer 必须确认 source 含 `async with db.begin_nested():` + `except IntegrityError:` + re-SELECT 结构
4. **Contract Pack `test_debt` 条目**（R4-F003 更新）— 明确记录 PostgreSQL CI 延期方案草稿

**PostgreSQL CI 延期方案草稿**（未来激活，不在本批次执行）:
- 使用 `testcontainers-python` 启动真实 PostgreSQL 16 容器，或在 GHA CI 中起 postgres service
- `db_engine` fixture 切换为 `create_async_engine("postgresql+asyncpg://...")`
- S7c 实现草稿：用两个独立 session（不同 `async_sessionmaker` 调用），Session B 通过原生 `asyncpg.connect()` 或**不同的 AsyncSession** 预 `commit` rival "14"（跨 session 可见），然后 Session A 调被测函数 `upsert_questions_from_skeleton([13,14,15])`——"14" 的 `SELECT` 在 Session A 的新事务里能看到 rival（走 existing fast path），或 INSERT 时真实触发 UniqueConstraint 冲突（进入 SAVEPOINT retry）
- 验证点：Session A 的外层事务 commit 后 DB 有 3 题，"14" 指向 rival，"13"/"15" 保留

- [ ] **Step 2: Red verify**

```bash
python -m pytest tests/test_services_exam/test_publish_service.py::test_S7a_savepoint_semantics_preserves_outer_tx -v
python -m pytest tests/test_services_exam/test_publish_service.py::test_S7b_upsert_questions_existing_fast_path -v
```

**Expected (Red)**:
- S7a 应立即 PASS（纯 SAVEPOINT 语义，不依赖被测函数实现）
- S7b 若 T3 当前实现已有 SELECT-first existing update 主路径 → PASS；若只有 INSERT → FAIL（需要 Step 3 补 SELECT-first 逻辑）
- S7c 不写实现代码（R4-F003 修正），纯 test_debt 延期，此处无 Red/Green 命令

- [ ] **Step 3: 加入 SELECT-first + SAVEPOINT 单题 retry（R2-F001 + R3-F001 修正）**

修改 `upsert_questions_from_skeleton` 内部循环，实现 **SELECT-first → existing update 分支 / INSERT path with SAVEPOINT retry**：

```python
# 原（T3 概念实现）：
q = Question(...)
db.add(q)
await db.flush()
name_to_id[name] = q.id

# 改为（R2-F001 + R3-F001 SELECT-first + SAVEPOINT 方案）：
# === SELECT-first: 先查 existing（主路径，S7b 验证）===
existing_q = (await db.execute(
    select(Question).where(
        Question.subject_id == subject_id,
        Question.name == name,
    )
)).scalar_one_or_none()

if existing_q:
    # Fast path: update in place
    existing_q.question_type = qtype
    existing_q.max_score = max_score
    name_to_id[name] = existing_q.id
    continue

# === INSERT path with SAVEPOINT retry（S7a 语义 / S7c best-effort 验证）===
q = Question(subject_id=subject_id, school_id=school_id, name=name,
              question_type=qtype, max_score=max_score)
try:
    # SAVEPOINT: nested transaction, 冲突时只回滚子事务, 外层事务继续
    async with db.begin_nested():
        db.add(q)
        await db.flush()  # UniqueConstraint 冲突在此抛 IntegrityError
    name_to_id[name] = q.id
except IntegrityError:
    # SAVEPOINT 已自动回滚 (async with 退出时), 外层事务前序 Question 保留
    logger.warning(
        "upsert_questions: concurrent INSERT race for (subject=%s, name=%s), re-selecting existing",
        subject_id, name,
    )
    existing_q = (await db.execute(
        select(Question).where(
            Question.subject_id == subject_id,
            Question.name == name,
        )
    )).scalar_one()
    existing_q.question_type = qtype
    existing_q.max_score = max_score
    name_to_id[name] = existing_q.id
```

**关键点（reviewer 必须理解）**：
1. **SELECT-first 主路径**（S7b 验证）：避免 race 的最好办法是先 SELECT；绝大多数 publish 走此路径
2. `async with db.begin_nested():` 创建 SQLAlchemy SAVEPOINT 子事务（S7a 语义验证）
3. 子事务内 `db.flush()` 触发的 IntegrityError 让 `async with` 退出时自动 `SAVEPOINT ROLLBACK`，**只回滚当前子事务**
4. **外层事务**（`publish_card_atomic` 的 `async with db.begin():`）**继续有效**，前面已 flush 的 Question 保留
5. IntegrityError 从 `async with` 块传出被 except 捕获，逻辑进入 re-SELECT 分支（真实 race 才会走这条，主路径用 SELECT-first 规避）
6. 循环继续处理下一题；全部结束后外层事务一次 commit

**不允许的模式**：
- ❌ `await db.rollback()` — 回滚整个外层事务，破坏 publish 原子性
- ❌ 外层 `try/except` 包住整个循环 — 单题失败无法精准 retry
- ❌ 嵌套 retry（retry 内又 retry）— 无限循环风险
- ❌ 跳过 SELECT-first 直接 INSERT — 浪费 SAVEPOINT retry（S7b 主路径被绕过）

- [ ] **Step 4: Green verify + 前面所有测试**

```bash
python -m pytest tests/test_services_exam/test_publish_service.py -v
```

Expected: S7a + S7b PASS；前面所有测试保持 pass。S7c 不在本批次运行（纯 test_debt 延期）。

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/card/publish_service.py tests/test_services_exam/test_publish_service.py
git commit -m "feat(card): F003 SELECT-first + SAVEPOINT retry + S7a/b/c (T7, R2-F001 + R3-F001)"
```

**测试契约（S7a/b，R1-F004 + R2-F001 + R3-F001 + R4-F003 修正）:**

| slice | 入口 | 反例 | 边界 | 回归 | 命令 |
|-------|------|------|------|------|------|
| S7a | 直接用 `db` fixture 手动构造 3 题 + `async with db.begin_nested(): raise IntegrityError` | 错误实现（外层 rollback）→ `'13'/'15'` 全丢 → `names != ['13','15']` | SAVEPOINT 子事务 rollback 不影响外层事务 flushed 对象 | SAVEPOINT 语义基础护栏 | `pytest test_S7a_savepoint_semantics_preserves_outer_tx -v` |
| S7b | 预插 rival "14" + 调 `upsert_questions_from_skeleton([13,14,15])` | 错误实现跳过 SELECT 直接 INSERT → DB 有 2 条 "14" / IntegrityError / 返回错误 q_map | SELECT-first 主路径命中 existing + update max_score | R3-F001 主路径护栏 + R1-F004 retry 分支真正命中 | `pytest test_S7b_upsert_questions_existing_fast_path -v` |
| ~~S7c~~ | **R4-F003 修正：删除** | — | — | SAVEPOINT retry 分支 flush-time race 延期到 PostgreSQL CI（见 Contract Pack test_debt 条目）| — |

**边界条件:**
- 多 name 同时冲突 → 每题独立 SAVEPOINT，彼此不干扰
- SAVEPOINT rollback 后 session 状态由 SQLAlchemy 自动管理（无需手动 expire）
- 重试后仍冲突（第三方持续写入）→ SELECT 必能找到 existing 记录（UniqueConstraint 已经保证），不会无限递归
- 整个循环结束前不 commit 外层事务（由 T6 publish_card_atomic 负责）
- SAVEPOINT retry 分支的 flush-time race 测试（原 S7c）延期到 PostgreSQL CI（R4-F003 修正：不写伪实现，纯 test_debt）

**审查清单:**
- ✓ 正向：S7a PASS（纯 SAVEPOINT 语义）
- ✓ 正向：S7b PASS（SELECT-first existing update 主路径）
- ✓ 正向：S7c 不写实现代码，纯 test_debt 延期（R4-F003 修正）
- ✓ 正向：被测函数实现含 SELECT-first 分支（S7b 通过证明）
- ✓ 正向：被测函数实现含 `async with db.begin_nested():` + `except IntegrityError:` + re-SELECT（代码审查）
- ✓ 正向：log warning 记录并发事件
- ✗ 反向：`await db.rollback()` 出现在循环内（R2-F001 明确禁止）
- ✗ 反向：跳过 SELECT-first 直接 INSERT（S7b 会失败）
- ✗ 反向：使用未绑定 `db` fixture 的全局 `async_session` 预插 rival（R3-F001 明确禁止）
- ✗ 反向：无限 retry 循环（retry 分支内又 retry）
- 关键行为：SAVEPOINT 语义——子事务 rollback 不影响外层事务；SELECT-first 是主路径、SAVEPOINT retry 是并发防御；reviewer 需区分这两条路径

---

### Task 8: `card/router.py:1189 publish_card` 接入 service + integration

**Files:**
- Modify: `src/edu_cloud/modules/card/router.py:1189-1270`（删除内联 + 调 publish_service）
- Test: 复用 Task 2 的 `tests/test_api_exam/test_card_publish.py`（追加 router 层 integration）

- [ ] **Step 1: 写 integration 测试（Red）**

在 `tests/test_api_exam/test_card_publish.py` 追加：

```python
from unittest.mock import patch, AsyncMock

async def test_publish_endpoint_integration(client, db):
    """Slice F: POST /api/v1/card/publish 端到端完整路径（mock PDF/skeleton，验证 router 接入）。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.modules.exam.models import Exam, Subject, Question
    from edu_cloud.modules.card.models import Template
    from edu_cloud.shared.auth import create_access_token
    from sqlalchemy import select

    school = School(name="FInt", code="FINT01")
    db.add(school)
    await db.commit()
    user = User(username="f_int", display_name="F")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    exam = Exam(name="F考试", school_id=school.id, status="draft")
    db.add(exam)
    await db.commit()
    subject = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subject)
    await db.commit()

    async def fake_pdf(html, paper_size):
        return b"%PDF-F-integration"

    async def fake_extract(html):
        return {
            "image_width": 1587, "image_height": 1123, "anchors": [],
            "objective_groups": [], "slots": [{"sub_regions": [
                {"id": "essay-13", "name": "13", "score": 10, "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
            ]}],
            "regions": [
                {"id": "essay-13", "type": "subjective", "qno": 13, "side": "A",
                 "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
                {"id": "essay-14", "type": "subjective", "qno": 14, "side": "B",
                 "rect": {"x1": 0, "y1": 100, "x2": 100, "y2": 200}},
            ],
        }

    with patch("edu_cloud.modules.card.publish_service.html_to_pdf", side_effect=fake_pdf), \
         patch("edu_cloud.modules.card.publish_service.extract_skeleton", side_effect=fake_extract):
        resp = await client.post(
            "/api/v1/card/publish",
            json={"html": "<html/>", "subject_id": subject.id, "exam_id": exam.id, "paper_size": "A3"},
            headers=headers,
        )

    assert resp.status_code == 200
    assert resp.content == b"%PDF-F-integration"

    qs = (await db.execute(select(Question).where(Question.subject_id == subject.id))).scalars().all()
    assert len(qs) == 1

    tpls = (await db.execute(select(Template).where(Template.subject_id == subject.id))).scalars().all()
    assert len(tpls) == 2  # A + B (因为 essay-14 在 B 面)
    sides = sorted(t.side for t in tpls)
    assert sides == ["A", "B"]

    # exam.status 已切换
    exam_r = (await db.execute(select(Exam).where(Exam.id == exam.id))).scalar_one()
    assert exam_r.status == "scanning"
```

- [ ] **Step 2: Red verify（当前 router.py:1189 实现应跑不过 B 面断言）**

```bash
python -m pytest tests/test_api_exam/test_card_publish.py::test_publish_endpoint_integration -v
```

Expected: FAIL — `tpls[] 长度 1 != 2`（当前 publish_card 硬编码 A 面）

- [ ] **Step 3: 重构 router.py:1189 publish_card**

替换 L1189-1270 为：

```python
@router.post("/publish")
async def publish_card(
    body: PublishCardRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """原子发布答题卡：HTML→PDF + upsert Question + 双面 Template + status→scanning。

    F003 新实现：一站式入口，前端手工三步废弃。业务逻辑在 publish_service.py。
    """
    from edu_cloud.modules.card.publish_service import publish_card_atomic

    pdf_bytes = await publish_card_atomic(
        db,
        html=body.html,
        subject_id=body.subject_id,
        exam_id=body.exam_id,
        school_id=current["current_role"].school_id,
        paper_size=body.paper_size,
    )
    return Response(content=pdf_bytes, media_type="application/pdf")
```

删除原 L1195-1270 的内联实现。

- [ ] **Step 4: Green verify**

```bash
python -m pytest tests/test_api_exam/test_card_publish.py tests/test_services_exam/test_publish_service.py -v
```

Expected: 全部 pass

- [ ] **Step 5: 广域回归**

```bash
python -m pytest tests/test_api_exam/ tests/test_services_exam/ -q
```

Expected: 约 430+ tests pass（含 B2/B3a/B6a/B6c 前批次 + 本批次）

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/modules/card/router.py tests/test_api_exam/test_card_publish.py
git commit -m "refactor(card): F003 router.py publish_card 接入 publish_service (T8)"
```

**测试契约:**

| slice | 入口 | 反例 | 边界 | 回归 | 命令 |
|-------|------|------|------|------|------|
| F | POST /api/v1/card/publish + mock PDF/extract | 错误实现仍写单面 Template | 双面 skeleton → 2 条 Template | F003 router 层 | `pytest tests/test_api_exam/test_card_publish.py -v` |

**边界条件:**
- 无 exam_id / subject_id → 400
- Auth 缺失 → 401/403
- 单面 skeleton → 1 条 Template
- 双面 skeleton → 2 条 Template

**审查清单:**
- ✓ 正向：router.py L1189 不再有内联实现，所有逻辑在 publish_service.publish_card_atomic
- ✓ 正向：integration 测试 PASS
- ✓ 正向：广域 exam 测试无回归
- ✗ 反向：router 层做数据库操作
- ✗ 反向：遗留旧的 Template side="A" 硬编码

---

**Batch 2 结束 checkpoint：**
- Task 5-8 完成
- Question 表 UniqueConstraint 已生效
- publish_service.py 完整：upsert_questions + upsert_template + publish_card_atomic
- router.py:1189 已切换到 service
- 广域 exam 测试通过
- **预计耗时：** 5-8 小时 / 1 个 code review batch

---

## Batch 3: 前端切换 + pipeline 接通 + E2E（Slice G + H + I）

**目标：** 切换前端到新后端入口，pipeline 接通 save_answer_fn 闭包，端到端验证 F003 彻底修复。

### Task 9: 前端 `publishCard()` 重写 + V2 vitest

**Files:**
- Modify: `frontend/src/card-editor/export.js:177 publishCard()`
- Create: `frontend/src/__tests__/publishCard.test.js`

- [ ] **Step 1: 写失败测试 V2（Red）**

创建 `frontend/src/__tests__/publishCard.test.js`:

```js
import { describe, it, expect, vi, beforeEach } from 'vitest'

describe('F003 Slice G: publishCard 走 /api/v1/card/publish 单次调用', () => {
  beforeEach(() => {
    global.fetch = vi.fn()
    global.localStorage = { getItem: vi.fn().mockReturnValue('fake-token') }

    // 模拟 CardEditor 环境
    document.body.innerHTML = '<div class="preview-wrap"><div class="page" data-paper="A3" data-side="A"><div>test</div></div></div>'
    window._getValues = () => ({ paperSize: 'A3' })
  })

  it('V2: publishCard 只调用 /api/v1/card/publish 一次，参数含 subject_id/exam_id', async () => {
    const mockPdfBlob = new Blob(['fake pdf'], { type: 'application/pdf' })
    global.fetch.mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(mockPdfBlob),
    })

    // 存根 downloadBlob 避免真正触发下载
    const { publishCard } = await import('../card-editor/export.js')

    await publishCard('subject-123', 'exam-456', '答题卡.pdf')

    expect(global.fetch).toHaveBeenCalledTimes(1)
    const call = global.fetch.mock.calls[0]
    expect(call[0]).toBe('/api/v1/card/publish')
    expect(call[1].method).toBe('POST')
    const body = JSON.parse(call[1].body)
    expect(body.subject_id).toBe('subject-123')
    expect(body.exam_id).toBe('exam-456')
    expect(body.paper_size).toBe('A3')
    expect(typeof body.html).toBe('string')
  })

  it('V2b: publishCard fetch 失败时 throw', async () => {
    global.fetch.mockResolvedValue({ ok: false, status: 500 })
    const { publishCard } = await import('../card-editor/export.js')
    await expect(publishCard('s1', 'e1', 'f.pdf')).rejects.toThrow(/500/)
  })
})
```

- [ ] **Step 2: Red verify**

```bash
cd frontend && npx vitest run src/__tests__/publishCard.test.js
```

Expected: FAIL（当前 publishCard 调 3 个不同端点）

- [ ] **Step 3: 重写 publishCard**

编辑 `frontend/src/card-editor/export.js`，替换 `publishCard` 函数体：

```js
/**
 * 发布答题卡：一站式调用后端 /api/v1/card/publish
 * @param {string} subjectId - 科目 ID
 * @param {string} examId - 考试 ID（F003 新增参数）
 * @param {string} filename - PDF 文件名
 * @returns {Promise<{pdf: Blob}>}
 */
export async function publishCard(subjectId, examId, filename = '答题卡.pdf') {
  const html = await getCleanHTML();
  const paperSize = getCurrentPaperSize();
  const headers = getAuthHeaders();

  const resp = await fetch('/api/v1/card/publish', {
    method: 'POST',
    headers,
    body: JSON.stringify({
      html,
      subject_id: subjectId,
      exam_id: examId,
      paper_size: paperSize,
    }),
  });
  if (!resp.ok) throw new Error(`发布失败: HTTP ${resp.status}`);

  const pdfBlob = await resp.blob();
  downloadBlob(pdfBlob, filename);
  return { pdf: pdfBlob };
}
```

删除旧的 40 行手工三步逻辑。

- [ ] **Step 4: Green verify + 前端全量**

```bash
cd frontend && npx vitest run
```

Expected: 全量 184+ tests pass（含新增 V2 + V2b）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/card-editor/export.js frontend/src/__tests__/publishCard.test.js
git commit -m "refactor(frontend): F003 publishCard 单次调用 /card/publish (T9)"
```

**测试契约（V2）:**

| slice | 入口 | 反例 | 边界 | 回归 | 命令 |
|-------|------|------|------|------|------|
| V2 | `publishCard(subjectId, examId, filename)` | 错误实现仍调 3 个端点 → fetch 调用次数 > 1 | 单次 POST `/card/publish` | D8 单入口 | `npx vitest run src/__tests__/publishCard.test.js` |
| V2b | fetch 500 响应 | 错误实现吞异常 → 测试无法捕获 | throw Error 包含 500 | 错误传播 | 同上 |

**边界条件:**
- fetch 网络异常 → throw
- 返回非 200 → throw
- PDF blob 空 → 仍下载（让后端决定）

**审查清单:**
- ✓ 正向：publishCard 只调用一次 fetch
- ✓ 正向：调用目标是 `/api/v1/card/publish`
- ✓ 正向：body 含 html/subject_id/exam_id/paper_size
- ✗ 反向：遗留对 `/export/pdf`、`/export/skeleton`、`PUT /templates/` 的调用
- 关键行为：新签名 3 参数（subjectId, examId, filename），调用方必须同步更新（T10）

---

### Task 10: `ExamDetailPage.vue` 调用签名 + V3 vitest（R2-F004 + R3-F004 修正）

**Files:**
- Modify: `frontend/src/pages/ExamDetailPage.vue:242-249`（发布按钮加 `data-testid`）+ L868（调用 publishCard 处改 3 参）
- Test: `frontend/src/pages/__tests__/ExamDetailPage.publish.test.js`（新建）

**R3-F004 修正要点（必须基于锚点段 CR-3/CR-4 真实代码）**：

- `ExamDetailPage.vue:446-447` import 路径：`api/exams` 导出 `getExam, updateExam`；**`api/subjects` 导出 `listSubjects, createSubject`**（两个独立模块，V3 mock 必须分别 mock）
- `api/subjects.js` 第 3 行 `listSubjects = (examId) => client.get(...)` 返回 **axios Promise**（含 `.data` 包装）；`loadExam` L655-658 读取 `examRes.data` / `subjRes.data`
- 发布按钮 `disabled` 双条件：`!visualEditorSubjectId || exam?.status !== 'draft'`——V3 必须同时满足：`visualEditorSubjectId.value` 非空 + `exam.value.status === 'draft'`
- 当前按钮**无 `data-testid`**（见锚点段 CR-3）——Step 2 必须显式添加 `data-testid="publish-card-btn"`
- `handlePublishCard` 真实流程（L848-881）：函数内 `dialog.warning({onPositiveClick: async () => { ...publishCard... }})`——**真正的 publishCard 调用在 dialog 的 `onPositiveClick` 回调里**，不是直接在 handler 里
- V3 测试方案：mock `useDialog` 让 `warning({onPositiveClick})` **立即同步调用 `onPositiveClick`**，跳过真实弹窗渲染；测试用 `wrapper.vm.handlePublishCard()` 直接调（或点按钮触发）

- [ ] **Step 1: 定位调用点（事实核对）**

```bash
grep -n "publishCard\|data-testid\|handlePublishCard" frontend/src/pages/ExamDetailPage.vue
# 预期输出应与锚点段 CR-3 一致
```

- [ ] **Step 2: 修改 `ExamDetailPage.vue` 按钮属性 + 调用签名**

两处改动：

**2a. 发布按钮加 `data-testid`**（L242-249，见锚点段 CR-3）:

```vue
<!-- 原: -->
<n-button
  size="small"
  class="btn-pill toolbar-btn"
  :disabled="!visualEditorSubjectId || exam?.status !== 'draft'"
  @click="handlePublishCard"
>
  发布答题卡
</n-button>

<!-- 改为 (R3-F004 要求): -->
<n-button
  size="small"
  class="btn-pill toolbar-btn"
  data-testid="publish-card-btn"
  :disabled="!visualEditorSubjectId || exam?.status !== 'draft'"
  @click="handlePublishCard"
>
  发布答题卡
</n-button>
```

**2b. L868 调用签名加 `examId` 参数**（L471 `const examId = route.params.id` 已有）:

```vue
// 原 (L868):
await exportModule.publishCard(subjectId, filename)

// 改为:
await exportModule.publishCard(subjectId, examId, filename)
```

- [ ] **Step 3: 写 V3 测试（Red → Green，R3-F004 修正：真实 mock 对齐现实）**

创建 `frontend/src/pages/__tests__/ExamDetailPage.publish.test.js`:

```js
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'

/**
 * V3 (R3-F004 修正): 基于锚点段 CR-3/CR-4 的真实组件结构.
 *
 * 关键 mock 点:
 * 1. api/exams (getExam, updateExam) — 分开 mock
 * 2. api/subjects (listSubjects, createSubject) — 分开 mock (R3-F004 核心修复)
 * 3. api/rubrics (getRubric, upsertRubric) — setup 期间被调, 最小 mock 防异常
 * 4. api/cards + api/scan — 设为最小 stub
 * 5. card-editor/export.js (publishCard, getCleanHTML) — spy
 * 6. useDialog — mock 让 warning({onPositiveClick}) 立即同步执行回调
 * 7. axios 响应 shape: { data: {...} } / { data: [...] } (loadExam 读 .data)
 */

const publishCardSpy = vi.fn().mockResolvedValue(new Blob(['%PDF'], { type: 'application/pdf' }))

// mock Naive UI useDialog: warning({onPositiveClick}) 立即执行 onPositiveClick
const dialogStub = {
  warning: vi.fn((options) => {
    // 异步调用 onPositiveClick 模拟用户点"发布"按钮
    if (options?.onPositiveClick) {
      Promise.resolve().then(() => options.onPositiveClick())
    }
    return { destroy: vi.fn() }
  }),
}
const messageStub = { success: vi.fn(), warning: vi.fn(), error: vi.fn(), info: vi.fn() }

vi.mock('naive-ui', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useDialog: () => dialogStub,
    useMessage: () => messageStub,
  }
})

// mock api 模块 (shape 对齐 axios: { data: ... })
vi.mock('../../api/exams', () => ({
  getExam: vi.fn().mockResolvedValue({
    data: {
      id: 'exam-route-params-id',
      name: 'Test Exam',
      status: 'draft',                // ★ 按钮 disabled 依赖 status === 'draft'
      card_title: '',
    },
  }),
  updateExam: vi.fn().mockResolvedValue({ data: { ok: true } }),
}))

// R3-F004 核心: listSubjects 从 api/subjects (不是 api/exams)
vi.mock('../../api/subjects', () => ({
  listSubjects: vi.fn().mockResolvedValue({
    data: [{ id: 'subject-abc', name: '数学', code: 'SX' }],  // 至少 1 个科目
  }),
  createSubject: vi.fn().mockResolvedValue({ data: {} }),
}))

// 最小 stub: rubrics / cards / scan
vi.mock('../../api/rubrics', () => ({
  getRubric: vi.fn().mockResolvedValue({ data: null }),
  upsertRubric: vi.fn().mockResolvedValue({ data: {} }),
}))
vi.mock('../../api/cards', () => ({
  generateBarcode: vi.fn(),
  parseAnswers: vi.fn(),
  previewByWeights: vi.fn(),
  generateCardV2: vi.fn(),
}))
vi.mock('../../api/scan', () => ({
  scanDirectory: vi.fn(),
  startPipeline: vi.fn(),
  getPipelineProgress: vi.fn(),
  stopPipeline: vi.fn(),
  previewScan: vi.fn(),
  importTpl: vi.fn(),
}))

// spy publishCard (核心断言对象)
vi.mock('../../card-editor/export.js', () => ({
  publishCard: publishCardSpy,
  getCleanHTML: vi.fn().mockReturnValue('<html/>'),
}))

describe('F003 Task 10 V3 (R3-F004): ExamDetailPage publishCard 3-arg 调用', () => {
  let router

  beforeEach(() => {
    setActivePinia(createPinia())
    publishCardSpy.mockClear()
    dialogStub.warning.mockClear()

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/exams/:id', name: 'ExamDetail', component: { template: '<div/>' } },
      ],
    })
  })

  it('V3: handlePublishCard 调用 publishCard 时 examId = route.params.id (via dialog.onPositiveClick)', async () => {
    const testExamId = 'exam-route-params-id'
    router.push(`/exams/${testExamId}`)
    await router.isReady()

    const ExamDetailPage = (await import('../ExamDetailPage.vue')).default
    const wrapper = mount(ExamDetailPage, {
      global: {
        plugins: [router],
        stubs: {
          // stub 重型子组件
          CardEditor: true,
          NDataTable: true,
          NTabs: false,
          NTabPane: false,
        },
      },
    })
    await flushPromises()  // 等 loadExam 完成

    // 前置: 设置 visualEditorSubjectId 让按钮 enabled (锚点 CR-3: disabled 双条件)
    // 直接操作 wrapper.vm (组合式 API 暴露 setup return)
    wrapper.vm.visualEditorSubjectId = 'subject-abc'
    await flushPromises()

    // 直接调 handlePublishCard (绕过真实按钮 click + NDialog 渲染)
    // mock 的 useDialog.warning 会自动异步执行 onPositiveClick
    await wrapper.vm.handlePublishCard()
    await flushPromises()  // 等 onPositiveClick 微任务
    await flushPromises()  // 等 publishCard await

    // 断言 1: dialog.warning 被调用 (确认走到了 handlePublishCard 正常路径)
    expect(dialogStub.warning).toHaveBeenCalledTimes(1)

    // 断言 2: publishCard spy 被调用 1 次
    expect(publishCardSpy).toHaveBeenCalledTimes(1)

    // 断言 3 (R3-F004 核心): callArgs[1] === testExamId
    // 签名: publishCard(subjectId, examId, filename)
    const callArgs = publishCardSpy.mock.calls[0]
    expect(callArgs[0]).toBe('subject-abc')       // subjectId
    expect(callArgs[1]).toBe(testExamId)           // examId (核心断言)
    expect(typeof callArgs[2]).toBe('string')     // filename 非空字符串
    expect(callArgs[2]).toContain('答题卡')
  })

  it('V3b (R3-F004 反例): 按钮 data-testid 存在且 disabled 行为正确', async () => {
    const testExamId = 'exam-route-params-id'
    router.push(`/exams/${testExamId}`)
    await router.isReady()

    const ExamDetailPage = (await import('../ExamDetailPage.vue')).default
    const wrapper = mount(ExamDetailPage, {
      global: {
        plugins: [router],
        stubs: { CardEditor: true, NDataTable: true },
      },
    })
    await flushPromises()

    // 断言: 发布按钮存在, 含 data-testid="publish-card-btn" (Step 2 硬要求)
    const btn = wrapper.find('[data-testid="publish-card-btn"]')
    expect(btn.exists()).toBe(true)

    // 前置 visualEditorSubjectId 未设置 → 按钮 disabled
    // (wrapper.vm.visualEditorSubjectId 为 null/undefined)
    expect(btn.attributes('disabled')).toBeDefined()
  })
})
```

**关键事实对齐（R3-F004 修正）**：
- `api/exams.js` 只有 `getExam / updateExam`，**不导出 `listSubjects`**
- `api/subjects.js` 导出 `listSubjects / createSubject`，返回 axios Promise
- `loadExam()` 读 `.data` 包装：`exam.value = examRes.data; subjects.value = subjRes.data`
- 发布按钮 disabled 条件：`!visualEditorSubjectId || exam?.status !== 'draft'`
- `handlePublishCard` 通过 `dialog.warning({onPositiveClick: async () => {...publishCard...}})` 中转
- `useDialog` / `useMessage` 是 Naive UI 的 composables，测试必须 mock 返回 stub

**注意（test 实现可能的调整点）：**
1. 若 `mount` 时 Vue 3 composition API 的 `wrapper.vm.handlePublishCard` 未自动暴露 → 改用 `script setup` 的 `defineExpose` 或通过点击按钮触发
2. 若 `wrapper.vm.visualEditorSubjectId` 只读 → 改用 NSelect 的 `@update:value` 触发（但 mock 简化后直接赋值更稳妥）
3. 若 stubs 列表不够 → 运行时报错补充对应组件名
4. 若 `useDialog` mock 返回需要的不是 `dialog` 对象而是其他方法 → 查 Naive UI 源码对齐

Step 2 之前先 `cd frontend && npm list @vue/test-utils vue-router` 确认依赖已装；若未装则 `npm install -D @vue/test-utils`。

- [ ] **Step 4: 跑 vitest 确认 V3 PASS + 前端全量无回归**

```bash
cd frontend && npx vitest run src/pages/__tests__/ExamDetailPage.publish.test.js
cd frontend && npx vitest run  # 全量
```

Expected: V3 + V3b PASS；前端全量无回归。

- [ ] **Step 5: 手动 smoke test（可选）**

- 启动前端 :5273 + 后端 :9000
- 登录 admin_academic_director_2
- 打开 2026第一次月考 / 数学科目 CardEditor
- 点"发布答题卡"→ dialog 确认"发布"
- 预期：PDF 下载成功 + F12 网络面板看到单次 `/api/v1/card/publish` + body.exam_id 正确

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/ExamDetailPage.vue frontend/src/pages/__tests__/ExamDetailPage.publish.test.js
git commit -m "fix(frontend): F003 ExamDetailPage publishCard 3-arg + data-testid + V3 mount (T10, R3-F004)"
```

**测试契约（V3 / V3b，R2-F004 + R3-F004 修正）:**

| slice | 入口 | 反例 | 边界 | 回归 | 命令 |
|-------|------|------|------|------|------|
| V3 | `mount(ExamDetailPage)` + `router.push('/exams/exam-route-params-id')` + 设 `visualEditorSubjectId='subject-abc'` + 调 `wrapper.vm.handlePublishCard()` + mock useDialog 异步执行 onPositiveClick | 错误实现 L868 漏改 → `callArgs[1]` undefined；mock 路径错（listSubjects 仍 mock 到 api/exams）→ loadExam 失败；无 data-testid → V3b 失败 | route.params.id 非空；exam.status='draft'；visualEditorSubjectId 已设 | F003 Task 10 真实挂载 + 调用签名 + 按钮 testid | `npx vitest run src/pages/__tests__/ExamDetailPage.publish.test.js` |
| V3b | 同 mount + 按钮 disabled 反例 | 按钮无 `data-testid="publish-card-btn"` → `btn.exists()==false` | 未选 subject → disabled | 按钮 selector 稳定性 | 同 V3 |

**边界条件:**
- `exam.value.status === 'draft'` + `visualEditorSubjectId.value` 非空 → 按钮 enabled
- 任一不满足 → 按钮 disabled（V3b 反向验证）
- `examId` 为 route.params.id（组件顶层 const，L471）→ 正常传入
- `publishCard` 3-arg 顺序：`(subjectId, examId, filename)`——V3 显式断言每个位置
- axios 响应 shape：loadExam 读 `.data` → V3 mock 返回 `{ data: [...] }`
- `handlePublishCard` 通过 dialog.warning 中转 → V3 必须 mock useDialog 让 onPositiveClick 立即执行
- 若 `wrapper.vm.handlePublishCard` 未暴露 → 改用按钮 click 触发（需考虑 NButton stub/真实差异）

**审查清单:**
- ✓ 正向：`data-testid="publish-card-btn"` 已添加到 L242-249 发布按钮
- ✓ 正向：L868 改为 3-arg `publishCard(subjectId, examId, filename)`
- ✓ 正向：V3 mock 路径分离：`api/exams`（getExam/updateExam）+ `api/subjects`（listSubjects）
- ✓ 正向：V3 mock 响应 shape 包含 `.data` 包装
- ✓ 正向：V3 mock `useDialog` 让 `warning.onPositiveClick` 异步执行
- ✓ 正向：V3 前置设置 `exam.status='draft'` + `visualEditorSubjectId='subject-abc'`
- ✓ 正向：V3 断言 `callArgs[1] === testExamId` 显式验证 examId 位置
- ✓ 正向：V3b 断言 `data-testid` 存在 + disabled 行为正确
- ✗ 反向：`listSubjects` mock 到 `api/exams.js`（R3-F004 明确禁止）
- ✗ 反向：mock 返回裸对象不含 `.data` 包装（R3-F004 禁止，与 loadExam 读取方式不符）
- ✗ 反向：跳过 `useDialog` mock → dialog.warning 真实弹窗阻塞测试
- ✗ 反向：不设置 `visualEditorSubjectId` / `exam.status` → 按钮 disabled → publishCard 永不被调用
- ✗ 反向：直接 import publishCard 绕过组件（R2-F004 明确禁止）
- 关键行为：
  - V3 测的是 `ExamDetailPage.vue:868` 的真实调用点，通过真实 mount + 真实 handlePublishCard → mock dialog 中转 → spy 拦截 publishCard 参数
  - V3b 作为 data-testid 存在性 + disabled 行为的静态护栏（Step 2 落地证明）

**审查清单:**
- ✓ 正向：V3 通过 `mount(ExamDetailPage)` 挂载真实组件（非 import publishCard 绕过）
- ✓ 正向：触发发布按钮 `click` 事件真正走 `ExamDetailPage.vue:868` 调用链
- ✓ 正向：spy 断言 `publishCardSpy` 被调用 + `callArgs[1] === testExamId`
- ✓ 正向：`ExamDetailPage.vue:868` 调用 publishCard 时传入组件 scope 的 examId（L471 const）
- ✓ 正向：前端 vitest 全量 pass（含 V3）
- ✗ 反向（R2-F004 明确禁止）：只 `import publishCard` 直接三参调用，不 mount 组件
- ✗ 反向：用 `props.exam.id`（该 path 不存在，组件无 props.exam）
- ✗ 反向：在测试中不断言 `callArgs[1]` 只断言 spy 被调用
- 关键行为：examId 必须从 `useRoute().params.id` 派生（L471 的 const），不要引入新的 ref / store 访问

---

### Task 11: `pipeline_router.py` 接通 save_answer_fn 闭包 + S8a/b/c/d（R2-F002/F003/F005 + R3-F002/F003/F005 修正）

**Files:**
- Modify: `src/edu_cloud/modules/scan/pipeline_router.py`（抽 `build_pipeline_save_answer_fn` 工厂函数 + `start_pipeline` 调工厂 + 统一装配两条分支）
- Create: `tests/test_api_exam/test_pipeline_save_answer.py`（S8a/b/c 工厂函数测试）
- Create: `tests/test_api_exam/test_pipeline_router_wiring.py`（S8d 入口级装配测试）

**R2/R3 修正要点:**

- **R2-F002**（契约锁定，R3 已核实正确）：`StartPipelineRequest`（`pipeline_router.py:25-29`）只有 `subject_id / side / image_dir / tpl_path` 4 字段，**无 `exam_id`**。现有实现通过 `subject.exam_id` 派生（见锚点段 CR-2）。本 Task 锁定契约不变。
- **R2-F003 + R3-F003**：抽出 `build_pipeline_save_answer_fn` 工厂函数作为 pipeline_router 与 tests 的公共装配路径。**R3 追加要求**：除了 S8a/b/c 测工厂函数自身，还须补 **S8d 入口级装配测试**——mock `pipeline_service.run_pipeline`，从 HTTP 入口 `POST /api/v1/scan/pipeline/start` 调起，断言 `run_pipeline` 实际收到的 kwargs 里 `save_answer_fn` 非 None 且可调用。工厂单测 PASS ≠ wiring 正确，S8d 是这个 gap 的护栏。
- **R2-F005**：S8 移除 `pytest.skip` / `TODO` / "FAIL 或 skip" 占位，S8a/b/c/d 全部确定性断言。
- **R3-F002**（session 隔离修复）：`conftest.py db` fixture 是 in-memory SQLite，**`client` fixture 的 monkey-patch 让全局 `async_session` 指向同一 engine**（见锚点段 CR-1）。S8a/b/c 的 fixture 从 `db` 改为 `client + db`——进入 `async with AsyncClient:` 上下文后，工厂闭包内的 `async_session()` 才会打到测试 DB。断言查询仍用 `db` fixture，但需要 `db.expire_all()` 或新 SELECT 取最新可见（跨 session commit 可见性）。
- **R3-F005**（tpl_path 分支统一装配）：`start_pipeline` 当前有两条模板加载分支（`.tpl` 文件 vs DB Template，见锚点段 CR-2）：
  - 分支 A（tpl_path）: `template = parse_tpl_file(req.tpl_path)` —— **只有 `template` dict，无 `tpl` ORM 对象**
  - 分支 B（DB）: `tpl` 是 Template ORM，`template` 是手工构造 dict
  - **两个分支的共同产物是 `template` dict**，其 `"regions"` key 是 `list[dict]`
  - 修复：工厂函数签名改为接 `regions: list[dict]`（不再接 `Template` ORM 对象），两条分支都能传 `template.get("regions") or []`，消除 NameError。

- [ ] **Step 1: 写失败测试 S8a/S8b/S8c（Red，基于工厂函数 + 修正 session fixture）**

**关键（R3-F002 修正）**：S8a/b/c 必须用 `client + db` 组合 fixture——`client` fixture 进入 `async with AsyncClient:` 上下文时会 `monkey-patch edu_cloud.database.async_session` 指向 in-memory test DB（见锚点段 CR-1 L93-95）。只用 `db` fixture 时 monkey-patch 未生效，工厂闭包内的 `async_session()` 会打到生产配置 DB，与 `db` fixture 的查询脱节。

新建 `tests/test_api_exam/test_pipeline_save_answer.py`:

```python
"""Slice H: build_pipeline_save_answer_fn 工厂函数单元测试（R2-F003/F005 + R3-F002 修正）。

Fixture 策略（R3-F002）:
- 使用 `client + db` 组合 fixture, 让 `edu_cloud.database.async_session` 被 monkey-patch
  到与 `db` fixture 相同的 in-memory SQLite engine (见 conftest.py L93-95)
- 工厂闭包调用 `async_session()` 会拿到与 `db` 同一个 engine 的新 session, 写入可被 `db` 查询看到
  (需要 `db.expire_all()` 或新 SELECT 取跨 session 最新可见)
- **测试必须在 `async with AsyncClient:` 生效期间调用工厂**, 即 `client` fixture 已进入上下文

不经过 /api/v1/scan/pipeline/start HTTP 入口, 不依赖 async background run_pipeline;
直接调工厂拿到闭包 → 手动驱动闭包 → 断言 DB 行为。S8d (test_pipeline_router_wiring.py)
才是 HTTP 入口级装配验证, 两者互补。
"""
import logging
import pytest
from sqlalchemy import select

from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.card.models import Template
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.scan.pipeline_router import build_pipeline_save_answer_fn


@pytest.fixture
async def pipeline_fixture(db):
    """创建 school / exam / subject / Question + Template (含合法 region + orphan region).

    用 db fixture 预先写入测试数据;查询时仍用 db (session 隔离问题由 client fixture 的
    monkey-patch + db.expire_all() 解决, 见下方测试函数)。
    """
    school = School(name="S8Sch", code="S8SCH")
    db.add(school); await db.commit()
    user = User(username="s8_u", display_name="S8"); user.set_password("p")
    db.add(user); await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()

    exam = Exam(name="S8 考试", school_id=school.id, status="scanning")
    db.add(exam); await db.commit()
    subject = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subject); await db.commit()
    q1 = Question(subject_id=subject.id, school_id=school.id, name="13",
                  question_type="subjective", max_score=10.0)
    db.add(q1); await db.commit()

    tpl_a = Template(
        subject_id=subject.id, side="A", school_id=school.id,
        image_width=200, image_height=150, anchors=[],
        regions=[
            {"id": "essay-13", "name": "13", "type": "subjective",
             "rect": {"x1": 10, "y1": 10, "x2": 90, "y2": 70}, "question_id": q1.id},
            # essay-99 无 question_id → orphan
            {"id": "essay-99", "name": "99", "type": "subjective",
             "rect": {"x1": 10, "y1": 80, "x2": 90, "y2": 140}},
        ],
    )
    db.add(tpl_a); await db.commit()

    return {"school": school, "exam": exam, "subject": subject, "question": q1, "tpl_a": tpl_a}


async def test_S8a_factory_skips_orphan_region_with_warning(client, db, pipeline_fixture, caplog):
    """S8a (R3-F002 修正): 工厂构建 region_map → 闭包收 orphan region_id → skip + log + DB 零。

    Fixture 顺序: `client, db, pipeline_fixture` — 进入 `client` 上下文后 monkey-patch 生效,
    工厂闭包的 async_session() 指向测试 DB;`pipeline_fixture` 已通过 `db` 写入预置数据。

    反例: 错误实现不反查 region_map, 直接把 region_id 当 question_id 写库
    → 外键 question_id=essay-99 找不到 Question → IntegrityError 或非法记录 → 断言 rows==0 失败
    """
    caplog.set_level(logging.WARNING)
    fx = pipeline_fixture
    # 工厂函数接 regions: list[dict] (R3-F005 修正 —— 不接 Template ORM 对象)
    save_answer = build_pipeline_save_answer_fn(
        regions=fx["tpl_a"].regions,
        exam_id=fx["exam"].id,
        subject_id=fx["subject"].id,
        school_id=fx["school"].id,
    )

    # pipeline_service 语义遗留:参数名 question_id 实际是 region_id
    await save_answer(
        exam_id=fx["exam"].id,
        subject_id=fx["subject"].id,
        student_id="stu-orphan-001",
        question_id="essay-99",  # 传 orphan region_id
        image_path="/fake/orphan.png",
        school_id=fx["school"].id,
    )

    # 跨 session 断言: 工厂闭包用 async_session() 新 session 写库, db fixture 的原 session
    # 需要 expire_all() 或开新事务查询才能看到最新状态
    db.expire_all()  # R4-F002: 同步 API, 不 await
    rows = (await db.execute(
        select(StudentAnswer).where(StudentAnswer.subject_id == fx["subject"].id)
    )).scalars().all()
    assert len(rows) == 0, f"orphan region 应 skip, 实际 DB 写入 {len(rows)} 条"

    warnings = [r for r in caplog.records if "orphan" in r.getMessage().lower()]
    assert len(warnings) >= 1, "应 log warning 记录 orphan region"


async def test_S8b_factory_writes_student_answer_for_valid_region(client, db, pipeline_fixture):
    """S8b (R3-F002 修正): 工厂闭包收合法 region_id → 反查 region_map → INSERT StudentAnswer 成功。

    Fixture 顺序: `client, db, pipeline_fixture` —— monkey-patch 生效期间调用工厂。

    反例: 错误实现不写 StudentAnswer 或写错 question_id → rows==0 / question_id 不等 → 断言失败
    """
    fx = pipeline_fixture
    save_answer = build_pipeline_save_answer_fn(
        regions=fx["tpl_a"].regions,
        exam_id=fx["exam"].id,
        subject_id=fx["subject"].id,
        school_id=fx["school"].id,
    )

    await save_answer(
        exam_id=fx["exam"].id,
        subject_id=fx["subject"].id,
        student_id="stu-valid-001",
        question_id="essay-13",  # 合法 region_id
        image_path="/fake/valid.png",
        school_id=fx["school"].id,
    )

    db.expire_all()  # R4-F002: 同步 API, 不 await
    rows = (await db.execute(
        select(StudentAnswer).where(StudentAnswer.subject_id == fx["subject"].id)
    )).scalars().all()
    assert len(rows) == 1, f"合法 region 应写入 1 条 StudentAnswer, 实际 {len(rows)}"
    assert rows[0].question_id == fx["question"].id, (
        "question_id 应反查为真实 Question.id, 而非原 region_id"
    )
    assert rows[0].student_id == "stu-valid-001"
    assert rows[0].image_path == "/fake/valid.png"


async def test_S8c_factory_idempotent_on_duplicate_insert(client, db, pipeline_fixture):
    """S8c (R3-F002 修正): 同 (exam_id, student_id, question_id) 重复调闭包 → DB 1 条.

    Fixture 顺序: `client, db, pipeline_fixture`.

    断言 T0 决策: 现有 3 列 UniqueConstraint(exam_id, student_id, question_id) 天然幂等.
    反例: 错误实现未捕获 IntegrityError → 第二次 INSERT 抛异常中断 → 断言失败.
    """
    fx = pipeline_fixture
    save_answer = build_pipeline_save_answer_fn(
        regions=fx["tpl_a"].regions,
        exam_id=fx["exam"].id,
        subject_id=fx["subject"].id,
        school_id=fx["school"].id,
    )

    for _ in range(2):
        await save_answer(
            exam_id=fx["exam"].id,
            subject_id=fx["subject"].id,
            student_id="stu-dup-001",
            question_id="essay-13",
            image_path="/fake/dup.png",
            school_id=fx["school"].id,
        )

    db.expire_all()  # R4-F002: 同步 API, 不 await
    rows = (await db.execute(
        select(StudentAnswer).where(
            StudentAnswer.subject_id == fx["subject"].id,
            StudentAnswer.student_id == "stu-dup-001",
        )
    )).scalars().all()
    assert len(rows) == 1, f"重复 INSERT 应幂等, DB 应 1 条, 实际 {len(rows)}"
```

- [ ] **Step 1b: 写 S8d 入口级装配测试（R3-F003 修正，新增）**

**目的（R3-F003 + R4-F004 + R5-F002 修正）**：工厂单元测试通过 ≠ `start_pipeline` 真的调工厂 + 传 `save_answer_fn` 给 `run_pipeline`。**R4-F004 进一步要求：S8d 断言必须能区分 "真实工厂闭包" 和 "哑闭包"**。如果仅断言 `callable(save_answer_fn)`，错误实现 `save_answer_fn=lambda **_: None` 也能通过。**R5-F002 修正**：Python 3.11.9 的 `unittest.mock.MagicMock` 无 `spy_return` 属性，`patch.object(..., wraps=original)` + `spy.spy_return` 模式会在断言阶段抛 `AttributeError`。修复方案改为：自定义 `tracked_factory(**kwargs)` 调真工厂并把返回值 append 到外部 `factory_returns` 列表，`patch.object(..., side_effect=tracked_factory)` 做 spy，断言 `spy.called` + `spy.call_args.kwargs` + `len(factory_returns)==1` + `captured_kwargs["save_answer_fn"] is factory_returns[0]`（identity 透传）。

新建 `tests/test_api_exam/test_pipeline_router_wiring.py`:

```python
"""S8d (R3-F003 + R4-F004 + R5-F002 修正): HTTP 入口级装配测试 —
start_pipeline 必须 (1) 调 build_pipeline_save_answer_fn (2) 把返回值 identity 透传给 run_pipeline.

反例守卫:
- 错误实现不调工厂 → spy.called == False + factory_returns 为空
- 错误实现调工厂但不传 run_pipeline → captured_kwargs['save_answer_fn'] is not factory_returns[0]
- 错误实现传哑闭包 (async def noop(**_): pass) → identity 断言失败
"""
import pytest
from unittest.mock import patch, MagicMock


async def test_S8d_start_pipeline_tracks_factory_and_asserts_identity(
    client, db, tmp_path, pipeline_fixture
):
    """S8d (R5-F002): tracked_factory + 外部列表捕获 + identity 断言.

    策略:
    1. 定义 tracked_factory(**kwargs): 调真工厂 + append 返回值到 factory_returns 外部列表
    2. patch.object(..., side_effect=tracked_factory) 让 patched 对象被调时运行 tracked_factory
       （Python 3.11 unittest.mock 的 MagicMock 无 `spy_return` 属性，必须用外部列表捕获真返回值）
    3. mock run_pipeline 拦截 kwargs
    4. 断言 spy.called + spy.call_args.kwargs.regions 非空 + len(factory_returns) == 1
       + kwargs['save_answer_fn'] is factory_returns[0]

    反例守卫:
    - 哑闭包实现 `save_answer_fn=lambda **_: None` → identity 断言失败 (不是 factory_returns[0])
    - 不调工厂直接构造闭包 → spy.called == False + factory_returns 为空
    - 调工厂但传给 run_pipeline 的是另一个对象 → identity 断言失败
    """
    from edu_cloud.shared.auth import create_access_token
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.modules.scan import pipeline_router as pr_mod
    from PIL import Image

    fx = pipeline_fixture

    # 创建假扫描图
    scan_dir = tmp_path / "scan"
    scan_dir.mkdir()
    for i in range(2):
        Image.new("RGB", (200, 150), (255, 255, 255)).save(scan_dir / f"S{i:04d}A.png")

    # admin JWT
    admin = User(username="s8d_admin", display_name="S8d Admin"); admin.set_password("p")
    db.add(admin); await db.commit()
    db.add(UserRole(user_id=admin.id, role="admin", school_id=fx["school"].id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": admin.id, "school_id": fx["school"].id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    # Mock run_pipeline: 拦截 kwargs
    captured_kwargs = {}

    async def fake_run_pipeline(**kwargs):
        captured_kwargs.update(kwargs)

    # R5-F002 核心: tracked_factory + 外部列表捕获真工厂返回闭包
    # （Python 3.11 unittest.mock.MagicMock 无 spy_return 属性，
    #   必须显式 wrap + 外部列表才能拿到真实返回值做 identity 断言）
    original_factory = pr_mod.build_pipeline_save_answer_fn
    factory_returns = []

    def tracked_factory(**kwargs):
        result = original_factory(**kwargs)
        factory_returns.append(result)
        return result

    with patch.object(
        pr_mod, "build_pipeline_save_answer_fn",
        side_effect=tracked_factory,
    ) as spy_factory, \
         patch("edu_cloud.modules.scan.pipeline_service.is_running", return_value=False), \
         patch("edu_cloud.modules.scan.pipeline_service.list_scan_images",
               return_value=[str(scan_dir / "S0000A.png"), str(scan_dir / "S0001A.png")]), \
         patch("edu_cloud.modules.scan.pipeline_service.run_pipeline",
               side_effect=fake_run_pipeline):

        resp = await client.post(
            "/api/v1/scan/pipeline/start",
            json={
                "subject_id": fx["subject"].id,
                "side": "A",
                "image_dir": str(scan_dir),
            },
            headers=headers,
        )

        # 等 asyncio.create_task 调度完成（AsyncClient 关闭前 task 应已执行）
        import asyncio
        await asyncio.sleep(0.05)

    assert resp.status_code == 200, f"start_pipeline 应返回 200, 实际 {resp.status_code}: {resp.text}"

    # 断言 1 (R5-F002): spy 被调用
    assert spy_factory.called, (
        "start_pipeline 必须调用 build_pipeline_save_answer_fn 工厂 "
        "—— 错误实现 (如 save_answer_fn=lambda **_: None 哑闭包) 会让 spy.called == False"
    )
    assert spy_factory.call_count == 1, f"工厂应只调一次，实际 {spy_factory.call_count}"

    # 断言 2: spy 收到正确参数
    call_kwargs = spy_factory.call_args.kwargs
    assert "regions" in call_kwargs, f"工厂应收到 regions kwarg, 实际 kwargs keys: {list(call_kwargs.keys())}"
    assert isinstance(call_kwargs["regions"], list), (
        f"regions 应为 list[dict] (R3-F005 修正), 实际 {type(call_kwargs['regions'])}"
    )
    # DB 分支从 tpl.regions 提取 —— pipeline_fixture 的 tpl_a 有 2 条 region (essay-13 + essay-99)
    assert len(call_kwargs["regions"]) == 2, (
        f"DB 分支应传 tpl_a.regions (2 条), 实际 {len(call_kwargs['regions'])}"
    )
    assert call_kwargs.get("exam_id") == fx["subject"].exam_id, (
        f"exam_id 应从 subject 派生 (R2-F002 契约), 实际 {call_kwargs.get('exam_id')}"
    )
    assert call_kwargs.get("subject_id") == fx["subject"].id
    assert call_kwargs.get("school_id") == fx["school"].id

    # 断言 3 (R5-F002 tracked_factory): factory_returns 捕获到真工厂返回值
    assert len(factory_returns) == 1, (
        f"tracked_factory 应被调用一次并捕获到 1 个真工厂返回值, 实际 {len(factory_returns)}"
    )

    # 断言 4 (R5-F002 核心 identity): run_pipeline 收到的 save_answer_fn 是 factory_returns[0] 本身
    assert "save_answer_fn" in captured_kwargs, (
        f"run_pipeline kwargs 必须含 save_answer_fn, 实际 keys: {list(captured_kwargs.keys())}"
    )
    assert captured_kwargs["save_answer_fn"] is factory_returns[0], (
        "run_pipeline 收到的 save_answer_fn 必须 identity-equal 于工厂真实返回值 "
        "—— 错误实现传哑闭包 / 另造 closure / None placeholder 都会在此失败 (R5-F002 守卫)"
    )

    # 断言 5: exam_id 来源锁定 (R2-F002)
    assert captured_kwargs.get("exam_id") == fx["subject"].exam_id


async def test_S8d_tpl_path_branch_also_wires_save_answer_fn(
    client, db, tmp_path, pipeline_fixture
):
    """S8d-b (R3-F005 + R4-F004 + R5-F002 修正): `.tpl` 分支也必须统一装配 save_answer_fn 且 identity 透传.

    反例 1: tpl_path 分支 NameError 'tpl' is not defined → start_pipeline 返回 500
    反例 2: tpl_path 分支不调工厂 → spy.called == False + factory_returns 为空
    反例 3: tpl_path 分支调工厂但另造闭包传给 run_pipeline → identity 失败
    """
    from edu_cloud.shared.auth import create_access_token
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.modules.scan import pipeline_router as pr_mod
    from sqlalchemy import select
    from PIL import Image
    import json

    fx = pipeline_fixture

    # 空 regions 的 .tpl 文件 —— 工厂返回 orphan-only 闭包 (regions=[])
    tpl_file = tmp_path / "test.tpl"
    tpl_file.write_text(json.dumps({
        "image_size": {"width": 200, "height": 150},
        "anchors": [],
        "regions": [],  # 空 list, 工厂会产生 region_map 为空的 orphan-only 闭包
    }))

    scan_dir = tmp_path / "scan_tpl"
    scan_dir.mkdir()
    Image.new("RGB", (200, 150), (255, 255, 255)).save(scan_dir / "S0001A.png")

    admin = (await db.execute(select(User).where(User.username == "s8d_admin_tpl"))).scalar_one_or_none()
    if not admin:
        admin = User(username="s8d_admin_tpl", display_name="S8d Tpl"); admin.set_password("p")
        db.add(admin); await db.commit()
        db.add(UserRole(user_id=admin.id, role="admin", school_id=fx["school"].id, is_primary=True))
        await db.commit()
    token = create_access_token({"sub": admin.id, "school_id": fx["school"].id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    captured_kwargs = {}

    async def fake_run_pipeline(**kwargs):
        captured_kwargs.update(kwargs)

    # R5-F002: tracked_factory + 外部列表捕获真工厂返回闭包（同 S8d-a）
    original_factory = pr_mod.build_pipeline_save_answer_fn
    factory_returns = []

    def tracked_factory(**kwargs):
        result = original_factory(**kwargs)
        factory_returns.append(result)
        return result

    with patch.object(
        pr_mod, "build_pipeline_save_answer_fn",
        side_effect=tracked_factory,
    ) as spy_factory, \
         patch("edu_cloud.modules.scan.pipeline_service.is_running", return_value=False), \
         patch("edu_cloud.modules.scan.pipeline_service.list_scan_images",
               return_value=[str(scan_dir / "S0001A.png")]), \
         patch("edu_cloud.modules.scan.pipeline_service.run_pipeline",
               side_effect=fake_run_pipeline):
        resp = await client.post(
            "/api/v1/scan/pipeline/start",
            json={
                "subject_id": fx["subject"].id,
                "side": "A",
                "image_dir": str(scan_dir),
                "tpl_path": str(tpl_file),  # ← .tpl 分支
            },
            headers=headers,
        )
        import asyncio
        await asyncio.sleep(0.05)

    assert resp.status_code == 200, (
        f".tpl 分支 start_pipeline 应返回 200, 实际 {resp.status_code}: {resp.text} "
        "—— 错误实现会因 NameError 'tpl' is not defined 返回 500 (R3-F005)"
    )

    # R5-F002: identity 断言 (.tpl 分支)
    assert spy_factory.called, ".tpl 分支也必须调工厂"
    assert len(factory_returns) == 1, (
        f".tpl 分支 tracked_factory 应被调一次, 实际 {len(factory_returns)}"
    )
    call_kwargs = spy_factory.call_args.kwargs
    assert isinstance(call_kwargs["regions"], list)
    assert call_kwargs["regions"] == []  # 空 regions（orphan-only 闭包）

    assert captured_kwargs.get("save_answer_fn") is factory_returns[0], (
        ".tpl 分支 save_answer_fn 必须 identity-equal 于 factory_returns[0] (R5-F002 守卫)"
    )
```

**R5-F002 关键技术点（reviewer 必须理解）**:
- **Python 3.11 API 限制**：`unittest.mock.MagicMock` 在 Python 3.11.9 下**没有** `spy_return` 属性（该属性不存在于当前 `unittest.mock` API 中，GPT 已在 R5 实测验证）。因此 R4-F004 的 `patch.object(..., wraps=original)` + `spy_factory.spy_return` 模式会在断言阶段抛 `AttributeError`，测试实际无效。必须改用**外部列表捕获**模式
- **tracked_factory 模式**：自定义 `def tracked_factory(**kwargs)` 调真工厂 (`original_factory(**kwargs)`) 并把返回值 `append` 到外部 `factory_returns` 列表，然后 `patch.object(..., side_effect=tracked_factory)` 让 patched 对象被调时运行 tracked_factory
- **side_effect 返回值语义**：当 `side_effect` 可调用返回非 `DEFAULT` 值时，该返回值**成为 patched 对象的返回值**（`unittest.mock` 标准行为）——因此 `run_pipeline` 收到的 `save_answer_fn` 与 `factory_returns[0]` 是**同一对象**（标准 Python identity）
- **spy 属性仍可用**：`side_effect=tracked_factory` 模式下 `spy_factory.called` / `spy_factory.call_args` / `spy_factory.call_count` 仍然工作（标准 MagicMock 行为，不依赖 `spy_return`）
- `captured_kwargs["save_answer_fn"] is factory_returns[0]` 是 Python `is` 对象身份比较——只有 `start_pipeline` 把真工厂返回的那个闭包对象**直接**传给 `run_pipeline` 才通过
- 哑闭包实现 `save_answer_fn = lambda **_: None` 或 `async def noop(**_): pass`——这些都是新创建的对象，`is factory_returns[0]` 必然为 False，断言失败
- 不调工厂直接写死 closure → `spy.called == False` 且 `len(factory_returns) == 0`，双重失败
- 调工厂 + 另造一个 closure 传 `run_pipeline` → `factory_returns[0] is not captured.save_answer_fn`，断言失败

四种错误实现都被 tracked_factory + identity 断言守卫。

- [ ] **Step 2: Red verify**

```bash
python -m pytest tests/test_api_exam/test_pipeline_save_answer.py -v
```

Expected (Red)：import 阶段即失败 `ImportError: cannot import name 'build_pipeline_save_answer_fn' from 'edu_cloud.modules.scan.pipeline_router'`——工厂函数尚未实现。

- [ ] **Step 3: 实现工厂函数 + start_pipeline 接入（R2-F002/F003 + R3-F005 修正：signature 改为 regions: list[dict]）**

编辑 `src/edu_cloud/modules/scan/pipeline_router.py`：

**3a. 顶部新增 imports + 工厂函数**（放在现有 `router = APIRouter(...)` 之前）:

```python
from typing import Callable, Awaitable
from sqlalchemy.exc import IntegrityError

# R4-F001: 禁止 `from edu_cloud.database import async_session` —— 那会把函数引用抓到本模块
# 命名空间, conftest.py client fixture 的 monkey-patch 将无效. 改用模块引用 + 运行时属性查找.
import edu_cloud.database as db_mod

from edu_cloud.modules.scan.models import StudentAnswer


def build_pipeline_save_answer_fn(
    regions: list[dict],                    # R3-F005 修正: 接 list[dict] 不接 Template ORM
    exam_id: str,
    subject_id: str,
    school_id: str,
) -> Callable[..., Awaitable[None]]:
    """构造 pipeline 的 save_answer_fn 闭包——region_id → question_id 反查 + 写 StudentAnswer.

    Args:
        regions: Template.regions 或 parse_tpl_file(tpl).regions (两条分支都是 list[dict] 格式);
                 每条 region 可选 `question_id` 字段, 无此字段的 region 被视为 orphan.
        exam_id / subject_id / school_id: 闭包捕获的上下文.

    职责:
      1. 从 regions 构建 region_map = {region_id: question_id}
         (仅含 question_id 非空的 region, 其余为 orphan)
      2. 返回 async 闭包:
         - pipeline_service.run_pipeline 传入的 `question_id` 参数实际是 `region_id`
           (pipeline_service 命名遗留), 闭包内部反查 region_map
         - orphan region → log warning + skip, 不 raise, 不中断 pipeline
         - 命中 → INSERT StudentAnswer; 重复 INSERT 触发 3 列 UniqueConstraint
           → IntegrityError 捕获 rollback 天然幂等 (见 design §5.5)

    设计原则 D7: run_pipeline 对 region_map 零感知, 全部语义封装在闭包.
    测试复用: S8a/b/c 与 Task 12 S9b 通过导入此工厂取代手工 db.add.

    Session 一致性 (R3-F002 + R4-F001 修正):
      闭包内 `db_mod.async_session()` 是运行时属性查找 —— client fixture 的 monkey-patch
      `_db_mod.async_session = session_factory` 在测试期间重赋值 `edu_cloud.database.async_session`
      属性, 闭包每次调用都会拿到当前的 session_factory, 从而与 db fixture 共享
      in-memory test engine. 禁止在本模块顶层写 `from edu_cloud.database import async_session`,
      那会绑定旧函数对象到本模块命名空间, 使 monkey-patch 失效.
    """
    region_map: dict[str, str] = {
        r["id"]: r["question_id"]
        for r in (regions or [])
        if r.get("question_id")
    }

    async def save_answer(
        exam_id: str,
        subject_id: str,
        student_id: str,
        question_id: str,
        image_path: str,
        school_id: str,
    ) -> None:
        # 注意: pipeline_service.run_pipeline 传入的 `question_id` 参数名沿用 pipeline_service
        # 的字段命名, 实际值是 crop["region_id"]. 闭包负责反查 region_map 得到真实 Question.id.
        region_id = question_id
        real_qid = region_map.get(region_id)
        if not real_qid:
            logger.warning(
                "pipeline_orphan_crop: region_id=%s not in region_map (subject=%s, student=%s), skip",
                region_id, subject_id, student_id,
            )
            return

        # R4-F001: 运行时属性查找, 让 client fixture monkey-patch 生效
        async with db_mod.async_session() as db2:
            db2.add(StudentAnswer(
                exam_id=exam_id,
                subject_id=subject_id,
                student_id=student_id,
                question_id=real_qid,
                image_path=image_path,
                school_id=school_id,
            ))
            try:
                await db2.commit()
            except IntegrityError:
                # 3 列 UniqueConstraint(exam_id, student_id, question_id) 天然幂等
                # 重跑 pipeline 同学同题 → 捕获后 skip (见 design §5.5 / T0)
                await db2.rollback()
                logger.debug(
                    "pipeline_duplicate_answer: student=%s question=%s already exists, skip",
                    student_id, real_qid,
                )

    return save_answer
```

**3b. 修改 `start_pipeline` 统一两条分支的装配（R3-F005 修正）：**

参照锚点段 CR-2 真实代码：两条分支（`.tpl` 文件 vs DB Template）的共同产物是 `template` dict，其中 `template["regions"]` 是 `list[dict]`。**工厂函数统一从 `template["regions"]` 读取**，消除 R3-F005 的 NameError。

```python
# 原 (pipeline_router.py:90-156, 见锚点段 CR-2)：
# 分支 A (tpl_path): template = parse_tpl_file(...)  ← 只有 template dict, 无 tpl 对象
# 分支 B (DB):       tpl = SELECT Template;          ← tpl 是 ORM, template 是手工 dict
#                    template = {image_size, anchors, regions: tpl.regions or [], barcode_region}
# 然后统一:
# asyncio.create_task(pipeline_service.run_pipeline(..., template=template, ...))

# 改为 (R2-F002/F003 + R3-F005)：
# --- template 加载逻辑保持现状（两条分支都产出 template dict），在分支末尾追加 ---

# 统一提取 regions for factory (R3-F005 修正: 两条分支都从 template dict 取 regions)
regions_for_factory: list[dict] = template.get("regions") or []

# R2-F002: 通过工厂构造 save_answer_fn 闭包, exam_id 从 subject 派生
# (StartPipelineRequest 保持 4 字段契约不变, 见锚点段 CR-2)
save_answer_fn = build_pipeline_save_answer_fn(
    regions=regions_for_factory,
    exam_id=subject.exam_id,
    subject_id=req.subject_id,
    school_id=school_id,
)

if not any(r.get("question_id") for r in regions_for_factory):
    logger.warning(
        "pipeline start: empty region_map for subject=%s side=%s → StudentAnswer 将不会写入",
        req.subject_id, req.side,
    )

# 后台启动, 传入 save_answer_fn
asyncio.create_task(pipeline_service.run_pipeline(
    image_dir=req.image_dir,
    template=template,
    output_dir=output_dir,
    exam_id=subject.exam_id,  # R2-F002: 从 subject 派生
    subject_id=req.subject_id,
    school_id=school_id,
    side=req.side,
    save_answer_fn=save_answer_fn,  # ★ Slice H 接通 (两条分支统一)
))
```

**契约锁定（R2-F002）**：`StartPipelineRequest` 保持 4 字段 `subject_id / side / image_dir / tpl_path` **不变**，**不新增 `exam_id` 字段**。所有 `exam_id` 来源统一为 `subject.exam_id`。设计 / 实现 / 测试 / OpenAPI 文档共享此单一来源。

**两条分支统一（R3-F005）**：
- 分支 A (`req.tpl_path`): `template = parse_tpl_file(req.tpl_path)` 产物是 dict，`template["regions"]` 可能为空列表（开发调试路径）→ `regions_for_factory = []` → 工厂产生的闭包所有 region 都是 orphan，log warning（不视为 bug）
- 分支 B (DB Template): `tpl.regions` 写入 `template["regions"]` → `regions_for_factory` 从 `template["regions"]` 取，与分支 A 统一
- **关键**：工厂调用参数 `regions=regions_for_factory`，两条分支都走同一行代码，**没有 `tpl` 变量引用**，消除 R3-F005 NameError

- [ ] **Step 4: Green verify**

```bash
python -m pytest tests/test_api_exam/test_pipeline_save_answer.py -v
```

Expected: S8a + S8b + S8c 全部 PASS。

- [ ] **Step 5: 广域回归**

```bash
python -m pytest tests/test_services_exam/test_scan_pipeline.py tests/test_api_exam/ -q
```

Expected: 全部 pass，`StartPipelineRequest` 契约未变 → 现有 pipeline 测试不受影响。

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/modules/scan/pipeline_router.py tests/test_api_exam/test_pipeline_save_answer.py
git commit -m "feat(scan): F003 build_pipeline_save_answer_fn 工厂接通 save_answer (T11)"
```

**测试契约（S8a / S8b / S8c / S8d，R2-F003/F005 + R3-F002/F003/F005 + R4-F001/F002/F004 修正）:**

| slice | 入口 | 反例 | 边界 | 回归 | 命令 |
|-------|------|------|------|------|------|
| S8a | `client + db + pipeline_fixture` fixture 下调 `build_pipeline_save_answer_fn(regions=tpl_a.regions, ...)` 后闭包传入 orphan `region_id="essay-99"` | 错误实现不反查 region_map → DB 非零 或 IntegrityError | Template.regions 含 orphan → skip + log warning | F003 orphan 不中断 pipeline | `pytest test_pipeline_save_answer.py::test_S8a_factory_skips_orphan_region_with_warning -v` |
| S8b | 同 fixture + 工厂调闭包传入合法 `region_id="essay-13"` | 错误实现未写 StudentAnswer / question_id 错 → 断言失败 | region_map 命中 → INSERT StudentAnswer(question_id=Question.id) | F003 pipeline writeback 主路径 | `pytest test_pipeline_save_answer.py::test_S8b_factory_writes_student_answer_for_valid_region -v` |
| S8c | 同 fixture + 工厂重复调 2 次 `(exam, student, question)` | 错误实现未捕获 IntegrityError → 中断 | 3 列 UniqueConstraint 幂等 → DB 1 条 | pipeline 重跑幂等 | `pytest test_pipeline_save_answer.py::test_S8c_factory_idempotent_on_duplicate_insert -v` |
| S8d-a (HTTP wiring DB 分支) | `POST /api/v1/scan/pipeline/start` + `patch.object(pr_mod, "build_pipeline_save_answer_fn", side_effect=tracked_factory)` + 外部 `factory_returns` 列表 + mock `run_pipeline` | **错误实现 1**: 不调工厂 (`save_answer_fn=lambda **_: None`) → `spy.called == False` 且 `len(factory_returns)==0` → 断言失败；**错误实现 2**: 调工厂但另造 closure → `captured.save_answer_fn is not factory_returns[0]` → identity 断言失败；**错误实现 3**: 漏传 `save_answer_fn` kwarg → `"save_answer_fn" not in captured_kwargs` → 失败 | DB 分支装配 + identity 断言 + exam_id 来源锁定 | **R3-F003 + R4-F004 + R5-F002 入口级 identity 护栏** | `pytest test_pipeline_router_wiring.py::test_S8d_start_pipeline_tracks_factory_and_asserts_identity -v` |
| S8d-b (HTTP wiring tpl_path 分支) | 同 `tracked_factory` + `factory_returns` 策略 + body 带 `tpl_path` 空 regions 文件 | 错误实现 NameError 'tpl' → 500；或 tpl_path 分支不调工厂 → spy + `factory_returns` 断言失败 | tpl_path 分支工厂收到 `regions=[]`（orphan-only 闭包）+ identity 透传 | **R3-F005 + R4-F004 + R5-F002 tpl_path 分支 NameError + identity 双重护栏** | `pytest test_pipeline_router_wiring.py::test_S8d_tpl_path_branch_also_wires_save_answer_fn -v` |

**边界条件:**
- `template["regions"]` 为空 → region_map 空 → 所有 crop 是 orphan，log warning
- region 有 id 但 `question_id=None` → 不进 region_map → 闭包内 skip
- 同 (exam_id, student_id, question_id) 重复调 → IntegrityError 捕获 rollback
- `start_pipeline` 从 `subject.exam_id` 派生 exam_id，`StartPipelineRequest` 4 字段契约不变（R2-F002）
- DB 分支 + tpl_path 分支**都走 `template["regions"]` 提取**，工厂调用一行代码统一（R3-F005）
- **测试 fixture 必须用 `client + db` 组合**，让 `async_session` monkey-patch 生效（R3-F002）
- **被测模块 pipeline_router.py 必须用 `import edu_cloud.database as db_mod`**（R4-F001：运行时属性查找让 monkey-patch 生效）
- **断言前 `db.expire_all()` 必须是同步调用**（R4-F002：`AsyncSession.expire_all()` 不返回 Awaitable）
- **S8d 必须用 `patch.object(..., side_effect=tracked_factory)` + 外部 `factory_returns` 列表 + identity 断言**（R4-F004：`callable` 弱断言可被哑闭包绕过；R5-F002：Python 3.11 无 `spy_return` 属性）

**审查清单:**
- ✓ 正向：`build_pipeline_save_answer_fn(regions: list[dict], ...)` signature 接 list 不接 Template ORM
- ✓ 正向：pipeline_router.py 用 `import edu_cloud.database as db_mod` + 闭包内 `db_mod.async_session()` 运行时查找（R4-F001）
- ✓ 正向：`start_pipeline` 两条分支都从 `template["regions"]` 提取 `regions_for_factory`，统一调工厂
- ✓ 正向：S8a/b/c 用 `client + db` 组合 fixture（让 `async_session` monkey-patch 生效）
- ✓ 正向：S8a/b/c 断言前用**同步** `db.expire_all()`，不带 `await`（R4-F002）
- ✓ 正向：S8d 用 `patch.object(..., side_effect=tracked_factory)` spy 工厂函数 + 外部 `factory_returns` 列表捕获真返回值（R5-F002）
- ✓ 正向：S8d 断言 `spy.called == True` + `spy.call_args.kwargs` 内容正确 + `len(factory_returns)==1` + `captured["save_answer_fn"] is factory_returns[0]` identity 透传（R4-F004 + R5-F002）
- ✓ 正向：S8d-a 和 S8d-b 分别覆盖 DB 和 tpl_path 两条分支，都做 identity 断言
- ✓ 正向：orphan region → log warning + skip
- ✓ 正向：重复 INSERT → IntegrityError 捕获幂等
- ✗ 反向：`StartPipelineRequest` 加 `exam_id` 字段（R2-F002 禁止）
- ✗ 反向：`from edu_cloud.database import async_session` 模块顶层绑定（R4-F001 禁止：monkey-patch 失效）
- ✗ 反向：`await db.expire_all()`（R4-F002 禁止：同步 API）
- ✗ 反向：S8/S9b 绕开工厂手工 `db.add(StudentAnswer)`（R2-F003 禁止）
- ✗ 反向：S8 用 `pytest.skip` / TODO 占位（R2-F005 禁止）
- ✗ 反向：S8 只用 `db` fixture 不用 `client`（R3-F002：monkey-patch 未生效）
- ✗ 反向：工厂签名接 `Template` ORM 对象（R3-F005：tpl_path 分支无 tpl 变量 → NameError）
- ✗ 反向：S8d 只断言 `callable(save_answer_fn)` 或 `is not None`（R4-F004：哑闭包 `lambda **_: None` 可绕过）
- ✗ 反向：S8d 回退用 `wraps=original` + `spy.spy_return`（R5-F002：Python 3.11 无此属性，断言 `AttributeError`）
- ✗ 反向：S8d 跳过 `tracked_factory` 改用 unittest.mock.MagicMock 直接拦截（丢失工厂内部真实逻辑覆盖）
- ✗ 反向：闭包内使用 request 级 db session（必须用 `db_mod.async_session()`）
- 关键行为：
  - `question_id` 参数名沿用 pipeline_service 命名，实际接 `region_id`（reviewer 需理解命名遗留）
  - `client` fixture monkey-patch + 被测模块 `import ... as db_mod` 组合才能让跨 session 写入可见
  - S8d identity 断言（`is factory_returns[0]`，R5-F002 tracked_factory 模式）是 CE-002 缓解路径的真正护栏，`callable` 断言不够

---

### Task 12: E2E (S9) + 回归 (R1/R2/R3) + CLAUDE.md 同步 + [实现完成] 标记

**Files:**
- Modify: `tests/test_api_exam/test_card_publish.py`（追加 S9/R1/R2/R3）
- Modify: `edu-cloud/CLAUDE.md` 同步 `/api/v1/card/publish` 端点描述
- Modify: `docs/plans/2026-04-11-f003-question-writeback-design.md` 头部加 `[实现完成]` 标记

- [ ] **Step 1: 写 S9a publish-only 可见性测试（Plan Review R1 F005 修正）**

**拆分说明**：原 S9/R1 总验证被证明有漏洞（Plan Review R1 F005）——断言只查 `marking/subjects.questions` 非空，但这个字段本来就直接从 Question 表取，pipeline 写 StudentAnswer 即使彻底断裂此测试也会通过。修正为两部分：
- **S9a** (`test_S9a_publish_creates_questions_visible_in_marking`) — 只证 publish → Question/Template/marking 查询通，**不涉及** pipeline，断言限定在 questions 列表
- **S9b** (`test_S9b_pipeline_writeback_total_answers_visible`) — 证 pipeline save_answer_fn → StudentAnswer → marking/subjects `total_answers > 0`，这才是 F003 的真正总验证

在 `tests/test_api_exam/test_card_publish.py` 追加：

```python
async def test_S9a_publish_creates_questions_visible_in_marking(client, db):
    """S9a: publish → Question/Template/exam.status + marking/subjects 返回 questions 非空。

    断言范围: Question 表 + Template 表 + exam.status + marking/subjects.questions
    不包含: StudentAnswer / total_answers（由 S9b 覆盖）
    反例: 错误实现不创建 Question → marking/subjects.questions=[]
    """
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.modules.exam.models import Exam, Subject, Question
    from edu_cloud.modules.card.models import Template
    from edu_cloud.shared.auth import create_access_token
    from sqlalchemy import select

    # setup
    school = School(name="S9Sch", code="S9SCH")
    db.add(school)
    await db.commit()
    user = User(username="s9_u", display_name="S9")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    exam = Exam(name="S9 考试", school_id=school.id, status="draft")
    db.add(exam)
    await db.commit()
    subject = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subject)
    await db.commit()

    # Mock PDF + skeleton (模拟 Playwright 输出)
    async def fake_pdf(html, paper_size):
        return b"%PDF-S9"

    async def fake_extract(html):
        return {
            "image_width": 1587, "image_height": 1123, "anchors": [],
            "objective_groups": [
                {"group_id": "obj1", "start_no": 1, "count": 12, "options": 4,
                 "symbols": "A,B,C,D", "per_score": 3,
                 "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}}
            ],
            "slots": [{"sub_regions": [
                {"id": "essay-13", "name": "13", "score": 10, "rect": {"x1": 0, "y1": 100, "x2": 100, "y2": 200}},
                {"id": "essay-14", "name": "14", "score": 15, "rect": {"x1": 0, "y1": 200, "x2": 100, "y2": 300}},
            ]}],
            "regions": [
                {"id": "essay-13", "type": "subjective", "qno": 13, "side": "A",
                 "rect": {"x1": 0, "y1": 100, "x2": 100, "y2": 200}},
                {"id": "essay-14", "type": "subjective", "qno": 14, "side": "B",
                 "rect": {"x1": 0, "y1": 200, "x2": 100, "y2": 300}},
            ],
        }

    with patch("edu_cloud.modules.card.publish_service.html_to_pdf", side_effect=fake_pdf), \
         patch("edu_cloud.modules.card.publish_service.extract_skeleton", side_effect=fake_extract):
        resp = await client.post(
            "/api/v1/card/publish",
            json={"html": "<html/>", "subject_id": subject.id, "exam_id": exam.id, "paper_size": "A3"},
            headers=headers,
        )
    assert resp.status_code == 200

    # S9 断言 1: Question 表有 12 (objective) + 2 (subjective) = 14 条
    qs = (await db.execute(select(Question).where(Question.subject_id == subject.id))).scalars().all()
    assert len(qs) == 14, f"期望 14 条 Question（12 选择题 + 2 主观题），实际 {len(qs)}"
    obj_count = sum(1 for q in qs if q.question_type == "objective")
    subj_count = sum(1 for q in qs if q.question_type == "subjective")
    assert obj_count == 12
    assert subj_count == 2

    # S9 断言 2: Template 双面
    tpls = (await db.execute(select(Template).where(Template.subject_id == subject.id))).scalars().all()
    assert len(tpls) == 2
    sides = sorted(t.side for t in tpls)
    assert sides == ["A", "B"]

    # S9 断言 3: exam.status = scanning
    exam_r = (await db.execute(select(Exam).where(Exam.id == exam.id))).scalar_one()
    assert exam_r.status == "scanning"

    # S9a 断言 4: GET /api/v1/marking/subjects 返回数学 subject 的 questions 非空
    # (注：marking_subjects 走 visible_codes 过滤，admin 角色会看到全部)
    resp = await client.get(
        f"/api/v1/marking/subjects?exam_id={exam.id}",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    math_subj = next((s for s in data if s["name"] == "数学"), None)
    assert math_subj is not None, f"数学科目应出现在 marking/subjects 响应中，实际: {[s['name'] for s in data]}"
    assert len(math_subj["questions"]) == 14, (
        f"数学 questions 应有 14 条，实际 {len(math_subj['questions'])} (原 F003 症状: 0 条)"
    )
    # S9a 不断言 total_answers —— 那是 S9b 的职责
```

- [ ] **Step 2: 写 S9b pipeline writeback 测试（R1-F005 + R2-F003 修正）**

**关键（R2-F003 修正）**：S9b **必须经过 T11 抽出的 `build_pipeline_save_answer_fn` 工厂函数**获取闭包，然后手动驱动闭包写 StudentAnswer——而不是测试里手工 `db.add(StudentAnswer)`。这样 S9b 真正触达 `pipeline_router` 的装配路径（region_map 构造 + 闭包反查），CE-002 缓解路径才成立。

```python
async def test_S9b_pipeline_writeback_total_answers_visible(client, db):
    """S9b (R1-F005 + R2-F003 修正): publish → build_pipeline_save_answer_fn 工厂 → 闭包写 StudentAnswer → marking total_answers 可见。

    断言范围: F003 写入责任链 pipeline 端——
    publish 写 Template.regions[].question_id → 工厂构造 region_map → 闭包反查 → StudentAnswer 表非空 → marking/subjects.total_answers > 0

    反例 1: pipeline_router 没抽工厂 / 没传 save_answer_fn → S9b 在 import 阶段失败
    反例 2: 工厂未正确反查 region_map → 闭包写入错误 question_id → 断言 q13.total_answers 失败
    反例 3: publish 未写 Template.regions[].question_id → assert region_13.get("question_id") 失败
    """
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.modules.exam.models import Exam, Subject, Question
    from edu_cloud.modules.card.models import Template
    from edu_cloud.modules.scan.models import StudentAnswer
    from edu_cloud.modules.scan.pipeline_router import build_pipeline_save_answer_fn
    from edu_cloud.shared.auth import create_access_token
    from sqlalchemy import select

    school = School(name="S9bSch", code="S9BSCH")
    db.add(school)
    await db.commit()
    user = User(username="s9b_u", display_name="S9b")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    exam = Exam(name="S9b 考试", school_id=school.id, status="draft")
    db.add(exam)
    await db.commit()
    subject = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subject)
    await db.commit()

    # Step A: publish 触发 upsert Question + Template（复用 S9a 的 mock 方式）
    async def fake_pdf(html, paper_size):
        return b"%PDF"

    async def fake_extract(html):
        return {
            "image_width": 1587, "image_height": 1123, "anchors": [],
            "objective_groups": [],
            "slots": [{"sub_regions": [
                {"id": "essay-13", "name": "13", "score": 10, "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
            ]}],
            "regions": [
                {"id": "essay-13", "type": "subjective", "qno": 13, "side": "A",
                 "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
            ],
        }

    with patch("edu_cloud.modules.card.publish_service.html_to_pdf", side_effect=fake_pdf), \
         patch("edu_cloud.modules.card.publish_service.extract_skeleton", side_effect=fake_extract):
        resp = await client.post(
            "/api/v1/card/publish",
            json={"html": "<html/>", "subject_id": subject.id, "exam_id": exam.id, "paper_size": "A3"},
            headers=headers,
        )
    assert resp.status_code == 200

    # Step B: 验证 Template.regions 已带 question_id（publish 写入正确）
    tpl_a = (await db.execute(
        select(Template).where(Template.subject_id == subject.id, Template.side == "A")
    )).scalar_one()
    region_13 = next(r for r in tpl_a.regions if r.get("id") == "essay-13")
    assert region_13.get("question_id"), "F003 核心前提：Template.regions[].question_id 非空"

    # Step C (R2-F003 + R3-F002/F005 修正): 通过 T11 工厂函数构造 save_answer_fn 闭包,
    # 签名为 regions: list[dict] (不是 Template ORM, 与 start_pipeline 装配路径完全一致).
    # client fixture 的 monkey-patch 生效期间调用工厂 → 闭包内 async_session() 打到 in-memory test DB.
    save_answer = build_pipeline_save_answer_fn(
        regions=tpl_a.regions,             # ← 传 list[dict], 不传 Template ORM
        exam_id=exam.id,
        subject_id=subject.id,
        school_id=school.id,
    )

    # 模拟 2 个学生各 1 张切图，驱动闭包写入（闭包内部负责 region_map 反查 + INSERT）
    # pipeline_service 命名遗留：闭包 question_id 参数实际接 region_id
    for student_id in ("stu-001", "stu-002"):
        await save_answer(
            exam_id=exam.id,
            subject_id=subject.id,
            student_id=student_id,
            question_id="essay-13",  # region_id，闭包反查为 Question.id
            image_path=f"/fake/{student_id}.png",
            school_id=school.id,
        )

    # Step D: 断言 StudentAnswer 已落库
    # 跨 session 可见性 (R3-F002): 工厂闭包在新 session 写入, db fixture 需 expire_all 看到最新
    db.expire_all()  # R4-F002: 同步 API, 不 await
    answers = (await db.execute(select(StudentAnswer).where(StudentAnswer.subject_id == subject.id))).scalars().all()
    assert len(answers) == 2, f"应有 2 条 StudentAnswer，实际 {len(answers)}"
    # 断言闭包正确反查：question_id 指向真实 Question.id，而非原 region_id
    q13_real = (await db.execute(
        select(Question).where(Question.subject_id == subject.id, Question.name == "13")
    )).scalar_one()
    assert all(a.question_id == q13_real.id for a in answers), (
        "StudentAnswer.question_id 应反查为真实 Question.id，证明经过工厂闭包装配路径"
    )

    # Step E: 断言 marking/subjects.total_answers 反映了写入
    resp = await client.get(
        f"/api/v1/marking/subjects?exam_id={exam.id}",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    math_subj = next((s for s in data if s["name"] == "数学"), None)
    assert math_subj is not None

    # 找到 Question.name="13" 的统计行
    q13 = next((q for q in math_subj["questions"] if q["name"] == "13"), None)
    assert q13 is not None, f"题目 13 应在 questions 列表中"
    assert q13["total_answers"] == 2, (
        f"S9b 核心断言: question 13 的 total_answers 应为 2，实际 {q13['total_answers']}"
        " —— 这是 F003 的真正总验证（原症状 total_answers=0）"
    )
```

- [ ] **Step 3: 写回归测试 R3（幂等 + 孤儿保留）**

```python
async def test_R3_second_publish_preserves_orphans_and_idempotent(client, db):
    """R3: 发布 → 再发布（删一题 + 改分值）→ 原 Question 保留，分值更新。

    这是 design.md §11 验收标准第 7 / 8 两项的合并测试。
    """
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.modules.exam.models import Exam, Subject, Question
    from edu_cloud.shared.auth import create_access_token
    from sqlalchemy import select

    school = School(name="R3Sch", code="R3SCH")
    db.add(school)
    await db.commit()
    user = User(username="r3_u", display_name="R3")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    exam = Exam(name="R3 考试", school_id=school.id, status="draft")
    db.add(exam)
    await db.commit()
    subject = Subject(exam_id=exam.id, name="物理", code="WL", school_id=school.id)
    db.add(subject)
    await db.commit()

    async def fake_pdf(html, paper_size):
        return b"%PDF-R3"

    # 第一次 publish：3 道题 (13/14/15)
    async def extract_v1(html):
        return {
            "image_width": 1587, "image_height": 1123, "anchors": [],
            "objective_groups": [],
            "slots": [{"sub_regions": [
                {"id": "essay-13", "name": "13", "score": 10, "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
                {"id": "essay-14", "name": "14", "score": 10, "rect": {"x1": 0, "y1": 100, "x2": 100, "y2": 200}},
                {"id": "essay-15", "name": "15", "score": 10, "rect": {"x1": 0, "y1": 200, "x2": 100, "y2": 300}},
            ]}],
            "regions": [
                {"id": "essay-13", "type": "subjective", "qno": 13, "side": "A",
                 "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
                {"id": "essay-14", "type": "subjective", "qno": 14, "side": "A",
                 "rect": {"x1": 0, "y1": 100, "x2": 100, "y2": 200}},
                {"id": "essay-15", "type": "subjective", "qno": 15, "side": "A",
                 "rect": {"x1": 0, "y1": 200, "x2": 100, "y2": 300}},
            ],
        }

    with patch("edu_cloud.modules.card.publish_service.html_to_pdf", side_effect=fake_pdf), \
         patch("edu_cloud.modules.card.publish_service.extract_skeleton", side_effect=extract_v1):
        resp1 = await client.post(
            "/api/v1/card/publish",
            json={"html": "<html>v1</html>", "subject_id": subject.id, "exam_id": exam.id, "paper_size": "A3"},
            headers=headers,
        )
    assert resp1.status_code == 200
    qs1 = (await db.execute(select(Question).where(Question.subject_id == subject.id))).scalars().all()
    assert len(qs1) == 3
    assert {q.name for q in qs1} == {"13", "14", "15"}

    # 第二次 publish：删除 15，把 13 分值改为 12
    async def extract_v2(html):
        return {
            "image_width": 1587, "image_height": 1123, "anchors": [],
            "objective_groups": [],
            "slots": [{"sub_regions": [
                {"id": "essay-13", "name": "13", "score": 12, "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
                {"id": "essay-14", "name": "14", "score": 10, "rect": {"x1": 0, "y1": 100, "x2": 100, "y2": 200}},
            ]}],
            "regions": [
                {"id": "essay-13", "type": "subjective", "qno": 13, "side": "A",
                 "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
                {"id": "essay-14", "type": "subjective", "qno": 14, "side": "A",
                 "rect": {"x1": 0, "y1": 100, "x2": 100, "y2": 200}},
            ],
        }

    with patch("edu_cloud.modules.card.publish_service.html_to_pdf", side_effect=fake_pdf), \
         patch("edu_cloud.modules.card.publish_service.extract_skeleton", side_effect=extract_v2):
        resp2 = await client.post(
            "/api/v1/card/publish",
            json={"html": "<html>v2</html>", "subject_id": subject.id, "exam_id": exam.id, "paper_size": "A3"},
            headers=headers,
        )
    assert resp2.status_code == 200

    # R3 断言 1: Question 表仍然 3 条（15 保留为孤儿）
    qs2 = (await db.execute(select(Question).where(Question.subject_id == subject.id))).scalars().all()
    assert len(qs2) == 3, f"R3 回归: 孤儿 Question 15 应保留，实际 {len(qs2)} 条"
    assert {q.name for q in qs2} == {"13", "14", "15"}

    # R3 断言 2: 13 的 max_score 已更新为 12
    q13 = next(q for q in qs2 if q.name == "13")
    assert q13.max_score == 12.0, f"Question 13 max_score 应更新为 12，实际 {q13.max_score}"

    # R3 断言 3: exam.status 维持 scanning（二次 publish 不重置）
    exam_r = (await db.execute(select(Exam).where(Exam.id == exam.id))).scalar_one()
    assert exam_r.status == "scanning"
```

**注：** S9/R1/R3 的测试聚焦 publish 路径 + marking/subjects 查询，**不涉及** scan pipeline 的 StudentAnswer 写入。pipeline 部分已由 Task 11 的 S8 独立覆盖。这个切分让 Task 12 的测试保持 unit/integration 级别，不需要跑真实 Playwright 或 async background task。

- [ ] **Step 2: Run E2E + 回归 verify**

```bash
python -m pytest tests/test_api_exam/test_card_publish.py -v
```

Expected: S9 + R1 + R3 全部 PASS

- [ ] **Step 3: 广域全量回归**

```bash
python -m pytest -q
cd frontend && npx vitest run
```

Expected: 后端全量 + 前端全量都 PASS

- [ ] **Step 4: 更新 CLAUDE.md**

编辑 `edu-cloud/CLAUDE.md` 找到 `/api/v1/card/publish` 段（若有），更新描述；若无则追加：

```markdown
| POST | `/api/v1/card/publish` | 一站式发布答题卡：html→PDF + upsert Question + 双面 Template + exam.status=scanning。F003 修复后为前端 publishCard 唯一入口，取代原手工三步 |
```

- [ ] **Step 5: 更新 design.md 头部 [实现完成] 标记**

在 `docs/plans/2026-04-11-f003-question-writeback-design.md` §0 之后追加：

```markdown
> [YYYY-MM-DD HH:MM:SS 实现完成] Commits: <first>..<last>
```

- [ ] **Step 6: Commit**

```bash
git add tests/test_api_exam/test_card_publish.py CLAUDE.md docs/plans/2026-04-11-f003-question-writeback-design.md
git commit -m "feat(card): F003 E2E + 回归 + design [实现完成] 标记 (T12)"
```

**测试契约（S9a / S9b / R3，Plan Review R1 F005 修正）:**

| slice | 入口 | 反例 | 边界 | 回归 | 命令 |
|-------|------|------|------|------|------|
| S9a | POST /api/v1/card/publish + GET /marking/subjects | 错误实现 publish 不创建 Question → marking.questions=[] | 14 题（12 obj + 2 subj）→ questions 长度=14 + Template 双面 + exam.status=scanning | F003 publish 端路径 | `pytest test_S9a_publish_creates_questions_visible_in_marking -v` |
| S9b | publish + 直调 save_answer_fn 闭包写 StudentAnswer + GET /marking/subjects | 错误实现 pipeline 未接 region_map → StudentAnswer=0 → total_answers=0 | 2 学生 × 1 题 → total_answers=2 | **F003 总验证（真正的 E2E）** | `pytest test_S9b_pipeline_writeback_total_answers_visible -v` |
| R3 | publish v1 → publish v2（删 15 + 改 13 分值）→ 查 Question 表 | hard-delete 实现 → Question 数量减少 | 第一次 3 题 → 第二次 2 题 → DB 仍 3 条 | D4 孤儿保留 + 幂等 | `pytest test_R3_second_publish_preserves_orphans_and_idempotent -v` |

**边界条件:**
- E2E 链路每一步都可能挂，需要 fixture 覆盖全套状态
- pipeline 是 async background task，需要合适的等待机制
- R1 必须对应原 F003 症状文字描述（marking_subjects questions 空的断言）

**审查清单:**
- ✓ 正向：S9 完整 E2E PASS
- ✓ 正向：R1/R3 回归 PASS
- ✓ 正向：design.md 头部有 `[实现完成]` 时间戳 + commit 范围
- ✓ 正向：CLAUDE.md 路由表含 `/api/v1/card/publish`
- ✓ 正向：全量后端 + 前端测试 PASS
- ✗ 反向：S9 用 pass 占位未实现

---

**Batch 3 结束 checkpoint:**
- Task 9-12 全部完成
- 前端走新入口，pipeline 接通闭包
- E2E S9 + R1/R3 回归 PASS
- CLAUDE.md 同步
- design.md 标记 [实现完成]
- **预计耗时：** 6-10 小时 / 1 个 code review batch

---

## 全局 Spec Coverage 自检（writing-plans self-review）

对照 design.md 每一节，验证 plan 有对应 Task：

| design 段 | plan Task | 覆盖状态 |
|----------|----------|---------|
| §1 背景与根因 | — | 无需任务（背景） |
| §2 设计原则 | T1-T12 通过 invariants 守护 | ✓ |
| §3 D1 Question 权威源 | T3+T6 | ✓ |
| §3 D2 Publish-time upsert | T6 (publish_card_atomic) | ✓ |
| §3 D3 命名纯题号 | T3 (upsert_questions_from_skeleton) | ✓ |
| §3 D4 upsert 孤儿保留 | T3 (S4 test) | ✓ |
| §3 D5 逐题存储 | T3 (objective group 展开) | ✓ |
| §3 D6 双面 Template | T4 (upsert_template_both_sides) + T1 (F001 render.js) | ✓ |
| §3 D7 save_answer_fn 闭包 | T11 (pipeline_router 构建闭包) | ✓ |
| §3 D8 前端走 /card/publish | T9+T10 (publishCard + ExamDetailPage) | ✓ |
| §4 数据流架构 | T6 (publish_card_atomic) + T11 (pipeline_router) | ✓ |
| §5.1 publish_service 新模块 | T3+T4+T6 | ✓ |
| §5.2 6 文件改动清单 | T1 (render.js) / T9 (export.js) / T10 (ExamDetailPage) / T3-T6 (publish_service 新建) / T8 (card/router) / T11 (pipeline_router) | ✓ |
| §5.4 Question UniqueConstraint migration | T5 | ✓ |
| §5.5 StudentAnswer 唯一约束调查 | T0 | ✓ |
| §6.1 事务原子性 | T6 (S6) | ✓ |
| §6.2 并发 IntegrityError retry | T7 | ✓ |
| §6.3 orphan region pipeline | T11 (S8) | ✓ |
| §6.4 前置校验清单 | T6 (publish_card_atomic 前置校验) | ✓ |
| §7 测试 9 slices | T1 (V1) + T2 (A2) + T3 (S2/S3/S4) + T4 (S5) + T6 (S6) + T7 (S7) + T8 (F) + T11 (S8) + T12 (S9) | ✓ |
| §8 批次划分 | Batch 1/2/3 结构 | ✓ |
| §9 不在范围清单 | — | 无需任务 |
| §10 风险清单 | T0 (StudentAnswer 约束) + T5 (UniqueConstraint) 缓解 | ✓ |
| §11 验收标准 9 项 | T12 E2E + R1/R3 + 手动 smoke | ✓ |

**覆盖率：** 100% — design.md 所有规范章节都有对应的 plan Task 实现。

**Placeholder 扫描：** Task 12 Step 1 的 S9/R1/R3 测试体以 `pass` 占位，需要在实施时展开完整断言。这个是有意的——因为 E2E 场景需要配合前面 11 个 Task 的具体实现来编写真实数据流。实施方应在 Task 12 开始前回读 design.md §11 验收标准补全。

**类型一致性：** publish_service 的三个函数签名在 T3/T4/T6 中一致（db/subject_id/school_id/skeleton/question_map）。

---

## 执行交接（writing-plans skill 默认选项的项目级覆盖）

**标准 writing-plans skill 提供两个选项**（subagent-driven / inline），但项目规则 CLAUDE.md 明确：

> **Superpowers 覆盖规则**
> - writing-plans 完成后：T3/T4 禁止"同会话执行"，必须新会话

因此 B1 F003 不走 skill 默认两个选项，而是：

1. **本会话**：写完 plan → self-review → 生成 state.json → commit draft → 调 codex-review (plan) Gate 1 → 处置 finding → commit final plan → gates.json pass
2. **新会话**：用 handoff-card skill 生成的启动 prompt 启动，调 executing-plans skill 开始 Batch 1

**下一步动作（本会话）:**
- 写 `docs/plans/2026-04-11-f003-question-writeback-state.json` sidecar
- commit plan draft
- 调 codex-review skill 进行跨模型 plan review
- 根据 Gate 1 finding 决定是否有修订
- 生成 `docs/plans/2026-04-11-f003-question-writeback-gates.json` 回执
- 调 handoff-card skill 生成新会话启动 prompt
- 结束本会话

---

## 附录 A: 预估工作量

| Batch | Tasks | 代码 LOC 估算 | 测试 LOC 估算 | 预计时间 |
|-------|-------|-------------|-------------|---------|
| Batch 1 | T0-T4 | 220 | 320 | 4-6 h |
| Batch 2 | T5-T8 | 150 | 180 | 5-8 h |
| Batch 3 | T9-T12 | 140 | 260 | 6-10 h |
| **合计** | 13 tasks | ~510 | ~760 | **15-24 h** |

按每日 6h 有效开发估算：**3-4 个工作日**

## 附录 B: 外部依赖检查

- [ ] Playwright chromium 已安装（T2 integration 测试依赖）
- [ ] PostgreSQL 本地运行（T5 migration 生产环境校验时用）
- [ ] Redis 运行（pipeline 的 arq background task，T11 间接依赖）
- [ ] 前端 vitest + happy-dom 已配置（T1/T9/T10 依赖）

## 附录 C: 回退方案

如果 Batch 2 / Batch 3 任一阶段出现不可恢复问题：

1. **Batch 1 可独立保留**：纯函数 + F001 修复无对外接口变更，可保留在主线
2. **Batch 2 回退**：revert T5-T8 commits，保留 T0-T4，还原为"Batch 1 + 原 publish 端点内联"
3. **Batch 3 回退**：revert T9-T12 commits，保留 T0-T8，前端 publishCard 暂不切换（运行时会走旧路径，不影响已有功能）

完整回退命令：
```bash
git revert <commit-T12> <commit-T11> ... <commit-T5>
```

## 附录 D: 相关 Finding 关系

| Finding | Tier | 关系 | 处理方式 |
|---------|------|------|---------|
| F001 | T1 | 前置 | 合并为 T1（Slice A） |
| F002 | T3 | 并行 | B5 独立批次 |
| F003 | T4 | 本设计主目标 | B1 全部 Tasks |
| F003a | T2 | 合并 | T4 (双面 Template) |
| F008 | HIGH | 依赖 | F003 修复后可独立验证 |
| F011-F014 / F015 | — | 不在范围 | 各自独立批次 |



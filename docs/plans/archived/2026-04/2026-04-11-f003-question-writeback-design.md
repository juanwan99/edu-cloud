---
type: design
topic: f003-question-writeback
created: 2026-04-11 21:10:18
tier: T4
status: completed
depends_on:
  - docs/plans/archived/2026-04/2026-04-08-card-xiaowei-layout-v2-handoff.md  # 小微排版 v2 视觉验收必须先回主线
related_findings:
  - F001  # render.js .page 缺 data-side 属性（作为本设计的前置子任务）
  - F003  # Question 创建入口从未接通（本设计的主目标）
  - F003a # publish 硬编码 side="A"（合并到双面 Template 写入）
  - F008  # 选择题识别 + anchor/affine 被 F003 遮蔽（F003 修复后解锁独立验证）
exploration_source: docs/plans/archived/2026-04/2026-04-11-exploration-notes.md §D6 + §Round 3
---

# F003 Question 写入责任链重设 — Design

> [2026-04-12 16:29:15 实现完成] Commits: e73881a..0e072bc
> [2026-04-12 17:23:18 对齐] 架构级偏差 3 项已对齐 | 偏差来源: 交接单自审 🔀 + GPT 审查 finding | Commits: e73881a..23f5928
>
> 1. **T6 事务边界变更**: publish_card_atomic DB 操作加 `begin_nested()` 外层包裹（原设计未指定）— 原因: SQLite in-memory 下直接 `db.rollback()` 无法回滚已 RELEASE 的内层 SAVEPOINT，外层 begin_nested 确保原子性。PostgreSQL 下行为等价。
> 2. **T11 API 签名扩展**: `build_pipeline_save_answer_fn` 新增 `_session_factory=None` 可选参数 — 原因: aiosqlite + greenlet MissingGreenlet 限制，测试需注入 session factory。生产不传则默认 `db_mod.async_session`，不影响调用方。
> 3. **B2-F001 跨 scope 回归修复**: T5 UniqueConstraint 引入后 `/api/v1/questions` POST/PATCH 500 回归 — 用户授权 scope 扩展，`modules/exam/router.py` create_question/update_question 加 IntegrityError→409 处理。

## §0 TL;DR

edu-cloud 阅卷管道端到端断裂的根因是 **Question 创建入口从未接通**：CardEditor 布局写 `editor_layouts/*.json` 文件不同步 DB，后端 `/api/v1/card/publish` 端点虽然实现了一站式 publish 却从未被前端调用（僵尸端点），而前端 `publishCard()` 手工三步只写 Template A 面不创建 Question。方案 D 将 Question 创建责任前移到 publish 时刻，由后端 `/api/v1/card/publish` 统一承担 "html→PDF + skeleton→upsert Question + 双面 Template + exam.status 切换" 的原子职责，前端 `publishCard()` 简化为单次 HTTP 调用。

**影响面**：6 个文件改动 + 1 个新模块 + 1 个 schema migration（Question 加 UniqueConstraint）
**前置依赖**：F001 render.js 4 处 `.page` 加 `data-side` 属性（card 模块 WIP 冲突区，需等小微排版 v2 视觉验收回主线）
**Tier**: T4（跨模块、跨前后端、接口语义变更、schema 变更）

## §1 背景与根因

### 1.1 F003 现象

edu-cloud 全量探索测试发现的管道断裂：

- 367 学生 × 6 题 = 2202 张切图全部落盘 `storage/{school_id}/{exam_id}/{subject_id}/{student_number}/Q{N}.png`
- `GET /api/v1/grading/progress/{exam_id}` → `{total_papers:0, graded_papers:0}`
- `GET /api/v1/marking/subjects` → 数学科目 question_count=0, total_answers=0
- 切图文件和数据库完全解耦，无法被任何阅卷/统计/自适应模块消费

### 1.2 根因（`notes.md §D2 §D6` 深挖）

1. **CardEditor 布局是文件存储，不走 DB**
   - `card/router.py:39` `_EDITOR_LAYOUT_DIR = editor_layouts/`
   - `card/router.py:157 PUT /card/editor-layout/{subject_id}` 只调 `_editor_layout_path(...).write_text(...)`
   - 没有任何 Question/StudentAnswer 写入

2. **前端 `createQuestion` 是死代码**
   - `frontend/src/api/questions.js:5` 定义了 `createQuestion` 但全代码库零调用

3. **后端 `POST /api/v1/card/publish` 是僵尸端点**
   - `card/router.py:1189` 实现了一站式 publish（含 `build question_map`、`skeleton_to_paperseg_json`、Template 写入、exam.status 切换）
   - 前端 `ExamDetailPage.vue:868` 调用 `exportModule.publishCard()` 走的是 `export.js:177` 的手工三步：`/export/pdf` + `/export/skeleton` + `PUT /templates/{subjectId}/A`
   - **从未触达 `/api/v1/card/publish`**

4. **僵尸端点即使被调用也不创建 Question**
   - `router.py:1225-1229` 从**已有的** Question 表读取构建 `question_map={q.name: q.id}`
   - 如果 Question 表空 → question_map 永远为空 → Template.regions 没有 question_id → pipeline 切图无法关联题目

5. **Template 硬编码单面**
   - `router.py:1247` `.where(Template.side == "A")` 只写 A 面，B 面永远不存在（F003a）

### 1.3 原 R1 方案 A/B/C 全部失效的证据（`notes.md §D6`）

- 方案 A（pipeline 自动创建 Question）：pipeline 层无题目元数据，且反向依赖 card 模块违反边界
- 方案 B（pipeline 输出改兼容 importer 目录）：`marking/importer` 只处理已有 Question 的 StudentAnswer 关联，Question 本身还是没人创建
- 方案 C（新增 `/pipeline/commit` 端点）：同样依赖 Question 表非空

## §2 设计原则

- **Question 表是权威源**：所有下游（marking/grading/analytics/adaptive/knowledge-tree）直接从 Question 表读取，editor_layouts 降级为纯布局坐标
- **Publish 是写入时机边界**：save_editor_layout 保持纯文件写入（无 DB 副作用），publish 承担一次性的 DB 写入事务
- **一条路径主义**：前端 publishCard 废弃手工三步，全部走后端 `/api/v1/card/publish` 僵尸端点（复活为唯一主路径）
- **事务原子性**：Question upsert + Template 双面 + exam.status 切换在单事务中，任一失败全部 rollback（PDF 生成在事务外）
- **幂等性**：多次 publish 结果一致，老师可以反复发布不产生副作用
- **孤儿保留**：老师发布后删题目再发布，旧 Question 在 DB 里保留不删（下游通过 StudentAnswer 关联天然无害）

## §3 8 个核心决策（brainstorming 已锁定）

| # | 决策点 | 选项 | 理由 |
|---|--------|------|------|
| D1 | Question 权威源 | **Question 表是真实源** | 所有下游读取都经 Question 表；editor_layouts 只存布局坐标 |
| D2 | 写入时机 | **Publish-time upsert** | 草稿阶段 DB 不污染；publish 是语义承诺点 |
| D3 | 命名约定 | **纯题号字符串**（"12" / "15.1"）| seed_demo.py 现有 5 科种子数据已用此格式，零 migration |
| D4 | upsert 策略 | **by (subject_id, name) 新增+更新，孤儿保留** | 幂等、零 schema 改动、保护历史阅卷数据 |
| D5 | 选择题粒度 | **逐题 N 条 Question** | 现有 export.py:62-67 的 `per_question_ids` 已假设逐题；marking/analytics 下游按 Question.id 查 |
| D6 | 双面 Template | **单次 publish 原子写 A+B**（F001 作为前置）| Template schema 已有 UniqueConstraint(subject_id, side)；publish 应原子 |
| D7 | save_answer_fn | **闭包捕获 region_map**，run_pipeline 零感知 | 职责分层；run_pipeline 保持纯调度 |
| D8 | 前端路径 | **废弃 publishCard 三步，走 /card/publish** | 一条路径主义；僵尸端点复活；前端从 40 行减到 10 行 |

## §4 架构与数据流

### 4.1 整体流程

```
[时间线]        [老师]           [前端]              [后端]                      [存储]
─────────────────────────────────────────────────────────────────────────────
草稿编辑期  →  CardEditor 拖拽  →  save_editor_layout  →  PUT /card/editor-layout →  editor_layouts/{school}/{subject}.json
                                                          (router.py:157 保持纯文件写)   (文件系统，纯布局坐标)

发布答题卡  →  点"发布"       →  publishCard(subjectId,→  POST /card/publish        →  [事务原子写入]
                                      examId, filename)     (复活 router.py:1189)        1. Question upsert × N
                                                                                         2. Template upsert × (A+B)
                                                                                         3. exam.status = scanning
                                               ←  返回 PDF blob ←                          + PDF blob（事务外生成）

扫描切割    →  POST /pipeline/start →  pipeline_router   →  run_pipeline(save_answer_fn)
                                         ─ 读 Template(subject_id, side)
                                         ─ 构建 region_map = {region_id: question_id}
                                         ─ 构建 save_answer_fn 闭包
                                              ↓
                                         pipeline_service.run_pipeline (零改)
                                         ─ list_scan_images → process_one_image
                                         ─ 对每个 crop 调 save_answer_fn(region_id, image_path)
                                                                                 ↓
                                                                            save_answer_fn 闭包
                                                                            ─ question_id = region_map[region_id]
                                                                            ─ if None: log warning + skip
                                                                            ─ else: INSERT StudentAnswer

阅卷 / 统计 /  → 全部走 Question 表 + StudentAnswer (外键 question_id)
自适应 / 知识点
```

### 4.2 关键 invariants

- **invariant 1**：`save_editor_layout` 无 DB 副作用（文件写入 only）
- **invariant 2**：`publish_card_atomic` 内部所有 DB 写在一个事务，PDF 生成在事务外
- **invariant 3**：pipeline 层不直接访问 Question 表，通过 region_map 闭包获得 question_id
- **invariant 4**：Question.name 的字符串值在全链路一致（CardEditor qno → layout JSON → skeleton slot.name → Question.name → export.py question_map key）
- **invariant 5**：Template 存在的主 key 是 `(subject_id, side)`，双面考试必须有 2 条记录
- **invariant 6**：孤儿 Question 不阻塞任何下游（通过 StudentAnswer 关联天然过滤）

## §5 组件清单

### 5.1 新增模块

#### `src/edu_cloud/modules/card/publish_service.py`（新文件）

导出 3 个 async 函数：

```python
async def upsert_questions_from_skeleton(
    db: AsyncSession,
    subject_id: str,
    school_id: str,
    skeleton: dict,
) -> dict[str, str]:
    """从 skeleton 扫描 regions + objective_groups，upsert Question 表。

    对 subjective regions：每个 region.name 作为 Question.name upsert 一条。
    对 objective_groups：按 start_no + i 展开为 N 道 Question，name = str(qno)。

    upsert 语义：
      SELECT ... WHERE (subject_id, name)
        match → UPDATE max_score/question_type
        no match → INSERT
      孤儿（DB 有但 skeleton 没）→ 保留不动

    返回 {name: question_id} 的映射表，用于后续 skeleton_to_paperseg_json(question_map)。

    并发保护：SELECT 前先捕获可能的 IntegrityError（唯一约束冲突），重新 SELECT 拿 id。
    """

async def upsert_template_both_sides(
    db: AsyncSession,
    subject_id: str,
    school_id: str,
    skeleton: dict,
    question_map: dict[str, str],
) -> tuple[Template, Template | None]:
    """按 skeleton.regions[].side 分组，构建 A 面 + B 面 tpl_data，分别 upsert Template。

    A 面必存（若缺失 raise HTTPException(400)，防止 B-only 导致下游按 A 面查
    Template 查不到的隐藏故障），B 面可选（单面考试时返回 None）。
    upsert 走 UniqueConstraint(subject_id, side) 复合键。

    合法返回形态: (tpl_a, None) [单面] 或 (tpl_a, tpl_b) [双面]
    非法输入: B-only skeleton → raise HTTPException(400)
    """

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
      4. [BEGIN]
      5. upsert_questions_from_skeleton → question_map
      6. upsert_template_both_sides(question_map)
      7. exam.status = 'scanning' if exam.status == 'draft'
      8. [COMMIT]
      9. 返回 pdf_bytes
    """
```

**职责边界**：`publish_service` 只做业务逻辑，不做 HTTP 层校验（router 负责）。

### 5.2 改动文件

| # | 文件 | 改动 | 行数估算 |
|---|------|------|---------|
| F1 | `frontend/src/card-editor/render.js` | 4 处 `.page` DOM 加 `data-side="A/B"` 属性（F001 前置修复）| +4 |
| F2 | `frontend/src/card-editor/export.js publishCard()` | 重写：从 40 行手工三步缩到 ~15 行单次 `/card/publish` 调用；新签名加 examId 参数 | -25 |
| F3 | `frontend/src/pages/ExamDetailPage.vue:868` | 调用 publishCard 处加 examId 实参 | +1 |
| B1 | `src/edu_cloud/modules/card/publish_service.py` | **新建**，3 个导出函数 + 内部 helper | +200 |
| B2 | `src/edu_cloud/modules/card/router.py:1189 publish_card` | 调用 `publish_service.publish_card_atomic`，router 只做 auth/入参校验 | 替换 L1189-1270 为 ~20 行 |
| B3 | `src/edu_cloud/modules/scan/pipeline_router.py` pipeline start 端点 | 读 Template → 构建 region_map + save_answer_fn 闭包 → 传给 run_pipeline | +30 |

### 5.3 零改动（明确边界）

- `src/edu_cloud/modules/card/export.py skeleton_to_paperseg_json` — 已支持 question_map 参数
- `src/edu_cloud/modules/scan/pipeline_service.py run_pipeline` — save_answer_fn 参数已预留
- `src/edu_cloud/modules/card/html_export.py _extract_skeleton_sync` — F001 前端修好后 side 字段自然正确
- `Template` / `StudentAnswer` 表 schema
- `editor_layouts/*.json` 文件 schema

### 5.4 Schema 变更

**唯一一个 migration**：

```python
# alembic/versions/xxx_question_unique_subject_name.py
"""add unique constraint on (subject_id, name) for questions table

防止并发 publish 导致的重复 Question 插入。
"""
def upgrade():
    op.create_unique_constraint(
        "uq_question_subject_name",
        "questions",
        ["subject_id", "name"],
    )

def downgrade():
    op.drop_constraint("uq_question_subject_name", "questions", type_="unique")
```

**为什么需要**：
- 当前 Question 表只有 school_id 隔离，同一 subject_id 下允许相同 name 的重复 Question
- 并发 publish 场景（两个老师同时点击）会出现 race：双方都 SELECT → 都 INSERT → 产生重复
- 加 UniqueConstraint 后数据库层自动阻止，应用层捕获 IntegrityError 重新 SELECT 即可
- 现有 5 科种子数据已满足 (subject_id, name) 唯一，migration 不会失败

### 5.5 StudentAnswer 写入幂等（已核实）

**事实**（Plan Review R1 F003 修正）：`src/edu_cloud/modules/scan/models.py:23` 现有约束为 **3 列**：

```python
__table_args__ = (UniqueConstraint("exam_id", "student_id", "question_id"),)
```

**决策**：现有 3 列唯一键 **已经满足** pipeline 写回语义。理由：
- 同一 exam + 同一学生 + 同一题 → 全局唯一一条 StudentAnswer 记录
- subject_id 由 question_id → Question.subject_id 间接确定（同一 question_id 必然归属唯一 subject_id），所以无需加入唯一键
- 重跑 pipeline 相同学生同题 → 触发 IntegrityError，save_answer_fn 捕获后跳过 log warning，天然幂等

**实现策略**：save_answer_fn 内部使用 `INSERT` + `try: await db.commit() except IntegrityError: await db.rollback()` 模式。**无需任何 schema migration**。

## §6 错误处理

### 6.1 publish 事务原子性

```
事务外：
  - Subject/Exam 归属校验（快速失败 404）
  - exam.status ∈ {draft, scanning} 校验（快速失败 400）
  - html_to_pdf (Playwright 外部进程，失败 500 不污染 DB)
  - extract_skeleton

外层事务开始（publish_card_atomic 的 async with db.begin():）：
  - upsert_questions_from_skeleton
      └─ 循环每题：async with db.begin_nested():  # SAVEPOINT 子事务
             db.add(Question); await db.flush()
         IntegrityError 触发时 SAVEPOINT 自动 rollback（子事务），
         外层事务继续，前面题目保留 → 进入 retry 分支 re-select existing
  - upsert_template_both_sides
  - exam.status = scanning
  - commit（外层事务一次性）

任一步非并发异常 → 外层 db.rollback() → raise HTTPException → PDF bytes 丢弃（前端收到 error 会重试）
```

**关键不变量（R2-F001 补充）**：`upsert_questions_from_skeleton` 的单题冲突只能收敛在 SAVEPOINT 子事务内，**禁止**在循环内调用 `await db.rollback()`（会破坏外层事务、回滚前面已 upsert 的其他题目）。外层事务的完整性由 `publish_card_atomic` 独占。

### 6.2 并发 publish 保护

**场景**：两个老师同时点 publish 同一 subject_id → Question upsert race

**防御（R2-F001 修正：SAVEPOINT 方案）**：
1. Question 表加 `UniqueConstraint(subject_id, name)` — 数据库层硬约束
2. `upsert_questions_from_skeleton` 循环内每题包 `async with db.begin_nested():` 创建 SAVEPOINT 子事务
3. 子事务内 `db.add + db.flush()` 触发的 `IntegrityError` 让 SAVEPOINT 自动回滚（`async with` 块退出时），**外层事务及其前面已 flush 的其他 Question 不受影响**
4. except 捕获 IntegrityError 后：
   - 重新 SELECT 同 `(subject_id, name)` 的 Question（rival 方已 commit，可见）
   - 更新 `question_type` / `max_score`
   - 填入 `name_to_id[name] = existing_q.id`
   - 继续下一题
5. 最多重试 1 次（publish 非高频操作，rival 方已落库后不会持续冲突）

**禁止模式**：
- ❌ 循环内 `await db.rollback()`（破坏外层事务完整性，回滚前面已成功 upsert 的其他题目 → 半提交状态 → 违反 INV-002 / INV-005）
- ❌ 外层 try/except 包整个循环（单题失败无法精准 retry，粒度错误）
- ❌ retry 分支内再嵌 retry（无限循环风险）

**测试护栏**：T7 S7 `test_S7_concurrent_upsert_savepoint_preserves_outer_tx` 构造 3 题 `[13,14,15]`，让 `"14"` 触发 IntegrityError，断言外层事务 commit 后 DB 有完整 3 条 Question——错误实现（全局 rollback）会丢失 `"13"` 触发断言失败。

### 6.3 orphan region 处理（pipeline 侧）

```python
# pipeline_router 构建闭包
async def save_answer(region_id, image_path, student_id, ...):
    question_id = region_map.get(region_id)
    if not question_id:
        logger.warning(
            "pipeline_orphan_crop: region_id=%s not in template region_map, skipping",
            region_id,
        )
        progress.warnings.append({
            "file": image_path,
            "message": f"orphan region_id={region_id}",
        })
        return  # skip, do not abort pipeline

    # upsert StudentAnswer (待 §5.5 确认唯一约束后决定 INSERT vs UPSERT)
    db.add(StudentAnswer(
        exam_id=exam_id,
        subject_id=subject_id,
        student_id=student_id,
        question_id=question_id,
        image_path=image_path,
        school_id=school_id,
    ))
    await db.commit()
```

**不中断 pipeline 的理由**：孤儿 region 可能由"老师发布后删题再发布 + B 面 Template 残留"等合法场景产生。应记录不中断，让其他切图继续。

### 6.4 前置校验清单（publish 端点入口）

| 校验 | 失败状态码 | 位置 |
|------|-----------|------|
| Exam 归属当前 school | 404 | router 层 |
| Subject 归属 exam | 400 | router 层 |
| Exam.status ∈ {draft, scanning} | 400 | router 层 |
| HTML 非空 | 400 | router 层 |
| **不加**空 skeleton 校验 | — | 允许老师发布草稿 PDF 看视觉效果 |

### 6.5 失败降级

- PDF 生成失败（Playwright 崩溃）→ 500，DB 无变化
- upsert Question 失败（非约束冲突）→ rollback，exam.status 不变
- upsert Template 失败 → rollback，Question 插入也回滚
- Commit 成功但返回 PDF 前网络断 → 前端重试，所有动作幂等

## §7 测试策略

### 7.1 Backend unit/integration（pytest）

| # | 测试名 | 层级 | 覆盖决策 |
|---|--------|------|---------|
| S2 | `test_upsert_questions_from_skeleton_new_subject` | unit | D1+D3+D5 |
| S3 | `test_upsert_questions_from_skeleton_idempotent` | unit | D4 幂等 |
| S4 | `test_upsert_questions_preserves_orphan` | unit | D4 孤儿保留 |
| S5 | `test_upsert_template_both_sides` | unit | D6 双面 |
| S6 | `test_publish_card_atomic_rollback_on_template_fail` | integration | 事务原子性 |
| S7 | `test_publish_card_concurrent_upsert_retry` | integration | 并发 UniqueConstraint |
| S8 | `test_pipeline_region_map_orphan_crop_skipped` | integration | D7 orphan |
| S9 | `test_e2e_publish_to_marking_visible` | e2e | F003 总体验证 |

### 7.2 Frontend（Vitest + happy-dom）

| # | 测试名 | 覆盖 |
|---|--------|------|
| V1 | `test_render_page_has_data_side_attribute` | F001 render.js |
| V2 | `test_publishCard_single_api_call` | D8 前端路径 |
| V3 | `test_ExamDetailPage_publishCard_signature` | F3 调用签名 |

### 7.3 回归（F003 原症状）

| # | 名称 | 预期 |
|---|------|------|
| R1 | 跑 pipeline 后 `GET /marking/subjects` 返回 questions 非空 | 修复后应见题目列表 |
| R2 | 发布+扫描 367 学生 × 12 题 → 生成 ~4400 条 StudentAnswer（按种子数据规模） | 数量匹配 |
| R3 | 发布后再发布 → 现有 Question 数量不增加，max_score 更新 | 幂等 + 孤儿保留 |

### 7.4 TDD 切片顺序（writing-plans 展开）

1. **Slice A**：F001 render.js data-side 修复 + V1 + 验证 extract_skeleton 输出 side 正确
2. **Slice B**：upsert_questions_from_skeleton + S2/S3/S4（纯函数先行）
3. **Slice C**：upsert_template_both_sides + S5
4. **Slice D**：publish_card_atomic + S6 事务原子性
5. **Slice E**：Question UniqueConstraint migration + S7 并发保护
6. **Slice F**：router.py:1189 接入 publish_service + integration
7. **Slice G**：前端 export.js publishCard 重写 + V2/V3 + ExamDetailPage 适配
8. **Slice H**：pipeline_router region_map + save_answer_fn 闭包 + S8
9. **Slice I**：E2E S9 + 回归 R1/R2/R3

## §8 依赖与顺序

### 8.1 前置依赖（阻塞 B1 启动）

1. **小微排版 v2 视觉验收**（card 模块 WIP）必须先回主线
   - 文件：`frontend/src/card-editor/render.js` / `styles.css` / `answer_parser.py` / `answer_standardizer.py` / `card_layout.py`
   - 完成度 70-80%，归属 `docs/plans/archived/2026-04/2026-04-08-card-xiaowei-layout-v2-handoff.md`
   - **原因**：F001 修复点在 render.js 同文件，不能混入 WIP 的 diff

2. **StudentAnswer 唯一约束调查**（§5.5）— writing-plans 第一个 Task 完成

### 8.2 内部顺序

```
Slice A (F001 render.js)
    ↓
Slice B (upsert_questions 纯函数)
Slice C (upsert_template 纯函数)
    ↓
Slice D (publish_card_atomic 事务)
Slice E (UniqueConstraint migration)
    ↓
Slice F (router publish 接入 service)
    ↓
Slice G (前端 publishCard 重写)
Slice H (pipeline region_map + closure)
    ↓
Slice I (E2E + 回归)
```

A/B/C 可并行，D/E 可并行，F 阻塞 G，H 可并行 F-G，I 是总测试关卡。

### 8.3 批次划分（给 writing-plans 参考）

- **Batch 1**：Slice A + B + C（前置修复 + 纯函数，可独立测试）
- **Batch 2**：Slice D + E + F（publish 事务层 + migration + router 接入）
- **Batch 3**：Slice G + H + I（前端切换 + pipeline 接通 + 端到端验证）

每批次走 code review gate，Batch 3 后整体 reconciliation。

## §9 不在本批次范围

- **F015** analytics/service.py 权限过滤 — 独立批次 B8
- **F014** calendar notification stub dispatch — B7a 独立批次
- **F013** grading LLM 路径统一 — B7b 延后
- **F011/F012** 4 个前端占位页面 — B4a/b/c/d 独立批次
- **F002** CardEditor 双坐标系文档化 — B5 独立批次
- **F004/F007/F010** 已在 T2 快修批次完成（B2/B3a/B6a/B6c）
- **Exam.subject_code / subject_name / max_score / exam_date legacy 字段清理** — 延后独立任务
- **手工 Question 创建入口** `POST /api/v1/questions` 保留不动 — 联考/题库导入未来使用
- **editor_layouts JSON schema 规范化** — 当前 schema 够用，若将来需要增强再议
- **CardEditor "题号编辑 vs 布局编辑" 的 UI 区分** — 本方案不强制分离，老师仍在同一界面编辑，publish 时系统自动区分

## §10 风险与未决问题

| 风险 | 影响 | 缓解 |
|------|------|------|
| card WIP 验收拖延 → B1 启动时间不确定 | B1 计划就绪但执行阻塞 | design.md 先写，plan.md 先就绪，等 WIP 回主线立刻进入执行 |
| StudentAnswer 现有唯一约束未知 | 可能重复写入 | writing-plans 第一个 Task 查 schema，必要时加 migration |
| 现有 5 科种子 Question 的 name 可能存在非纯数字（如"大题1"）| upsert by name 时不命中，创建重复 | writing-plans 阶段抽样查询确认；若有非数字名需要 migration 规整 |
| 老师发布后删题场景的 UI 一致性 | 老师看不到孤儿 Question 但 DB 有 | 接受此设计；未来如需要，单独加"清理孤儿"管理工具 |
| Playwright PDF 生成在事务外 → 事务内任一失败，PDF 已浪费 CPU | 无 DB 后果，只是资源浪费 | 接受；publish 不是高频操作 |
| 并发 publish 超过 1 次 retry 仍失败 | 第二个老师收到 500 | 可接受；publish 是手工操作，用户重试即可 |

## §11 验收标准

B1 所有批次完成后，以下场景必须通过：

1. 老师在 CardEditor 编辑数学科目布局（12 选择题 + 6 解答题）
2. 点"发布答题卡"→ PDF 下载 + Question 表新增 18 条记录 + Template 表新增 A/B 两条
3. 用户上传扫描图 + 启动 pipeline → 2202 张切图落盘 + StudentAnswer 表新增 ~4400 条
4. `GET /marking/subjects?exam_id=...` → 数学科目 questions 非空 + total_answers > 0
5. 进入人工阅卷界面 → 能看到每道题的学生答卷，可打分
6. 启动 AI 阅卷任务 → Rubric 就绪前提下跑通（worker 不再 trivially completed）
7. 重复 publish 相同布局 → Question/Template 数量不变，max_score 若改动则更新
8. 删除布局中的某题 → 再 publish → DB 中原 Question 保留（孤儿），不影响当前阅卷
9. 两个浏览器同时点 publish → 两次都成功（可能一次 retry），最终 Question 表无重复

## §12 相关文档

- 探索测试根因深挖：`docs/plans/archived/2026-04/2026-04-11-exploration-notes.md §D2 §D6`
- T2 快修 state（B2/B3a/B6a/B6c）：commit `d5cedb4`, `bbeeb8f`, `2ce070b`, `75922c7`
- card 模块 WIP 归属：`docs/plans/archived/2026-04/2026-04-08-card-xiaowei-layout-v2-handoff.md`
- 6 批拆单 + 7 批调整：`docs/plans/archived/2026-04/2026-04-11-exploration-notes.md §Round 3 汇总`
- 架构规范（review-templates）：`~/.claude/rules-t3/review-templates.md`

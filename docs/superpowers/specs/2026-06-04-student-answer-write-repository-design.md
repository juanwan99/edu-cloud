# StudentAnswer 统一写入入口（架构收敛）设计

> 日期：2026-06-04
> 性质：T3+ 结构性重构（根因治理）
> 适用项目：`/home/ops/projects/edu-cloud`
> 上游：吸收 GPT R1/R2 审查后，用户要求「以后不能再出现」跨科目/归属链类漏洞 → 从「集中化工具 + 自觉调用」升级为「唯一写入门 + 机器强制」

## 1. 背景与根因

### 1.1 问题
`StudentAnswer` 是阅卷/统计的核心数据。它的写入点**散布在 5 个文件、共 11 处**，每处都靠开发者自己记得校验「school→exam→subject→question」归属链。漏一处就出洞——本次 GPT 审查就在 `compat_router`（fail-open）和 `pipeline_router`（缺 subject_id 过滤）各发现一处。

### 1.2 根因
**写入路径分散 + 校验靠自觉**。即使已把校验集中成 `core/ownership.py`，仍没有任何机制强制新代码调用它。靠自觉 = 迟早再漏。

### 1.3 写入点清单（证据）

| # | 位置 | question_id 来源 | 当前归属校验 | 可选字段 |
|---|------|-----------------|-------------|---------|
| 1 | `modules/scan/router.py:67` upload_single | 外部 HTTP | `_verify_ownership`（已修）| image_path |
| 2 | `modules/scan/router.py:143` upload_batch | 外部 HTTP | `verify_questions_belong_to_subject`（已修）| image_path |
| 3 | `modules/scan/router.py:330` objective absent | 该 subject 全部题 | 自产（按 subject 查）| score=0, is_absent |
| 4 | `modules/scan/router.py:376` objective normal | 外部 HTTP | subject_id 条件（已修）| detected_answer, score, is_anomaly, fill_ratios |
| 5 | `api/compat_router.py:308` upload | 外部 HTTP | 完整 exam→subject→question 三段查（已有）| image_path, question_type |
| 6 | `api/compat_router.py:376` objective absent | 该 subject 全部题 | 自产 | score=0, is_absent |
| 7 | `api/compat_router.py:409` objective normal | 外部 HTTP | subject_id 条件 + 404（已修）| detected_answer, score, is_anomaly, fill_ratios |
| 8 | `modules/scan/pipeline_router.py:219` save_answer 闭包 | region_map 映射（`r["question_id"]`）| **⚠ region_map 未校验 subject 归属**——主观题与 F-002 同类隐患，收敛时修复 | image_path |
| 9 | `modules/scan/pipeline_router.py:287` save_objective 闭包 | questions_by_group | subject_id 过滤（已修）| detected_answer, score, fill_ratios, is_anomaly |
| 10 | `modules/marking/importer.py:131` | 自建 question（按 subject 派生）| 自产自销 | image_path |
| 11 | `modules/exam_import/service.py:482` | 自建/查 question（按 subject 派生）| 自产自销 | score, detected_answer, is_absent |

> 排除：`data/seed_demo.py:343`（种子数据，非生产路径）、`modules/scan/models.py:21`（模型定义）。

字段维度收敛：5 个必填（exam_id, subject_id, student_id, question_id, school_id）+ 一组可选（image_path / detected_answer / score / is_absent / is_anomaly / fill_ratios / question_type）。一个统一接口可覆盖全部。

## 2. 目标与非目标

### 2.1 目标
1. 所有 `StudentAnswer` 写入收敛到**唯一 repository**，归属一致性校验焊在内部，物理上绕不过去。
2. 静态守卫断言「代码库零裸写 `StudentAnswer(`」，新增裸写 → CI 红。
3. 不破坏现有任何写入功能（含 pipeline 独立 session、批量事务、导入）。

### 2.2 非目标
- 不改判分逻辑（score 由调用方算好传入）。
- 不在写入时做 image_path 路径安全（读取时校验，Phase 2 已解决）。
- 不处理历史脏数据（用户确认为测试数据，不管）。
- 不重构无关代码。

## 3. 架构

### 3.1 位置
新增 `src/edu_cloud/core/student_answer_repository.py`，与 `core/ownership.py` 同层（跨模块共享基础设施；写入消费方横跨 scan/compat/marking/exam_import 四个模块，放 core/ 而非任一模块内）。依赖 `core/ownership.py`。

### 3.2 对外接口（仅两个入口）

```python
async def create_answer_checked(
    db: AsyncSession, *,
    exam_id: str, subject_id: str, student_id: str,
    question_id: str, school_id: str,
    image_path: str | None = None,
    detected_answer: str | None = None,
    score: float | None = None,
    is_absent: bool = False,
    is_anomaly: bool = False,
    fill_ratios: dict | None = None,
    question_type: str | None = None,
) -> StudentAnswer:
    """接受外部传入 question_id 的单条写入。
    内部强制 verify_exam_subject_question_chain（1 次 DB 查），
    校验通过后构造 StudentAnswer 并 db.add()，返回实例（不 commit）。
    用于：写入点 1, 4, 5, 7。
    """


async def create_answers_for_subject(
    db: AsyncSession, *,
    exam_id: str, subject_id: str, school_id: str,
    rows: list[StudentAnswerRow],
) -> list[StudentAnswer]:
    """批量写入。调用方已持有从本 subject 派生的 Question（或已校验的 question_id）。
    内部对每行内存断言 row.question.subject_id == subject_id（零额外查询），
    断言通过后逐条 db.add()，返回实例列表（不 commit）。
    用于：写入点 2, 3, 6, 8, 9, 10, 11（批量 / 自产自销 / 缺考）。
    """
```

`StudentAnswerRow` 为一个轻量 dataclass，携带 `question`（Question **对象**，提供 subject_id 断言依据）+ student_id + 可选字段。

**关键约束：批量入口的 row 必须携带 Question 对象**（不能只给 question_id 字符串），否则无法做内存断言。这对 pipeline 两个闭包提出改造要求：

- `build_pipeline_save_objective_fn`：已持有 `questions_by_group`（Question 派生 dict），直接满足。
- `build_pipeline_save_answer_fn`（写入点 8，主观题）：当前 `region_map` 只把 `region_id → question_id` 字符串映射，**未校验这些 question_id 属于本 subject**。改造时在闭包**装配阶段**用 `verify_questions_belong_to_subject` 把 region 的 question_id 批量校验并解析成 `region_id → Question` 缓存，闭包内查缓存得到 Question 对象。此举**顺带消除写入点 8 主观题的跨 subject 隐患**（与 F-002 同类，本设计阶段新发现，GPT 审查未覆盖）。

> 设计取舍：被否方案——(a) 单一 `create()` 函数 + `verified: bool` 旗标：旗标语义易误用，且批量场景仍逐条查库性能差；(b) `StudentAnswerRepository` 类：项目现有 `ownership.py`/`path_safety.py` 均为模块级函数风格，引入类不一致。最终选「两个语义明确的函数」：一个对应「外部输入 → 查库校验」，一个对应「已持有 Question → 内存断言」，两条路径都不可能写入归属不一致的数据。

### 3.3 数据流
```
端点/worker
  → 算好 score/字段 + 确定 question 来源
  → create_answer_checked(...) 或 create_answers_for_subject(...)
      → [入口内] 归属一致性校验（查库 or 内存断言）
      → 校验失败 → HTTPException(404)（外部输入）/ ValueError（内部断言违反，编程错误）
      → 校验通过 → db.add(StudentAnswer(...))
  → 调用方负责 db.commit()（请求 / 独立 session / 批量）
```

### 3.4 错误处理
- `create_answer_checked` 归属链不匹配 → `HTTPException(404, ...)`（沿用 ownership.py 现有语义，外部输入的合法拒绝）。
- `create_answers_for_subject` 内存断言失败（question.subject_id != subject_id）→ `ValueError`（这是调用方编程错误，不是用户输入问题，应在测试期暴露而非运行期 404）。
- 唯一约束冲突（重复答案）→ repository **不**吞 `IntegrityError`，交由调用方按现有逻辑处理（各端点对重复的处理不同：409 / skip / rollback）。

## 4. 静态守卫（收敛的机器验收）

新增 `tests/governance/test_student_answer_write_guard.py`，复用 `test_tenant_static.py` 范式：
- 扫描 `src/edu_cloud/` 全部 `.py`。
- 正则匹配 `StudentAnswer(` 直接构造。
- ALLOWLIST 仅含：`core/student_answer_repository.py`（唯一合法构造点）、`modules/scan/models.py`（模型定义）、`data/seed_demo.py`（种子）。
- 断言：allowlist 外零匹配。

迁移完成后此测试即「零裸写」的持续证明；任何新写入点裸写 → 测试红 → CI 拦截。

## 5. 迁移计划（11 点分批）

子代理隔离执行（worktree），每批独立测试验证后再下一批：

| 批次 | 文件 | 写入点 | 验证测试 |
|------|------|--------|---------|
| B1 | `modules/scan/router.py` | 1,2,3,4 | test_scan_*, test_student_answer_ownership_chain |
| B2 | `api/compat_router.py` | 5,6,7 | test_compat*, test_student_answer_ownership_chain |
| B3 | `modules/scan/pipeline_router.py` | 8,9 | test_scan_pipeline_api, test_pipeline_*, test_services_exam/test_pipeline_objective；**新增：主观题 region 跨 subject 被拒测试**（覆盖写入点 8 新发现隐患）|
| B4 | `modules/marking/importer.py` | 10 | test_marking_import_isolation, test_marking |
| B5 | `modules/exam_import/service.py` | 11 | test_exam_import* |
| B6 | 启用静态守卫 | — | test_student_answer_write_guard |

每批结束跑对应模块测试；全部迁移后跑后端全量回归 + 启用静态守卫。

## 6. 影响面
- **新增**：`core/student_answer_repository.py`、`tests/governance/test_student_answer_write_guard.py`
- **修改**：5 个写入点文件
- **风险点**：pipeline 独立 session 兼容、批量事务边界、导入功能回归 → 每批迁移后全量跑该模块测试兜底；批量入口设计为不 commit，由调用方维持原事务语义
- **不碰**：判分逻辑、路径安全层、模型定义、历史数据

## 7. 测试策略
- 每个写入点迁移后，其原有测试必须仍通过（行为不变，仅写入路径改道）。
- repository 单元测试：`create_answer_checked` 跨科目 → 404；`create_answers_for_subject` 断言违反 → ValueError；正常路径 → 正确构造。
- 静态守卫测试：零裸写断言。
- 全量后端回归：确认无跨模块连带破坏。

## 8. 验收标准
1. 11 个写入点全部改道 repository，无一裸写。
2. 静态守卫测试通过（零裸写）。
3. 全量后端测试通过（基线 2314 passed 量级，无新增 fail）。
4. codex-review plan + 每批 code review + 集成 review 全 PASS。

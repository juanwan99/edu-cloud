<!-- legacy-format -->
# Phase 4 · card 模块子目录化方案

> 状态：**方案待批准**（本文档仅规划，不含任何代码改动）
> 创建时间：2026-04-17（UTC+8）
> 前置依赖：Phase 2 Task 1 `docs/arch/module-template.md`（§"反模式清单" 明示"平铺超过 10 文件为反模式"）
> 实施限制：需**独立 session**走 T3 完整 SVD 4-check，本 session 不启动实施

## 1. 现状

### 1.1 文件清点（2026-04-17 直接 `ls src/edu_cloud/modules/card/*.py` verify）

`modules/card/` 目录共 18 个 `.py` 文件，其中 `__init__.py` 空壳占位，**17 业务文件**：

| # | 文件 | 大小 (B) | 职责（来自文件 docstring） |
|---|------|---------|---------------------------|
| 1 | `answer_parser.py` | 3876 | 答案文档解析器 — 从 `.docx` 提取结构化题目答案数据 |
| 2 | `answer_standardizer.py` | 14370 | LLM 答案标准化：正则粗解析/PDF 图片 → 结构化题目信息 |
| 3 | `barcode_gen.py` | 4186 | 条码贴纸 PDF 生成器 |
| 4 | `confidence.py` | 664 | 后端置信度计算（始终用规则，不信赖 LLM 返回值） |
| 5 | `defaults.py` | 10317 | 内置默认编辑器布局模板（`card_design_config.json["_layout"]` 迁移） |
| 6 | `export.py` | 3819 | 答题卡骨架 → paper-seg 兼容的切割模板 JSON |
| 7 | `html_export.py` | 5203 | HTML 答题卡 → PDF 导出 + skeleton JSON 提取（playwright 线程池） |
| 8 | `layout.py` | 18952 | 答题卡布局引擎（坐标工具 + 纸张定义 + 区域计算） |
| 9 | `models.py` | 1437 | Card ORM（`Template` + `CardSkeleton`，从 exam-ai 提取） |
| 10 | `publish_service.py` | 9346 | F003 B1 publish 一站式原子操作的业务逻辑 |
| 11 | `renderer.py` | 47462 | 答题卡 PDF 渲染器（reportlab，TQL 像素级复刻 v2） |
| 12 | `router.py` | 44722 | 答题卡生成 + 条码贴纸 + 骨架管理 API（23 端点） |
| 13 | `subject_defaults.py` | 26121 | 各学科答题卡默认编辑器布局（TQL 模板代码化） |
| 14 | `template_library.py` | 7216 | 内置模板库（从 `data/templates/` 加载 JSON） |
| 15 | `template_router.py` | 3688 | `Template` 路由（前缀 `/api/v1/templates`，从 exam-ai 迁入） |
| 16 | `tpl_parser.py` | 9524 | 解析月小二 `.tpl` 模板文件为 `CardSkeleton` 数据 |
| 17 | `word_parser.py` | 9591 | Word 答案模板：生成骨架 + 解析答案 + 文字量→权重 |

### 1.2 import 影响面（2026-04-17 Bash grep verify）

- 命中数：**135 处** `from edu_cloud.modules.card` import（前序交接卡 §5.3 原估 "50+" 已据实修正为 135）
- 分布文件数：**32 个**（`src/` + `tests/`）
- 前序交接卡 §2.3 "16 业务文件" 表述据实修正为 **17 业务文件**

### 1.3 触发重构的理由

- `docs/arch/module-template.md` 定义"B 重功能 HTTP 型"模块上限 ~10 文件；`card` 以 17 文件属**反模式**
- `renderer.py` 47KB + `router.py` 44KB + `subject_defaults.py` 26KB + `layout.py` 19KB 四个大文件共 136KB，跨功能耦合（渲染 / 路由 / 默认模板 / 布局）
- 新增功能（如新学科 TQL、新导出格式）继续平铺将推向 20+ 文件

## 2. 子目录方案（建议）

按"功能域归类 + 顶层保留跨域服务"原则，拆分为 4 个子目录：

```
src/edu_cloud/modules/card/
├── __init__.py
├── models.py              # 顶层保留（跨子域共享 ORM：Template/CardSkeleton）
├── router.py              # 顶层保留（主路由 /api/v1/card/*，23 端点）
├── template_router.py     # 顶层保留（子路由 /api/v1/templates，跨子域）
├── publish_service.py     # 顶层保留（publish 原子操作，跨 rendering/export/parser）
├── rendering/
│   ├── __init__.py
│   ├── renderer.py           # 47KB 主渲染器
│   ├── layout.py             # 19KB 布局引擎
│   ├── tpl_parser.py         # 9KB  .tpl 解析
│   ├── subject_defaults.py   # 26KB 学科默认布局
│   └── defaults.py           # 10KB 编辑器默认
├── export/
│   ├── __init__.py
│   ├── export.py             # paper-seg 切割模板 JSON
│   ├── html_export.py        # HTML → PDF
│   └── barcode_gen.py        # 条码贴纸
├── parser/
│   ├── __init__.py
│   ├── answer_parser.py      # .docx 答案解析
│   ├── answer_standardizer.py # LLM 标准化
│   ├── word_parser.py        # Word 答案模板
│   └── confidence.py         # 置信度计算
└── template/
    ├── __init__.py
    └── template_library.py   # 内置模板库
```

- 顶层 4 文件 + 4 子目录 × (5 + 3 + 4 + 1) 文件 = **17 业务文件 不变**
- 子目录 `template/` 仅 1 文件略薄，保留一致性（后续模板管理逻辑从 `template_router.py` 下沉时可扩展）

## 3. import 迁移策略（用户二选一）

### 3.1 方案 A · 全部硬迁移（135 处 import 一次性改）

- **做法**：每个外部 `from edu_cloud.modules.card.renderer import X` 改为 `from edu_cloud.modules.card.rendering.renderer import X`，用 AST 重写（不用 sed 避免误改字符串字面量）
- **优点**：
  - 彻底干净，无遗留 stub 债务
  - 与 2026-04-17 ORM 搬迁（`core/models/llm_slot.py` → `models/llm_slot.py`，10 处 import 批量更新）策略一致
  - 与 `docs/arch/orm-placement.md` "Task 22 stubs 容忍保留，**禁止新增**"规则一致
- **缺点**：
  - 一次改 135 处，跨 32 文件，回滚集中（需 `git tag svd-pre-card-subdir`）
  - T3 重构要求完整 4-check（inventory + caller_check + semantic regression + pytest 多次回归）
- **推荐度**：★★★★☆

### 3.2 方案 B · 加 re-export stub（外部代码零改动）

- **做法**：`modules/card/__init__.py` 顶层 re-export（如 `from .rendering.renderer import *`），外部 `from edu_cloud.modules.card.renderer import X` 仍可用
- **优点**：
  - 影响面缩到 `modules/card/` 内部
  - 零外部回归风险
- **缺点**：
  - 与 `docs/arch/module-template.md` + `docs/arch/orm-placement.md` 明文"**禁止新增 stub**"规则**直接冲突**
  - 4 个 `子目录/__init__.py` 实质做 stub 工作，为 Task 22 遗留 ORM stubs 债务开口子
  - 用户 2026-04-17 明确"不留隐患"指令与此方案矛盾
- **推荐度**：★★☆☆☆

### 3.3 规划窗口推荐

**方案 A**。依据：
1. 与用户"不留隐患"原则一致（前序交接卡 §6.1 记录）
2. 与前序 ORM 搬迁"等级 2 全量硬迁"做法一致（不新增 stub，只容忍历史 Task 22）
3. 一次性 T3 成本虽高但**回报集中**，无长尾维护

**最终决策权在用户**（§6 用户决策点）。

## 4. 实施步骤（批准后**另起 session** 执行）

### 4.1 前置 Gate（本 session 不做，另 session 启动时 verify）

1. 用户批准方案 A 或 B
2. 用户确认 Sunset/退役窗口不冲突（card 子目录化与 Phase 5 compat 退役并行不冲突，已 verify）
3. `git status` clean 或用户认可未 commit 改动入本次 T3 范围

### 4.2 执行步骤

| # | 步骤 | 说明 | 验收 |
|---|------|------|------|
| 0 | `git tag svd-pre-card-subdir` | T3 SVD 起点锚 | tag 创建成功 |
| 1 | 创建 4 子目录 + `__init__.py` × 4 | 空 `__init__.py`，不加 re-export（方案 A） | 目录结构与 §2 对齐 |
| 2 | `git mv` 12 文件入子目录 | 保留 git 历史（不是 rm + add） | `ls modules/card/` 仅剩 5 顶层文件 |
| 3 | AST 重写 135 处 import | 按子目录分批（rendering → export → parser → template） | Grep `from edu_cloud.modules.card.renderer` → 0 命中（未加子目录前缀者清零） |
| 4 | 单元测试逐目录验证 | 按子目录 Smoke：`pytest tests/test_card/*` + 模块间 import smoke | 每子目录单独 PASS |
| 5 | 全量 pytest 回归 | 必须 1935/0/23 或与 Phase 5 后基线一致 | 零 failed |
| 6 | `caller_check_hook.py` 自动检测 | 删除定义的 caller 残留（方案 A 不删定义只搬位置，应零命中） | 零残留 |
| 7 | SVD 4-check 完整流程 | inventory + marker check + 语义回归 + 测试 | 四项齐全 |

### 4.3 T 级别与 SVD

- **T 级别**：**T3**（跨模块大规模 import 变动 + 文件搬迁）
- **SVD**：完整 4-check（见 `~/.claude/rules/svd-rules.md`）
- **预计时长**：2-4 小时聚焦工作 + 多次全量 pytest 回归
- **实施者**：独立 session（本卡规划窗口不具备持续 T3 监督能力）

## 5. 风险与回滚

| 风险 | 场景 | 缓解 |
|------|------|------|
| R1 | AST 重写误改字符串字面量（如 docstring / 日志 msg 内 "edu_cloud.modules.card" 字符串） | 用 `libcst`/`ast` 改 import AST 节点，不用 `sed`；改后 `grep -rn "edu_cloud.modules.card" src/ tests/` 对照 import 视觉校对 |
| R2 | 子目录文件间循环依赖（`rendering/layout.py` ↔ `rendering/renderer.py` 等） | 步骤 1 后立即 `python -c "import edu_cloud.modules.card.rendering"` smoke test；循环 → 拆 interface 到顶层 |
| R3 | 大文件搬迁后 git history 断裂 | 强制 `git mv`（不是 `rm + add`），PR 中 reviewer 用 `git log --follow` verify |
| R4 | tests/ 中 monkeypatch / patch 路径失效（如 `@patch("edu_cloud.modules.card.renderer.X")`） | 步骤 3 的 AST 重写必须覆盖 `@patch("...")` 字符串参数（`unittest.mock` 字符串路径非 import 语句，单独处理） |
| R5 | FastAPI router 挂载失效（`template_router` 顶层保留但内部 import 子目录类） | 步骤 4 单目录 smoke 先验；步骤 5 全量 pytest 覆盖 `test_api_exam/` |

**回滚**：`git reset --hard svd-pre-card-subdir` + `git clean -fd src/edu_cloud/modules/card/`。

## 6. 用户决策点

待用户在启动 Phase 4 实施 session 前明确：

| # | 决策项 | 选项 | 规划窗口建议 |
|---|-------|------|-------------|
| D1 | 迁移策略 | A（硬迁移 135 处） / B（re-export stub） | **A** |
| D2 | 本次范围 | 仅 card / card + ai/models（同步上浮） | **仅 card**（ai/models 前序妥协保留，不同步） |
| D3 | 顶层保留 | models/router/template_router/publish_service 4 文件 / 仅 models + router 2 文件 | **4 文件**（跨子域服务集中顶层） |
| D4 | `template/` 子目录 | 保留（仅 1 文件）/ 合并入顶层 | **保留**（后续 `template_router.py` 下沉扩展用） |
| D5 | 实施窗口 | 与 Phase 5 T+30 前 / T+30 后 | **T+30 前**（paper-seg 迁移尚未开始，card 变动不影响 compat 层） |

### 6.1 用户决策记录

2026-04-17 用户"按推荐走"裁决（技术债清理执行 session 规划窗口收尾）：

- ✅ D1 = **方案 A**（硬迁移 135 处，无 stub）
- ✅ D2 = **仅 card**（`ai/models.py` 保留不同步上浮）
- ✅ D3 = **4 文件顶层保留**（`models/router/template_router/publish_service`）
- ✅ D4 = **保留 `template/` 子目录**（后续扩展用）
- ✅ D5 = **Phase 5 T+30 前**实施（建议窗口 2026-05-02 ~ 2026-06-01）

上述决策锁定，实施 session 按此启动，**偏离需重走决策流程**。

---

**变更记录**：

| 日期 | 变更 | 作者 |
|------|------|------|
| 2026-04-17 | 初版（Phase 4 方案规划，执行窗口） | 技术债清理执行窗口 |

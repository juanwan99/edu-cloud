<!-- legacy-format -->
# W1 · Phase 4 card 模块子目录化 · 执行窗口交接卡

> 类型：T1 并行执行窗口（4 窗口之一）
> 创建：2026-04-17 规划窗口
> 对应方案：`docs/plans/2026-04-17-card-subdir-plan.md`（D1-D5 决策已锁定）
> 起点 git HEAD：`6f3dc81`（commit 拆分后）
> 工作分支：**`feat/card-subdir`**（独立分支，禁止直接 push master）

## 1. 范围定义（红线必读）

### 1.1 可改文件（白名单）
- `src/edu_cloud/modules/card/` — 16 业务文件移动到 4 子目录
- 32 个 import 调用方文件（Grep `from edu_cloud.modules.card`）：
  - `src/edu_cloud/{ai/tools/card_layout,api/{app,compat_router},models/card,modules/scan/pipeline_router}.py`
  - `tests/test_api_exam/test_{card_publish,pipeline_router_wiring,pipeline_save_answer}.py`
  - `tests/test_api/test_compat.py`
  - `tests/test_exam_misc/test_{answer_standardizer,confidence,integration,template_library}.py`
  - `tests/test_services_exam/test_barcode_gen.py`
  - 其他通过 `Grep "from edu_cloud.modules.card" src/ tests/ -l` 列出

### 1.2 红线禁区（绝对不能碰，违反即停）
- `src/edu_cloud/modules/conduct/*` — W4 范围
- `src/edu_cloud/modules/knowledge_tree/*` — W2 间接依赖
- `frontend/*` — W2 范围
- `frontend-nuxt/*` — W3 范围
- `src/edu_cloud/api/compat_router.py` 的 deprecation 逻辑 — Phase 5 已就位，仅可改 import 路径
- `docs/arch/`、`docs/plans/` — 不动（除自己输出）
- `CLAUDE.md` — 仅本窗口范围内的 import 路径同步可改（card 模块结构）

## 2. 实施步骤（按 card-subdir-plan §4 严格执行）

```bash
# Step 0: 起分支 + tag 基线
cd /home/ops/projects/edu-cloud
git checkout -b feat/card-subdir
git tag svd-pre-card-subdir HEAD

# Step 1: 创建 4 子目录 + __init__.py + 移动 12 文件
mkdir -p src/edu_cloud/modules/card/{rendering,export,parser,template}
git mv src/edu_cloud/modules/card/{renderer,layout,tpl_parser,subject_defaults,defaults}.py src/edu_cloud/modules/card/rendering/
git mv src/edu_cloud/modules/card/{export,html_export,barcode_gen}.py src/edu_cloud/modules/card/export/
git mv src/edu_cloud/modules/card/{answer_parser,answer_standardizer,word_parser,confidence}.py src/edu_cloud/modules/card/parser/
git mv src/edu_cloud/modules/card/template_library.py src/edu_cloud/modules/card/template/
# 创建 __init__.py
for d in rendering export parser template; do touch src/edu_cloud/modules/card/$d/__init__.py; done

# Step 2: AST 重写 32 处 import（不用 sed，避免误改字符串字面量）
# 用 Python 脚本扫 src/ tests/ 用 ast 模块改 ImportFrom node
# 见 card-subdir-plan §5 风险 1

# Step 3: 模块内 import smoke test
.venv/bin/python -c "from edu_cloud.modules.card import rendering, export, parser, template; print('OK')"

# Step 4: card 模块测试子集
.venv/bin/python -m pytest tests/test_api_exam/test_card_publish.py tests/test_api_exam/test_pipeline_router_wiring.py tests/test_api_exam/test_pipeline_save_answer.py tests/test_exam_misc/ tests/test_services_exam/test_barcode_gen.py tests/test_api/test_compat.py --tb=short -q

# Step 5: caller_check_hook verify (hook 自动检测删除函数定义)

# Step 6: SVD 4-check（git tag + inventory + 4-check）

# Step 7: CLAUDE.md 同步 card 模块结构章节（如有需要）

# Step 8: commit 到 feat/card-subdir 分支（多次小 commit OK）
```

## 3. 验收契约
- card/ 目录结构：4 子目录 + 4 顶层文件（__init__.py / models.py / router.py / template_router.py / publish_service.py）
- 32 处 import 全部更新（Grep `from edu_cloud.modules.card.X` X 必须是 rendering/export/parser/template 之一或顶层）
- card 模块测试子集 100% PASS
- 不引入新依赖
- 不动红线文件

## 4. 测试隔离（不跑全量，留给 T2 汇总）

```bash
# 仅跑 card 相关测试
.venv/bin/python -m pytest tests/test_api_exam/ tests/test_exam_misc/ tests/test_services_exam/test_barcode_gen.py tests/test_api/test_compat.py --tb=short -q
# 预期 ~100 测试 PASS
```

**禁止**：跑 `python -m pytest`（全量）— 会与其他并行窗口的 sqlite/资源争抢。

## 5. checkpoint 输出格式（完成时）

```
【W1 card 子目录化 · 待汇总】
- 工作分支：feat/card-subdir
- 最终 commit hash：<sha>
- 改动统计：modules/card/ 移动 12 文件，32 文件 import 更新（实际 N 处行）
- card 测试子集：N passed / 0 failed
- SVD 4-check：通过/失败
- CLAUDE.md 同步：是/否（同步内容）
- 异常/已知问题：<列出，无则"无">
- 等 T2 汇总窗口 merge
```

## 6. 与其他窗口的同步点
- **零文件冲突**（W2/W3/W4 的红线均互斥）
- **不直接 commit master** — 完成在 feat/card-subdir
- **不 push origin** — T2 汇总窗口统一处理

## 7. 第一步指令（执行窗口接到本卡后）

```bash
cd /home/ops/projects/edu-cloud
cat docs/plans/2026-04-17-card-subdir-plan.md     # 必读方案 + D1-D5 决策
cat docs/plans/2026-04-17-w1-card-subdir-exec-handoff.md  # 必读本卡
git log --oneline -5                                # 应见 6f3dc81 等 5 commit
git status                                          # 应空
git checkout -b feat/card-subdir                    # 起分支
git tag svd-pre-card-subdir                         # 基线 tag
# 报告："已起 feat/card-subdir 分支，tag svd-pre-card-subdir 已建，准备 Step 1"
```

等用户确认进入实施后才开 Step 1。

## 8. 兜底
- 任何 32 处 import 改不全 → 立即 git reset --hard svd-pre-card-subdir 回滚
- caller_check_hook 报错 → 按 hook 提示修，不绕过
- 同子项被纠正 ≥3 次 → 主动放弃，输出"超出能力边界"声明

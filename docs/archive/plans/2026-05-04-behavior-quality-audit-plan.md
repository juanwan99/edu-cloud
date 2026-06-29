<!-- legacy-format -->
# Claude 开发行为质量深度审计计划

> 审计窗口: 2026-04-28 → 2026-05-04 (7 天)
> 审计模式: GPT 主导 + Claude 补充，双模型独立取证后收敛
> 触发原因: meta-v2 + Guardian 上线后首次周期复盘，用户要求评估 AI 实际开发行为质量
> 性质: 审计计划（非代码实现计划），无测试基线

## 背景

元能力体系 + 守护者系统在 04-28 完成 Phase 1 部署。已有一轮 hook 指标评估（事件分布、block 率），但只覆盖了"管道运行质量"，未覆盖"管道保护的对象——AI 开发行为质量"。

用户是个人开发者，高度依赖体系门控。核心诉求：这 7 天 Claude 干活干得怎么样？哪里进步了、哪里退步了、哪里还有大的提升空间？

## 审计维度 × 证据源 × 方法

### D1. 宏观决策质量

| 子维度 | 证据源 | 审计方法 |
|---|---|---|
| D1.1 指令理解 | git log commit messages + hook blocks (session_guard) | 抽查 5+ 个多步任务的 commit 链，看是否跳步/曲解 |
| D1.2 全局 vs 局部 | git diff 大变更 + plan 文件 + L017 相关 hook events | 检查是否有 GPT 建议覆盖全局设计的案例 |
| D1.3 资产盘点 | git log --diff-filter=A (新建文件) + parallel_dir_guard blocks | 检查新建文件是否在已有模块目录下，有无平行系统 |
| D1.4 规划纪律 | plan/design 文件列表 + session_guard tier 记录 + gates.json | T3+ 任务是否走了 plan→review→execute？ |

### D2. 微观执行质量

| 子维度 | 证据源 | 审计方法 |
|---|---|---|
| D2.1 执行漂移 | git diff --stat per commit + trajectory_collector warns | 检查 commit 改动范围是否与 commit message 一致 |
| D2.2 技术债 | grep 废代码模式 (commented-out, TODO, unused import) | 窗口期新增文件抽样检查 |
| D2.3 完成诚实度 | completion_guard blocks + truth-status hash 对比 | prove_gate 509 次 block 后最终状态：source→build 是否对齐？ |
| D2.4 证据纪律 | plan 文件中 Evidence Block 检查 + decision-evidence 规则符合度 | T3+ plan 是否有 file:line 引用？ |

### D3. 工程纪律

| 子维度 | 证据源 | 审计方法 |
|---|---|---|
| D3.1 Git 体系 | git log --all --graph + branch 拓扑 + merge 历史 | 分支是否干净？有无悬挂分支？merge 是否正确？ |
| D3.2 Commit 质量 | git log --format + diff-stat | 抽样 10+ commit：message 是否准确？改动是否原子？ |
| D3.3 ORM-DB 一致性 | db_doctor 当前结果 + 本周 drift 事故复盘 | 这次 500 事故的完整因果链 |
| D3.4 并行版本 | git log --diff-filter=A + 目录结构审查 | 有无在错误目录创建新文件？ |
| D3.5 回归控制 | truth-status + API 500 检查 + 测试基线变化 | pytest 基线从 2246p/33f 变成了什么？ |

### D4. 行为模式分析

| 子维度 | 证据源 | 审计方法 |
|---|---|---|
| D4.1 scope 控制 | git diff 大 commit + write_guard blocks | 有无"修 A 顺手改了 B"？ |
| D4.2 自审能力 | completion_guard blocks reason 分析 | block 后 Claude 的响应模式：立即修正 vs 绕过？ |
| D4.3 纠正响应 | hook event 中 session_guard blocks + 用户纠正后的 commit 模式 | 纠正后是停下调查还是继续原路线？ |
| D4.4 能力边界 | 同一文件重复修改次数 (trajectory_collector) | 有无反复改同一个文件 3+ 次（打地鼠模式）？ |

## 执行步骤

### Phase 1: 数据采集（Claude 执行）

```
1.1 git log --oneline --all --graph --since="2026-04-28" → 完整 commit 图
1.2 git log --format="%h %ai %s" --since="2026-04-28" → commit 时间线
1.3 git log --diff-filter=A --name-only --since="2026-04-28" → 新建文件清单
1.4 git diff --stat HEAD~50..HEAD → 近 50 commit 改动范围
1.5 hook-events.jsonl 按维度聚合（部分已完成，见本会话前半段）
1.6 trajectory_collector 打地鼠检测记录
1.7 truth-status 当前快照（已完成）
1.8 pytest 基线当前值
1.9 branch 拓扑 + 悬挂分支检查
1.10 gates.json 全量扫描（格式 + 状态）
```

### Phase 2: GPT 独立审计（GPT 主导）

GPT 拿到 Phase 1 数据包后，按 D1-D4 四个维度独立分析。GPT 有完整文件系统访问权，可以自主读取 git log、代码文件、hook 日志。

审计要求：
- 每个 finding 必须有 commit hash / file:line / 数据引用
- 每个维度给出 1-5 分评分 + 关键 finding
- 区分"体系问题"（hook/guard 设计缺陷）和"行为问题"（Claude 执行质量）
- 最终给出"作为个人开发者的质量门控，整体打几分"

### Phase 3: Claude 补充 + 收敛

Claude 对 GPT 的 finding 做事实核查，补充 GPT 可能遗漏的视角，双方收敛产出最终报告。

## 产出物

`docs/meta-reviews/2026-05-04-behavior-quality-audit.md`

结构：
1. 执行摘要（一页纸）
2. D1-D4 逐维度评分 + finding
3. 优化 vs 劣化对比表
4. Top 5 提升建议（按 ROI 排序）
5. 附录：原始数据

## 约束

- 所有结论必须有实证，禁止凭印象
- GPT 是审计主导方，Claude 是数据采集 + 补充
- 不在本计划中执行修复，只产出诊断报告
- 审计范围限定在 04-28 → 05-04 窗口

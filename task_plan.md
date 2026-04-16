# Task Plan: A4 答题卡渲染与导出根因诊断

## Goal
基于代码事实梳理 edu-cloud 答题卡编辑器中 A4 双面渲染与 PDF 导出的完整数据流，定位已知问题的精确根因并给出架构修复方向。

## Current Phase
Phase 1

## Phases
### Phase 1: 范围确认与文件读取
- [ ] 逐个读取用户指定文件
- [ ] 建立后端到前端的数据流
- [ ] 记录关键发现到 findings.md
- **Status:** in_progress

### Phase 2: A3/A4 渲染路径对比
- [ ] 对比 A3 与 A4 的布局和渲染入口
- [ ] 标出分叉点与不一致的契约
- [ ] 记录结构性差异
- **Status:** pending

### Phase 3: 根因定位
- [ ] 针对五个已知问题定位代码级根因
- [ ] 标注文件与行号
- [ ] 形成可验证的因果链
- **Status:** pending

### Phase 4: 修复方案设计
- [ ] 给出 A4 渲染层的修复/重写建议
- [ ] 给出 PDF 导出链路修复方案
- [ ] 评估统一 A3/A4 路径的方向
- **Status:** pending

### Phase 5: 交付
- [ ] 输出中文诊断报告
- [ ] 检查是否覆盖所有用户问题
- **Status:** pending

## Key Questions
1. 后端生成的 layout 在 A3 与 A4 模式下有哪些结构差异？
2. 前端渲染和导出分别依赖哪些字段、DOM 结构和 CSS 约定？

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 先追踪后端 layout 生成，再追踪前端渲染与导出 | 避免只看前端表象，遗漏布局源头问题 |
| 以 A3 正常路径作为对照组 | 用户已明确 A3 正常，适合做分叉定位 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
|       | 1       |            |

## Notes
- 只做诊断，不做推测性修补
- 所有结论都需要回溯到具体代码与数据流

---

# Task Plan: 知识图谱重构设计独立评审

## Goal
基于设计文档、现有知识树实现、知识库源数据与 knowledge_db.sql，独立评审知识图谱重构方案在教育领域适配性、架构完整性、BKT/自适应兼容性、迁移风险与替代方案上的可行性。

## Current Phase
Phase 1

## Phases
### Phase 1: 材料确认与事实采集
- [ ] 读取用户指定设计文档、项目规则、现有代码
- [ ] 读取知识库样本与 DDL
- [ ] 记录缺失或不一致的输入
- **Status:** complete

### Phase 2: 设计对照评审
- [ ] 对照现有 schema/API/sync 机制检查设计自洽性
- [ ] 对照知识库数据结构检查 4 层模型假设
- [ ] 对照 adaptive/BKT 模型检查兼容性
- **Status:** complete

### Phase 3: 形成评审结论
- [ ] 输出优点
- [ ] 输出风险/问题并按严重程度排序
- [ ] 输出替代建议与总体评价
- **Status:** in_progress

## Key Questions
1. 设计文档提出的 4 层模型是否真能从当前知识库稳定推导？
2. 现有知识树 API 与同步服务是否足以承接该重构，还是需要更深层投影与迁移改造？
3. 该设计是否破坏 adaptive/BKT 现有以 DA 为核心的追踪链路？

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 先核对设计输入是否存在，再进入评审 | 缺失设计文档时不能伪造设计意图 |
| 以代码与知识库样本为主，不接受“应该如此”的假设 | 用户要求独立评审，必须基于事实 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| 用户给定设计文档 `docs/plans/2026-04-09-knowledge-graph-restructure-design.md` 不存在 | 1 | 已转为检索 `docs/plans/` 下相近文件名，待确认正确文档 |

## Notes
- 评审以教育专业性和工程可行为重点
- 如果设计文档缺失，将明确说明哪些结论只能基于现状反推

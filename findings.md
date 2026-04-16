# Findings & Decisions

## Requirements
- 逐个读取指定后端与前端文件，追踪 A4/A3 数据流
- 对比 A3 和 A4 渲染路径的架构差异
- 分析五个已知问题的根因并给出文件:行号
- 提出整体架构建议与 PDF 导出修复方案

## Research Findings
- `tpl_parser.py` 将 `.tpl` 解析为统一骨架，关键输出包括 `paper_size`、`columns`、`objective_groups`、`subjective_slots`、`tpl_images`
- `subject_defaults.py:tql_to_editor_layout()` 直接把 TQL 坐标映射为编辑器 `layout.sides[].columns[].regions[]`，A4 双面和 A3 在这里第一次分叉
- `router.py:get_editor_layout()` 会用默认布局与已保存布局做结构兼容与 config 合并；前端实际拿到的 `layout` 可能是 default，也可能是 saved+merged config
- `html_export.py` 不理解布局语义，只把前端上传的完整 HTML 交给 Playwright 渲染 PDF，因此 PDF 问题优先看前端 `getCleanHTML`/`batchExportPdf`
- A3 渲染路径使用 `renderColumnRegions()` + `renderA3Col()` + `.a3-layout/.a3-col`，每栏是固定高度 flex 容器，`heightRatio` 通过 inline `flex` 生效
- A4 渲染路径绕开 `renderColumnRegions()`，在 `_renderA4()` 中手工拼两页 DOM，并把所有非 fixed region 扁平化；A4 页面本身不是 flex 容器
- `buildChoiceGroupsHTML()` 虽然读取了 TQL 的 `choiceGroups[x,y,w]`，但最终返回值在 `render.js` 末尾统一把所有选择题合并成一个固定 `perRow` 网格，前面的 `renderGroup()`/vertical 判断实际未用于最终输出
- `CardEditor.vue:getValues()` 会把 `_choices` 重新压缩成只含 `start/count/options` 的 `choiceGroups`，会覆盖后端带来的 `x/y/w` 坐标
- 单个 PDF 导出 `getCleanHTML()` 清掉 `transform` 但没有清掉 `applyCSSToPage()` 写入的负 `marginBottom`；批量导出则显式清掉了 `marginBottom`，两条导出链行为不一致
- 导出 HTML 的 CSS 来源依赖运行时遍历 `document.styleSheets` 并抽取 `href` 包含 `styles.css` 的那一份；若样式未加载或读不到，导出 HTML 将几乎无样式
- `extract_skeleton()` 通过最近的 `[data-side]` 推断面别，但当前渲染 HTML 中没有任何 `data-side` 容器，导出的 skeleton 面别会默认成 `A`

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 采用“布局生成 -> API 输出 -> 前端加载 -> 渲染 -> 导出”链路分析 | 能覆盖所有已知问题的完整因果链 |
| 将 A3 作为对照组，A4 作为偏离组 | A3 已知稳定，适合定位架构分叉后的异常 |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| PowerShell 控制台对部分中文源码行显示乱码 | 不影响行号与结构判断，结论以代码结构和字段为准 |

## Resources
- `src/edu_cloud/modules/card/tpl_parser.py`
- `src/edu_cloud/modules/card/subject_defaults.py`
- `src/edu_cloud/modules/card/router.py`
- `src/edu_cloud/modules/card/html_export.py`
- `frontend/src/card-editor/render.js`
- `frontend/src/card-editor/export.js`
- `frontend/src/card-editor/model.js`
- `frontend/src/components/CardEditor.vue`
- `frontend/public/card-editor/styles.css`

## Visual/Browser Findings
- 本任务不依赖浏览器截图，重点是代码与导出 HTML/CSS 链路

---

## Session: 2026-04-09 知识图谱重构设计评审

### Requirements
- 读取设计文档、CLAUDE.md、知识树现状代码、知识库样本和 knowledge_db.sql
- 从教育适配性、架构完整性、BKT/自适应兼容性、风险盲点、替代方案五个维度做独立评审
- 输出优点、风险/问题、替代建议、总体评价

### Research Findings
- 用户指定的设计文档 `docs/plans/2026-04-09-knowledge-graph-restructure-design.md` 当前不存在，不能直接引用设计文本
- `knowledge_tree/detail_service.py` 当前详情聚合仍以 `concept -> DA -> curriculum_requirements/q_matrix` 为核心链路，不是课标大概念驱动
- `knowledge_tree/router.py` 当前 API 只有 `/graph`、`/mastery`、`/graph/{node_id}/detail`、`/edit` 四类，详情接口默认面向“概念节点”而非多层级混合节点
- `knowledge_tree/sync_service.py` 当前同步是从 knowledge.db 的 `concepts` 和 `concept_relations` 直接全量覆盖 PG 投影；模块来自 concept id 中 `_M{n}_` 正则提取，不依赖课标 big concept
- 生物 L1 样本 `M1_concepts.json` 是“模块内平铺概念列表”：字段有 `id/canonical_name/module/l0_ids/req_ids/parent/children/aliases/cross_module`，样本中 `parent` 全为 `null`、`children` 为空，说明当前源数据本身并没有稳定的大概念树
- `knowledge_db.sql` 中 `curriculum_requirements.big_concept` 是可空字段；`concepts` 只有 `knowledge_level`（L0/L1/L2），不存在 Subject/Module/BigConcept/Concept 四层表述
- `knowledge_db.sql` 中 `study_units` 已把 `source_concept_ids`、`linked_da_ids`、`l0_recall_ids` 分开建模，表明现有自适应规划更接近“概念 + DA + L0 证据”组合，而不是单靠层级树
- 当前前端知识树页实际消费的是“模块卡片 + 模块/概念树导航 + 平铺图节点 + 抽屉详情”；`GraphResponse` 只返回平铺 `nodes/edges`，并不提供三级导航所需的层级结构
- 生物高中源数据定量结果：L1 共 108 个概念，`parent=null` 104 个，`parent=ORPHAN` 4 个，`children` 非空 0 个；说明用 `parent_id` 自动推出稳定大概念树没有数据基础
- 生物高中课程标准 JSON 中有 5 个模块、10 个 big concepts、151 条 content requirements；而实库 `knowledge.db` 中 `curriculum_requirements` 共 175 条，其中 151 条 `big_concept` 非空、24 条为空，空值主要来自 academic requirements（`areq:*`）
- `skeleton/progressions/*.json` 另有 10 条 big concept progression 和 28 条 sub concept progression，说明 BigConcept 更像“学习进阶/课标组织层”，不是 `L1 concepts` 的天然父节点
- 对 108 个 L1 概念做 `req_ids -> curriculum_requirements.big_concept` 映射后：106 个概念落到单一 big concept，2 个概念同时落到两个 big concepts，0 个完全无 big concept；说明该聚合在生物 content requirement 维度“多数可用，但并非严格单值”
- `sub_concept_progressions` 仅覆盖 28/108 个 L1 概念（25.93%），无法作为通用的大概念父子锚点
- 实库 `knowledge.db` 中 `concepts` 共 1233 条：L0=1103、L1=108、L2=22；当前知识树同步只投影 `concepts`/`concept_relations`，并未同步 big concept / progression / study_unit
- 实库 `concept_relations` 共 335 条，远少于节点数 1233；当前 `/graph?module=all` 若直接返回全量节点，对力导向图的教育可读性和前端性能都不理想
- 当前 adaptive 主链路是 `StudentDaMastery -> DaCatalogSnapshot/DaKnowledgePointMap -> learning_path`；`QuestionDaOverride` 只支持 `da_ids` 覆盖，`question_selector` 只按 `transfer_band` 选题，并不消费 `difficulty` 或 `bloom_level`
- `concept_graph_nodes` 模型没有 `subject` 字段，`/graph` 也没有 `subject` 过滤；如果设计改为多学科单库，现有投影表和 API 天然不具备隔离能力

### Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 在未找到设计文档前，先从现状代码与数据反证设计假设是否站得住 | 这样至少能识别明显不成立的前提 |
| 把 `curriculum_requirements.big_concept` 视为待验证辅助字段，而非可靠主键 | DDL 已显示其可空 |

### Issues Encountered
| Issue | Resolution |
|-------|------------|
| 设计文档路径不存在 | 已检索 `docs/plans/`，待进一步搜索相近文件或请用户确认路径 |

### Resources
- `docs/plans/` 目录
- `CLAUDE.md`
- `src/edu_cloud/modules/knowledge_tree/detail_service.py`
- `src/edu_cloud/modules/knowledge_tree/router.py`
- `src/edu_cloud/modules/knowledge_tree/sync_service.py`
- `C:/Users/Administrator/edu-knowledge-base/subjects/biology_senior/skeleton/L1/M1_concepts.json`
- `C:/Users/Administrator/edu-knowledge-base/schemas/knowledge_db.sql`

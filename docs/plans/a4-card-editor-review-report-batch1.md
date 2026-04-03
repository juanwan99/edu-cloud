[edu-cloud] GPT Reviewer | 2026-04-03 19:53:55
## 审查报告: Task 1-8 (3 轮)
结论: PASS (Round 3, code-bug + test-gap 全部修复)

### Round 1 → FAIL (4 findings)
| ID | Severity | Category | Type | 状态 |
|----|----------|----------|------|------|
| F001 | HIGH | code-bug | defect_fix | R2 修复 → verified |
| F002 | HIGH | test-gap | defect_fix | R2 修复 → verified |
| F003 | MED | code-bug | defect_fix | R2 修复 → verified |
| F004 | MED | design-concern | defect_fix | 不阻塞，deferred |

### Round 2 → FAIL (F001-F003 resolved, F005 new)
| ID | Severity | Category | Type | 状态 |
|----|----------|----------|------|------|
| F005 | MED | code-bug | defect_fix | R3 修复 → verified |

### Round 3 → PASS (F005 code fix + regression test)
GPT 确认 F005 代码修复正确（filter+max 同步 options），
唯一阻塞项是缺回归测试 → 已补 3 个 Vitest 测试（commit 03e0ae6）。

### 第一段：测试充分性
- A4 layout 契约: 8 个后端测试（fallback + TQL 路径）
- API 集成: 英语 A4 + 化学结构 + 数学 A3 负向测试
- essayConfig 一致性: TQL 英语 essayConfig==essayCount 回归
- 前端 DOM: 4 个渲染结构测试 + 3 个 TQL choiceGroups 同步测试
- 总计: 43 后端 + 7 前端 = 50 tests

### 第二段：行为正确性

#### 变更理解
本批次重构 A4 双面答题卡编辑器，统一 A3/A4 渲染架构。核心变更：
1. **后端 layout 契约统一**：TQL A4 路径将多 column essay 合并到 col 0，与 fallback 路径一致
2. **CSS 重构**：`.a4-essay-area` → `.a4-col` flex 容器 + `.a4-content` 页面骨架
3. **渲染统一**：A4 复用 `renderColumnRegions()` + `renderFixedRegions()` 共享函数
4. **选择题竖排**：TQL 坐标存在时按组 renderGroup，getValues 保留原始分组结构
5. **PDF 导出**：CSS fetch 内联 + marginBottom 清除 + Noto CJK fallback

#### Executor 自审抽检
- test_a4_layout_single_column_per_side: 独立验证——删除 col 合并逻辑后断言 `len==1` 确实失败
- test_tql_essay_config_matches_count: 独立验证——revert essayConfig 修复后 `len(essayConfig)!=essayCount` 确实失败

#### 对抗性审查
- **边界输入**: B 面无 regions → 不渲染 #pageB（Vitest 验证）；化学 fallback 14<30 走 A3（后端测试验证）
- **异常路径**: TQL choiceGroups 无匹配 choices → 保留原始 options（F005 测试第 2 case）
- **假阴性检测**: 化学测试从条件断言改为无条件（F002 修复），数学负向测试硬断言 A3（F002 修复）

#### 具体核实
- TQL A4 col 合并: is_a4_dual 时 essays 合并到 col 0（verified by TQL contract tests）
- A4 结构校验: router.py 扩展检查多 col saved layout → structure_mismatch
- renderFixedRegions: A3/A4 共享，输出相同 HTML（verified by A3 test unchanged）
- getValues TQL sync: 保留 start/count/x/y/w + 同步 options（verified by F005 tests）

### 第三段：未测试风险
- 前端 TQL 选择题的坐标定位（x/y/w absolute positioning）未实际使用 → design scope
- `_cachedStyleCSS` 在 SPA 长期运行中可能缓存过期 CSS → low risk
- 批量导出路径的 CSS 获取也改用了 fetchStyleCSS → 一致性已保证

### 发现清单（最终状态）
| ID | Severity | Category | Type | Status | 处置 |
|----|----------|----------|------|--------|------|
| F001 | HIGH | code-bug | defect_fix | verified → resolved | commit 124bf5a |
| F002 | HIGH | test-gap | defect_fix | verified → resolved | commit 124bf5a |
| F003 | MED | code-bug | defect_fix | verified → resolved | commit 124bf5a |
| F004 | MED | design-concern | defect_fix | verified | deferred, 不阻塞 |
| F005 | MED | code-bug | defect_fix | verified → resolved | commit 22f9e7e + 03e0ae6 |

[edu-cloud] Executor→Reviewer | 2026-04-04 23:08:27
## 审查交接单: Task 16-17 (Batch 5 IntentRouter + 工具注册)
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-04-agent-evolution-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T16 | EntityExtractor + IntentRouter | commit 0d88cd3, 2 files + 9 tests | ✅ | 关键词规则 3 工作流 + 7 域 + 实体提取 |
| T17 | 工具注册验证 | commit 507c016, 1 test 追加 | ✅ | 6 新工具全部在 registry 中确认 |

### 预审自检
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 | 反证验证 |
|---------------|------------------|---------|---------|---------|
| 考后意图匹配 | test_intent_router::test_route_post_exam | `python -m pytest tests/test_ai/test_intent_router.py::test_route_post_exam -v` | PASSED | 不适用 |
| 自由模式 | test_intent_router::test_route_free_mode | `python -m pytest tests/test_ai/test_intent_router.py::test_route_free_mode -v` | PASSED | 不适用 |
| 实体提取 | test_intent_router::test_extract_subject | `python -m pytest tests/test_ai/test_intent_router.py::test_extract_subject -v` | PASSED | 不适用 |
| 工具注册 | test_tools_registration::test_new_domain_tools_registered | `python -m pytest tests/test_ai/test_tools_registration.py::test_new_domain_tools_registered -v` | PASSED | 不适用 |

### 验证清单自检
- ✅ WORKFLOW_KEYWORDS 覆盖 3 个工作流
- ✅ DOMAIN_KEYWORDS 覆盖 7 个域
- ✅ 低置信度 needs_clarification=True
- ✅ EntityExtractor 支持 9 个科目
- ✅ 6 个新工具全部注册
- ✅ 327 AI 测试全部 PASS

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: IntentRouter.classify("你好", available_workflows=[])
  运行命令: `python -m pytest tests/test_ai/test_intent_router.py::test_route_free_mode -v`
  实际输出:
  ```
  PASSED
  ```
  结论: 无关键词消息正确路由到 free mode

- 字符串匹配/条件判断的假阴性：
  构造输入: EntityExtractor.extract("3班数学成绩") — 同时提取科目+班级
  运行命令: `python -m pytest tests/test_ai/test_intent_router.py::test_route_with_entities -v`
  实际输出:
  ```
  PASSED
  ```
  结论: 多实体正确提取

- 状态变量/锁的异常路径：
  构造输入: IntentRouter.classify with single keyword (low confidence)
  运行命令: `python -m pytest tests/test_ai/test_intent_router.py::test_route_low_confidence -v`
  实际输出:
  ```
  PASSED
  ```
  结论: 低置信度正确标记 needs_clarification

使用 codex-review skill 进行 GPT 代码审查。

[edu-cloud] Executor→Reviewer | 2026-04-04 08:50:42
## 审查交接单: F005 + NEW-F006 (R3 修复)
计划: GPT R2 FAIL — 2 test-gap findings

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| F005 | get_student_scores + get_class_scores 执行级测试 | commit f340227, 4 tests（success/not_found/missing_exam/permission） | ✅ | |
| NEW-F006 | anonymizer 反证测试强化 | commit ec38aa4, mock_chat 捕获 round 2 messages，断言含 S001 不含张三/T001 | ✅ | |

### 预审自检
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 | 反证验证 |
|---------------|------------------|---------|---------|---------|
| get_student_scores 正常返回 | test_tools_execution.py::test_get_student_scores_success | `pytest tests/test_ai/test_tools_execution.py -k student_scores -v` | 2 passed | 不适用：新增测试 |
| get_class_scores 缺 exam_id | test_tools_execution.py::test_get_class_scores_missing_exam_id | `pytest tests/test_ai/test_tools_execution.py -k class_scores -v` | 2 passed | 不适用：新增测试 |
| anonymizer 消息内容断言 | test_ai_api_v2.py::test_agentloop_anonymizer_integration | `pytest tests/test_ai/test_ai_api_v2.py::test_agentloop_anonymizer_integration -v` | 1 passed | 删除 agent_loop.py L175 anonymize 调用 → FAILED: "S001 not found, got 张三" ✅ |

### 验证清单自检
- ✅ F005: get_student_scores — success（mock service 返回 2 科成绩，验证 total=175）+ not_found（学生不存在）
- ✅ F005: get_class_scores — missing_exam_id（空 input）+ permission_denied（class_id 不在 ctx.class_ids）
- ✅ NEW-F006: captured_messages_round2 非 None + tool_msg.content 含 S001 + 不含张三 + 不含 T001
- ✅ NEW-F006 反证: 删除 anonymize() 行 → 测试 FAIL（"tool message to LLM should contain S001, got 张三"）
- ✅ 全量 AI 测试: 211 passed

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: get_student_scores 学生不存在
  运行命令: `pytest tests/test_ai/test_tools_execution.py::test_get_student_scores_not_found -v`
  实际输出:
  ```
  PASSED
  ```
  结论: mock service 返回 None → ToolResult(success=False, error="学生不存在")

- 状态变量/锁的异常路径：
  构造输入: get_class_scores 有 class_ids 限制但请求 c99
  运行命令: `pytest tests/test_ai/test_tools_execution.py::test_get_class_scores_permission_denied -v`
  实际输出:
  ```
  PASSED
  ```
  结论: ctx.class_ids=["c1"] 时请求 c99 → ToolResult(success=False, error="无权访问该班级")

- 字符串匹配/条件判断的假阴性：
  构造输入: anonymizer 反证——删除 anonymize() 核心逻辑
  运行命令: `python -c "..." (临时禁用 anonymize 行并运行测试)`
  实际输出:
  ```
  FAILED: NEW-F006: tool message to LLM should contain anonymized code S001, got: {'success': True, 'data': {'students': [{'student_name': '张三', ...}]}}
  ```
  结论: 测试在核心逻辑删除后正确失败，非假绿

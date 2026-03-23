"""Agent context — system prompt building + session-level context management."""
from __future__ import annotations
import json
import logging
from edu_cloud.ai.schemas import ChatMessage, ToolCall  # noqa: F401

logger = logging.getLogger(__name__)

# ── Role localization ──────────────────────────────────────────────────────
ROLE_CN = {
    "platform_admin": "平台管理员", "district_admin": "教育局管理员",
    "principal": "校长", "academic_director": "教务主任",
    "grade_leader": "年级组长", "homeroom_teacher": "班主任",
    "subject_teacher": "科任教师", "parent": "家长",
}


def build_system_prompt(role: str, display_name: str, scope: dict, tool_names: list[str]) -> str:
    """Build platform system prompt for Agent."""
    role_cn = ROLE_CN.get(role, role)
    scope_desc = ""
    if scope.get("school"):
        scope_desc += f"学校：{scope['school']}\n"
    if scope.get("classes"):
        scope_desc += f"班级：{', '.join(scope['classes'])}\n"
    if scope.get("grades"):
        scope_desc += f"年级：{', '.join(scope['grades'])}\n"
    if scope.get("subjects"):
        scope_desc += f"学科：{', '.join(scope['subjects'])}\n"
    tools_desc = "、".join(tool_names) if tool_names else "无"
    return f"""你是 edu-cloud 智能教学分析助手。

当前用户：{display_name}（{role_cn}）
{scope_desc}
你可以使用以下工具查询数据：{tools_desc}

【教育统计知识】
得分率 > 0.7: 较容易；0.4-0.7: 适中；< 0.4: 较难
区分度 > 0.3: 良好；0.2-0.3: 一般；< 0.2: 差
班级均分差异 > 10%: 显著

【因果分析框架】
成绩出现显著变化时按以下维度排查：
1. 命题因素：本次难度/区分度与历次对比
2. 题目因素：哪些题得分率异常低
3. 班级因素：个别班级还是全年级
4. 学生因素：整体下滑还是个别拖后腿
注意：只提供数据层面分析，教学方法等信息提示用户结合实际判断。

【输出要求】
- 中文回答，数据结论必须附具体数字
- 对比分析先结论后展开
- 不确定时明确标注 [UNCERTAIN]
- 不编造数据
- 学生姓名已匿名化（如 S001），在回答中使用匿名 ID"""


# ── Token estimation ──────────────────────────────────────────────────────
_CHARS_PER_TOKEN = 3


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


# ── Session context management ────────────────────────────────────────────
class AgentContext:
    """Session-level context manager with token budget enforcement.

    Maintains per-session message history. When token budget is exceeded,
    oldest messages are pruned (system prompt always kept).
    """

    def __init__(self, system_content: str):
        self._system_content = system_content
        self._sessions: dict[str, list[ChatMessage]] = {}

    def _get_session(self, session_id: str) -> list[ChatMessage]:
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        return self._sessions[session_id]

    def add_user_message(self, content: str, session_id: str):
        self._get_session(session_id).append(ChatMessage(role="user", content=content))

    def add_assistant_message(
        self, content: str | None, session_id: str, tool_calls: list[ToolCall] | None = None
    ):
        self._get_session(session_id).append(
            ChatMessage(role="assistant", content=content, tool_calls=tool_calls)
        )

    def add_tool_result(self, tool_call: ToolCall, result: dict, session_id: str):
        self._get_session(session_id).append(
            ChatMessage(
                role="tool",
                content=json.dumps(result, ensure_ascii=False, default=str),
                tool_call_id=tool_call.id,
                name=tool_call.name,
            )
        )

    def build_messages(self, session_id: str, max_tokens: int = 80000) -> list[ChatMessage]:
        """Build messages with token budget. Prunes oldest messages first."""
        system_msg = ChatMessage(role="system", content=self._system_content)
        history = list(self._get_session(session_id))

        system_tokens = _estimate_tokens(self._system_content)
        budget = max_tokens - system_tokens

        kept: list[ChatMessage] = []
        total = 0
        for msg in reversed(history):
            msg_tokens = _estimate_tokens(msg.content or "") + _estimate_tokens(
                json.dumps([tc.to_openai() for tc in msg.tool_calls], ensure_ascii=False)
                if msg.tool_calls else ""
            )
            if total + msg_tokens > budget:
                break
            kept.append(msg)
            total += msg_tokens

        kept.reverse()
        return [system_msg] + kept

    def get_session_messages(self, session_id: str) -> list[ChatMessage]:
        return list(self._get_session(session_id))

    def clear_session(self, session_id: str):
        self._sessions.pop(session_id, None)

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())

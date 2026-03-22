import httpx
import json
import logging
from edu_cloud.ai.schemas import ChatMessage, ToolCall
from edu_cloud.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self.url = settings.LLM_API_URL
        self.model = settings.LLM_MODEL
        self.timeout = settings.LLM_TIMEOUT

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
    ) -> ChatMessage:
        payload = {
            "model": self.model,
            "messages": [self._msg_to_dict(m) for m in messages],
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                self.url,
                json=payload,
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
            )
            resp.raise_for_status()

        data = resp.json()
        choice = data["choices"][0]["message"]

        tool_calls = None
        if choice.get("tool_calls"):
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=(
                        json.loads(tc["function"]["arguments"])
                        if isinstance(tc["function"]["arguments"], str)
                        else tc["function"]["arguments"]
                    ),
                )
                for tc in choice["tool_calls"]
            ]

        return ChatMessage(
            role="assistant",
            content=choice.get("content"),
            tool_calls=tool_calls,
        )

    def _msg_to_dict(self, msg: ChatMessage) -> dict:
        d: dict = {"role": msg.role}
        if msg.content is not None:
            d["content"] = msg.content
        if msg.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in msg.tool_calls
            ]
        if msg.tool_call_id:
            d["tool_call_id"] = msg.tool_call_id
        if msg.name:
            d["name"] = msg.name
        return d

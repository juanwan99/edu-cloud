"""会话级数据脱敏 — 姓名→代号映射，student_number 移除。"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

# 需要脱敏的字段名
_NAME_FIELDS = {"student_name", "name", "display_name"}
# 需要完全移除的字段（不发送给 LLM）
_STRIP_FIELDS = {"student_number"}


class Anonymizer:
    """会话级姓名脱敏。线程不安全，每个会话独立实例。"""

    def __init__(self):
        self._name_to_code: dict[str, str] = {}
        self._code_to_name: dict[str, str] = {}
        self._counter = 0

    def _get_or_create_code(self, name: str) -> str:
        if name in self._name_to_code:
            return self._name_to_code[name]
        self._counter += 1
        code = f"S{self._counter:03d}"
        self._name_to_code[name] = code
        self._code_to_name[code] = name
        return code

    def get_code(self, name: str) -> str | None:
        """查询已有映射，不自动创建。"""
        return self._name_to_code.get(name)

    def anonymize(self, data):
        """脱敏 dict 或 list[dict]。返回深拷贝，不修改原数据。"""
        if isinstance(data, list):
            return [self.anonymize(item) for item in data]
        if not isinstance(data, dict):
            return data
        result = {}
        for key, value in data.items():
            if key in _STRIP_FIELDS:
                continue  # 完全移除
            if key in _NAME_FIELDS and isinstance(value, str) and value:
                result[key] = self._get_or_create_code(value)
            elif isinstance(value, dict):
                result[key] = self.anonymize(value)
            elif isinstance(value, list):
                result[key] = self.anonymize(value)
            else:
                result[key] = value
        return result

    def deanonymize(self, text: str) -> str:
        """将文本中的代号替换回真实姓名。整句替换，避免逐 token 截断。"""
        if not text or not self._code_to_name:
            return text
        # 按代号长度降序排列，避免 S1 替换 S10 的前缀
        for code in sorted(self._code_to_name, key=len, reverse=True):
            text = text.replace(code, self._code_to_name[code])
        return text

    def reset(self):
        self._name_to_code.clear()
        self._code_to_name.clear()
        self._counter = 0

    @property
    def mapping_count(self) -> int:
        return len(self._name_to_code)

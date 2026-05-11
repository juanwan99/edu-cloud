"""Entity reference type registry for AI chat data picker."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RefType:
    type_code: str
    label: str
    icon: str
    children_type: str | None = None
    searchable: bool = True

    def to_dict(self) -> dict:
        return {
            "type_code": self.type_code,
            "label": self.label,
            "icon": self.icon,
            "children_type": self.children_type,
            "searchable": self.searchable,
        }


@dataclass
class RefItem:
    id: str
    label: str
    subtitle: str | None = None
    children_type: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "subtitle": self.subtitle,
            "children_type": self.children_type,
        }


REF_TYPES: list[RefType] = [
    RefType("exam", "考试", "exam", children_type="subject"),
    RefType("subject", "科目", "subject", children_type="question"),
    RefType("class", "班级", "class", children_type="student"),
    RefType("student", "学生", "student"),
    RefType("question", "题目", "question"),
]

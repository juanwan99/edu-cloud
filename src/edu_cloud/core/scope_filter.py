from __future__ import annotations

from edu_cloud.models.user_role import UserRole


class ScopeFilter:
    """基于 UserRole 的 scope 自动注入 WHERE 条件。"""

    def __init__(self, role: UserRole):
        self.school_id = role.school_id
        self.grade_ids = role.grade_ids
        self.class_ids = role.class_ids
        self.subject_codes = role.subject_codes

    def apply(self, stmt, model, *, school_col="school_id",
              class_col=None, grade_col=None, subject_col=None):
        """追加过滤条件。school_id 始终追加（非 None 时）；
        grade/class/subject 有 scope 值且 model 有对应列时才追加。"""
        if self.school_id:
            stmt = stmt.where(getattr(model, school_col) == self.school_id)
        if self.class_ids and class_col:
            stmt = stmt.where(getattr(model, class_col).in_(self.class_ids))
        if self.grade_ids and grade_col:
            stmt = stmt.where(getattr(model, grade_col).in_(self.grade_ids))
        if self.subject_codes and subject_col:
            stmt = stmt.where(getattr(model, subject_col).in_(self.subject_codes))
        return stmt

    @classmethod
    def from_role(cls, role) -> ScopeFilter | None:
        """platform_admin/district_admin 等无 school_id 的角色返回 None（不过滤）。"""
        if not role or not role.school_id:
            return None
        return cls(role)

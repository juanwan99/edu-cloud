"""Conduct Pydantic schemas"""
from datetime import date as _date_type
from typing import Optional

from pydantic import BaseModel, Field


# ── Parent Auth ──
class InviteCodeInfo(BaseModel):
    class_name: str
    school_name: str
    verify_code_type: str

class ParentRegisterRequest(BaseModel):
    invite_code: str = Field(..., min_length=4, max_length=10)
    display_name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., pattern=r"^1\d{10}$")
    password: str = Field(..., min_length=6)
    relationship: str = Field(default="other")

class ParentLoginRequest(BaseModel):
    phone: str
    password: str

class ParentBindRequest(BaseModel):
    class_id: str
    student_name: str
    verify_code: str
    relationship: str = Field(default="other")


# ── Conduct Records (for later tasks) ──
class AddPointsRequest(BaseModel):
    student_ids: list[str] = Field(..., min_length=1)
    points: int
    reason: str = Field(..., min_length=1)
    rule_item_id: Optional[str] = None
    record_date: Optional[_date_type] = None

class PointsRecordResponse(BaseModel):
    id: str
    student_id: str
    student_name: str
    points: int
    reason: str
    date: _date_type
    operator_name: str
    source: str
    rule_item_name: Optional[str] = None
    created_at: str


# ── Rules ──
class RuleCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    sort_order: int = 0

class RuleItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    points: int

class RuleCategoryResponse(BaseModel):
    id: str
    name: str
    sort_order: int
    items: list[dict] = []


# ── Groups ──
class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    avatar: Optional[str] = None

class GroupMemberAdd(BaseModel):
    student_ids: list[str]


# ── Config ──
class ConductConfigUpdate(BaseModel):
    verify_code_type: Optional[str] = None
    required_parent_fields: Optional[list[str]] = None
    is_active: Optional[bool] = None
    alert_threshold: Optional[int] = None

"""Scan 模块服务 — StorageService（从 exam-ai shared/storage.py 迁入）。"""
import os

import aiofiles

from edu_cloud.config import settings


class StorageService:
    def __init__(self, root: str | None = None):
        self.root = root or settings.STORAGE_ROOT

    def _validate_component(self, name: str, value: str) -> None:
        if ".." in value or "/" in value or "\\" in value or os.path.isabs(value):
            raise ValueError(f"Invalid path component {name}: {value}")

    def build_path(
        self, school_id: str, exam_id: str, subject_id: str, question_id: str, student_id: str,
    ) -> str:
        for name, val in [("school_id", school_id), ("exam_id", exam_id),
                          ("subject_id", subject_id), ("question_id", question_id),
                          ("student_id", student_id)]:
            self._validate_component(name, val)
        path = os.path.join(self.root, school_id, exam_id, subject_id, question_id, f"{student_id}.png")
        if not os.path.normpath(path).startswith(os.path.normpath(self.root)):
            raise ValueError("Path escapes storage root")
        return path

    async def save(
        self, school_id: str, exam_id: str, subject_id: str,
        question_id: str, student_id: str, data: bytes,
    ) -> str:
        path = self.build_path(school_id, exam_id, subject_id, question_id, student_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
        return path


def get_storage() -> StorageService:
    return StorageService()

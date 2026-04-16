"""edu-cloud 统一日志配置。

双输出:
- Console: 人类可读格式（开发用）
- File:    JSONL 格式（持久化，可用 jq/grep 分析）

Request ID 追踪:
- ContextVar 注入，所有日志自动携带 req_id
- FastAPI 中间件设置，无需改动已有 logger 调用
"""

import json
import logging
import os
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler

_configured = False

_TZ_UTC8 = timezone(timedelta(hours=8))

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
current_user_var: ContextVar[str | None] = ContextVar("current_user_id", default=None)


class _UTC8Formatter(logging.Formatter):
    """Console 用：人类可读，UTC+8 时区。"""

    def formatTime(self, record, datefmt=None):  # noqa: N802
        dt = datetime.fromtimestamp(record.created, tz=_TZ_UTC8)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")


class _JSONLFormatter(logging.Formatter):
    """File 用：每行一个 JSON 对象，机器可解析。"""

    def format(self, record):
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=_TZ_UTC8).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "msg": record.getMessage(),
            "req_id": request_id_var.get(),
        }
        if record.exc_info and record.exc_info[1]:
            entry["error"] = f"{type(record.exc_info[1]).__name__}: {record.exc_info[1]}"
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(
    level: int = logging.DEBUG,
    log_dir: str = "./logs",
    file_level: int = logging.INFO,
) -> None:
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger("edu_cloud")
    root.setLevel(logging.DEBUG)
    root.propagate = False

    # Console handler
    console_fmt = "%(asctime)s | %(name)s | %(levelname)-5s | %(message)s"
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(_UTC8Formatter(console_fmt))
    root.addHandler(console_handler)

    # File handler: JSONL
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app.jsonl")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(_JSONLFormatter())
    root.addHandler(file_handler)

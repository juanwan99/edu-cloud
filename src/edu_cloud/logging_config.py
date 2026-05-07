"""edu-cloud 统一日志系统 v2。

进程分文件写入 + 统一 Schema + 全链路追踪：
- Console: 人类可读格式（开发用）
- File: JSONL 格式（持久化，按进程分目录）
  - logs/api/edu-api-YYYY-MM-DD.NNN.jsonl     (FastAPI 进程)
  - logs/worker/edu-worker-YYYY-MM-DD.NNN.jsonl (arq Worker 进程)
  - logs/business/edu-biz-YYYY-MM-DD.jsonl     (业务事件归档)

ContextVar 全链路追踪：trace_id / req_id / user_id / school_id
"""

import json
import logging
import os
from contextvars import ContextVar
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

_configured = False

TZ_UTC8 = timezone(timedelta(hours=8))

SCHEMA_VERSION = 1
MAX_FILE_BYTES = 64 * 1024 * 1024  # 64MB per file

# --- ContextVars (全链路追踪) ---

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")
current_user_var: ContextVar[str | None] = ContextVar("current_user_id", default=None)
current_school_var: ContextVar[str | None] = ContextVar("current_school_id", default=None)
impersonator_var: ContextVar[str | None] = ContextVar("impersonator_id", default=None)


def get_trace_context() -> dict:
    return {
        "trace_id": trace_id_var.get(),
        "req_id": request_id_var.get(),
        "user_id": current_user_var.get(),
        "school_id": current_school_var.get(),
        "impersonator_id": impersonator_var.get(),
    }


# --- Formatters ---

class _UTC8Formatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):  # noqa: N802
        dt = datetime.fromtimestamp(record.created, tz=TZ_UTC8)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")


class _JSONLFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "v": SCHEMA_VERSION,
            "ts": datetime.fromtimestamp(record.created, tz=TZ_UTC8).isoformat(),
            "level": record.levelname.lower(),
            "layer": getattr(record, "_layer", "app"),
            "event": getattr(record, "_event", None),
            "msg": record.getMessage(),
            "service": "edu-cloud",
            "logger": record.name,
            "trace_id": trace_id_var.get(),
            "req_id": request_id_var.get(),
            "user_id": current_user_var.get(),
            "school_id": current_school_var.get(),
        }
        duration = getattr(record, "_duration_ms", None)
        if duration is not None:
            entry["duration_ms"] = duration
        data = getattr(record, "_data", None)
        if data:
            entry["data"] = data
        if record.exc_info and record.exc_info[1]:
            exc = record.exc_info[1]
            entry["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        return json.dumps(entry, ensure_ascii=False, default=str)


# --- Daily Rolling File Handler (进程安全) ---

class _DailyRollingHandler(logging.Handler):
    """按日期+大小滚动，每个进程独立写自己的文件。"""

    def __init__(self, log_dir: str, prefix: str, max_bytes: int = MAX_FILE_BYTES):
        super().__init__()
        self._log_dir = Path(log_dir)
        self._prefix = prefix
        self._max_bytes = max_bytes
        self._current_date: date | None = None
        self._current_file = None
        self._current_path: Path | None = None
        self._current_size = 0
        self._roll_index = 0

    def _ensure_file(self):
        today = datetime.now(tz=TZ_UTC8).date()
        if self._current_date != today:
            self._current_date = today
            self._roll_index = 0
            self._close_file()
            self._open_new_file()
        elif self._current_size >= self._max_bytes:
            self._roll_index += 1
            self._close_file()
            self._open_new_file()

    def _open_new_file(self):
        self._log_dir.mkdir(parents=True, exist_ok=True)
        d = self._current_date or date.today()
        filename = f"{self._prefix}-{d.isoformat()}.{self._roll_index:03d}.jsonl"
        self._current_path = self._log_dir / filename
        self._current_file = open(self._current_path, "a", encoding="utf-8")
        self._current_size = self._current_path.stat().st_size if self._current_path.exists() else 0

    def _close_file(self):
        if self._current_file:
            self._current_file.close()
            self._current_file = None

    def emit(self, record):
        try:
            self._ensure_file()
            msg = self.format(record) + "\n"
            if self._current_file:
                self._current_file.write(msg)
                self._current_file.flush()
            self._current_size += len(msg.encode("utf-8"))
        except Exception:
            self.handleError(record)

    def close(self):
        self._close_file()
        super().close()


# --- Business Event Logger ---

_business_handler: _DailyRollingHandler | None = None


def business_event(
    action: str,
    entity_type: str,
    entity_id: str,
    *,
    old_state: str | None = None,
    new_state: str | None = None,
    fields_changed: dict | None = None,
    reason: str | None = None,
    exam_id: str | None = None,
    **extra,
) -> None:
    """记录业务状态变更事件。写入主流 + business 归档。"""
    logger = logging.getLogger("edu_cloud.business")
    record = logger.makeRecord(
        "edu_cloud.business", logging.INFO,
        "(business)", 0,
        f"{action} {entity_type} {entity_id}: {old_state} → {new_state}",
        (), None,
    )
    record._layer = "business"
    record._event = f"business.{action}"
    record._data = {
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "old_state": old_state,
        "new_state": new_state,
        "fields_changed": fields_changed,
        "reason": reason,
        "exam_id": exam_id,
        **{k: v for k, v in extra.items() if v is not None},
    }
    logger.handle(record)
    if _business_handler:
        _business_handler.handle(record)


# --- Structured Log Helpers ---

def log_event(
    logger_name: str,
    level: int,
    layer: str,
    event: str,
    msg: str,
    *,
    duration_ms: float | None = None,
    **data,
) -> None:
    """发出结构化日志事件。"""
    logger = logging.getLogger(logger_name)
    if not logger.isEnabledFor(level):
        return
    record = logger.makeRecord(
        logger_name, level, "(structured)", 0, msg, (), None,
    )
    record._layer = layer
    record._event = event
    record._duration_ms = duration_ms
    record._data = {k: v for k, v in data.items() if v is not None} or None
    logger.handle(record)


# --- Setup ---

def setup_logging(
    level: int = logging.DEBUG,
    log_dir: str = "./logs",
    file_level: int = logging.INFO,
    process: str = "api",
) -> None:
    """初始化日志系统。每个进程调用一次。

    Args:
        process: "api" 或 "worker"，决定日志文件前缀和目录。
    """
    global _configured, _business_handler
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

    # Main file handler (process-specific directory)
    process_dir = os.path.join(log_dir, process)
    prefix = f"edu-{process}"
    main_handler = _DailyRollingHandler(process_dir, prefix)
    main_handler.setLevel(file_level)
    main_handler.setFormatter(_JSONLFormatter())
    root.addHandler(main_handler)

    # Business event archive (shared directory, all processes write)
    biz_dir = os.path.join(log_dir, "business")
    _business_handler = _DailyRollingHandler(biz_dir, "edu-biz", max_bytes=MAX_FILE_BYTES)
    _business_handler.setLevel(logging.INFO)
    _business_handler.setFormatter(_JSONLFormatter())

    # Legacy compatibility: also write to app.jsonl (7-day transition)
    legacy_path = os.path.join(log_dir, "app.jsonl")
    if os.path.exists(legacy_path):
        from logging.handlers import RotatingFileHandler
        legacy_handler = RotatingFileHandler(
            legacy_path, maxBytes=10 * 1024 * 1024, backupCount=2, encoding="utf-8",
        )
        legacy_handler.setLevel(file_level)
        legacy_handler.setFormatter(_JSONLFormatter())
        root.addHandler(legacy_handler)

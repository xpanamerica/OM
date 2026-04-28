import logging
import sys
from pathlib import Path


class _RequestIdFilter(logging.Filter):
    """为 format 提供 ``request_id`` 占位（无上下文时为 ``-``）。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            try:
                from app.core.request_context import request_id_cv

                rid = request_id_cv.get()
            except Exception:
                rid = None
            record.request_id = rid if rid else "-"
        return True


def setup_logging() -> None:
    from app.core.config import settings

    level_name = (settings.LOG_LEVEL or "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    if root.handlers:
        for h in root.handlers:
            h.setLevel(level)
        return
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s [request_id=%(request_id)s] %(message)s",
    )
    req_filt = _RequestIdFilter()

    h = logging.StreamHandler(sys.stdout)
    h.setLevel(level)
    h.setFormatter(fmt)
    h.addFilter(req_filt)
    root.addHandler(h)

    log_dir_raw = (settings.LOG_FILE_DIR or "").strip()
    if log_dir_raw:
        log_dir = Path(log_dir_raw)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "app.log"
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(fmt)
        fh.addFilter(req_filt)
        root.addHandler(fh)


def log_app_error(status_code: int, code: str | None, message: str, *, request_id: str | None = None) -> None:
    """可恢复错误：写 error 日志（不含口令/token；仅摘要）。"""
    extra: dict = {}
    if request_id:
        extra["request_id"] = request_id
    logging.getLogger("app.error").error(
        "handled_error status=%s code=%s detail=%s",
        status_code,
        code or "-",
        (message or "")[:500],
        extra=extra,
    )

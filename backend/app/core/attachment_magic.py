"""附件「魔数」与声明扩展名一致性校验，降低伪装扩展名风险。"""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import AppError
from app.core.upload_codes import UPLOAD_ATTACHMENT_MAGIC_MISMATCH

# Microsoft OLE 复合文档（旧版 .doc / .xls / .ppt）
_OLE_HEADER = bytes.fromhex("d0cf11e0a1b11ae1")

_READ_BYTES = 64


def assert_attachment_file_magic_matches_extension(*, file_path: Path, ext: str) -> None:
    """读取文件头若干字节，与 ``ext``（不含点、小写）比对；不匹配则抛 ``UPLOAD_ATTACHMENT_MAGIC_MISMATCH``。"""
    ext_l = (ext or "").strip().lower().lstrip(".")
    if not ext_l:
        raise AppError("附件扩展名为空", status_code=400, code=UPLOAD_ATTACHMENT_MAGIC_MISMATCH)

    if ext_l == "txt":
        return

    try:
        head = file_path.read_bytes()[:_READ_BYTES]
    except OSError as e:
        raise AppError(f"无法读取附件以校验内容：{e}", status_code=500, code="ATTACHMENT_MAGIC_READ_FAILED") from e

    if len(head) < 4:
        raise AppError("附件过短，无法完成内容校验", status_code=400, code=UPLOAD_ATTACHMENT_MAGIC_MISMATCH)

    if not _head_matches_extension(head, ext_l):
        raise AppError(
            "附件内容与扩展名不一致（可能被伪装成其它类型），请检查文件后重试",
            status_code=400,
            code=UPLOAD_ATTACHMENT_MAGIC_MISMATCH,
        )


def _head_matches_extension(head: bytes, ext_l: str) -> bool:
    if ext_l in ("jpg", "jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext_l == "png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext_l == "gif":
        return head[:6] in (b"GIF87a", b"GIF89a")
    if ext_l == "webp":
        return len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if ext_l == "bmp":
        return head[:2] == b"BM"
    if ext_l == "pdf":
        return head.startswith(b"%PDF")
    if ext_l in ("zip", "docx", "xlsx", "pptx"):
        return (
            head.startswith(b"PK\x03\x04")
            or head.startswith(b"PK\x05\x06")
            or head.startswith(b"PK\x07\x08")
        )
    if ext_l in ("doc", "xls", "ppt"):
        return head[:8] == _OLE_HEADER
    # 白名单内新增扩展名：未配置魔数时放行（由扩展名白名单与其它策略兜底）
    return True

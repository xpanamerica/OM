"""阶段 14：概念 / 学习路径文本规范化。"""

from __future__ import annotations

import unicodedata


def normalize_concept_name(value: str) -> str:
    s = unicodedata.normalize("NFKC", value).strip()
    if not s:
        raise ValueError("概念名称不能为空")
    if len(s) > 128:
        raise ValueError("概念名称过长（最多 128 字符）")
    return s


def normalize_concept_description(value: str | None, *, max_len: int = 4000) -> str | None:
    if value is None:
        return None
    s = unicodedata.normalize("NFKC", value).strip()
    if not s:
        return None
    if len(s) > max_len:
        raise ValueError(f"描述过长（最多 {max_len} 字符）")
    return s


def normalize_learning_path_title(value: str) -> str:
    s = unicodedata.normalize("NFKC", value).strip()
    if not s:
        raise ValueError("标题不能为空")
    if len(s) > 255:
        raise ValueError("标题过长（最多 255 字符）")
    return s


def normalize_learning_path_description(value: str | None, *, max_len: int = 8000) -> str | None:
    if value is None:
        return None
    s = unicodedata.normalize("NFKC", value).strip()
    if not s:
        return None
    if len(s) > max_len:
        raise ValueError(f"描述过长（最多 {max_len} 字符）")
    return s

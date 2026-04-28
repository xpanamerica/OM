"""分类 / 标签名称规范化（展示与唯一性一致）。"""

from __future__ import annotations

import unicodedata


def normalize_taxonomy_name(value: str) -> str:
    """NFKC 规范化并去首尾空白；用于写入与查重前的规范化。

    长度按规范化后的 UTF-8 字符数校验，最大 64（与列定义一致）。
    """
    s = unicodedata.normalize("NFKC", value).strip()
    if not s:
        raise ValueError("名称不能为空")
    if len(s) > 64:
        raise ValueError("名称过长")
    return s


def normalize_taxonomy_name_lookup(value: str) -> str:
    """查重用的规范化（不重复抛出「不能为空」类校验，供 repository 防御性调用）。"""
    return unicodedata.normalize("NFKC", value).strip().lower()


def normalize_taxonomy_description(value: str | None, *, max_len: int = 512) -> str | None:
    """分类说明：NFKC + trim；空串视为未填（None）。长度按规范化后的字符数校验。"""
    if value is None:
        return None
    s = unicodedata.normalize("NFKC", value).strip()
    if not s:
        return None
    if len(s) > max_len:
        raise ValueError(f"说明过长（最多 {max_len} 字符）")
    return s

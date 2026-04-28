import pytest

from app.core.taxonomy_text import normalize_taxonomy_description


def test_normalize_description_nfkc_and_trim():
    s = normalize_taxonomy_description("  \u3000ab\u3000  ")
    assert s == "ab"


def test_normalize_description_empty_to_none():
    assert normalize_taxonomy_description(None) is None
    assert normalize_taxonomy_description("  \u3000  ") is None


def test_normalize_description_too_long():
    with pytest.raises(ValueError, match="说明过长"):
        normalize_taxonomy_description("x" * 513)

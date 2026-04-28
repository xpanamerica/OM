"""video_http：ETag 与 If-None-Match 纯函数。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.v1.video_http import if_none_match_matches, weak_etag_for_video


def test_weak_etag_changes_with_updated_at():
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
    vid = uuid.uuid4()
    a = SimpleNamespace(id=vid, updated_at=t0, row_version=1)
    b = SimpleNamespace(id=vid, updated_at=t1, row_version=1)
    assert weak_etag_for_video(a) != weak_etag_for_video(b)


def test_weak_etag_changes_with_row_version():
    t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    vid = uuid.uuid4()
    a = SimpleNamespace(id=vid, updated_at=t, row_version=1)
    b = SimpleNamespace(id=vid, updated_at=t, row_version=2)
    assert weak_etag_for_video(a) != weak_etag_for_video(b)


def test_weak_etag_changes_with_vod_detail_tier():
    t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    vid = uuid.uuid4()
    row = SimpleNamespace(id=vid, updated_at=t, row_version=1)
    assert weak_etag_for_video(row, vod_detail_tier="full") != weak_etag_for_video(
        row, vod_detail_tier="redacted"
    )


def test_if_none_match_accepts_list_and_star():
    etag = 'W/"abc123"'
    assert if_none_match_matches(f'{etag}, W/"other"', etag) is True
    assert if_none_match_matches("*", etag) is True
    assert if_none_match_matches('W/"nomatch"', etag) is False

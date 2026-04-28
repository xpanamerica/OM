"""comment_http：评论列表 ETag 纯函数。"""

import uuid
from datetime import datetime, timezone

from app.api.v1.comment_http import weak_etag_for_comment_list_page


def test_weak_etag_comment_list_changes_with_total():
    vid = uuid.uuid4()
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = weak_etag_for_comment_list_page(
        video_id=vid, total=1, max_updated_at=t0, limit=10, offset=0, cursor_key=""
    )
    b = weak_etag_for_comment_list_page(
        video_id=vid, total=2, max_updated_at=t0, limit=10, offset=0, cursor_key=""
    )
    assert a != b


def test_weak_etag_comment_list_changes_with_pagination():
    vid = uuid.uuid4()
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = weak_etag_for_comment_list_page(
        video_id=vid, total=1, max_updated_at=t0, limit=10, offset=0, cursor_key=""
    )
    b = weak_etag_for_comment_list_page(
        video_id=vid, total=1, max_updated_at=t0, limit=10, offset=10, cursor_key=""
    )
    assert a != b

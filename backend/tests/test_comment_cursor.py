"""评论列表游标编解码。"""

import uuid

from app.core.comment_cursor import decode_comment_list_cursor, encode_comment_list_cursor


def test_comment_cursor_roundtrip():
    cid = uuid.uuid4()
    tok = encode_comment_list_cursor(comment_id=cid)
    dec = decode_comment_list_cursor(tok)
    assert dec == cid


def test_comment_cursor_decode_invalid():
    assert decode_comment_list_cursor("") is None
    assert decode_comment_list_cursor("@@@") is None

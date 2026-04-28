import uuid

from app.core.taxonomy_cursor import decode_taxonomy_cursor, encode_taxonomy_cursor


def test_encode_decode_roundtrip():
    uid = uuid.uuid4()
    tok = encode_taxonomy_cursor(name="Hello", row_id=uid)
    n, i = decode_taxonomy_cursor(tok)
    assert n == "Hello"
    assert i == uid

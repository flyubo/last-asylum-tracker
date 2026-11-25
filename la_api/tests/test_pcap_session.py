from la_api.pcap_session import parse_protobuf_fields
from la_api.socket_client import _int_field, _string_field


def test_login_notice_protobuf_fields_round_trip():
    body = _int_field(1, 139) + _string_field(2, "test-account") + _string_field(3, "ko")
    assert parse_protobuf_fields(body) == [(1, 0, 139), (2, 2, b"test-account"), (3, 2, b"ko")]


def test_reconnect_payload_field_numbers():
    body = _string_field(1, "test-account") + _int_field(2, 123456) + _string_field(3, "test-token")
    assert parse_protobuf_fields(body) == [(1, 2, b"test-account"), (2, 0, 123456), (3, 2, b"test-token")]

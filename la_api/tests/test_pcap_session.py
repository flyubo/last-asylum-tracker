from la_api.pcap_session import parse_protobuf_fields
from la_api.socket_client import _int_field, _string_field


def test_login_notice_protobuf_fields_round_trip():
    body = _int_field(1, 139) + _string_field(2, "test-account") + _string_field(3, "ko")
    assert parse_protobuf_fields(body) == [(1, 0, 139), (2, 2, b"test-account"), (3, 2, b"ko")]


def test_reconnect_payload_field_numbers():
    body = _string_field(1, "test-account") + _int_field(2, 123456) + _string_field(3, "test-token")
    assert parse_protobuf_fields(body) == [(1, 2, b"test-account"), (2, 0, 123456), (3, 2, b"test-token")]


def test_captured_session_keeps_exact_notice_body():
    from la_api.pcap_session import CapturedSession
    body = b"\x08\x8b\x01\x12\x03abc"
    session = CapturedSession("abc", 1, "hidden", 139, "127.0.0.1", 9929, b"reconnect", body)
    assert session.notice_body == body


def test_captured_session_keeps_startup_frames():
    from la_api.pcap_session import CapturedSession
    frames = [("GetUnionHelpListC2S", b""), ("LoginSuccessC2S", b"\\x08\\x01")]
    session = CapturedSession("abc", 1, "hidden", 139, "127.0.0.1", 9929,
                              b"reconnect", b"notice", frames)
    assert session.startup_frames == frames

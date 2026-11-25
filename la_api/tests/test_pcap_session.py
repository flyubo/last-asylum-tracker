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



def test_reconnect_request_uses_fresh_token_from_server_response():
    from la_api.pcap_session import _replace_reconnect_token
    old_token = "A" * 96
    fresh_token = "B" * 96
    body = _string_field(1, "test-account") + _int_field(2, 123456) + _string_field(3, old_token)
    refreshed = _replace_reconnect_token(body, fresh_token)
    fields = parse_protobuf_fields(refreshed)
    assert fields == [
        (1, 2, b"test-account"),
        (2, 0, 123456),
        (3, 2, fresh_token.encode("ascii")),
    ]


def test_reconnect_token_refresh_refuses_ambiguous_fields():
    import pytest
    from la_api.pcap_session import _replace_reconnect_token
    token = "A" * 96
    body = _string_field(1, token) + _string_field(2, token)
    with pytest.raises(ValueError, match="exactly one"):
        _replace_reconnect_token(body, "B" * 96)



def test_startup_capture_keeps_all_frames_after_reconnect():
    from types import SimpleNamespace
    from la_api.pcap_session import _capture_startup_frames
    frames = [
        SimpleNamespace(name="LoginNoticeC2S", body=b"notice"),
        SimpleNamespace(name="LoginReconnectC2S", body=b"reconnect"),
        SimpleNamespace(name="GetUnionHelpListC2S", body=b""),
        SimpleNamespace(name="LoginSuccessC2S", body=b"success"),
        SimpleNamespace(name="GetPlayerMailTabC2S", body=b"mail"),
        SimpleNamespace(name="EyGameUpdateClientInfoC2S", body=b"client"),
    ]
    assert _capture_startup_frames(frames) == [
        ("GetUnionHelpListC2S", b""),
        ("LoginSuccessC2S", b"success"),
        ("GetPlayerMailTabC2S", b"mail"),
        ("EyGameUpdateClientInfoC2S", b"client"),
    ]

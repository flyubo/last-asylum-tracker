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



def test_connect_replays_handshake_in_captured_stages(monkeypatch):
    from la_api.pcap_session import CapturedSession
    from la_api.protocol import Frame
    from la_api.socket_client import JuFengClient

    session = CapturedSession(
        "test-account", 1, "hidden", 139, "127.0.0.1", 9929,
        _string_field(3, "A" * 96), b"notice",
        [("GetUnionHelpListC2S", b""), ("LoginSuccessC2S", b"success")],
    )
    client = JuFengClient(session)
    monkeypatch.setattr("la_api.socket_client.socket.create_connection", lambda *a, **k: object())

    events = []
    monkeypatch.setattr(client, "_send", lambda name, body: events.append(("send", name)))

    nested_login = b"\x20\x7b"  # protobuf field 4 (gameUid) = 123
    response_body = b"\x0a\x02" + nested_login

    def fake_wait_sequence(expected, timeout=None):
        events.append(("wait", tuple(expected)))
        if expected == ["EyGameLoginReconnectRespS2C", "EyGameMiddleAgesReconnectRespS2C"]:
            return [
                Frame("EyGameLoginReconnectRespS2C", response_body, False, 1),
                Frame("EyGameMiddleAgesReconnectRespS2C", b"", False, 2),
            ]
        return [
            Frame(
                name,
                (_string_field(2, "B" * 96) if name == "LoginReconnectTokenKeyS2C" else b""),
                False,
                i + 1,
            )
            for i, name in enumerate(expected)
        ]

    monkeypatch.setattr(client, "_wait_sequence", fake_wait_sequence)
    result = client.connect()

    assert result["game_uid"] == 123
    assert parse_protobuf_fields(session.reconnect_body) == [(3, 2, b"B" * 96)]
    assert session.token_key == "B" * 96
    assert events == [
        ("send", "LoginNoticeC2S"),
        ("wait", ("LoginNoticeS2C", "AckCode")),
        ("send", "LoginReconnectC2S"),
        ("wait", ("AckCode", "LoginReconnectTokenKeyS2C")),
        ("wait", ("EyGameLoginReconnectRespS2C", "EyGameMiddleAgesReconnectRespS2C")),
        ("send", "GetUnionHelpListC2S"),
        ("send", "LoginSuccessC2S"),
    ]


def test_wait_sequence_reports_last_ack_before_server_close(monkeypatch):
    from la_api.pcap_session import CapturedSession
    from la_api.protocol import Frame
    from la_api.socket_client import JuFengClient

    session = CapturedSession("abc", 1, "hidden", 139, "127.0.0.1", 9929)
    client = JuFengClient(session)
    received = iter([
        Frame("AckCode", b"", False, 1),
        ConnectionError("Server closed TCP connection"),
    ])

    def next_frame(timeout=None):
        item = next(received)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(client, "_next_frame", next_frame)
    import pytest
    with pytest.raises(ConnectionError, match=r"waiting for LoginReconnectTokenKeyS2C; matched=\['AckCode'\]"):
        client._wait_sequence(["AckCode", "LoginReconnectTokenKeyS2C"], timeout=1)

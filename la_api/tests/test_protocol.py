import gzip
import pytest
from la_api.protocol import FrameCounter, FrameDecoder, ProtocolError, encode_frame


def test_small_payload_round_trip_and_chunking():
    tx, rx = FrameCounter(), FrameDecoder(FrameCounter())
    wire = encode_frame("QueryRankInfoC2S", b"\\x08\\x8b\\x01", tx)
    assert rx.feed(wire[:5]) == []
    frame = rx.feed(wire[5:])[0]
    assert (frame.name, frame.body, frame.counter) == ("QueryRankInfoC2S", b"\\x08\\x8b\\x01", 1)


def test_gzip_payload_round_trip():
    payload = b"A" * 5000
    frame = FrameDecoder().feed(encode_frame("LargeResponseS2C", payload, FrameCounter()))[0]
    assert frame.compressed and frame.body == payload


def test_counter_wrap():
    counter = FrameCounter(0x70A2)
    assert counter.next() == 0
    assert counter.next() == 1


def test_checksum_mismatch_is_rejected():
    wire = bytearray(encode_frame("TestC2S", b"abc", FrameCounter()))
    wire[3] ^= 1
    with pytest.raises(ProtocolError):
        FrameDecoder().feed(bytes(wire))

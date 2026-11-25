"""Last Asylum JuFeng frame codec.

Transport framing only: this module does not perform account login or generate
SDK credentials.
"""
from __future__ import annotations

import gzip
import struct
from dataclasses import dataclass
from typing import Optional

MAGIC = b"\x70\xA3"
COUNTER_WRAP = 0x70A3
GZIP_THRESHOLD = 4096


class ProtocolError(ValueError):
    pass


@dataclass
class Frame:
    name: str
    body: bytes
    compressed: bool
    counter: int


class FrameCounter:
    """One counter per direction. First frame uses counter value 1."""
    def __init__(self, value: int = 0):
        if not 0 <= value < COUNTER_WRAP:
            raise ValueError("counter out of range")
        self.value = value

    def next(self) -> int:
        self.value = 0 if self.value + 1 == COUNTER_WRAP else self.value + 1
        return self.value


def _key_bytes(counter: int) -> tuple[int, int]:
    a = (~counter) & 0xFF
    b = ((a << 4) | (a >> 4)) & 0xFF
    return a, b


def _crypt(data: bytes, counter: int) -> bytes:
    a, b = _key_bytes(counter)
    return bytes((~((((a + byte) & 0xFF) ^ b))) & 0xFF for byte in data)


def _decrypt(data: bytes, counter: int) -> bytes:
    a, b = _key_bytes(counter)
    return bytes(((((~byte) & 0xFF) ^ b) - a) & 0xFF for byte in data)


def _checksum(data: bytes, counter: int) -> int:
    a, b = _key_bytes(counter)
    return (~(((sum(data) + a) & 0xFF) ^ b)) & 0xFF


def encode_frame(name: str, protobuf_body: bytes, counter: FrameCounter) -> bytes:
    if not name or not name.isascii():
        raise ProtocolError("message name must be non-empty ASCII")
    name_bytes = name.encode("ascii")
    if len(name_bytes) > 0xFFFF:
        raise ProtocolError("message name too long")
    if not isinstance(protobuf_body, (bytes, bytearray, memoryview)):
        raise TypeError("protobuf_body must be bytes-like")

    raw = bytes(protobuf_body)
    compressed = len(raw) >= GZIP_THRESHOLD
    wire_plain = gzip.compress(raw) if compressed else raw
    c = counter.next()
    encrypted = _crypt(wire_plain, c)
    flag = 1 if compressed else 0
    sign = _checksum(wire_plain, c) if wire_plain else 0
    return (
        MAGIC + bytes((flag, sign))
        + struct.pack(">H", len(name_bytes)) + name_bytes
        + struct.pack(">I", len(encrypted)) + encrypted
    )


class FrameDecoder:
    """Incremental decoder for one TCP receive direction."""
    def __init__(self, counter: Optional[FrameCounter] = None):
        self.counter = counter or FrameCounter()
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[Frame]:
        self.buffer.extend(data)
        frames: list[Frame] = []
        while True:
            if len(self.buffer) < 10:
                break
            if self.buffer[:2] != MAGIC:
                pos = self.buffer.find(MAGIC, 1)
                if pos < 0:
                    self.buffer[:] = self.buffer[-1:]
                    break
                del self.buffer[:pos]
                if len(self.buffer) < 10:
                    break
            flag, sign = self.buffer[2], self.buffer[3]
            name_len = struct.unpack_from(">H", self.buffer, 4)[0]
            name_end = 6 + name_len
            if len(self.buffer) < name_end + 4:
                break
            body_len = struct.unpack_from(">I", self.buffer, name_end)[0]
            frame_end = name_end + 4 + body_len
            if len(self.buffer) < frame_end:
                break
            name_bytes = bytes(self.buffer[6:name_end])
            encrypted = bytes(self.buffer[name_end + 4:frame_end])
            del self.buffer[:frame_end]
            try:
                name = name_bytes.decode("ascii")
            except UnicodeDecodeError as exc:
                raise ProtocolError("non-ASCII message name") from exc
            c = self.counter.next()
            wire_plain = _decrypt(encrypted, c)
            expected = _checksum(wire_plain, c) if wire_plain else 0
            if sign != expected:
                raise ProtocolError(
                    f"checksum mismatch for {name}: got {sign:#04x}, expected {expected:#04x}"
                )
            if flag not in (0, 1):
                raise ProtocolError(f"invalid compression flag: {flag}")
            try:
                body = gzip.decompress(wire_plain) if flag else wire_plain
            except OSError as exc:
                raise ProtocolError(f"invalid gzip payload for {name}") from exc
            frames.append(Frame(name, body, bool(flag), c))
        return frames

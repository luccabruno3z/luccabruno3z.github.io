"""Binary decoder for PRDemo files.

PRDemo files are zlib-compressed streams of length-prefixed messages.
All integers are little-endian. Strings are null-terminated.
"""

import io
import struct
import zlib
from dataclasses import dataclass
from typing import Iterator, Optional, Tuple

from .types import MessageType


class BinReader:
    """Low-level binary reader with little-endian decoding."""

    __slots__ = ("_buf", "_pos", "_size")

    def __init__(self, data: bytes, offset: int = 0, size: Optional[int] = None):
        self._buf = data
        self._pos = offset
        self._size = offset + (size if size is not None else len(data) - offset)

    @property
    def remaining(self) -> int:
        return self._size - self._pos

    def _read_raw(self, n: int) -> bytes:
        if self._pos + n > self._size:
            raise EOFError(f"Need {n} bytes but only {self.remaining} remain")
        result = self._buf[self._pos : self._pos + n]
        self._pos += n
        return result

    def read_uint8(self) -> int:
        return self._read_raw(1)[0]

    def read_int8(self) -> int:
        return struct.unpack_from("<b", self._read_raw(1))[0]

    def read_uint16(self) -> int:
        return struct.unpack_from("<H", self._read_raw(2))[0]

    def read_int16(self) -> int:
        return struct.unpack_from("<h", self._read_raw(2))[0]

    def read_uint32(self) -> int:
        return struct.unpack_from("<I", self._read_raw(4))[0]

    def read_int32(self) -> int:
        return struct.unpack_from("<i", self._read_raw(4))[0]

    def read_float32(self) -> float:
        return struct.unpack_from("<f", self._read_raw(4))[0]

    def read_bool(self) -> bool:
        return self.read_uint8() != 0

    def read_string(self) -> str:
        """Read a null-terminated string."""
        parts = []
        while True:
            b = self._read_raw(1)[0]
            if b == 0:
                break
            parts.append(b)
        return bytes(parts).decode("utf-8", errors="replace")

    def read_remaining(self) -> bytes:
        """Read all remaining bytes."""
        return self._read_raw(self.remaining)


@dataclass
class RawMessage:
    """A raw message with its type and binary payload reader."""

    msg_type: MessageType
    reader: BinReader


def _decompress_or_raw(data: bytes) -> bytes:
    """Try zlib decompression; if it fails, assume the data is already raw."""
    try:
        return zlib.decompress(data)
    except zlib.error:
        pass
    # Some tracker files use a zlib stream without the standard header
    try:
        return zlib.decompress(data, -zlib.MAX_WBITS)
    except zlib.error:
        pass
    # Not compressed — use as-is
    return data


class DemoReader:
    """Iterator over messages in a PRDemo file.

    The file format is:
    1. File may be zlib-compressed or raw
    2. Decompressed stream: sequence of messages
    3. Each message: uint16 length, then `length` bytes of payload
    4. Payload: first byte = MessageType, rest = type-specific data
    """

    def __init__(self, data: bytes):
        """Initialize from decompressed data."""
        self._data = data
        self._pos = 0
        self._size = len(data)

    @classmethod
    def from_file(cls, path: str) -> "DemoReader":
        """Open a .PRdemo file (zlib-compressed or raw)."""
        with open(path, "rb") as f:
            raw = f.read()
        return cls(_decompress_or_raw(raw))

    @classmethod
    def from_bytes(cls, data: bytes) -> "DemoReader":
        """Create reader from bytes (tries zlib decompression, falls back to raw)."""
        return cls(_decompress_or_raw(data))

    def __iter__(self) -> Iterator[RawMessage]:
        return self

    def __next__(self) -> RawMessage:
        if self._pos + 2 > self._size:
            raise StopIteration

        msg_len = struct.unpack_from("<H", self._data, self._pos)[0]
        self._pos += 2

        if self._pos + msg_len > self._size:
            raise StopIteration

        if msg_len < 1:
            raise StopIteration

        payload_start = self._pos
        self._pos += msg_len

        type_byte = self._data[payload_start]
        try:
            msg_type = MessageType(type_byte)
        except ValueError:
            msg_type = MessageType(type_byte) if type_byte in MessageType._value2member_map_ else None
            if msg_type is None:
                # Unknown message type — skip it
                return self.__next__()

        reader = BinReader(self._data, payload_start + 1, msg_len - 1)
        return RawMessage(msg_type=msg_type, reader=reader)

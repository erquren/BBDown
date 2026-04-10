"""gRPC message packing/unpacking ported from C# AppHelper.cs (PackMessage/ReadMessage)."""

import gzip
import struct


def pack_message(data: bytes) -> bytes:
    """Add gRPC framing header: 1-byte compressed flag + 4-byte big-endian length + gzip body."""
    compressed = gzip.compress(data)
    header = struct.pack(">BI", 1, len(compressed))
    return header + compressed


def read_message(data: bytes) -> bytes:
    """Read a gRPC framed response: parse 5-byte header, decompress if needed."""
    flag = data[0]
    size = struct.unpack(">I", data[1:5])[0]
    if flag == 1:
        return gzip.decompress(data[5:])
    return data[5 : 5 + size]

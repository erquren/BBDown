"""BV/AV ID converter for Bilibili.

Ported from: https://github.com/Colerar/abv/blob/main/src/lib.rs
"""

_XOR_CODE = 23442827791579
_MASK_CODE = (1 << 51) - 1
_MAX_AID = _MASK_CODE + 1
_MIN_AID = 1
_BASE = 58
_BV_LEN = 9

_ALPHABET = b"FcwAPNKTMug3GV5Lj7EJnHpWsx4tb8haYeviqBz6rkCy12mUSDQX9RdoZf"
_REV_ALPHABET = {b: i for i, b in enumerate(_ALPHABET)}


def encode(avid: int) -> str:
    """Encode an AV ID to a BV ID string."""
    if avid < _MIN_AID:
        raise ValueError(f"Av {avid} is smaller than {_MIN_AID}")
    if avid >= _MAX_AID:
        raise ValueError(f"Av {avid} is bigger than {_MAX_AID}")

    bvid = bytearray(_BV_LEN)
    tmp = (_MAX_AID | avid) ^ _XOR_CODE

    i = _BV_LEN - 1
    while tmp != 0:
        bvid[i] = _ALPHABET[tmp % _BASE]
        tmp //= _BASE
        i -= 1

    bvid[0], bvid[6] = bvid[6], bvid[0]
    bvid[1], bvid[4] = bvid[4], bvid[1]

    return "BV1" + bvid.decode("ascii")


def decode(bvid_str: str) -> int:
    """Decode a BV ID string (without 'BV1' prefix) to an AV ID."""
    if len(bvid_str) != _BV_LEN:
        raise ValueError(f"Bv BV1{bvid_str} must be 12 chars")

    bvid = bytearray(bvid_str.encode("ascii"))
    bvid[0], bvid[6] = bvid[6], bvid[0]
    bvid[1], bvid[4] = bvid[4], bvid[1]

    avid = 0
    for b in bvid:
        avid = avid * _BASE + _REV_ALPHABET[b]

    return (avid & _MASK_CODE) ^ _XOR_CODE

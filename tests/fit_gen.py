"""Minimal FIT file generator for tests.

Produces a valid .FIT file containing file_id, session and record messages
that can be parsed by fitparse.
"""

import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path

FIT_EPOCH_UNIX = 631065600  # 1989-12-31T00:00:00Z (unix seconds)
PROTOCOL_VERSION = 0x10
PROFILE_VERSION = 0x0E3A

# Base type ids (must match fitparse's BASE_TYPES)
ENUM = 0x00
UINT8 = 0x02
UINT16 = 0x84
SINT32 = 0x85
UINT32 = 0x86

# Global message numbers
FILE_ID_MSG = 0
SESSION_MSG = 18
RECORD_MSG = 20

SPORT_IDS = {
    "generic": 0,
    "running": 1,
    "cycling": 2,
    "swimming": 5,
    "walking": 11,
    "hiking": 17,
}

_CRC_TABLE = (
    0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
    0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400,
)


def _crc16(data: bytes, crc: int = 0) -> int:
    """FIT CRC-16, byte-for-byte compatible with fitparse.Crc."""
    for byte in data:
        tmp = _CRC_TABLE[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc = crc ^ tmp ^ _CRC_TABLE[byte & 0xF]
        tmp = _CRC_TABLE[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc = crc ^ tmp ^ _CRC_TABLE[(byte >> 4) & 0xF]
    return crc & 0xFFFF


def _definition_message(local_type: int, global_num: int, fields: list) -> bytes:
    """Build a definition message (record header bit 6 set = definition)."""
    body = bytearray()
    body.append(0x00)  # reserved
    body.append(0x00)  # architecture: little endian
    body += struct.pack("<H", global_num)
    body.append(len(fields))
    for field_num, size, base_type in fields:
        body.append(field_num)
        body.append(size)
        body.append(base_type)
    return bytes([0x40 | local_type]) + bytes(body)


def _data_message(local_type: int, values: list) -> bytes:
    """Build a data message (normal header: bit 7=0, bit 6=0)."""
    return bytes([local_type & 0x0F]) + b"".join(values)


def generate_fit(
    file_path,
    n_records=100,
    sport="running",
    start=None,
    with_session=True,
    with_records=True,
):
    """Generate a valid FIT file at file_path."""
    if start is None:
        start = datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
    start_ts = int(start.timestamp()) - FIT_EPOCH_UNIX

    data = bytearray()

    # --- file_id (local type 0) ---
    data += _definition_message(0, FILE_ID_MSG, [(0, 1, UINT8), (4, 4, UINT32)])
    data += _data_message(0, [struct.pack("<B", 6), struct.pack("<I", start_ts)])

    # --- record samples ---
    rows = []
    for i in range(n_records):
        t = start + timedelta(seconds=10 * i)
        rows.append(
            {
                "ts": int(t.timestamp()) - FIT_EPOCH_UNIX,
                "lat": 37.7749 + i * 0.0001,
                "lon": -122.4194 + i * 0.0002,
                "alt": 10.0 + (i % 50) * 0.5,
                "hr": 140 + (i % 20),
                "dist": i * 10.0,
                "speed": 3.0 + (i % 5) * 0.5,
                "power": 150 + (i % 40),
            }
        )

    # --- session (local type 1) ---
    if with_session:
        hrs = [r["hr"] for r in rows]
        alt_deltas = (
            [rows[i + 1]["alt"] - rows[i]["alt"] for i in range(n_records - 1)]
            if n_records > 1
            else []
        )
        ascent = sum(max(d, 0.0) for d in alt_deltas)
        descent = sum(max(-d, 0.0) for d in alt_deltas)
        total_time = max((n_records - 1) * 10.0, 0.0)
        total_dist = rows[-1]["dist"] if rows else 0.0

        session_fields = [
            (5, 1, ENUM),     # sport
            (7, 4, UINT32),   # start_time
            (8, 4, UINT32),   # total_timer_time (s * 1000)
            (9, 4, UINT32),   # total_distance (m * 100)
            (21, 2, UINT16),  # total_ascent (m)
            (22, 2, UINT16),  # total_descent (m)
            (16, 1, UINT8),   # avg_heart_rate
            (17, 1, UINT8),   # max_heart_rate
        ]
        data += _definition_message(1, SESSION_MSG, session_fields)
        data += _data_message(
            1,
            [
                struct.pack("<B", SPORT_IDS.get(sport, 1)),
                struct.pack("<I", start_ts),
                struct.pack("<I", int(total_time * 1000)),
                struct.pack("<I", int(total_dist * 100)),
                struct.pack("<H", int(ascent)),
                struct.pack("<H", int(descent)),
                struct.pack("<B", int(sum(hrs) / len(hrs))),
                struct.pack("<B", max(hrs)),
            ],
        )

    # --- records (local type 2) ---
    if with_records:
        record_fields = [
            (253, 4, UINT32),  # timestamp
            (0, 4, SINT32),    # position_lat
            (1, 4, SINT32),    # position_long
            (2, 2, UINT16),    # altitude
            (3, 1, UINT8),     # heart_rate
            (5, 4, UINT32),    # distance
            (6, 2, UINT16),    # speed
            (7, 2, UINT16),    # power
        ]
        data += _definition_message(2, RECORD_MSG, record_fields)
        for r in rows:
            data += _data_message(
                2,
                [
                    struct.pack("<I", r["ts"]),
                    struct.pack("<i", int(r["lat"] * (2 ** 31 / 180.0))),
                    struct.pack("<i", int(r["lon"] * (2 ** 31 / 180.0))),
                    struct.pack("<H", int((r["alt"] + 500) * 5)),
                    struct.pack("<B", r["hr"]),
                    struct.pack("<I", int(r["dist"] * 100)),
                    struct.pack("<H", int(r["speed"] * 1000)),
                    struct.pack("<H", r["power"]),
                ],
            )

    body = bytes(data)
    header = (
        bytes([12, PROTOCOL_VERSION])
        + struct.pack("<H", PROFILE_VERSION)
        + struct.pack("<I", len(body))
        + b".FIT"
    )
    crc = _crc16(header + body)
    Path(file_path).write_bytes(header + body + struct.pack("<H", crc))

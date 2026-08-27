"""生成测试用 FIT（Flexible and Interoperable Data Transfer）文件。

FIT 是 Garmin 等运动设备使用的二进制数据格式。
此脚本生成包含 GPS、心率、速度、步频等数据的模拟跑步活动文件。
"""

import struct
from datetime import datetime, timedelta


def _crc(data: bytes) -> int:
    """计算 FIT CRC（16-bit CRC-CCitt）。"""
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x4001
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def _write_crc(data: bytes) -> bytes:
    """在数据后追加 CRC。"""
    crc_val = _crc(data)
    crc_bytes = struct.pack("<H", crc_val)
    return data + crc_bytes


def _encode_value(value, type_num):
    """根据 FIT 类型编码值为字节。"""
    type_map = {
        0: ("uint8", 1),
        1: ("int8", 1),
        2: ("uint16", 2),
        3: ("int16", 2),
        4: ("uint32", 4),
        5: ("int32", 4),
        6: ("float32", 4),
        7: ("float64", 8),
        10: ("uint8z", 1),
        11: ("uint16z", 2),
        12: ("uint32z", 4),
        13: ("string", None),
    }
    type_name, size = type_map.get(type_num, ("uint8", 1))

    if type_name == "string":
        if isinstance(value, str):
            value = value.encode("utf-8")
        return value
    elif type_name.startswith("uint"):
        if size == 1:
            return struct.pack("<B", int(value))
        elif size == 2:
            return struct.pack("<H", int(value))
        elif size == 4:
            return struct.pack("<I", int(value))
    elif type_name.startswith("int"):
        if size == 1:
            return struct.pack("<b", int(value))
        elif size == 2:
            return struct.pack("<h", int(value))
        elif size == 4:
            return struct.pack("<i", int(value))
    elif type_name == "float32":
        return struct.pack("<f", float(value))
    elif type_name == "float64":
        return struct.pack("<d", float(value))
    return b""


def make_definition_msg(local_num, fields):
    """构造 FIT 定义消息。

    :param local_num: 本地消息编号
    :param fields: [(field_num, type_num), ...]
    """
    header = bytes([0x40 | local_num])
    content = struct.pack("<BBB", 0, 0, len(fields))
    for field_num, type_num in fields:
        content += struct.pack("<BB", field_num, type_num)
    return _write_crc(header + content)


def make_data_msg(local_num, values, def_fields):
    """构造 FIT 数据消息。

    :param local_num: 本地消息编号
    :param values: [value1, value2, ...]
    :param def_fields: [(field_num, type_num), ...]
    """
    header = bytes([0x00 | local_num])
    content = b""
    for (_, type_num), val in zip(def_fields, values):
        content += _encode_value(val, type_num)
    return _write_crc(header + content)


def generate_running_fit(filename: str = "test_running.fit"):
    """生成一个模拟的 5 公里跑步活动 FIT 文件。"""

    base_time = datetime(2024, 8, 15, 7, 0, 0)
    # FIT timestamp: seconds since UTC 2000-12-31
    fit_epoch = datetime(2000, 12, 31, 0, 0, 0)
    base_timestamp = int((base_time - fit_epoch).total_seconds())

    # 路线：北京奥森公园附近（模拟）
    center_lat = 39.9932
    center_lng = 116.3964

    # 生成 5 公里圆形路线
    import math
    num_points = 600  # 每 5 秒一个点，共 50 分钟
    points = []
    for i in range(num_points):
        t = i * 5  # 秒
        angle = (i / num_points) * 2 * math.pi
        radius = 400  # 米

        lat = center_lat + (radius / 111320) * math.sin(angle)
        lng = center_lng + (radius / (111320 * math.cos(math.radians(center_lat)))) * math.cos(angle)

        # 心率：从 140 到 165 逐渐升高
        hr = 140 + 25 * (i / num_points) + (hash(str(i)) % 5 - 2)

        # 速度：从 4.0 到 5.5 m/s，配速约 5:30-4:30 /km
        speed = 4.5 + 1.0 * math.sin(angle * 2) + (hash(str(i)) % 100 - 50) / 100

        # 步频：170-185 spm
        cadence = 175 + 10 * math.sin(angle * 3) + (hash(str(i * 7)) % 60 - 30) / 10
        cadence_byte = int(cadence / 2)

        # 海拔：45-55 米
        altitude = 50 + 5 * math.sin(angle * 4)

        # 距离
        distance = (radius * angle) / 1000  # km

        timestamp = base_timestamp + t

        points.append({
            "timestamp": timestamp,
            "lat": int(lat * 1e7),
            "lng": int(lng * 1e7),
            "altitude": int(altitude * 5),
            "speed": int(speed * 1000),
            "hr": int(hr),
            "cadence": cadence_byte,
            "distance": int(distance * 100),
        })

    # FIT 文件结构
    # 1. 文件头 (FIT 协议格式: header_size(1) + protocol_ver(1) + profile_ver(2) + data_size(4) + ".FIT"(4) = 12 bytes)
    header_size = 12
    protocol_ver = 0x10  # protocol 1.0
    profile_ver = 800    # profile 8.0 -> 8 * 100 + 0
    data_size_placeholder = 0

    # 先构建不含 CRC 的头部来计算数据大小
    header_no_crc = struct.pack("<BBHI4x", header_size, protocol_ver, profile_ver, data_size_placeholder)
    # header_no_crc 现在是 12 字节，但实际格式是:
    # Byte 0: header_size (uint8)
    # Byte 1: protocol_ver (uint8)  
    # Byte 2-3: profile_ver (uint16 LE)
    # Byte 4-7: data_size (uint32 LE)
    # Byte 8-11: 被 '4x' 跳过
    
    # 实际上 .FIT 是在位置 8-11，而 4x 是读 .FIT 时跳过的填充
    # 让我们重新按照正确布局构建
    header_base = bytearray()
    header_base.append(header_size)
    header_base.append(protocol_ver)
    header_base.extend(struct.pack("<H", profile_ver))
    header_base.extend(struct.pack("<I", data_size_placeholder))
    header_base.extend(b".FIT")  # bytes 8-11

    # 计算实际数据大小后再回填
    header_crc = _crc(bytes(header_base))
    fit_header = bytes(header_base)

    # 2. 定义消息
    # File Id message (local 0)
    file_id_def = make_definition_msg(0, [
        (0, 0),   # type (uint8)
        (1, 13),  # manufacturer (string)
        (2, 2),   # product (uint16)
        (3, 4),   # serial_number (uint32)
        (4, 4),   # time_created (uint32)
        (5, 13),  # product_name (string)
    ])

    # Record message (local 1) - GPS + 运动数据
    record_def = make_definition_msg(1, [
        (253, 4),  # timestamp (uint32)
        (0, 5),    # position_lat (int32)
        (1, 5),    # position_long (int32)
        (2, 2),    # altitude (uint16)
        (3, 2),    # speed (uint16)
        (4, 0),    # heart_rate (uint8)
        (5, 0),    # cadence (uint8)
        (6, 4),    # distance (uint32)
    ])

    # Device Info message (local 2)
    device_info_def = make_definition_msg(2, [
        (253, 4),  # timestamp
        (0, 0),    # device_index
        (1, 0),    # device_type
        (2, 2),    # manufacturer
        (3, 2),    # serial_number
        (4, 2),    # product
        (5, 2),    # software_version
    ])

    # 3. 数据消息
    data = b""

    # File ID
    data += make_data_msg(0, [1, b"Garmin", 1234, 1234567890, base_timestamp, b"Forerunner 945"],
                          [(0, 0), (1, 13), (2, 2), (3, 4), (4, 4), (5, 13)])

    # Device Info
    data += make_data_msg(2, [base_timestamp, 0, 1, 1, 12345, 3456, 540],
                          [(253, 4), (0, 0), (1, 0), (2, 2), (3, 2), (4, 2), (5, 2)])

    # Records
    for p in points:
        data += make_data_msg(1, [
            p["timestamp"], p["lat"], p["lng"], p["altitude"],
            p["speed"], p["hr"], p["cadence"], p["distance"]
        ], [(253, 4), (0, 5), (1, 5), (2, 2), (3, 2), (4, 0), (5, 0), (6, 4)])

    # 4. 构建完整文件：先计算数据大小，再回填头部
    definitions = file_id_def + record_def + device_info_def
    total_data = definitions + data
    data_size = len(total_data)

    # 重新构建带正确 data_size 的头部
    header_final = bytearray()
    header_final.append(header_size)
    header_final.append(protocol_ver)
    header_final.extend(struct.pack("<H", profile_ver))
    header_final.extend(struct.pack("<I", data_size))
    header_final.extend(b".FIT")

    # 头部 CRC (仅当 header_size > 12 时存在)
    # header_size=12 表示无 CRC，直接使用
    full_header = bytes(header_final)

    # 数据尾部 CRC
    data_crc = _crc(total_data)
    full_data = full_header + total_data + struct.pack("<H", data_crc)

    # 写入文件
    with open(filename, "wb") as f:
        f.write(full_data)

    print(f"FIT 文件已生成: {filename}")
    print(f"  时间: {base_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"  点数: {len(points)}")
    print(f"  时长: 50 分钟")
    print(f"  距离: ~5.0 km")
    print(f"  心率范围: 140-165 bpm")


def generate_long_run_fit(filename: str = "long_run.fit"):
    """生成一个模拟的 15 公里长距离跑步活动 FIT 文件。"""

    base_time = datetime(2024, 8, 17, 6, 30, 0)
    fit_epoch = datetime(2000, 12, 31, 0, 0, 0)
    base_timestamp = int((base_time - fit_epoch).total_seconds())

    center_lat = 39.9932
    center_lng = 116.3964

    import math
    num_points = 1800  # 每 5 秒一个点，共 150 分钟
    points = []
    for i in range(num_points):
        t = i * 5
        angle = (i / num_points) * 4 * math.pi
        radius = 800

        lat = center_lat + (radius / 111320) * math.sin(angle)
        lng = center_lng + (radius / (111320 * math.cos(math.radians(center_lat)))) * math.cos(angle)

        # 心率：稳定在 150-160 bpm
        hr = 150 + 10 * math.sin(angle * 0.5) + (hash(str(i)) % 6 - 3)

        # 速度：稳定 4.2-4.8 m/s
        speed = 4.5 + 0.3 * math.sin(angle) + (hash(str(i)) % 60 - 30) / 100

        # 步频：172-180 spm
        cadence = 176 + 4 * math.sin(angle * 2) + (hash(str(i * 5)) % 40 - 20) / 10
        cadence_byte = int(cadence / 2)

        # 海拔：40-60 米，有起伏
        altitude = 50 + 10 * math.sin(angle * 0.7)

        distance = (radius * angle) / 1000

        timestamp = base_timestamp + t

        points.append({
            "timestamp": timestamp,
            "lat": int(lat * 1e7),
            "lng": int(lng * 1e7),
            "altitude": int(altitude * 5),
            "speed": int(speed * 1000),
            "hr": int(hr),
            "cadence": cadence_byte,
            "distance": int(distance * 100),
        })

    # 构建 FIT 文件
    header_size = 12
    protocol_ver = 0x10
    profile_ver = 800

    file_id_def = make_definition_msg(0, [
        (0, 0), (1, 13), (2, 2), (3, 4), (4, 4), (5, 13),
    ])

    record_def = make_definition_msg(1, [
        (253, 4), (0, 5), (1, 5), (2, 2), (3, 2), (4, 0), (5, 0), (6, 4),
    ])

    device_info_def = make_definition_msg(2, [
        (253, 4), (0, 0), (1, 0), (2, 2), (3, 2), (4, 2), (5, 2),
    ])

    data = b""
    data += make_data_msg(0, [1, b"Garmin", 1234, 987654321, base_timestamp, b"Forerunner 945"],
                          [(0, 0), (1, 13), (2, 2), (3, 4), (4, 4), (5, 13)])
    data += make_data_msg(2, [base_timestamp, 0, 1, 1, 54321, 3456, 540],
                          [(253, 4), (0, 0), (1, 0), (2, 2), (3, 2), (4, 2), (5, 2)])
    for p in points:
        data += make_data_msg(1, [
            p["timestamp"], p["lat"], p["lng"], p["altitude"],
            p["speed"], p["hr"], p["cadence"], p["distance"]
        ], [(253, 4), (0, 5), (1, 5), (2, 2), (3, 2), (4, 0), (5, 0), (6, 4)])

    # 构建完整文件
    definitions = file_id_def + record_def + device_info_def
    total_data = definitions + data
    data_size = len(total_data)

    header_final = bytearray()
    header_final.append(header_size)
    header_final.append(protocol_ver)
    header_final.extend(struct.pack("<H", profile_ver))
    header_final.extend(struct.pack("<I", data_size))
    header_final.extend(b".FIT")

    full_header = bytes(header_final)
    data_crc = _crc(total_data)
    full_data = full_header + total_data + struct.pack("<H", data_crc)

    with open(filename, "wb") as f:
        f.write(full_data)

    print(f"FIT 文件已生成: {filename}")
    print(f"  时间: {base_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"  点数: {len(points)}")
    print(f"  时长: 150 分钟")
    print(f"  距离: ~15.0 km")
    print(f"  心率范围: 150-160 bpm")


if __name__ == "__main__":
    import os
    out_dir = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
    os.makedirs(out_dir, exist_ok=True)
    generate_running_fit(os.path.join(out_dir, "sample_run.fit"))
    generate_long_run_fit(os.path.join(out_dir, "long_run.fit"))
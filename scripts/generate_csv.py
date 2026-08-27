"""生成 CSV 格式的跑步活动测试数据。

这些数据模拟真实运动手表记录，包含 GPS、心率、配速、步频等信息。
"""

import csv
import math
from datetime import datetime, timedelta


def generate_run_csv(filename: str, duration_min: int = 50, distance_km: float = 5.0):
    """生成单次跑步活动的 CSV 文件。"""

    start_time = datetime(2024, 8, 15, 7, 0, 0)
    center_lat = 39.9932
    center_lng = 116.3964

    num_points = duration_min * 12  # 每 5 秒一个点
    interval_sec = 5

    rows = []
    for i in range(num_points):
        t = i * interval_sec
        angle = (i / num_points) * 2 * math.pi
        radius = (distance_km * 1000) / (2 * math.pi)

        lat = center_lat + (radius / 111320) * math.sin(angle)
        lng = center_lng + (radius / (111320 * math.cos(math.radians(center_lat)))) * math.cos(angle)

        # 心率：随时间上升
        hr = 140 + 25 * (i / num_points) + (hash(str(i)) % 5 - 2)
        hr = max(60, min(210, hr))

        # 配速：从 5:30 到 4:30 /km
        pace_sec_per_km = 330 - 60 * (i / num_points) + (hash(str(i)) % 20 - 10)
        pace_sec_per_km = max(240, min(420, pace_sec_per_km))

        # 速度（m/s）
        speed = 1000 / pace_sec_per_km

        # 步频：170-185 spm
        cadence = 175 + 10 * math.sin(angle * 3) + (hash(str(i * 7)) % 60 - 30) / 10
        cadence = max(120, min(220, cadence))

        # 海拔
        altitude = 50 + 5 * math.sin(angle * 4)

        # 累计距离
        cum_distance = (radius * angle) / 1000

        # 温度（°C）
        temp = 25 + 2 * math.sin(angle * 0.5)

        timestamp = start_time + timedelta(seconds=t)

        rows.append({
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "latitude": round(lat, 6),
            "longitude": round(lng, 6),
            "altitude_m": round(altitude, 1),
            "speed_mps": round(speed, 2),
            "pace_sec_per_km": int(pace_sec_per_km),
            "heart_rate_bpm": int(hr),
            "cadence_spm": int(cadence),
            "cumulative_distance_km": round(cum_distance, 3),
            "temperature_c": round(temp, 1),
        })

    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ 生成 {filename}: {len(rows)} 条记录, {duration_min} 分钟, {distance_km} km")


def generate_long_run_csv(filename: str):
    """生成长距离跑步（15km / 150min）的 CSV 文件。"""

    start_time = datetime(2024, 8, 17, 6, 30, 0)
    center_lat = 39.9932
    center_lng = 116.3964

    duration_min = 150
    distance_km = 15.0
    num_points = duration_min * 12

    rows = []
    for i in range(num_points):
        t = i * 5
        angle = (i / num_points) * 4 * math.pi
        radius = (distance_km * 1000) / (4 * math.pi)

        lat = center_lat + (radius / 111320) * math.sin(angle)
        lng = center_lng + (radius / (111320 * math.cos(math.radians(center_lat)))) * math.cos(angle)

        hr = 150 + 10 * math.sin(angle * 0.5) + (hash(str(i)) % 6 - 3)
        hr = max(60, min(210, hr))

        pace_sec_per_km = 360 - 20 * math.sin(angle) + (hash(str(i)) % 15 - 7)
        pace_sec_per_km = max(300, min(420, pace_sec_per_km))

        speed = 1000 / pace_sec_per_km
        cadence = 176 + 4 * math.sin(angle * 2) + (hash(str(i * 5)) % 40 - 20) / 10
        cadence = max(120, min(220, cadence))
        altitude = 50 + 10 * math.sin(angle * 0.7)
        cum_distance = (radius * angle) / 1000
        temp = 22 + 3 * math.sin(angle * 0.3)
        timestamp = start_time + timedelta(seconds=t)

        rows.append({
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "latitude": round(lat, 6),
            "longitude": round(lng, 6),
            "altitude_m": round(altitude, 1),
            "speed_mps": round(speed, 2),
            "pace_sec_per_km": int(pace_sec_per_km),
            "heart_rate_bpm": int(hr),
            "cadence_spm": int(cadence),
            "cumulative_distance_km": round(cum_distance, 3),
            "temperature_c": round(temp, 1),
        })

    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ 生成 {filename}: {len(rows)} 条记录, {duration_min} 分钟, {distance_km} km")


def generate_intervals_csv(filename: str):
    """生成间歇训练的 CSV 文件（400m × 8 间歇）。"""

    start_time = datetime(2024, 8, 18, 17, 0, 0)
    center_lat = 39.9932
    center_lng = 116.3964

    rows = []
    timestamp = start_time

    for interval in range(8):
        # 400m 快跑（约 75 秒，5:00/km 配速，心率 170+）
        for sec in range(0, 75, 5):
            t = sec
            angle = interval * 0.5 + (t / 75) * 0.02
            radius = 200

            lat = center_lat + (radius / 111320) * math.sin(angle)
            lng = center_lng + (radius / (111320 * math.cos(math.radians(center_lat)))) * math.cos(angle)

            hr = 165 + (sec / 75) * 15 + (hash(str(sec)) % 5 - 2)
            pace = 300 - 10 * math.sin(angle) + (hash(str(sec)) % 10 - 5)
            speed = 1000 / pace
            cadence = 180 + 5 + (hash(str(sec * 3)) % 10 - 5)
            altitude = 48 + 2 * math.sin(angle)
            cum_dist = interval * 0.4 + (t / 75) * 0.4
            temp = 28

            rows.append({
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "latitude": round(lat, 6),
                "longitude": round(lng, 6),
                "altitude_m": round(altitude, 1),
                "speed_mps": round(speed, 2),
                "pace_sec_per_km": int(pace),
                "heart_rate_bpm": int(hr),
                "cadence_spm": int(cadence),
                "cumulative_distance_km": round(cum_dist, 3),
                "temperature_c": round(temp, 1),
            })
            timestamp += timedelta(seconds=5)

        # 2 分钟慢跑恢复（心率 140 左右）
        for sec in range(0, 120, 5):
            angle = interval * 0.5 + 0.02 + (sec / 120) * 0.03
            radius = 200

            lat = center_lat + (radius / 111320) * math.sin(angle)
            lng = center_lng + (radius / (111320 * math.cos(math.radians(center_lat)))) * math.cos(angle)

            hr = 140 + (sec / 120) * 10 + (hash(str(sec + 100)) % 4 - 2)
            pace = 390 + (hash(str(sec + 200)) % 30 - 15)
            speed = 1000 / pace
            cadence = 170 + (hash(str(sec + 300)) % 20 - 10)
            altitude = 48 + 2 * math.sin(angle)
            cum_dist = interval * 0.4 + 0.4 + (sec / 120) * 0.15
            temp = 28

            rows.append({
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "latitude": round(lat, 6),
                "longitude": round(lng, 6),
                "altitude_m": round(altitude, 1),
                "speed_mps": round(speed, 2),
                "pace_sec_per_km": int(pace),
                "heart_rate_bpm": int(hr),
                "cadence_spm": int(cadence),
                "cumulative_distance_km": round(cum_dist, 3),
                "temperature_c": round(temp, 1),
            })
            timestamp += timedelta(seconds=5)

    filename = filename
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ 生成 {filename}: {len(rows)} 条记录, 8×400m 间歇训练")


if __name__ == "__main__":
    import os
    out_dir = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
    os.makedirs(out_dir, exist_ok=True)

    generate_run_csv(os.path.join(out_dir, "sample_run.csv"), duration_min=50, distance_km=5.0)
    generate_long_run_csv(os.path.join(out_dir, "long_run.csv"))
    generate_intervals_csv(os.path.join(out_dir, "intervals.csv"))
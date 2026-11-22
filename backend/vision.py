"""
Vision pipeline adapter.
In production: runs YOLOv8 on camera frames → vehicle counts + sizes.
For demo: simulates realistic traffic fluctuations on each segment.
Swap simulate_frame() with real_frame() once camera feed is connected.
"""
import math
import random
import time
from traffic_state import state_store

# Segments in our demo road network (matches graph.py node pairs)
DEMO_SEGMENTS = {
    "A-B": {"base_count": 8,  "speed_base": 45},
    "A-C": {"base_count": 3,  "speed_base": 60},
    "B-D": {"base_count": 12, "speed_base": 30},   # the congested bottleneck
    "C-D": {"base_count": 2,  "speed_base": 55},
    "B-E": {"base_count": 5,  "speed_base": 50},
    "E-D": {"base_count": 4,  "speed_base": 50},
}

_start_time = time.time()


def _sine_noise(t: float, period: float, amplitude: float, offset: float) -> float:
    return offset + amplitude * math.sin(2 * math.pi * t / period)


def simulate_frame():
    """
    Produce one round of synthetic segment observations.
    B-D is intentionally congested to trigger the conflict resolver.
    """
    t = time.time() - _start_time
    for seg_id, cfg in DEMO_SEGMENTS.items():
        noise = random.uniform(-1, 1)
        count = max(0, int(_sine_noise(t, period=60, amplitude=3,
                                       offset=cfg["base_count"]) + noise))
        # Gradually build up B-D congestion for demo effect
        if seg_id == "B-D":
            ramp = min(1.0, t / 30.0)   # fully congested after 30s
            count = int(count + ramp * 10)

        speed = max(5.0, cfg["speed_base"] - count * 2.0 + random.uniform(-2, 2))
        queue = max(0, count - 8)
        state_store.update_segment(seg_id, count, speed, queue)


def real_frame(camera_data: dict):
    """
    Adapter for real camera feed (Agros Atlas or any RTSP source).
    Expected camera_data format:
    {
        "segment_id": "A-B",
        "detections": [
            {"class": "car",   "bbox_px": [x1,y1,x2,y2], "confidence": 0.91},
            {"class": "truck", "bbox_px": [x1,y1,x2,y2], "confidence": 0.87},
            ...
        ],
        "frame_width_px": 1920,
        "frame_height_px": 1080,
        "calibrated_lane_width_m": 3.5,   # used for real-world size estimation
        "timestamp": 1700000000.0
    }
    """
    detections = camera_data.get("detections", [])
    segment_id = camera_data["segment_id"]

    # PCU weights: motorcycle=0.5, car=1, auto=1.2, bus=3, truck=2.5
    PCU_WEIGHT = {"motorcycle": 0.5, "bike": 0.5, "car": 1.0,
                  "auto": 1.2, "bus": 3.0, "truck": 2.5, "van": 1.5}

    pcu_total = sum(PCU_WEIGHT.get(d["class"], 1.0) for d in detections)
    vehicle_count = int(pcu_total)

    # Estimate avg speed from bbox motion (placeholder — needs frame pair)
    avg_speed = 40.0

    queue = max(0, vehicle_count - 8)
    state_store.update_segment(segment_id, vehicle_count, avg_speed, queue)

    return {"segment_id": segment_id, "pcu": pcu_total, "detections": len(detections)}


def estimate_vehicle_size(bbox_px: list, frame_width_px: int,
                           calibrated_lane_width_m: float) -> dict:
    """
    Estimate real-world vehicle footprint from bounding box.
    Uses homographic projection: known lane width as scale reference.
    """
    x1, y1, x2, y2 = bbox_px
    bbox_width_px = x2 - x1
    bbox_height_px = y2 - y1

    px_per_meter = frame_width_px / (calibrated_lane_width_m * 3)  # assume 3 lanes
    width_m = round(bbox_width_px / px_per_meter, 1)
    length_m = round(bbox_height_px / px_per_meter * 2.5, 1)  # foreshortening factor

    return {"width_m": width_m, "length_m": length_m}

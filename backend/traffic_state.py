"""
Live traffic state store.
Holds per-segment vehicle counts, density and speed updated by the vision pipeline.
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class SegmentState:
    segment_id: str
    vehicle_count: int = 0
    avg_speed_kmh: float = 50.0
    density: float = 0.0          # 0.0 (free) → 1.0 (jammed)
    queue_length: int = 0
    last_updated: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            "segment_id": self.segment_id,
            "vehicle_count": self.vehicle_count,
            "avg_speed_kmh": round(self.avg_speed_kmh, 1),
            "density": round(self.density, 2),
            "queue_length": self.queue_length,
            "last_updated": self.last_updated,
        }


class TrafficStateStore:
    """In-memory store for all segment states. Thread-safe via simple dict ops."""

    def __init__(self):
        self._segments: Dict[str, SegmentState] = {}
        self._pending_trips: List[dict] = []   # trips planned but not yet started

    def update_segment(self, segment_id: str, vehicle_count: int,
                       avg_speed_kmh: float, queue_length: int = 0):
        density = min(1.0, vehicle_count / 20.0)  # 20 vehicles = fully jammed
        self._segments[segment_id] = SegmentState(
            segment_id=segment_id,
            vehicle_count=vehicle_count,
            avg_speed_kmh=avg_speed_kmh,
            density=density,
            queue_length=queue_length,
            last_updated=time.time(),
        )

    def get_segment(self, segment_id: str) -> SegmentState:
        return self._segments.get(segment_id, SegmentState(segment_id=segment_id))

    def all_segments(self) -> Dict[str, dict]:
        return {sid: s.to_dict() for sid, s in self._segments.items()}

    def add_pending_trip(self, trip: dict):
        self._pending_trips.append(trip)

    def get_pending_trips(self) -> List[dict]:
        return list(self._pending_trips)

    def clear_pending_trips(self):
        self._pending_trips.clear()

    def remove_pending_trip(self, user_id: str):
        self._pending_trips = [t for t in self._pending_trips if t["user_id"] != user_id]


# Singleton
state_store = TrafficStateStore()

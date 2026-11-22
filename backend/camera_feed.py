"""
Agros Atlas camera feed adapter.
Connects to the Agros Atlas traffic camera API (when credentials are available)
and translates feed data into our internal vision pipeline format.

Usage:
  Set env vars:  AGROS_API_KEY, AGROS_BASE_URL
  Then call:     await poll_agros_feeds()  from the FastAPI background task.

If credentials are absent, falls back to vision.simulate_frame() automatically.
"""

import os
import httpx
import asyncio
from vision import real_frame, state_store

AGROS_BASE_URL = os.getenv("AGROS_BASE_URL", "https://api.agrosatlas.com/v1")
AGROS_API_KEY  = os.getenv("AGROS_API_KEY", "")

# Agros Atlas camera → our segment mapping.
# Fill this in once you get the camera list from the Agros dashboard.
# Format: { "agros_camera_id": "our_segment_id" }
CAMERA_SEGMENT_MAP: dict[str, str] = {
    # "cam_silk_board_01": "A-B",
    # "cam_koramangala_01": "B-D",
    # Add more as you onboard cameras
}


async def _fetch_camera_snapshot(session: httpx.AsyncClient, camera_id: str) -> dict | None:
    """Fetch the latest detection snapshot for a single camera."""
    try:
        resp = await session.get(
            f"{AGROS_BASE_URL}/cameras/{camera_id}/detections/latest",
            headers={"Authorization": f"Bearer {AGROS_API_KEY}"},
            timeout=5.0,
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"[Agros] Camera {camera_id} returned {resp.status_code}")
            return None
    except httpx.RequestError as e:
        print(f"[Agros] Request error for {camera_id}: {e}")
        return None


def _agros_to_vision_format(agros_data: dict, segment_id: str) -> dict:
    """
    Translate Agros Atlas API response to our internal vision format.
    Adjust field names below to match the actual Agros API schema.

    Expected Agros response (assumed — update when you get the API docs):
    {
        "camera_id": "cam_silk_board_01",
        "timestamp": 1700000000,
        "frame_width": 1920,
        "frame_height": 1080,
        "objects": [
            {"label": "car",   "bbox": [x1,y1,x2,y2], "confidence": 0.91},
            {"label": "truck", "bbox": [x1,y1,x2,y2], "confidence": 0.87}
        ]
    }
    """
    detections = [
        {
            "class": obj.get("label", "car"),
            "bbox_px": obj.get("bbox", [0, 0, 50, 30]),
            "confidence": obj.get("confidence", 1.0),
        }
        for obj in agros_data.get("objects", [])
    ]
    return {
        "segment_id": segment_id,
        "detections": detections,
        "frame_width_px": agros_data.get("frame_width", 1920),
        "frame_height_px": agros_data.get("frame_height", 1080),
        "calibrated_lane_width_m": 3.5,
        "timestamp": agros_data.get("timestamp", 0),
    }


async def poll_agros_feeds():
    """
    Poll all configured Agros Atlas cameras once and update traffic state.
    Call this in a background asyncio loop from main.py.
    Returns True if any real data was fetched, False if no cameras configured.
    """
    if not AGROS_API_KEY or not CAMERA_SEGMENT_MAP:
        return False   # caller should use simulate_frame() instead

    async with httpx.AsyncClient() as session:
        tasks = {
            cam_id: _fetch_camera_snapshot(session, cam_id)
            for cam_id in CAMERA_SEGMENT_MAP
        }
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for cam_id, result in zip(tasks.keys(), results):
            if isinstance(result, dict) and result:
                seg_id = CAMERA_SEGMENT_MAP[cam_id]
                vision_data = _agros_to_vision_format(result, seg_id)
                real_frame(vision_data)

    return True


async def list_available_cameras() -> list:
    """
    Discover all cameras available on the Agros Atlas account.
    Use this once to populate CAMERA_SEGMENT_MAP above.
    """
    if not AGROS_API_KEY:
        return []
    try:
        async with httpx.AsyncClient() as session:
            resp = await session.get(
                f"{AGROS_BASE_URL}/cameras",
                headers={"Authorization": f"Bearer {AGROS_API_KEY}"},
                timeout=10.0,
            )
            if resp.status_code == 200:
                return resp.json().get("cameras", [])
    except httpx.RequestError:
        pass
    return []

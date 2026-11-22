"""
TomTom Traffic Flow adapter.
Pulls live currentSpeed / freeFlowSpeed for each road segment midpoint.

Setup:
  1. Get a free key at https://developer.tomtom.com  (250k calls/month free)
  2. Add to backend/.env:
       TOMTOM_API_KEY=your_key_here

API used: Flow Segment Data
  GET https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json
      ?point={lat},{lon}&unit=KMPH&key={key}

Returns per-point:
  currentSpeed    — live speed km/h
  freeFlowSpeed   — free-flow reference speed km/h
  currentTravelTime  — seconds to traverse the segment
  freeFlowTravelTime — free-flow reference travel time
  confidence      — 0-1 data quality score
"""

import os
import asyncio
import httpx
from dotenv import load_dotenv
from traffic_state import state_store
from graph import NODES, EDGES

load_dotenv()

TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "")
TOMTOM_BASE    = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"

# Pre-compute midpoint lat/lon for each segment
def _midpoint(node_a: str, node_b: str) -> tuple[float, float]:
    lat_a, lon_a = NODES[node_a]
    lat_b, lon_b = NODES[node_b]
    return ((lat_a + lat_b) / 2, (lon_a + lon_b) / 2)

SEGMENT_MIDPOINTS: dict[str, tuple[float, float]] = {
    f"{u}-{v}": _midpoint(u, v)
    for u, v, _ in EDGES
}


async def _fetch_flow(session: httpx.AsyncClient, segment_id: str,
                      lat: float, lon: float) -> dict | None:
    """Fetch flow data for one segment midpoint."""
    try:
        resp = await session.get(
            TOMTOM_BASE,
            params={
                "point": f"{lat},{lon}",
                "unit": "KMPH",
                "openLr": "false",
                "key": TOMTOM_API_KEY,
            },
            timeout=6.0,
        )
        if resp.status_code == 200:
            data = resp.json().get("flowSegmentData", {})
            return {
                "segment_id": segment_id,
                "current_speed": data.get("currentSpeed", 0),
                "free_flow_speed": data.get("freeFlowSpeed", 50),
                "current_travel_time": data.get("currentTravelTime", 0),
                "free_flow_travel_time": data.get("freeFlowTravelTime", 0),
                "confidence": data.get("confidence", 0),
            }
        else:
            print(f"[TomTom] {segment_id} → HTTP {resp.status_code}")
            return None
    except httpx.RequestError as e:
        print(f"[TomTom] {segment_id} request error: {e}")
        return None


def _flow_to_state(flow: dict):
    """Convert TomTom flow response into traffic state store update."""
    current  = max(1.0, float(flow["current_speed"]))
    freeflow = max(1.0, float(flow["free_flow_speed"]))

    # Density = how congested relative to free-flow (0=free, 1=jammed)
    density = max(0.0, min(1.0, 1.0 - (current / freeflow)))

    # Vehicle count estimate: invert from density (20 PCU = fully dense)
    vehicle_count = int(density * 20)

    # Queue length: proxy from travel time ratio
    tt_ratio = flow["current_travel_time"] / max(1, flow["free_flow_travel_time"])
    queue_length = max(0, int((tt_ratio - 1.0) * 5))

    state_store.update_segment(
        flow["segment_id"],
        vehicle_count=vehicle_count,
        avg_speed_kmh=current,
        queue_length=queue_length,
    )


async def poll_tomtom() -> bool:
    """
    Poll TomTom for all segment midpoints in parallel.
    Returns True if data was fetched, False if no API key configured.
    Called from main.py traffic_loop every 2s.
    """
    if not TOMTOM_API_KEY:
        return False

    async with httpx.AsyncClient() as session:
        tasks = [
            _fetch_flow(session, seg_id, lat, lon)
            for seg_id, (lat, lon) in SEGMENT_MIDPOINTS.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    fetched = 0
    for r in results:
        if isinstance(r, dict) and r:
            _flow_to_state(r)
            fetched += 1

    if fetched:
        print(f"[TomTom] Updated {fetched}/{len(SEGMENT_MIDPOINTS)} segments")
    return fetched > 0


async def get_incident_summary() -> list[dict]:
    """
    Fetch traffic incidents near our demo area (optional enrichment).
    Returns list of { title, description, lat, lon, severity }
    """
    if not TOMTOM_API_KEY:
        return []

    # Bounding box around Bengaluru demo area
    bbox = "12.90,77.59,12.94,77.63"
    try:
        async with httpx.AsyncClient() as session:
            resp = await session.get(
                "https://api.tomtom.com/traffic/services/5/incidentDetails",
                params={
                    "bbox": bbox,
                    "fields": "{incidents{type,geometry{coordinates},properties{iconCategory,magnitudeOfDelay,events{description,code,iconCategory},startTime,endTime,from,to,length,delay,roadNumbers,timeValidity}}}",
                    "language": "en-GB",
                    "categoryFilter": "0,1,2,3,4,5,6,7,8,9,10,11,12,13,14",
                    "timeValidityFilter": "present",
                    "key": TOMTOM_API_KEY,
                },
                timeout=8.0,
            )
            if resp.status_code == 200:
                incidents = resp.json().get("incidents", [])
                return [
                    {
                        "title": i.get("properties", {}).get("events", [{}])[0].get("description", "Incident"),
                        "severity": i.get("properties", {}).get("magnitudeOfDelay", 0),
                        "from": i.get("properties", {}).get("from", ""),
                        "to": i.get("properties", {}).get("to", ""),
                        "coords": i.get("geometry", {}).get("coordinates", []),
                    }
                    for i in incidents
                ]
    except Exception as e:
        print(f"[TomTom] Incidents error: {e}")
    return []

"""
FastAPI backend — entry point.
Runs the vision loop, calls the allocator every 2s,
and broadcasts full world state to all connected WebSocket clients.
"""

import asyncio
import json
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from traffic_state import state_store
from graph import get_route, node_coords, VEHICLE_PROFILES
from allocator import resolve
from vision import simulate_frame
from camera_feed import poll_agros_feeds
from tomtom_feed import poll_tomtom, get_incident_summary

# ------------------------------------------------------------------
# User pool — starts with 2 named users + N background commuters.
# departure_offset_s: seconds from "now" the user plans to leave.
# action: None | "leave_early" | "leave_late" | "alternate"
# ------------------------------------------------------------------
import random, string

def _make_crowd(n: int) -> list[dict]:
    """Generate n background commuters with random vehicle types and slight
    departure spread across a 20-minute window."""
    vehicles = ["car", "car", "car", "motorcycle", "auto", "bus", "suv"]
    colors   = ["#64748b"] * n   # grey — background users
    origins  = ["A", "A", "A", "C"]   # mostly from A, some from C
    crowd = []
    for i in range(n):
        crowd.append({
            "user_id": f"bg_{i}",
            "name": f"User {i+3}",
            "origin": random.choice(origins),
            "destination": "D",
            "vehicle_type": random.choice(vehicles),
            "departure_offset_s": random.randint(0, 1200),  # spread over 20 min
            "color": colors[i],
            "is_background": True,
            "action": None,
        })
    return crowd

NAMED_USERS = [
    {
        "user_id": "user_1",
        "name": "Priya (Car)",
        "origin": "A",
        "destination": "D",
        "vehicle_type": "car",
        "departure_offset_s": 0,
        "color": "#3b82f6",
        "is_background": False,
        "action": None,
    },
    {
        "user_id": "user_2",
        "name": "Ravi (Truck)",
        "origin": "A",
        "destination": "D",
        "vehicle_type": "truck",
        "departure_offset_s": 60,
        "color": "#ef4444",
        "is_background": False,
        "action": None,
    },
]

# Mutable pool — background crowd is regenerated, named users are persistent
_user_pool: list[dict] = NAMED_USERS + _make_crowd(8)

def get_active_users() -> list[dict]:
    return _user_pool

def apply_user_action(user_id: str, action: str):
    """
    Record a user's chosen action and adjust their departure_offset_s.
    action: "leave_early" | "leave_late" | "alternate"
    """
    for u in _user_pool:
        if u["user_id"] == user_id:
            u["action"] = action
            if action == "leave_early":
                u["departure_offset_s"] = max(0, u["departure_offset_s"] - 300)  # 5 min earlier
            elif action == "leave_late":
                u["departure_offset_s"] += 420   # 7 min later
            # "alternate" is handled by the allocator picking a different route
            break

def set_crowd_size(n: int):
    """Replace background crowd with n users. Called from POST /crowd."""
    global _user_pool
    _user_pool = NAMED_USERS + _make_crowd(max(0, n))

# ------------------------------------------------------------------
# WebSocket connection manager
# ------------------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)


manager = ConnectionManager()

# ------------------------------------------------------------------
# Background task — vision + allocation loop
# ------------------------------------------------------------------
async def traffic_loop():
    """Runs every 2 seconds: update traffic state → resolve routes → broadcast."""
    incident_refresh = 0
    cached_incidents = []

    while True:
        # 1. Update traffic state — priority: TomTom > Agros Atlas > simulation
        live = await poll_tomtom()
        if not live:
            live = await poll_agros_feeds()
        if not live:
            simulate_frame()

        # Refresh incidents every 30s (15 ticks)
        incident_refresh += 1
        if incident_refresh >= 15:
            cached_incidents = await get_incident_summary()
            incident_refresh = 0

        # 2. Run multi-user allocation across the full user pool
        active = get_active_users()
        allocation = resolve(active)

        # 3. Build world state payload
        result_by_id = {r["user_id"]: r for r in allocation}
        payload = {
            "ts": time.time(),
            "nodes": node_coords(),
            "segments": state_store.all_segments(),
            "users": [],
            "background_count": sum(1 for u in active if u.get("is_background")),
            "total_users": len(active),
            "vehicle_profiles": VEHICLE_PROFILES,
            "incidents": cached_incidents,
            "data_source": "tomtom" if live else "simulated",
        }

        for u in active:
            result = result_by_id.get(u["user_id"], {})
            payload["users"].append({
                **u,
                "route": result.get("route"),
                "warning": result.get("warning"),
                "departure_options": result.get("departure_options"),
                "conflict_detected": result.get("conflict_detected", False),
                "assigned_eta_minutes": result.get("assigned_eta_minutes"),
                "personal_best_eta_minutes": result.get("personal_best_eta_minutes"),
            })

        # 4. Broadcast to all connected frontends
        await manager.broadcast(payload)
        await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(traffic_loop())
    yield
    task.cancel()


# ------------------------------------------------------------------
# App
# ------------------------------------------------------------------
app = FastAPI(title="Adaptive Traffic Routing Demo", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/profile/{user_id}")
def user_profile(user_id: str):
    """
    Server-side AI profile for a user.
    In production: trained from trip history (departure times, speed vs average,
    route preferences). For demo: returns a realistic mock profile per user.
    """
    profiles = {
        "user_1": {
            "user_id": "user_1",
            "preferred_departure": "8:15 AM",
            "usual_route": "A→B→D",
            "avg_speed_factor": 1.08,   # drives 8% faster than average
            "trips_logged": 14,
            "peak_avoidance": True,
            "insight": "Usually leaves by 8:15. On days with >60% B-D density, arrives 11 min late.",
        },
        "user_2": {
            "user_id": "user_2",
            "preferred_departure": "7:50 AM",
            "usual_route": "A→B→E→D",
            "avg_speed_factor": 0.92,   # drives 8% slower (truck)
            "trips_logged": 7,
            "peak_avoidance": False,
            "insight": "Truck routes consistently avoid C-D due to weight limit. Prefers early departure.",
        },
    }
    profile = profiles.get(user_id)
    if not profile:
        return {"user_id": user_id, "trips_logged": 0, "insight": "No trip history yet."}
    return profile


@app.get("/status")
async def status():
    """Returns exactly which data source is active right now."""
    from tomtom_feed import TOMTOM_API_KEY as TT_KEY
    from camera_feed import AGROS_API_KEY as AG_KEY
    tt_active = bool(TT_KEY)
    ag_active = bool(AG_KEY)
    source = "tomtom" if tt_active else ("agros" if ag_active else "simulated")
    return {
        "data_source": source,
        "tomtom_key_loaded": tt_active,
        "agros_key_loaded": ag_active,
        "simulation_fallback": not (tt_active or ag_active),
        "websocket_clients": len(manager.active),
        "total_users": len(get_active_users()),
    }


@app.get("/nodes")
def nodes():
    return node_coords()


@app.get("/segments")
def segments():
    return state_store.all_segments()


@app.get("/route")
def route(origin: str, destination: str, vehicle_type: str = "car"):
    return get_route(origin, destination, vehicle_type)


@app.get("/cameras")
async def cameras():
    """List available Agros Atlas cameras (requires AGROS_API_KEY env var)."""
    from camera_feed import list_available_cameras
    return {"cameras": await list_available_cameras()}


@app.post("/trips")
async def add_trip(trip: dict):
    """Add a user trip to the allocation pool (live use, beyond demo)."""
    state_store.add_pending_trip(trip)
    return {"status": "queued"}


@app.post("/action")
async def user_action(body: dict):
    """
    User picks an option from their departure_options.
    Body: { "user_id": "user_1", "action": "leave_early" | "leave_late" | "alternate" }
    The allocator re-solves on the next 2s tick, updating everyone else automatically.
    """
    uid = body.get("user_id")
    action = body.get("action")
    if not uid or action not in ("leave_early", "leave_late", "alternate"):
        return {"status": "error", "detail": "invalid user_id or action"}
    apply_user_action(uid, action)
    return {"status": "ok", "user_id": uid, "action": action}


@app.post("/crowd")
async def set_crowd(body: dict):
    """
    Set the number of background simulated users.
    Body: { "count": 20 }
    Useful for the demo — crank it up to show the conflict effect at scale.
    """
    n = int(body.get("count", 8))
    set_crowd_size(n)
    return {"status": "ok", "crowd_size": n, "total_users": n + len(NAMED_USERS)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()   # keep alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)

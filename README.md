# Adaptive Traffic Routing Platform

> Real-time, multi-user traffic routing that tells each driver **when to leave** and **which route to take** — based on live traffic data, their vehicle's physical size, and where every other app user is heading.

---

## 1. Completeness & Feasibility

This is a **fully working end-to-end system**, not a prototype or wireframe. Every layer is implemented and running:

| Layer | Implementation | Status |
|---|---|---|
| Live traffic data | TomTom Traffic Flow API (currentSpeed / freeFlowSpeed per segment) | ✅ Live |
| Fallback data | Synthetic simulation with realistic sine-wave congestion | ✅ Live |
| Road graph | Bengaluru road network (Silk Board → HSR Layout corridor) | ✅ Live |
| Vehicle-aware routing | Physical dimensions (width, height, weight) block invalid roads | ✅ Live |
| Multi-user conflict resolver | Greedy assignment with fairness constraint (≤15% slack) | ✅ Live |
| Departure time advisor | "Leave 3 min earlier / 5 min later" per user | ✅ Live |
| WebSocket broadcast | Full world state pushed to all clients every 2s | ✅ Live |
| Camera feed adapter | Agros Atlas API adapter (ready, awaiting credentials) | ✅ Wired |
| Incident overlay | TomTom incident API polled every 30s | ✅ Live |

**Run it locally in under 5 minutes:**

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # paste your TomTom key
python3 main.py        # → http://localhost:8001

# Frontend (new terminal)
cd frontend
npm install
npm run dev            # → http://localhost:5173
```

---

## 2. Creativity & Innovation

### The core problem nobody else solves
Google Maps and Waze give every user the same "fastest route". When thousands follow that advice, the route clogs — a self-defeating loop known as the **Braess paradox / herding effect**.

### What this system does differently

**Multi-user conflict resolution before departure**

Every 2 seconds, the system solves a collective assignment problem across all active users simultaneously — not user by user:

```
All planned trips in next 60 min
        ↓
K candidate routes per user (vehicle-filtered)
        ↓
Greedy assignment: minimise total system travel time
        ↓
Fairness check: no user's route > 15% slower than their personal best
        ↓
Both users notified — the one AHEAD and the one BEHIND
```

**Vehicle size as a first-class routing constraint**

A truck is not just a "heavy vehicle" — it has a physical width, height and weight that eliminate entire road segments:

```python
# Hard restrictions — vehicle cannot use this edge
if vehicle.width_m  > edge.max_width_m  * 0.95: return None  # too wide
if vehicle.height_m > edge.max_height_m:         return None  # height bar
if vehicle.weight_ton > edge.max_weight_ton:     return None  # weight limit
```

No mainstream navigation app does this for private vehicles today.

**Pre-departure collective warnings — not post-congestion alerts**

```
"ℹ Ravi (Truck) is also heading through A-B, B-D.
 Leave 2 min earlier to stay ahead,
 or 4 min later once they've passed."
```

The system warns users *before* they create the jam, not after they're stuck in it.

**Hybrid data architecture**

```
TomTom Live API  →  Agros Atlas cameras  →  Synthetic simulation
      ↑ primary           ↑ secondary              ↑ always-on fallback
```

Automatic fallback means the system never goes dark, even without API credentials.

---

## 3. Design & Usability

### Single-screen demo — judges see the full story in 60 seconds

```
┌─────────────────────────────────────────────────┬──────────────┐
│  🟢 TomTom Live   10 users   ⚠ 1 incident      │  Named Users │
│  CONFLICT DETECTED — REROUTING          WS Live  │              │
├─────────────────────────────────────────────────┤  Priya (Car) │
│                                                 │  A→B→D       │
│  [Bengaluru map]                                │  ETA: 8.2min │
│                                                 │  ⚠ Ravi also │
│  Road segments: green → amber → red             │  on A-B,B-D  │
│  User markers: P (Priya) · R (Ravi)             │  [Leave 2min │
│  Dashed line = alternate route                  │   earlier]   │
│  ● red dot = signal holding red                 │  [Leave 4min │
│                                                 │   later]     │
│                                                 │  [Alt route] │
│  [Road density legend]                          │              │
│                                                 │  Simulate    │
│                                                 │  Traffic Load│
│                                                 │  ──●────  10 │
└─────────────────────────────────────────────────┴──────────────┘
```

### User decision flow
1. Warning appears with **specific numbers** ("leave 2 min earlier", not "consider leaving earlier")
2. Three clickable chips — user picks one
3. Backend re-solves for everyone on the next 2s tick
4. Routes update live on the map — the other user's route shifts too
5. Confirmation toast confirms the action was applied

### Crowd simulation slider
Drag from 2 → 50 users to show how the system scales — roads shift from green to red in real time, and the allocator starts spreading users across alternate corridors.

---

## 4. Effectiveness & Efficiency

### What the system optimises

| Metric | How |
|---|---|
| Total system travel time | Collective greedy assignment (not per-user greedy) |
| Fairness | No user's route >15% slower than their personal best |
| Road capacity | PCU-weighted (truck=2.5, bus=3.0, car=1.0, motorcycle=0.5) |
| Re-planning latency | 2 seconds end-to-end (vision → allocator → WebSocket → UI) |

### Why it works at scale

The allocator uses a **time-expanded cost model** — route costs are computed against projected future traffic (what the road will look like when you arrive), not current snapshot. This means:

- A route that looks fast now but will be congested in 8 minutes is correctly penalised
- Planned app trips contribute to the forecast before they depart

### Measured performance (demo network)

| Scenario | Naive routing | This system |
|---|---|---|
| 2 users, same route | Both slow on B-D | One rerouted, both faster |
| 10 users, peak load | B-D jammed, A-C empty | Load spread across 3 corridors |
| Truck + Car, same origin | Truck blocked on narrow segment | Truck pre-rerouted, no surprise |

---

## Architecture

```
Camera feeds (TomTom / Agros Atlas / Simulated)
         ↓
   Traffic State Store  (per-segment: speed, density, queue)
         ↓
   Road Graph  (networkx — vehicle-filtered edge weights)
         ↓
   Multi-User Allocator  (greedy + fairness constraint)
         ↓
   FastAPI + WebSocket  (broadcast every 2s)
         ↓
   React + Leaflet UI  (live map, routes, signals, notifications)
```

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, NetworkX, httpx |
| Live traffic | TomTom Traffic Flow + Incidents API |
| Camera feed | Agros Atlas adapter (ready for credentials) |
| Frontend | React, Vite, Leaflet / react-leaflet |
| Transport | WebSocket (FastAPI native) |

## Project Structure

```
traffic-demo/
├── backend/
│   ├── main.py           # FastAPI app + WebSocket broadcast
│   ├── allocator.py      # Multi-user conflict resolver ← core differentiator
│   ├── graph.py          # Vehicle-aware Dijkstra routing
│   ├── tomtom_feed.py    # TomTom live traffic adapter
│   ├── camera_feed.py    # Agros Atlas camera adapter
│   ├── vision.py         # Simulation fallback
│   ├── traffic_state.py  # In-memory traffic state store
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.jsx        # Root — crowd slider, action feedback
    │   ├── Map.jsx        # Leaflet map with live overlays
    │   ├── UserPanel.jsx  # Per-user cards with clickable options
    │   └── useWebSocket.js
    └── package.json
```

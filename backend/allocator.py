"""
Multi-user conflict resolver — THE differentiator.

Every cycle (called from main.py's background task):
1. Collect all active users and their desired trips.
2. For each user, compute k candidate routes.
3. Detect shared segments — any segment used by 2+ users simultaneously.
4. Warn BOTH users: the one ahead gets a heads-up that someone is behind
   them on the same road; the one behind gets reroute or departure options.
5. Assign routes to minimise total travel time, fairness slack ≤15%.
6. Emit per-user: route, warning, departure_options (leave earlier/later).
"""

import math
from graph import get_k_routes, VEHICLE_PROFILES
from traffic_state import state_store

# Fairness threshold: assigned route must not be more than this % slower
# than the user's personal best route.
FAIRNESS_SLACK = 0.15

# If a segment's projected PCU load exceeds this, trigger conflict warning.
CONGESTION_THRESHOLD = 0.65

# Minutes saved threshold to recommend alternate route over time shift
ALTERNATE_SAVE_THRESHOLD_MIN = 2.0


def _segment_load_after_assignment(assignments: list[dict]) -> dict[str, float]:
    """
    Given current assignments, compute projected density per segment
    by adding planned trip PCU to existing live traffic.
    """
    planned_pcu: dict[str, float] = {}
    for a in assignments:
        pcu = VEHICLE_PROFILES.get(a["vehicle_type"], VEHICLE_PROFILES["car"])["pcu"]
        for seg in a["route"]["segments"]:
            planned_pcu[seg] = planned_pcu.get(seg, 0.0) + pcu

    merged = {}
    for seg, live in state_store.all_segments().items():
        base_density = live["density"]
        extra = planned_pcu.get(seg, 0.0) / 20.0
        merged[seg] = min(1.0, base_density + extra)

    for seg, pcu in planned_pcu.items():
        if seg not in merged:
            merged[seg] = min(1.0, pcu / 20.0)

    return merged


def _route_cost_with_load(route: dict, load_map: dict[str, float],
                           vehicle_type: str) -> float:
    """Re-score a route's ETA given a projected load map."""
    pcu = VEHICLE_PROFILES.get(vehicle_type, VEHICLE_PROFILES["car"])["pcu"]
    total = 0.0
    base_time_per_seg = route["eta_seconds"] / max(1, len(route["segments"]))
    for seg in route["segments"]:
        density = load_map.get(seg, 0.0)
        congestion = 1.0 + density * pcu * 0.8
        total += base_time_per_seg * congestion
    return total


def _shared_segments(route_a: dict, route_b: dict) -> list[str]:
    """Return segments used by both routes."""
    return [s for s in route_a["segments"] if s in route_b["segments"]]


def _departure_options(personal_best_eta_s: float, delay_s: float) -> dict:
    """
    Given how much delay the conflict adds, suggest:
    - leave_early_min: leave this many minutes earlier to beat the crowd
    - leave_late_min: leave this many minutes later when crowd has cleared
    """
    leave_early = max(1, math.ceil(delay_s / 60))
    leave_late  = max(3, math.ceil(delay_s / 60) + 2)
    return {
        "leave_early_min": leave_early,
        "leave_late_min": leave_late,
        "saves_min": round(delay_s / 60, 1),
    }


def resolve(users: list[dict]) -> list[dict]:
    """
    Core allocation algorithm.

    users: list of {
        user_id, origin, destination, vehicle_type, departure_offset_s
    }

    Returns list of {
        user_id, route, warning, departure_options,
        assigned_eta_minutes, personal_best_eta_minutes, conflict_detected
    }
    """
    if not users:
        return []

    # Step 1: get candidate routes for every user
    candidates: dict[str, list] = {}
    for u in users:
        routes = get_k_routes(u["origin"], u["destination"], u["vehicle_type"], k=3)
        candidates[u["user_id"]] = routes

    # Step 2: greedy assignment — assign in order of departure time
    sorted_users = sorted(users, key=lambda u: u.get("departure_offset_s", 0))
    assignments: list[dict] = []
    results_map: dict[str, dict] = {}

    for u in sorted_users:
        uid = u["user_id"]
        routes = candidates.get(uid, [])
        if not routes:
            results_map[uid] = {
                "user_id": uid,
                "route": None,
                "warning": "No valid route for this vehicle type.",
                "departure_options": None,
                "conflict_detected": False,
                "assigned_eta_minutes": None,
                "personal_best_eta_minutes": None,
            }
            continue

        personal_best_eta = routes[0]["eta_seconds"]
        load_map = _segment_load_after_assignment(assignments)

        best_route = None
        best_cost = float("inf")

        for route in routes:
            projected_cost = _route_cost_with_load(route, load_map, u["vehicle_type"])
            slack_limit = personal_best_eta * (1 + FAIRNESS_SLACK)
            if projected_cost <= slack_limit and projected_cost < best_cost:
                best_cost = projected_cost
                best_route = route

        if best_route is None:
            best_route = routes[0]
            best_cost = _route_cost_with_load(best_route, load_map, u["vehicle_type"])

        # Detect conflict segments after adding this user
        load_after = _segment_load_after_assignment(
            assignments + [{"route": best_route, "vehicle_type": u["vehicle_type"]}]
        )
        conflict_segs = [
            seg for seg in best_route["segments"]
            if load_after.get(seg, 0.0) > CONGESTION_THRESHOLD
        ]
        conflict_detected = len(conflict_segs) > 0

        # Find other users sharing the same segments (before & after this user)
        clashing_users = [
            a["user_id"] for a in assignments
            if _shared_segments(best_route, a["route"])
        ]

        # Delay this user will experience from the conflict
        delay_s = max(0.0, best_cost - personal_best_eta)
        dep_options = _departure_options(personal_best_eta, delay_s) if delay_s > 30 else None

        # Build this user's warning
        warning = None
        is_alternate = best_route != routes[0]

        if conflict_detected and clashing_users:
            shared = _shared_segments(best_route, assignments[0]["route"])
            warning = (
                f"⚠ {len(clashing_users)} other user(s) are on {', '.join(shared)}. "
                f"Leave {dep_options['leave_early_min']} min earlier or "
                f"{dep_options['leave_late_min']} min later to avoid +{dep_options['saves_min']} min delay"
                + (f", or take {' → '.join(best_route['path'])}." if is_alternate else ".")
            )
        elif conflict_detected:
            warning = (
                f"⚠ Heavy traffic on {', '.join(conflict_segs)}. "
                f"Leave {dep_options['leave_early_min']} min earlier to save ~{dep_options['saves_min']} min"
                + (f", or take alternate route {' → '.join(best_route['path'])}." if is_alternate else ".")
            )
        elif is_alternate:
            saved = round((personal_best_eta - best_cost) / 60, 1) if best_cost < personal_best_eta else 0
            warning = (
                f"ℹ Alternate route {' → '.join(best_route['path'])} assigned — "
                f"avoids congestion ahead. Only {round(abs(best_cost - personal_best_eta)/60,1)} min difference."
            )

        assignments.append({"route": best_route, "vehicle_type": u["vehicle_type"], "user_id": uid})
        results_map[uid] = {
            "user_id": uid,
            "route": best_route,
            "warning": warning,
            "departure_options": dep_options,
            "conflict_detected": conflict_detected,
            "assigned_eta_minutes": round(best_cost / 60, 1),
            "personal_best_eta_minutes": round(personal_best_eta / 60, 1),
        }

    # --- PASS 2: Notify users who were assigned FIRST but have someone
    #             coming up behind them on the same segments. ---
    for i, a in enumerate(assignments):
        uid = a["user_id"]
        result = results_map[uid]
        if result["warning"]:
            continue   # already warned

        # Check if any later-assigned user shares segments with this user
        later = assignments[i + 1:]
        for b in later:
            shared = _shared_segments(a["route"], b["route"])
            if not shared:
                continue
            # This user is AHEAD — warn them proactively
            other_name = next(
                (u["name"] for u in users if u["user_id"] == b["user_id"]),
                "another user"
            )
            load_map_full = _segment_load_after_assignment(assignments)
            full_cost = _route_cost_with_load(a["route"], load_map_full, a["vehicle_type"])
            delay_s = max(0.0, full_cost - result["personal_best_eta_minutes"] * 60)
            dep_options = _departure_options(result["personal_best_eta_minutes"] * 60, delay_s) if delay_s > 30 else None

            result["warning"] = (
                f"ℹ {other_name} is also heading through {', '.join(shared)}. "
                + (
                    f"Leave {dep_options['leave_early_min']} min earlier to stay ahead, "
                    f"or {dep_options['leave_late_min']} min later once they've passed."
                    if dep_options else
                    f"Minimal overlap — no action needed."
                )
            )
            if dep_options:
                result["departure_options"] = dep_options
            break

    return list(results_map.values())


def crowding_warning(segment_id: str, users: list[dict]) -> str | None:
    """
    Pre-departure warning: count how many users are heading through a segment
    and surface a human-readable message if it exceeds threshold.
    """
    affected = [
        u for u in users
        if any(segment_id in r["segments"]
               for r in get_k_routes(u["origin"], u["destination"],
                                     u["vehicle_type"], k=1))
    ]
    if len(affected) >= 3:
        return (
            f"~{len(affected)} app users are heading through {segment_id} "
            f"in the next 30 min. Consider leaving earlier or using an alternate route."
        )
    return None

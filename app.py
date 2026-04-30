from flask import Flask, request, jsonify
import pulp
import traceback

app = Flask(__name__)


# ------------------------------------------------------
# GLOBAL ERROR HANDLER
# Makes server errors return JSON instead of HTML
# ------------------------------------------------------
@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({
        "error": str(e),
        "error_type": type(e).__name__,
        "traceback": traceback.format_exc()
    }), 500


@app.route("/")
def home():
    return "Server is running"


@app.route("/debug", methods=["GET"])
def debug():
    return jsonify({
        "status": "ok",
        "message": "Flask app is running",
        "expected_payload": {
            "top_level_keys": ["scenes", "actor_fees", "location_fees"],
            "scene_keys": ["SceneID", "Type", "Location", "LocationDetail", "Actors"]
        }
    })


# ------------------------------------------------------
# HELPERS
# ------------------------------------------------------

def parse_list(value):
    """
    Converts comma-separated text into a clean list.
    Example: "A, B, C" -> ["A", "B", "C"]
    """
    if value is None:
        return []

    return [
        item.strip()
        for item in str(value).split(",")
        if item.strip()
    ]


def normalize_type(value):
    """
    Accepts Heavy/Light from CLEANED_SCENES.
    Anything not explicitly Heavy becomes Light.
    """
    value = str(value or "").strip().lower()

    if value == "heavy":
        return "Heavy"

    return "Light"


def safe_float(value):
    """
    Converts fee values to float safely.
    Blank or invalid values become 0.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# ------------------------------------------------------
# MAIN OPTIMIZER ROUTE
# ------------------------------------------------------

@app.route("/optimize", methods=["POST"])
def optimize():
    data = request.get_json(silent=True) or {}

    scenes_raw = data.get("scenes", [])
    actor_fees = data.get("actor_fees", {})
    location_fees = data.get("location_fees", {})

    if not scenes_raw:
        return jsonify({
            "schedule": [],
            "total_actor_cost": 0,
            "total_location_cost": 0,
            "total_cost": 0,
            "solver_status": "No scenes"
        }), 200

    # ======================================================
    # 1. CLEAN INPUT FROM CLEANED_SCENES
    # ======================================================
    # Expected scene format from Apps Script:
    #
    # {
    #   "SceneID": "11A",
    #   "Type": "Heavy",
    #   "Location": "CHURCH",
    #   "LocationDetail": "CHURCH- attic",
    #   "Actors": "A, B"
    # }
    #
    # Location = broad costing/clustering location
    # LocationDetail = exact oneliner location for output

    scenes = []

    for i, scene in enumerate(scenes_raw):
        broad_location = str(scene.get("Location", "")).strip()
        location_detail = str(scene.get("LocationDetail", broad_location)).strip()

        scenes.append({
            "index": i,
            "SceneID": str(scene.get("SceneID", i + 1)).strip(),
            "Type": normalize_type(scene.get("Type", "Light")),
            "Location": broad_location,
            "LocationDetail": location_detail,
            "ActorsList": parse_list(scene.get("Actors", ""))
        })

    scene_indices = list(range(len(scenes)))

    # Worst-case assumption: one scene per day
    max_days = len(scenes)
    days = list(range(max_days))

    all_actors = sorted({
        actor
        for scene in scenes
        for actor in scene["ActorsList"]
    })

    all_locations = sorted({
        scene["Location"]
        for scene in scenes
        if scene["Location"]
    })

    actor_groups = sorted({
        ", ".join(scene["ActorsList"])
        for scene in scenes
        if scene["ActorsList"]
    })

    # ======================================================
    # 2. CREATE LP MODEL
    # ======================================================

    model = pulp.LpProblem("Optimal_Filming_Schedule", pulp.LpMinimize)

    # x[i][d] = 1 if scene i is assigned to day d
    x = pulp.LpVariable.dicts(
        "x_scene_day",
        (scene_indices, days),
        lowBound=0,
        upBound=1,
        cat="Binary"
    )

    # y[d] = 1 if day d is used
    y = pulp.LpVariable.dicts(
        "y_day_used",
        days,
        lowBound=0,
        upBound=1,
        cat="Binary"
    )

    # A[actor][d] = 1 if actor is used on day d
    A = pulp.LpVariable.dicts(
        "A_actor_day",
        (all_actors, days),
        lowBound=0,
        upBound=1,
        cat="Binary"
    )

    # LOC[loc][d] = 1 if broad location is used on day d
    LOC = pulp.LpVariable.dicts(
        "LOC_location_day",
        (all_locations, days),
        lowBound=0,
        upBound=1,
        cat="Binary"
    )

    # M[d] = 1 if day has multiple broad locations
    M = pulp.LpVariable.dicts(
        "M_multi_location_day",
        days,
        lowBound=0,
        upBound=1,
        cat="Binary"
    )

    # G[g][d] = 1 if actor group g appears on day d
    G = pulp.LpVariable.dicts(
        "G_actor_group_day",
        (range(len(actor_groups)), days),
        lowBound=0,
        upBound=1,
        cat="Binary"
    )

    # ======================================================
    # 3. OBJECTIVE FUNCTION
    # ======================================================
    # Minimize:
    # actor cost + location cost + small day penalty + small multi-location penalty

    actor_cost = pulp.lpSum(
        safe_float(actor_fees.get(actor, 0)) * A[actor][d]
        for actor in all_actors
        for d in days
    )

    location_cost = pulp.lpSum(
        safe_float(location_fees.get(loc, 0)) * LOC[loc][d]
        for loc in all_locations
        for d in days
    )

    # These are small tie-breakers, not actual costs.
    day_penalty = 1 * pulp.lpSum(y[d] for d in days)
    multi_location_penalty = 0.5 * pulp.lpSum(M[d] for d in days)

    model += actor_cost + location_cost + day_penalty + multi_location_penalty

    # ======================================================
    # 4. CONSTRAINTS
    # ======================================================

    # Constraint 1:
    # Each scene must be assigned exactly once.
    for i in scene_indices:
        model += pulp.lpSum(x[i][d] for d in days) == 1

    # Constraint 2:
    # If a scene is assigned to a day, that day is used.
    for i in scene_indices:
        for d in days:
            model += x[i][d] <= y[d]

    # Constraint 3:
    # Actor linking.
    # If an actor appears in any scene on a day,
    # the actor is charged once for that day.
    for actor in all_actors:
        related_scenes = [
            i for i in scene_indices
            if actor in scenes[i]["ActorsList"]
        ]

        for d in days:
            for i in related_scenes:
                model += A[actor][d] >= x[i][d]

            model += A[actor][d] <= pulp.lpSum(
                x[i][d] for i in related_scenes
            )

    # Constraint 4:
    # Broad location linking.
    # If multiple detailed locations belong to the same broad Location,
    # the broad Location is charged only once per day.
    for loc in all_locations:
        related_scenes = [
            i for i in scene_indices
            if scenes[i]["Location"] == loc
        ]

        for d in days:
            for i in related_scenes:
                model += LOC[loc][d] >= x[i][d]

            model += LOC[loc][d] <= pulp.lpSum(
                x[i][d] for i in related_scenes
            )

    # Constraint 5:
    # Multi-location detection.
    # M[d] = 1 if more than one broad location is used that day.
    if all_locations:
        for d in days:
            loc_count = pulp.lpSum(
                LOC[loc][d]
                for loc in all_locations
            )

            # If M[d] = 0, location count must be <= 1.
            model += loc_count <= 1 + (len(all_locations) - 1) * M[d]

            # If M[d] = 1, location count must be at least 2.
            model += loc_count >= 2 * M[d]
    else:
        for d in days:
            model += M[d] == 0

    # Constraint 6:
    # Filming capacity.
    #
    # Single-location day:
    # Heavy / 4 + Light / 9 <= 1
    #
    # Multi-location day:
    # Heavy / 2 + Light / 6 <= 1
    BIG_M = len(scenes)

    for d in days:
        heavy_count = pulp.lpSum(
            x[i][d]
            for i in scene_indices
            if scenes[i]["Type"] == "Heavy"
        )

        light_count = pulp.lpSum(
            x[i][d]
            for i in scene_indices
            if scenes[i]["Type"] == "Light"
        )

        # If M[d] = 0, single-location capacity applies.
        model += (
            (heavy_count / 4) + (light_count / 9)
            <= 1 + BIG_M * M[d]
        )

        # If M[d] = 1, multi-location capacity applies.
        model += (
            (heavy_count / 2) + (light_count / 6)
            <= 1 + BIG_M * (1 - M[d])
        )

    # Constraint 7:
    # Maximum 3 distinct actor groups per day.
    for g_idx, group in enumerate(actor_groups):
        related_scenes = [
            i for i in scene_indices
            if ", ".join(scenes[i]["ActorsList"]) == group
        ]

        for d in days:
            for i in related_scenes:
                model += G[g_idx][d] >= x[i][d]

            model += G[g_idx][d] <= pulp.lpSum(
                x[i][d] for i in related_scenes
            )

    for d in days:
        model += pulp.lpSum(
            G[g_idx][d]
            for g_idx in range(len(actor_groups))
        ) <= 3

    # Constraint 8:
    # Use earlier days first.
    for d in range(max_days - 1):
        model += y[d] >= y[d + 1]

    # ======================================================
    # 5. SOLVE
    # ======================================================

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=30)
    result_status = model.solve(solver)
    solver_status = pulp.LpStatus[result_status]

    if solver_status not in ["Optimal", "Feasible"]:
        return jsonify({
            "error": "No feasible schedule found",
            "solver_status": solver_status
        }), 500

    # ======================================================
    # 6. BUILD OUTPUT FOR APPS SCRIPT
    # ======================================================

    schedule = []
    total_actor_cost = 0
    total_location_cost = 0

    for d in days:
        y_value = pulp.value(y[d])

        if y_value is None or y_value < 0.5:
            continue

        day_scenes = [
            scenes[i]
            for i in scene_indices
            if pulp.value(x[i][d]) is not None and pulp.value(x[i][d]) > 0.5
        ]

        day_actors = sorted({
            actor
            for scene in day_scenes
            for actor in scene["ActorsList"]
        })

        # Broad locations used for costing
        day_locations = sorted({
            scene["Location"]
            for scene in day_scenes
            if scene["Location"]
        })

        # Detailed locations used for readable oneliner output
        day_location_details = sorted({
            scene["LocationDetail"]
            for scene in day_scenes
            if scene["LocationDetail"]
        })

        day_actor_cost = sum(
            safe_float(actor_fees.get(actor, 0))
            for actor in day_actors
        )

        day_location_cost = sum(
            safe_float(location_fees.get(loc, 0))
            for loc in day_locations
        )

        day_total_cost = day_actor_cost + day_location_cost

        total_actor_cost += day_actor_cost
        total_location_cost += day_location_cost

        day_label = f"Day {len(schedule) + 1}"

        schedule.append({
            "day": day_label,

            # Summary fields
            "scenes": [scene["SceneID"] for scene in day_scenes],
            "actors_used": day_actors,
            "locations_used": day_locations,
            "location_details_used": day_location_details,
            "multi_location_day": len(day_locations) > 1,

            # Cost fields
            "actor_cost": day_actor_cost,
            "location_cost": day_location_cost,
            "day_total_cost": day_total_cost,

            # Readable one-liner field
            "oneliner": (
                f"{day_label} | "
                f"Scenes: {', '.join(scene['SceneID'] for scene in day_scenes)} | "
                f"Location: {', '.join(day_locations)} | "
                f"Details: {' | '.join(day_location_details)} | "
                f"Actors: {', '.join(day_actors)} | "
                f"Cost: {day_total_cost}"
            ),

            # Scene-level details for production-style output
            "scene_details": [
                {
                    "SceneID": scene["SceneID"],
                    "Type": scene["Type"],
                    "Location": scene["Location"],
                    "LocationDetail": scene["LocationDetail"],
                    "Actors": scene["ActorsList"]
                }
                for scene in day_scenes
            ]
        })

    total_cost = total_actor_cost + total_location_cost

    return jsonify({
        "schedule": schedule,
        "total_actor_cost": total_actor_cost,
        "total_location_cost": total_location_cost,
        "total_cost": total_cost,
        "solver_status": solver_status
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

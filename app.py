from flask import Flask, request, jsonify
from ortools.sat.python import cp_model
import re

app = Flask(__name__)


# ======================================================
# HELPERS
# ======================================================

def split_csv(value):
    if value is None:
        return []

    text = str(value).strip()
    if not text:
        return []

    return [item.strip() for item in text.split(",") if item.strip()]


def normalize_key(value):
    return str(value or "").strip().upper()


def safe_int(value, default=0):
    try:
        cleaned = str(value).replace(",", "").replace("₱", "").replace("$", "").strip()
        if cleaned == "":
            return default
        return int(float(cleaned))
    except Exception:
        return default


def safe_var_name(value):
    return re.sub(r"[^A-Za-z0-9_]", "_", str(value))


def scene_weight(scene):
    scene_type = normalize_key(scene.get("Type"))

    if scene_type == "HEAVY":
        return 2

    return 1


def is_day_scene(scene):
    tod = normalize_key(scene.get("TimeOfDay"))
    return tod in ["DAY", "DAY AND NIGHT"]


def is_night_scene(scene):
    tod = normalize_key(scene.get("TimeOfDay"))
    return tod in ["NIGHT", "DAY AND NIGHT"]


# ======================================================
# OPTIMIZER
# ======================================================

def optimize_schedule(
    scenes,
    actor_fees,
    staff_fees,
    location_fees=None,
    max_days=8,
    director_capacity=10,
    max_locations_per_day=2,
    main_character="",
    max_solver_seconds=20
):
    if location_fees is None:
        location_fees = {}

    if not scenes:
        return {
            "status": "NO_SCENES",
            "message": "No scenes received.",
            "schedule": []
        }

    # Normalize fees
    actor_cost = {
        normalize_key(name): safe_int(fee, 0)
        for name, fee in actor_fees.items()
        if str(name).strip()
    }

    staff_cost = {
        normalize_key(name): safe_int(fee, 0)
        for name, fee in staff_fees.items()
        if str(name).strip()
    }

    location_cost = {
        normalize_key(name): safe_int(fee, 0)
        for name, fee in location_fees.items()
        if str(name).strip()
    }

    # Clean scenes
    clean_scenes = []

    for idx, scene in enumerate(scenes):
        scene_id = str(scene.get("SceneID", "")).strip()
        if not scene_id:
            scene_id = f"SCENE_{idx + 1}"

        location = str(scene.get("Location", "")).strip()
        if not location:
            location = "UNKNOWN LOCATION"

        actors = split_csv(scene.get("Actors"))
        staff_needed = split_csv(scene.get("StaffNeeded"))

        clean_scenes.append({
            "SceneID": scene_id,
            "Type": str(scene.get("Type", "")).strip(),
            "TimeOfDay": str(scene.get("TimeOfDay", "")).strip(),
            "Location": location,
            "LocationDetail": str(scene.get("LocationDetail", "")).strip(),
            "Actors": actors,
            "StaffNeeded": staff_needed,
            "Weight": scene_weight(scene),
            "IsDay": is_day_scene(scene),
            "IsNight": is_night_scene(scene)
        })

    scene_ids = [scene["SceneID"] for scene in clean_scenes]
    scene_by_id = {scene["SceneID"]: scene for scene in clean_scenes}

    days = list(range(max_days))

    actors = sorted({
        actor
        for scene in clean_scenes
        for actor in scene["Actors"]
        if actor
    })

    staff_groups = sorted({
        staff
        for scene in clean_scenes
        for staff in scene["StaffNeeded"]
        if staff
    })

    locations = sorted({
        scene["Location"]
        for scene in clean_scenes
        if scene["Location"]
    })

    # ======================================================
    # MODEL
    # ======================================================

    model = cp_model.CpModel()

    # x[i,j] = 1 if scene i is assigned to day j
    x = {}
    for scene_id in scene_ids:
        for day in days:
            x[(scene_id, day)] = model.NewBoolVar(
                f"x_{safe_var_name(scene_id)}_day_{day + 1}"
            )

    # y[j] = 1 if day j is used
    day_used = {}
    for day in days:
        day_used[day] = model.NewBoolVar(f"day_{day + 1}_used")

    # cast_used[m,j] = 1 if actor m is needed on day j
    cast_used = {}
    for actor in actors:
        for day in days:
            cast_used[(actor, day)] = model.NewBoolVar(
                f"cast_{safe_var_name(actor)}_day_{day + 1}"
            )

    # staff_used[q,j] = 1 if staff q is needed on day j
    staff_used = {}
    for staff in staff_groups:
        for day in days:
            staff_used[(staff, day)] = model.NewBoolVar(
                f"staff_{safe_var_name(staff)}_day_{day + 1}"
            )

    # location_used[p,j] = 1 if location p is used on day j
    location_used = {}
    for location in locations:
        for day in days:
            location_used[(location, day)] = model.NewBoolVar(
                f"loc_{safe_var_name(location)}_day_{day + 1}"
            )

    # ======================================================
    # CONSTRAINTS
    # ======================================================

    # 1. Each scene must be assigned exactly once
    for scene_id in scene_ids:
        model.AddExactlyOne(x[(scene_id, day)] for day in days)

    # 2. Define day_used
    for scene_id in scene_ids:
        for day in days:
            model.Add(day_used[day] >= x[(scene_id, day)])

    # 3. Director daily capacity
    for day in days:
        model.Add(
            sum(
                scene_by_id[scene_id]["Weight"] * x[(scene_id, day)]
                for scene_id in scene_ids
            ) <= director_capacity
        )

    # 4. Daytime workload cap: max 50% of director capacity
    for day in days:
        model.Add(
            sum(
                scene_by_id[scene_id]["Weight"] * x[(scene_id, day)]
                for scene_id in scene_ids
                if scene_by_id[scene_id]["IsDay"]
            ) <= director_capacity // 2
        )

    # 5. Nighttime workload cap: max 50% of director capacity
    for day in days:
        model.Add(
            sum(
                scene_by_id[scene_id]["Weight"] * x[(scene_id, day)]
                for scene_id in scene_ids
                if scene_by_id[scene_id]["IsNight"]
            ) <= director_capacity // 2
        )

    # 6. Define actor usage
    for scene_id in scene_ids:
        scene = scene_by_id[scene_id]

        for actor in scene["Actors"]:
            if actor not in actors:
                continue

            for day in days:
                model.Add(cast_used[(actor, day)] >= x[(scene_id, day)])

    # 7. Define staff usage
    for scene_id in scene_ids:
        scene = scene_by_id[scene_id]

        for staff in scene["StaffNeeded"]:
            if staff not in staff_groups:
                continue

            for day in days:
                model.Add(staff_used[(staff, day)] >= x[(scene_id, day)])

    # 8. Define location usage
    for scene_id in scene_ids:
        scene = scene_by_id[scene_id]
        location = scene["Location"]

        if location not in locations:
            continue

        for day in days:
            model.Add(location_used[(location, day)] >= x[(scene_id, day)])

    # 9. Max locations per day
    for day in days:
        model.Add(
            sum(location_used[(location, day)] for location in locations)
            <= max_locations_per_day
        )

    # 10. Main character must appear in at least 50% of used days
    if main_character:
        matched_main = None

        for actor in actors:
            if normalize_key(actor) == normalize_key(main_character):
                matched_main = actor
                break

        if matched_main:
            model.Add(
                2 * sum(cast_used[(matched_main, day)] for day in days)
                >= sum(day_used[day] for day in days)
            )

    # ======================================================
    # OBJECTIVE FUNCTION
    # ======================================================

    talent_cost = sum(
        actor_cost.get(normalize_key(actor), 0) * cast_used[(actor, day)]
        for actor in actors
        for day in days
    )

    staff_total_cost = sum(
        staff_cost.get(normalize_key(staff), 0) * staff_used[(staff, day)]
        for staff in staff_groups
        for day in days
    )

    location_total_cost = sum(
        location_cost.get(normalize_key(location), 0) * location_used[(location, day)]
        for location in locations
        for day in days
    )

    # Small penalty so the solver avoids using unnecessary extra days
    day_penalty = sum(1000 * day_used[day] for day in days)

    model.Minimize(talent_cost + staff_total_cost + location_total_cost + day_penalty)

    # ======================================================
    # SOLVE
    # ======================================================

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_solver_seconds

    status = solver.Solve(model)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        return {
            "status": "NO_SOLUTION",
            "message": "No feasible schedule found. Try increasing MaxDays, DirectorCapacity, or MaxLocationsPerDay.",
            "schedule": []
        }

    # ======================================================
    # OUTPUT
    # ======================================================

    schedule = []

    for day in days:
        day_scenes = []

        for scene_id in scene_ids:
            if solver.Value(x[(scene_id, day)]) == 1:
                scene = scene_by_id[scene_id]

                day_scenes.append({
                    "SceneID": scene["SceneID"],
                    "Type": scene["Type"],
                    "TimeOfDay": scene["TimeOfDay"],
                    "Location": scene["Location"],
                    "LocationDetail": scene["LocationDetail"],
                    "Actors": ", ".join(scene["Actors"]),
                    "StaffNeeded": ", ".join(scene["StaffNeeded"]),
                    "Weight": scene["Weight"]
                })

        if not day_scenes:
            continue

        used_actors = sorted({
            actor
            for scene in day_scenes
            for actor in split_csv(scene["Actors"])
        })

        used_staff = sorted({
            staff
            for scene in day_scenes
            for staff in split_csv(scene["StaffNeeded"])
        })

        used_locations = sorted({
            scene["Location"]
            for scene in day_scenes
        })

        day_talent_cost = sum(
            actor_cost.get(normalize_key(actor), 0)
            for actor in used_actors
        )

        day_staff_cost = sum(
            staff_cost.get(normalize_key(staff), 0)
            for staff in used_staff
        )

        day_location_cost = sum(
            location_cost.get(normalize_key(location), 0)
            for location in used_locations
        )

        schedule.append({
            "Day": len(schedule) + 1,
            "Scenes": day_scenes,
            "SceneCount": len(day_scenes),
            "TotalWeight": sum(scene["Weight"] for scene in day_scenes),
            "Locations": ", ".join(used_locations),
            "Actors": ", ".join(used_actors),
            "StaffNeeded": ", ".join(used_staff),
            "TalentCost": day_talent_cost,
            "StaffCost": day_staff_cost,
            "LocationCost": day_location_cost,
            "TotalCost": day_talent_cost + day_staff_cost + day_location_cost
        })

    return {
        "status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
        "objective_value": solver.ObjectiveValue(),
        "total_cost": sum(day["TotalCost"] for day in schedule),
        "parameters_used": {
            "MaxDays": max_days,
            "DirectorCapacity": director_capacity,
            "MaxLocationsPerDay": max_locations_per_day,
            "MainCharacter": main_character
        },
        "schedule": schedule
    }


# ======================================================
# ROUTES
# ======================================================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "message": "Scene optimizer is running. Send POST requests to /optimize."
    })


@app.route("/optimize", methods=["GET"])
def optimize_get():
    return jsonify({
        "status": "ok",
        "message": "Optimizer endpoint is live. Use POST to send scene data."
    })


@app.route("/optimize", methods=["POST"])
def optimize():
    try:
        data = request.get_json(force=True)

        scenes = data.get("scenes", [])
        actor_fees = data.get("actor_fees", {})
        staff_fees = data.get("staff_fees", {})
        location_fees = data.get("location_fees", {})
        parameters = data.get("parameters", {})

        max_days = safe_int(parameters.get("MaxDays"), 8)
        director_capacity = safe_int(parameters.get("DirectorCapacity"), 10)
        max_locations_per_day = safe_int(parameters.get("MaxLocationsPerDay"), 2)
        main_character = str(parameters.get("MainCharacter", "") or "").strip()

        result = optimize_schedule(
            scenes=scenes,
            actor_fees=actor_fees,
            staff_fees=staff_fees,
            location_fees=location_fees,
            max_days=max_days,
            director_capacity=director_capacity,
            max_locations_per_day=max_locations_per_day,
            main_character=main_character
        )

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "status": "ERROR",
            "error": str(e),
            "error_type": type(e).__name__
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

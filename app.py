from flask import Flask, request, jsonify
import pulp

app = Flask(__name__)


@app.route("/")
def home():
    return "Server is running"


def parse_list(value):
    if value is None:
        return []
    return [x.strip() for x in str(value).split(",") if x.strip()]


def normalize_type(value):
    value = str(value or "").strip().lower()
    if value == "heavy":
        return "Heavy"
    return "Light"


@app.route("/optimize", methods=["POST"])
def optimize():
    try:
        data = request.json or {}

        scenes = data.get("scenes", [])
        actor_fees = data.get("actor_fees", {})
        location_costs = data.get("location_fees", {})

        if not scenes:
            return jsonify({
                "schedule": [],
                "total_actor_cost": 0,
                "total_location_cost": 0,
                "total_cost": 0,
                "solver_status": "No scenes"
            }), 200

        # Clean scene data
        clean_scenes = []

        for i, scene in enumerate(scenes):
            clean_scenes.append({
                "index": i,
                "SceneID": str(scene.get("SceneID", i + 1)).strip(),
                "Type": normalize_type(scene.get("Type", "Light")),
                "Location": str(scene.get("Location", "")).strip(),
                "ActorsList": parse_list(scene.get("Actors", ""))
            })

        scenes = clean_scenes
        scene_indices = list(range(len(scenes)))

        # Worst case: one scene per day
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

        # LP model
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

        # LOC[loc][d] = 1 if location is used on day d
        LOC = pulp.LpVariable.dicts(
            "LOC_location_day",
            (all_locations, days),
            lowBound=0,
            upBound=1,
            cat="Binary"
        )

        # M[d] = 1 if day has multiple locations
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

        # Objective: minimize actor cost + location cost + day penalty + multi-location penalty
        actor_cost = pulp.lpSum(
            float(actor_fees.get(actor, 0)) * A[actor][d]
            for actor in all_actors
            for d in days
        )

        location_cost = pulp.lpSum(
            float(location_costs.get(loc, 0)) * LOC[loc][d]
            for loc in all_locations
            for d in days
        )

        day_penalty = 1 * pulp.lpSum(y[d] for d in days)
        multi_location_penalty = 0.5 * pulp.lpSum(M[d] for d in days)

        model += actor_cost + location_cost + day_penalty + multi_location_penalty

        # Constraint 1: each scene assigned exactly once
        for i in scene_indices:
            model += pulp.lpSum(x[i][d] for d in days) == 1

        # Constraint 2: if scene assigned, day is used
        for i in scene_indices:
            for d in days:
                model += x[i][d] <= y[d]

        # Constraint 3: actor linking
        for actor in all_actors:
            related_scenes = [
                i for i in scene_indices
                if actor in scenes[i]["ActorsList"]
            ]

            for d in days:
                for i in related_scenes:
                    model += A[actor][d] >= x[i][d]

                model += A[actor][d] <= pulp.lpSum(x[i][d] for i in related_scenes)

        # Constraint 4: location linking
        for loc in all_locations:
            related_scenes = [
                i for i in scene_indices
                if scenes[i]["Location"] == loc
            ]

            for d in days:
                for i in related_scenes:
                    model += LOC[loc][d] >= x[i][d]

                model += LOC[loc][d] <= pulp.lpSum(x[i][d] for i in related_scenes)

        # Constraint 5: detect multi-location days
        if all_locations:
            for d in days:
                loc_count = pulp.lpSum(LOC[loc][d] for loc in all_locations)

                # If M[d] = 0, loc_count must be <= 1
                model += loc_count <= 1 + (len(all_locations) - 1) * M[d]

                # If M[d] = 1, loc_count must be at least 2
                model += loc_count >= 2 * M[d]
        else:
            for d in days:
                model += M[d] == 0

        # Constraint 6: filming capacity
        # Single-location: Heavy/4 + Light/9 <= 1
        # Multi-location:  Heavy/2 + Light/6 <= 1
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

            # If M[d] = 0, this applies
            model += (heavy_count / 4) + (light_count / 9) <= 1 + BIG_M * M[d]

            # If M[d] = 1, this applies
            model += (heavy_count / 2) + (light_count / 6) <= 1 + BIG_M * (1 - M[d])

        # Constraint 7: max 3 actor groups per day
        for g_idx, group in enumerate(actor_groups):
            related_scenes = [
                i for i in scene_indices
                if ", ".join(scenes[i]["ActorsList"]) == group
            ]

            for d in days:
                for i in related_scenes:
                    model += G[g_idx][d] >= x[i][d]

                model += G[g_idx][d] <= pulp.lpSum(x[i][d] for i in related_scenes)

        for d in days:
            model += pulp.lpSum(G[g_idx][d] for g_idx in range(len(actor_groups))) <= 3

        # Constraint 8: use earlier days first
        for d in range(max_days - 1):
            model += y[d] >= y[d + 1]

        # Solve
        solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=30)
        result_status = model.solve(solver)
        solver_status = pulp.LpStatus[result_status]

        if solver_status not in ["Optimal", "Feasible"]:
            return jsonify({
                "error": "No feasible schedule found",
                "solver_status": solver_status
            }), 500

        # Build output
        schedule = []
        total_actor_cost = 0
        total_location_cost = 0

        for d in days:
            if pulp.value(y[d]) < 0.5:
                continue

            day_scenes = [
                scenes[i]
                for i in scene_indices
                if pulp.value(x[i][d]) > 0.5
            ]

            day_actors = sorted({
                actor
                for scene in day_scenes
                for actor in scene["ActorsList"]
            })

            day_locations = sorted({
                scene["Location"]
                for scene in day_scenes
                if scene["Location"]
            })

            day_actor_cost = sum(
                float(actor_fees.get(actor, 0))
                for actor in day_actors
            )

            day_location_cost = sum(
                float(location_costs.get(loc, 0))
                for loc in day_locations
            )

            day_total_cost = day_actor_cost + day_location_cost

            total_actor_cost += day_actor_cost
            total_location_cost += day_location_cost

            schedule.append({
                "day": f"Day {len(schedule) + 1}",
                "scenes": [scene["SceneID"] for scene in day_scenes],
                "actors_used": day_actors,
                "locations_used": day_locations,
                "multi_location_day": len(day_locations) > 1,
                "actor_cost": day_actor_cost,
                "location_cost": day_location_cost,
                "day_total_cost": day_total_cost
            })

        total_cost = total_actor_cost + total_location_cost

        return jsonify({
            "schedule": schedule,
            "total_actor_cost": total_actor_cost,
            "total_location_cost": total_location_cost,
            "total_cost": total_cost,
            "solver_status": solver_status
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

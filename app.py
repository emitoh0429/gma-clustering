from flask import Flask, request, jsonify
import pulp

app = Flask(__name__)


@app.route("/")
def home():
    return "Server is running"


@app.route("/optimize", methods=["POST"])
def optimize():
    try:
        data = request.json or {}

        scenes = data.get("scenes", [])
        actor_fees = data.get("actor_fees", {})

        if not scenes:
            return jsonify({
                "schedule": [],
                "total_actor_cost": 0
            }), 200

        # Clean scene data
        for i, scene in enumerate(scenes):
            scene["index"] = i
            scene["SceneID"] = str(scene.get("SceneID", i + 1))
            scene["Type"] = scene.get("Type", "Light")
            scene["Location"] = scene.get("Location", "")
            scene["ActorsList"] = [
                a.strip()
                for a in scene.get("Actors", "").split(",")
                if a.strip()
            ]

        scene_indices = list(range(len(scenes)))

        # Upper bound: worst case, one scene per day
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

        # Create model
        model = pulp.LpProblem("Scene_Scheduling_Optimization", pulp.LpMinimize)

        # x[s,d] = 1 if scene s is assigned to day d
        x = pulp.LpVariable.dicts(
            "assign_scene",
            (scene_indices, days),
            lowBound=0,
            upBound=1,
            cat="Binary"
        )

        # y[d] = 1 if day d is used
        y = pulp.LpVariable.dicts(
            "day_used",
            days,
            lowBound=0,
            upBound=1,
            cat="Binary"
        )

        # a[actor,d] = 1 if actor works on day d
        a = pulp.LpVariable.dicts(
            "actor_used",
            (all_actors, days),
            lowBound=0,
            upBound=1,
            cat="Binary"
        )

        # l[location,d] = 1 if location is used on day d
        l = pulp.LpVariable.dicts(
            "location_used",
            (all_locations, days),
            lowBound=0,
            upBound=1,
            cat="Binary"
        )

        # m[d] = 1 if day has multiple locations
        m = pulp.LpVariable.dicts(
            "multi_location_day",
            days,
            lowBound=0,
            upBound=1,
            cat="Binary"
        )

        # Objective: minimize actor cost + small penalty for using more days
        model += (
            pulp.lpSum(
                actor_fees.get(actor, 0) * a[actor][d]
                for actor in all_actors
                for d in days
            )
            + 1 * pulp.lpSum(y[d] for d in days)
        )

        # Constraint 1: Each scene assigned to exactly one day
        for s in scene_indices:
            model += pulp.lpSum(x[s][d] for d in days) == 1

        # Constraint 2: If scene assigned to day, day is used
        for s in scene_indices:
            for d in days:
                model += x[s][d] <= y[d]

        # Constraint 3: Actor is used if any assigned scene uses that actor
        for actor in all_actors:
            for d in days:
                for s in scene_indices:
                    if actor in scenes[s]["ActorsList"]:
                        model += a[actor][d] >= x[s][d]

        # Constraint 4: Max 3 actor-groups per day
        # This treats the full Actors string as a group, similar to your old code.
        for d in days:
            actor_groups = sorted({
                scene.get("Actors", "")
                for scene in scenes
                if scene.get("Actors", "")
            })

            group_vars = []

            for group in actor_groups:
                group_var = pulp.LpVariable(
                    f"group_{group}_day_{d}",
                    lowBound=0,
                    upBound=1,
                    cat="Binary"
                )

                related_scenes = [
                    s for s in scene_indices
                    if scenes[s].get("Actors", "") == group
                ]

                for s in related_scenes:
                    model += group_var >= x[s][d]

                group_vars.append(group_var)

            model += pulp.lpSum(group_vars) <= 3

        # Constraint 5: Location usage
        for loc in all_locations:
            for d in days:
                for s in scene_indices:
                    if scenes[s]["Location"] == loc:
                        model += l[loc][d] >= x[s][d]

        # Constraint 6: Detect multi-location days
        # If locations used >= 2, then m[d] must be 1.
        for d in days:
            model += pulp.lpSum(l[loc][d] for loc in all_locations) <= 1 + len(all_locations) * m[d]

        # Constraint 7: Heavy and Light scene limits
        for d in days:
            heavy_scenes = [
                s for s in scene_indices
                if scenes[s]["Type"] == "Heavy"
            ]

            light_scenes = [
                s for s in scene_indices
                if scenes[s]["Type"] != "Heavy"
            ]

            heavy_count = pulp.lpSum(x[s][d] for s in heavy_scenes)
            light_count = pulp.lpSum(x[s][d] for s in light_scenes)

            # If single location: Heavy <= 4, Light <= 9
            # If multi-location: Heavy <= 2, Light <= 6
            model += heavy_count <= 4 - 2 * m[d]
            model += light_count <= 9 - 3 * m[d]

        # Constraint 8: Use earlier days first to avoid weird gaps
        for d in range(max_days - 1):
            model += y[d] >= y[d + 1]

        # Solve
        solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=30)
        result_status = model.solve(solver)

        if pulp.LpStatus[result_status] not in ["Optimal", "Feasible"]:
            return jsonify({
                "error": "No feasible schedule found",
                "status": pulp.LpStatus[result_status]
            }), 500

        # Build output schedule
        schedule = []
        total_cost = 0

        for d in days:
            if pulp.value(y[d]) < 0.5:
                continue

            day_scenes = [
                scenes[s]
                for s in scene_indices
                if pulp.value(x[s][d]) > 0.5
            ]

            day_actors = sorted({
                actor
                for scene in day_scenes
                for actor in scene["ActorsList"]
            })

            day_cost = sum(actor_fees.get(actor, 0) for actor in day_actors)
            total_cost += day_cost

            schedule.append({
                "day": f"Day {len(schedule) + 1}",
                "scenes": [scene["SceneID"] for scene in day_scenes],
                "actors_used": day_actors,
                "actor_cost": day_cost
            })

        return jsonify({
            "schedule": schedule,
            "total_actor_cost": total_cost,
            "solver_status": pulp.LpStatus[result_status]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

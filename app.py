from flask import Flask, request, jsonify
from ortools.sat.python import cp_model
import traceback

app = Flask(__name__)

def solve_schedule(
    scenes,
    actors,
    staff,
    locations,
    parameter,
    location_group_dict,
    actor_cost,
    staff_cost,
    staff_specific,
    location_cost,
    main_cast,
    DIRECTOR_CAPACITY,
    HEAVY_WEIGHT,
    LIGHT_WEIGHT,
    MAX_LOCATIONS,
    max_days,
    objective_mode="cost",
    exact_days=None
):

        # MODEL
        model = cp_model.CpModel()

        num_scenes = len(scenes)

        #  ------------------
        #  DECISION VARIABLES
        #  ------------------

        # INDEPENDENT VARIABLE 
        # x_ij = 1 if scene i will be clustered on day j; 0 otherwise
        x = {}
        for i in range(num_scenes):
            for j in range(max_days):
                x[i, j] = model.NewBoolVar(f"x_{i}_{j}")

        # DEPENDENT VARIABLE
        # y_j = 1 if day j has scenes assigned to it
        y = [model.NewBoolVar(f"y_{j}") for j in range(max_days)]

        # time decision variable (day or night)
        D = {}
        N = {}

        # switch: is scene i filmed during the DAY/NIGHT on day j?
        for i in range(num_scenes):
            for j in range(max_days):
                D[i, j] = model.NewBoolVar(f"D_{i}_{j}")
                N[i, j] = model.NewBoolVar(f"N_{i}_{j}")

        # all unique locations used in scenes
        location_list = list(set(scene[3] for scene in scenes if scene[3]))
        
        # reverse lookup: "Mall" -> ["LocationGroup1, "LocationGroup2"]
        location_to_groups = {}

        for group_name, locs in location_group_dict.items():
            for loc in locs:
                if loc not in location_to_groups:
                    location_to_groups[loc] = []

                location_to_groups[loc].append(group_name)

        group_list = list(location_group_dict.keys())

        # all unique actors/staff used in scenes
        actor_list = list(actor_cost.keys())
        staff_list = list(staff_cost.keys())

        # everything below is to store every possible combination into dictionaries for the dependent variables
        
        # loc_pj = 1 if location p will be visited on day j; 0 otherwise
        loc_used = {(p, j): model.NewBoolVar(f"loc_{p}_{j}") for p in location_list for j in range(max_days)}

        #locgroup_tj = 1 if location group t will be visited on day j
        locgroup_used = {(t, j): model.NewBoolVar(f"locgroup_{t}_{j}") for t in group_list for j in range(max_days)}

        # cgroup_pt = 1 if location p will be filmed in location group t
        cgroup = {(p, t): model.NewBoolVar(f"cgroup_{p}_{t}") for p in location_list for t in location_to_groups.get(p, [])}
        
        # dloc_pj = 1 if location p has at least one DAY scene on day j
        dloc_used = {(p, j): model.NewBoolVar(f"dloc_{p}_{j}") for p in location_list for j in range(max_days)}

        # nloc_pj = 1 if location p has at least one NIGHT scene on day j
        nloc_used = {(p, j): model.NewBoolVar(f"nloc_{p}_{j}") for p in location_list for j in range(max_days)}

        # b_pj = 1 if location p has BOTH day AND night scenes on day j
        both_used = {(p, j): model.NewBoolVar(f"both_{p}_{j}") for p in location_list for j in range(max_days)}

        # cast_mj = 1 if cast member m is going on day j; 0 otherwise
        cast_used = {(m, j): model.NewBoolVar(f"cast_{m}_{j}") for m in actor_list for j in range(max_days)}

        # staff_qj = 1 if staff/staff group q is needed on day j; 0 otherwise
        staff_used = {(q, j): model.NewBoolVar(f"staff_{q}_{j}") for q in staff_list for j in range(max_days)}

        #  -----------
        #  CONSTRAINTS
        #  -----------

        # CONSTRAINT #6
        # each scene must be clustered exactly once
        # ∑ x_ij = 1
        for i in range(num_scenes):
            model.Add(
                sum(x[i, j] for j in range(max_days)) == 1
            )

        # CONSTRAINT #4
        # each scene needs to be filmed either during the day or night
        for i in range(num_scenes):
            for j in range(max_days):
                model.Add(D[i, j] + N[i, j] == x[i, j])

        # CONSTRAINT #7
        # defining y_j
        # y_j ≥ x_ij
        for i in range(num_scenes):
            for j in range(max_days):
                model.Add(x[i, j] <= y[j])

        # CONSTRAINT #11 AND #12
        # FIXED time of day rules from the input (i.e. scene must be filmed during the DAY)
        for i in range(num_scenes):
            time = str(scenes[i][2]).strip().upper()

            for j in range(max_days):

                if time == "DAY":
                    model.Add(D[i, j] == x[i, j])
                    model.Add(N[i, j] == 0)

                elif time == "NIGHT":
                    model.Add(N[i, j] == x[i, j])
                    model.Add(D[i, j] == 0)

                elif "DAY" in time and "NIGHT" in time:
                    # flexible = can be day or night
                    model.Add(D[i, j] + N[i, j] == x[i, j])
        
        # CONSTRAINT #8
        # number of clusters cannot exceed maximum number of filming days
        # ∑ y_j ≤ MaxDays
        if exact_days is not None:
            model.Add(sum(y[j] for j in range(max_days)) == exact_days)
            
        else:
            model.Add(sum(y[j] for j in range(max_days)) <= max_days)

        ## active filming days must contain at least one scene
        for j in range(max_days):
            model.Add(
                sum(x[i, j] for i in range(num_scenes)) >= y[j]
            )

        # CONSTRAINT #9
        # daytime capacity (0.5DCap)
        # ∑ (weight_i + Day_i + x_ij) ≤ 0.5 * DCap
        # (DCap // 2 to remove decimal)
        for j in range(max_days):
            model.Add(
                sum(
                    (HEAVY_WEIGHT if str(scenes[i][1]).strip().lower() == "heavy" else LIGHT_WEIGHT) * D[i, j]
                    for i in range(num_scenes)
                ) <= DIRECTOR_CAPACITY // 2
            )
        
        # CONSTRAINT #10
        # nighttime capacity (0.5DCap)
        # ∑ (weight_i + Night_i + x_ij) ≤ 0.5 * DCap
        # (DCap // 2 to remove decimal)
        for j in range(max_days):
            model.Add(
                sum(
                    (HEAVY_WEIGHT if str(scenes[i][1]).strip().lower() == "heavy" else LIGHT_WEIGHT) * N[i, j]
                    for i in range(num_scenes)
                ) <= DIRECTOR_CAPACITY // 2
            )
        
        # CONSTRAINT #2
        # if scene i is filmed on cluster j and requires location p, then I need to visit location p on cluster j
        # x_ij lreq_ip ≤ ∑ loc_ptj
        for i in range(num_scenes):
            loc = str(scenes[i][3]).strip()

            if loc and loc in location_list:   # prevents ("", j)
                for j in range(max_days):
                    model.Add(x[i, j] <= loc_used[loc, j])

        # CONSTRAINT #21
        # every location should be filmed in exactly one feasible location group
        for p in location_list:
            if p in location_to_groups:
                model.Add(sum(cgroup[p, t] for t in location_to_groups[p]) == 1)
        
        # CONSTRAINT #14 AND #15
        # defining dloc and nloc
        for i in range(num_scenes):
            loc = str(scenes[i][3]).strip()

            if loc and loc in location_list:
                for j in range(max_days):
                    model.Add(D[i, j] <= dloc_used[loc, j])
                    model.Add(N[i, j] <= nloc_used[loc, j])
        
        # linking dloc and nloc to location usage
        # i.e. location has a DAY scene on day j ≤ location is used on day j
        for p in location_list:
            for j in range(max_days):
                model.Add(dloc_used[p, j] <= loc_used[p, j])
                model.Add(nloc_used[p, j] <= loc_used[p, j])

        # CONSTRAINT #16
        # defining b_pj
        for p in location_list:
            for j in range(max_days):
                # if both day and night -> b_pj = 1
                model.Add(both_used[p, j] <= dloc_used[p, j])
                model.Add(both_used[p, j] <= nloc_used[p, j])

                # if both are 1 -> b_pj must be 1
                model.Add(both_used[p, j] >= dloc_used[p, j] + nloc_used[p, j] - 1)

        # CONSTRAINT #17
        # only one location in a cluster may have both a scene that requires daytime filming and a scene that requires nighttime filming
        for j in range(max_days):
            model.Add(
                sum(both_used[p, j] for p in location_list) <= 1
            )

        # CONSTRAINT #13
        # max locations per day
        # ∑ loc_pj ≤ MaxLocationsPerDay
        for j in range(max_days):
            model.Add(sum(loc_used[p, j] for p in location_list) <= MAX_LOCATIONS)

        # CONSTRAINT #19
        # only 1 location group can be visited per day
        # ∑ locgroup_tj <= 1
        for j in range(max_days):
            model.Add(sum(locgroup_used[t, j] for t in group_list) <= 1)

        # CONSTRAINT #20
        # defining LocGrouptj; locations in a specific location group can only be visited if the location group is where filming will be done for the day
        # ∑ loc_ptj ≤ M(locgroup_tj)
        for p in location_list:
            if p in location_to_groups:
                for t in location_to_groups[p]:
                    for j in range(max_days):
                        model.Add(
                            loc_used[p, j] + cgroup[p, t] - 1 <= locgroup_used[t, j]
                        )

        # CONSTRAINT #1
        # defining cast
        # x_ij ≤ cast_mj
        for i in range(num_scenes):
            actors_raw = str(scenes[i][5]).strip()

            if actors_raw:  # only process if not empty
                actors_in_scene = actors_raw.split(",")

                for m in actors_in_scene:
                    m = m.strip()

                    if m and m in actor_list:   # prevents ("", j) error
                        for j in range(max_days):
                            model.Add(x[i, j] <= cast_used[m, j])
        
        # CONSTRAINT #3
        # defining staff
        # x_ij ≤ staff_qj
        for i in range(num_scenes):
            staff_raw = str(scenes[i][6]).strip()

            if staff_raw:
                staff_in_scene = staff_raw.split(",")

                for q in staff_in_scene:
                    q = q.strip()

                    if q and q in staff_list:
                        for j in range(max_days):
                            model.Add(x[i, j] <= staff_used[q, j])

        # CONSTRAINT #18
        # main cast members need to go on set for at least 50% of all filming days
        for m in actor_list:
            if m in main_cast:
                model.Add(
                    2 * sum(cast_used[m, j] for j in range(max_days)) >= sum(y[j] for j in range(max_days))
                )

        #  -----------------------------
        #  OBJECTIVE FUNCTION (MIN COST)
        #  -----------------------------

        cost_terms = []

        for j in range(max_days):
            # location costs per day
            for p in location_list:
                cost_terms.append(location_cost.get(p, 0) * loc_used[p, j])

            # actor costs per day
            for m in actor_list:
                cost_terms.append(actor_cost.get(m, 0) * cast_used[m, j])

            # staff cost per day
            for q in staff_list:
                if staff_specific.get(q, True):
                    # specialised staff
                    cost_terms.append(
                        staff_cost.get(q,0) * staff_used[q, j]
                    )

                else:
                    # non-spec staff
                    cost_terms.append(
                        staff_cost.get(q, 0) * y[j]
                    )
        
        if objective_mode == "cost":
            model.Minimize(
                sum(cost_terms) + 1000 * sum(y[j] for j in range(max_days))
            )
        else:
            model.Minimize(
                sum(y[j] for j in range(max_days))
            )

        #  ------
        #  SOLVER
        #  ------

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10
        status = solver.Solve(model)

        return {
            "status": status,
            "solver": solver,
            "x": x,
            "y": y,
            "max_days": max_days
        }

@app.route('/optimize', methods=['POST'])
def optimize():
    try:
        # get the data from google sheets
        data = request.json

        scenes_raw = data['scenes']
        actors_raw = data['actors']
        staff_raw = data['staff']
        locations_raw = data['locations']
        parameter_raw = data['parameter']

        location_groups_raw = data['location_groups']

        # remove headers from the list
        scenes = scenes_raw[1:]
        num_scenes = len(scenes)
        actors = actors_raw[1:]
        staff = staff_raw[1:]
        locations = locations_raw[1:]
        parameter_rows = parameter_raw[1:]

        parameter = {row[0]: row[1] for row in parameter_rows}

        # location group mapping
        # {"LocationGroup1": ["House", "Cafe"]}

        location_group_dict = {}

        for row in location_groups_raw:
            group_name = str(row[0]).strip()

            if not group_name.startswith("LocationGroup"):
                continue

            assigned_locations = []

            for cell in row[1:]:
                loc = str(cell).strip()
                if loc:
                    assigned_locations.append(loc)

            if assigned_locations:
                location_group_dict[group_name] = assigned_locations

        # parameter safety net (if sheet empty -> use default values)
        MAX_DAYS = int(parameter.get("MaxDays", 100) or 100)
        MAX_LOCATIONS = 2

        DIRECTOR_CAPACITY = int(parameter.get("DirectorCapacity", 50) or 50)

        HEAVY_WEIGHT = int(parameter.get("HeavySceneWeight", 2) or 2)
        LIGHT_WEIGHT = int(parameter.get("LightSceneWeight", 1) or 1)

        main_cast_raw = str(parameter.get("MainCharacter", ""))

        # allow multiple names separated by comma
        main_cast = [m.strip() for m in main_cast_raw.split(",") if m.strip()]

        # cost parameters -> CONSTANTS
        actor_cost = {row[0]: int(row[1]) for row in actors if row[1]}
        staff_cost = {row[0]: int(row[1]) for row in staff if row[1]}

        staff_specific = {
            row[0]: str(row[2]).strip().upper() == "TRUE"
            for row in staff
            if row[0]
        }

        location_cost = {row[0]: int(row[1]) for row in locations if row[1]}

        used_fallback = False
        final_days = MAX_DAYS

        result = solve_schedule(
            scenes,
            actors,
            staff,
            locations,
            parameter,
            location_group_dict,
            actor_cost,
            staff_cost,
            staff_specific,
            location_cost,
            main_cast,
            DIRECTOR_CAPACITY,
            HEAVY_WEIGHT,
            LIGHT_WEIGHT,
            MAX_LOCATIONS,
            MAX_DAYS,
            objective_mode="cost"
        )

        if result["status"] not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:

            relaxed_result = solve_schedule(
                scenes,
                actors,
                staff,
                locations,
                parameter,
                location_group_dict,
                actor_cost,
                staff_cost,
                staff_specific,
                location_cost,
                main_cast,
                DIRECTOR_CAPACITY,
                HEAVY_WEIGHT,
                LIGHT_WEIGHT,
                MAX_LOCATIONS,
                100,
                objective_mode="min_days"
            )

            if relaxed_result["status"] not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                return jsonify({
                    "error": "No feasible solution found",
                    "initial_status": int(result["status"]),
                    "relaxed_status": int(relaxed_result["status"])
                }), 500

            relaxed_solver = relaxed_result["solver"]
            relaxed_y = relaxed_result["y"]

            D_min = sum(
                relaxed_solver.Value(relaxed_y[j])
                for j in range(100)
            )

            used_fallback = True
            final_days = D_min

            result = solve_schedule(
                scenes,
                actors,
                staff,
                locations,
                parameter,
                location_group_dict,
                actor_cost,
                staff_cost,
                staff_specific,
                location_cost,
                main_cast,
                DIRECTOR_CAPACITY,
                HEAVY_WEIGHT,
                LIGHT_WEIGHT,
                MAX_LOCATIONS,
                D_min,
                objective_mode="cost",
                exact_days=D_min
            )

        #  ------
        #  OUTPUT
        #  ------

        solver = result["solver"]
        x = result["x"]
        y = result["y"]
        max_days = result["max_days"]

        schedule = []

        for j in range(max_days):

            # only process active filming days
            if solver.Value(y[j]) == 1:
                
                day_scenes = []
                
                for i in range(num_scenes):
                    if solver.Value(x[i, j]) == 1:
                        day_scenes.append(scenes[i][0])
                
                # MUST BE INSIDE LOOP
                if day_scenes:
                    schedule.append(day_scenes)

        # add day labels AFTER filtering
        formatted_schedule = []
        max_len = 0

        for idx, scenes_list in enumerate(schedule):
            row = [f"Day {idx + 1}"] + scenes_list
            formatted_schedule.append(row)

            if len(row) > max_len:
                max_len = len(row)

        # pad rows
        for row in formatted_schedule:
            while len(row) < max_len:
                row.append("")

        return jsonify({
            "schedule": formatted_schedule,
            "used_fallback": used_fallback,
            "final_days": final_days
        })
    
    except Exception as e:
        return jsonify({
            "error": str(e),
            "trace": traceback.format_exc()
        }), 500

@app.route('/')
def home():
    return "LP Solver Successfully Running"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)

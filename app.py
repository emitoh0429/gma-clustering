from flask import Flask, request, jsonify
from ortools.sat.python import cp_model

app = Flask(__name__)

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

        # remove headers from the list
        scenes = scenes_raw[1:]
        actors = actors_raw[1:]
        staff = staff_raw[1:]
        locations = locations_raw[1:]
        parameter_rows = parameter_raw[1:]

        parameter = {row[0]: row[1] for row in parameter_rows}

        # parameter safety net (if sheet empty -> use default values)
        MAX_DAYS = int(parameter.get("MaxDays", 8) or 8)
        MAX_LOCATIONS = 2

        DIRECTOR_CAPACITY = int(parameter.get("DirectorCapacity", 10) or 10)

        main_cast_raw = str(parameter.get("MainCharacter", ""))

        # allow multiple names separated by comma
        main_cast = [m.strip() for m in main_cast_raw.split(",") if m.strip()]

        # cost parameters -> CONSTANTS
        actor_cost = {row[0]: int(row[1]) for row in actors if row[1]}
        staff_cost = {row[0]: int(row[1]) for row in staff if row[1]}
        location_cost = {row[0]: int(row[1]) for row in locations if row[1]}

        # MODEL
        model = cp_model.CpModel()

        num_scenes = len(scenes)
        max_days = num_scenes #worst case scenario

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

        # time decision variable
        D = {}
        N = {}

        for i in range(num_scenes):
            for j in range(max_days):
                D[i, j] = model.NewBoolVar(f"D_{i}_{j}")
                N[i, j] = model.NewBoolVar(f"N_{i}_{j}")

        location_list = list(set(scene[3] for scene in scenes if scene[3]))
        actor_list = list(actor_cost.keys())
        staff_list = list(staff_cost.keys())

        # loc_pj = 1 if location p will be visited on day j; 0 otherwise
        loc_used = {(p, j): model.NewBoolVar(f"loc_{p}_{j}") for p in location_list for j in range(max_days)}

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

        # each scene must be clustered exactly once
        # ∑ x_ij = 1
        for i in range(num_scenes):
            model.Add(sum(x[i, j] for j in range(max_days)) == 1)

        # each scene needs to be filmed either during the day or night
        for i in range(num_scenes):
            for j in range(max_days):
                model.Add(D[i, j] + N[i, j] == x[i, j])

        # defining y_j
        # y_j ≥ x_ij
        for i in range(num_scenes):
            for j in range(max_days):
                model.Add(x[i, j] <= y[j])

        # FIXED time of day rules from the input
        for i in range(num_scenes):
            time = str(scenes[i][2]).upper()

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
        
        # number of clusters cannot exceed maximum number of filming days
        # ∑ y_j ≤ MaxDays
        model.Add(sum(y[j] for j in range(max_days)) <= MAX_DAYS)

        ## consecutive day usage (day 1,2,3... NO GAPS)
        ## i.e. if day 3 has scenes then so must day 1 and 2
        for j in range(max_days):
            model.Add(
                sum(x[i, j] for i in range(num_scenes)) >= y[j]
            )

        # daytime capacity (0.5DCap)
        # ∑ (weight_i + Day_i + x_ij) ≤ 0.5 * DCap
        # (DCap // 2 to remove decimal)
        for j in range(max_days):
            model.Add(
                sum(
                    (2 if scenes[i][1] == "Heavy" else 1) * D[i, j]
                    for i in range(num_scenes)
                ) <= DIRECTOR_CAPACITY // 2
            )
        
        # nighttime capacity (0.5DCap)
        # ∑ (weight_i + Night_i + x_ij) ≤ 0.5 * DCap
        # (DCap // 2 to remove decimal)
        for j in range(max_days):
            model.Add(
                sum(
                    (2 if scenes[i][1] == "Heavy" else 1) * N[i, j]
                    for i in range(num_scenes)
                ) <= DIRECTOR_CAPACITY // 2
            )
        
        # defining loc
        # x_ij ≤ loc_pj
        for i in range(num_scenes):
            loc = str(scenes[i][3]).strip()

            if loc and loc in location_list:   # prevents ("", j)
                for j in range(max_days):
                    model.Add(x[i, j] <= loc_used[loc, j])

        # defining dloc and nloc
        for i in range(num_scenes):
            loc = str(scenes[i][3]).strip()

            if loc and loc in location_list:
                for j in range(max_days):
                    model.Add(D[i, j] <= dloc_used[loc, j])
                    model.Add(N[i, j] <= nloc_used[loc, j])
        
        # linking dloc and nloc to location usage
        for p in location_list:
            for j in range(max_days):
                model.Add(dloc_used[p, j] <= loc_used[p, j])
                model.Add(nloc_used[p, j] <= loc_used[p, j])

        # defining b_pj
        for p in location_list:
            for j in range(max_days):
                # if both day and night -> b_pj = 1
                model.Add(both_used[p, j] <= dloc_used[p, j])
                model.Add(both_used[p, j] <= nloc_used[p, j])

                # if both are 1 -> b_pj must be 1
                model.Add(both_used[p, j] >= dloc_used[p, j] + nloc_used[p, j] - 1)

        # only one location in a cluster may have both a scene that requires daytime filming and a scene that requires nighttime filming
        for j in range(max_days):
            model.Add(
                sum(both_used[p, j] for p in location_list) <= 1
            )

        # max locations per day
        # ∑ loc_pj ≤ MaxLocationsPerDay
        for j in range(max_days):
            model.Add(sum(loc_used[p, j] for p in location_list) <= MAX_LOCATIONS)

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
                cost_terms.append(staff_cost.get(q, 0) * staff_used[q, j])
        
        model.Minimize(sum(cost_terms))

        #  ------
        #  SOLVER
        #  ------

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10
        solver.Solve(model)

        #  ------
        #  OUTPUT
        #  ------

        schedule = []

        for j in range(max_days):
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

        return jsonify({"schedule": formatted_schedule})  
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return "LP Solver Successfully Running"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)

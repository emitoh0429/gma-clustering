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

        # cost parameters -> CONSTANTS
        actor_cost = {row[0]: row[1] for row in actors}
        staff_cost = {row[0]: row[1] for row in staff}
        location_cost = {row[0]: row[1] for row in locations}

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

        location_list = list(set(scene[3] for scene in scenes))
        actor_list = list(actor_cost.keys())
        staff_list = list(staff_cost.keys())

        # loc_pj = 1 if location p will be visited on day j; 0 otherwise
        loc_used = {(p, j): model.NewBoolVar(f"loc_{p}_{j}") for p in location_list for j in range(max_days)}

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

        # defining y_j
        # y_j ≥ x_ij
        for i in range(num_scenes):
            for j in range(max_days):
                model.Add(x[i, j] <= y[j])
        
        # number of clusters cannot exceed maximum number of filming days
        # ∑ y_j ≤ MaxDays
        model.Add(sum(y[j] for j in range(max_days)) <= MAX_DAYS)

        # director's capacity for heavy vs light scenes (TOTAL)
        # ∑ (weight_i * x_ij) ≤ DCap ∀j
        for j in range(max_days):
            model.Add(
                sum(
                    (2 if scenes[i][1] == "Heavy" else 1) * x[i, j]
                    for i in range(num_scenes)
                ) <= DIRECTOR_CAPACITY
            )

        # daytime capacity (0.5DCap)
        # ∑ (weight_i + Day_i + x_ij) ≤ 0.5 * DCap
        # (DCap // 2 to remove decimal)
        for j in range(max_days):
            model.Add(
                sum(
                    (2 if scenes[i][1] == "Heavy" else 1) *
                    (1 if str(scenes[i][2]).upper() == "DAY" else 0) * x[i, j]
                    for i in range(num_scenes)
                ) <= DIRECTOR_CAPACITY // 2
            )
        
        # defining loc
        # x_ij ≤ loc_pj
        for i in range(num_scenes):
            loc = scenes[i][3]
            for j in range(max_days):
                model.Add(x[i, j] <= loc_used[loc, j])

        # max locations per day
        # ∑ loc_pj ≤ MaxLocationsPerDay
        for j in range(max_days):
            model.Add(sum(loc_used[p, j] for p in location_list) <= MAX_LOCATIONS)

        # defining cast
        # x_ij ≤ cast_mj
        for i in range(num_scenes):
            actors_in_scene = str(scenes[i][5]).split(",")
            for m in actors_in_scene:
                m = m.strip()
                for j in range(max_days):
                    model.Add(x[i, j] <= cast_used[m, j])
        
        # defining staff
        # x_ij ≤ staff_qj
        for i in range(num_scenes):
            staff_in_scene = str(scenes[i][6]).split(",")
            for q in staff_in_scene:
                q = q.strip()
                for j in range(max_days):
                    model.Add(x[i, j] <= staff_used[q, j])

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
            if solver.Value(y[j]) == 1:
                day_scenes = []
                for i in range(num_scenes):
                    if solver.Value(x[i, j]) == 1:
                        day_scenes.append(scenes[i][0])
                schedule.append([f"Day {len(schedule)+1}"] + day_scenes)

        return jsonify({"schedule": schedule})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return "LP Solver Successfully Running"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)

from flask import Flask, request, jsonify
# flask = server; request = receiving the data; jsonify = send JSON back (app script uses this language)

app = Flask(__name__)
# for the web server so we can run the code in google sheets

@app.route('/optimize', methods=['POST']) # for the API
def optimize():
    try:
        data = request.json
         # retrieve the data from the google sheets

        scenes = data.get('scenes', [])

        scenes = sorted(scenes, key=lambda x: (x.get('Location', ''), x.get('Type', ''), x.get('Actors', ''))) 
        # sort scenes first based on the variables; scenes do not have to be filmed in order

        if not scenes:
            return jsonify({"schedule": [["No data received"]]}), 200
        # extract the SCENES tab data


# ONLY CHANGE THIS WHEN ADDING VARIABLES 

        days = [] # list to store shooting days
        current_day = [] # list scenes for current days
        current_locations = set() # unique locations used in current day
        heavy_count = 0 # count heavy scenes
        light_count = 0 # count light scenes
        current_actors = set() # track actors in a current day


# ONLY CHANGE THIS PART OF THE CODE

        # loop through each scene possibility
        for scene in scenes:
            scene_type = scene.get('Type', '') # get if scene is heavy or light
            location = scene.get('Location', '') # get the location of the scene
            actor = scene.get('Actors','') 

            # check what will happen if we add a certain location
            temp_locations = current_locations.copy()
            temp_locations.add(location)
            location_change = len(temp_locations) > 1 # true if location changes within the day

            actor_change = actor not in current_actors

            # RULES WHEN THE LOCATION CHANGES
            if location_change:
                if scene_type == "Heavy" and heavy_count >= 2:
                    days.append(current_day)
                    # save current day

                    current_day = []
                    current_locations = set()
                    current_actors = set()
                    heavy_count = 0
                    light_count = 0
                    # reset everything when filming for a NEW day

                elif scene_type == "Light" and light_count >= 6:
                    days.append(current_day)
                    current_day = []
                    current_locations = set()
                    current_actors = set()
                    heavy_count = 0
                    light_count = 0
            
            # RULES WHEN LOCATION STAYS THE SAME
            else:
                if scene_type == "Heavy" and heavy_count >= 4:
                    days.append(current_day)
                    current_day = []
                    current_locations = set()
                    current_actors = set()
                    heavy_count = 0
                    light_count = 0
                elif scene_type == "Light" and light_count >= 9:
                    days.append(current_day)
                    current_day = []
                    current_locations = set()
                    current_actors = set()
                    heavy_count = 0
                    light_count = 0

            if len(current_actors) >= 3 and actor_change: # if already have 3 actors and new actor appears, start new day
                days.append(current_day)
                current_day = []
                current_locations = set()
                current_actors = set()
                heavy_count = 0
                light_count = 0

            # ADDING SCENES
            current_day.append(scene.get('SceneID')) # add the sceneID to the current day
            current_locations.add(location) # track the location used
            current_actors.add(actor)

            if scene_type == "Heavy":
                heavy_count += 1 # increase heavy count
            else:
                light_count += 1 # increase light count

        if current_day:
            days.append(current_day)
        # add the last day if it has scenes

        schedule = [] # FINAL OUTPUT LIST
        for i, d in enumerate(days):
            schedule.append([f"Day {i+1}"] + d)
            # for formatting purposes

        return jsonify({"schedule": schedule}) # send results to google sheets

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/')
def home():
    return "Server is running"


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)

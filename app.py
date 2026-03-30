from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/optimize', methods=['POST'])
def optimize():
    try:
        data = request.json
        scenes = data.get('scenes', [])

        if not scenes:
            return jsonify({"schedule": [["No data received"]]}), 200

        days = []
        current_day = []
        current_locations = set()
        heavy_count = 0
        light_count = 0

        for scene in scenes:
            scene_type = scene.get('Type', '')
            location = scene.get('Location', '')

            temp_locations = current_locations.copy()
            temp_locations.add(location)
            location_change = len(temp_locations) > 1

            if location_change:
                if scene_type == "Heavy" and heavy_count >= 2:
                    days.append(current_day)
                    current_day = []
                    current_locations = set()
                    heavy_count = 0
                    light_count = 0
                elif scene_type == "Light" and light_count >= 6:
                    days.append(current_day)
                    current_day = []
                    current_locations = set()
                    heavy_count = 0
                    light_count = 0
            else:
                if scene_type == "Heavy" and heavy_count >= 4:
                    days.append(current_day)
                    current_day = []
                    current_locations = set()
                    heavy_count = 0
                    light_count = 0
                elif scene_type == "Light" and light_count >= 9:
                    days.append(current_day)
                    current_day = []
                    current_locations = set()
                    heavy_count = 0
                    light_count = 0

            current_day.append(scene.get('SceneID'))
            current_locations.add(location)

            if scene_type == "Heavy":
                heavy_count += 1
            else:
                light_count += 1

        if current_day:
            days.append(current_day)

        schedule = []
        for i, d in enumerate(days):
            schedule.append([f"Day {i+1}"] + d)

        return jsonify({"schedule": schedule})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/')
def home():
    return "Server is running"


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
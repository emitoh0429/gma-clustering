from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/optimize', methods=['POST'])
def optimize():
    try:
        data = request.json
        scenes = data.get('scenes', [])
        actor_fees = data.get('actor_fees', {})

        scenes = sorted(scenes, key=lambda x: (x.get('Location', ''), x.get('Type', ''), x.get('Actors', '')))

        if not scenes:
            return jsonify({"schedule": []}), 200

        days = []
        current_day = []
        current_locations = set()
        heavy_count = 0
        light_count = 0
        current_actors = set()

        for scene in scenes:
            scene_type = scene.get('Type', '')
            location = scene.get('Location', '')
            actor = scene.get('Actors', '')

            temp_locations = current_locations.copy()
            temp_locations.add(location)
            location_change = len(temp_locations) > 1
            actor_change = actor not in current_actors

            if location_change:
                if scene_type == "Heavy" and heavy_count >= 2:
                    days.append(current_day)
                    current_day, current_locations, current_actors = [], set(), set()
                    heavy_count, light_count = 0, 0
                elif scene_type == "Light" and light_count >= 6:
                    days.append(current_day)
                    current_day, current_locations, current_actors = [], set(), set()
                    heavy_count, light_count = 0, 0
            else:
                if scene_type == "Heavy" and heavy_count >= 4:
                    days.append(current_day)
                    current_day, current_locations, current_actors = [], set(), set()
                    heavy_count, light_count = 0, 0
                elif scene_type == "Light" and light_count >= 9:
                    days.append(current_day)
                    current_day, current_locations, current_actors = [], set(), set()
                    heavy_count, light_count = 0, 0

            if len(current_actors) >= 3 and actor_change:
                days.append(current_day)
                current_day, current_locations, current_actors = [], set(), set()
                heavy_count, light_count = 0, 0

            current_day.append(scene)
            current_locations.add(location)
            current_actors.add(actor)
            if scene_type == "Heavy":
                heavy_count += 1
            else:
                light_count += 1

        if current_day:
            days.append(current_day)

        schedule = []
        total_cost = 0

        for i, day_scenes in enumerate(days, start=1):
            scene_ids = [s.get('SceneID') for s in day_scenes]
            day_actors = set()

            for scene in day_scenes:
                actors_raw = scene.get('Actors', '')
                for a in actors_raw.split(','):
                    day_actors.add(a.strip())

            day_cost = sum(actor_fees.get(a, 0) for a in day_actors)
            total_cost += day_cost

            schedule.append({
                "day": f"Day {i}",
                "scenes": scene_ids,
                "actors_used": list(day_actors),
                "actor_cost": day_cost
            })

        return jsonify({
            "schedule": schedule,
            "total_actor_cost": total_cost
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/')
def home():
    return "Server is running"


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)

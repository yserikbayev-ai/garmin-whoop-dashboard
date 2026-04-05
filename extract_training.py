"""
Extract today's training data from running dashboard API.
"""

import requests
import json
from datetime import date

BASE_URL = "http://127.0.0.1:5000"

def extract_training():
    today = date.today().isoformat()

    # Fetch from API
    try:
        stats = requests.get(f"{BASE_URL}/api/garmin/stats", timeout=5).json()
        activities = requests.get(f"{BASE_URL}/api/garmin/activities", timeout=5).json()
        heartrate = requests.get(f"{BASE_URL}/api/garmin/heartrate", timeout=5).json()
        sleep = requests.get(f"{BASE_URL}/api/garmin/sleep", timeout=5).json()
    except requests.exceptions.ConnectionError:
        print("❌ Flask server not running at http://127.0.0.1:5000")
        print("Start it with: python3 app.py")
        return None
    except requests.exceptions.Timeout:
        print("❌ Flask server timeout (Garmin API may be rate-limited)")
        print("Wait 15-30 minutes and try again.")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Server error: {e}")
        print("Check Flask logs: cat /tmp/garmin_app.log")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

    # Filter activities for today
    today_activities = [a for a in activities if a["start"].startswith(today)]

    training_data = {
        "date": today,
        "daily_summary": {
            "steps": stats.get("steps", 0),
            "distance_km": stats.get("distanceKm", 0),
            "calories": round(stats.get("calories", 0)),
            "active_calories": round(stats.get("activeCalories", 0)),
            "resting_hr": stats.get("restingHR", 0),
            "stress": stats.get("stress", 0),
            "intensity_minutes": stats.get("intensityMinutes", 0),
            "floors_climbed": stats.get("floorsClimbed", 0),
        },
        "sleep_last_night": {
            "total_hours": sleep.get("durationHours", 0),
            "deep_hours": sleep.get("deepSleep", 0),
            "light_hours": sleep.get("lightSleep", 0),
            "rem_hours": sleep.get("remSleep", 0),
            "awake_hours": sleep.get("awake", 0),
            "score": sleep.get("score", 0),
        },
        "heart_rate": {
            "resting": heartrate.get("resting", 0),
            "data_points": len(heartrate.get("points", [])),
        },
        "activities": [
            {
                "name": a.get("name", ""),
                "type": a.get("type", ""),
                "start_time": a.get("start", ""),
                "duration_minutes": a.get("durationMin", 0),
                "distance_km": a.get("distanceKm", 0),
                "calories": a.get("calories", 0),
                "avg_heart_rate": a.get("avgHR", 0),
                "max_heart_rate": a.get("maxHR", 0),
            }
            for a in today_activities
        ]
    }

    return training_data

def print_training(data):
    if not data:
        return

    print(f"\n{'='*70}")
    print(f"  TRAINING SUMMARY - {data['date']}")
    print(f"{'='*70}\n")

    # Daily stats
    s = data['daily_summary']
    print("📊 DAILY STATS")
    print(f"  👟 Steps:         {s['steps']:>10,}")
    print(f"  📍 Distance:      {s['distance_km']:>10} km")
    print(f"  🔥 Calories:      {s['calories']:>10,} kcal")
    print(f"  ⚡ Active Cal:    {s['active_calories']:>10} kcal")
    print(f"  ❤️  Resting HR:   {s['resting_hr']:>10} bpm")
    print(f"  🧘 Stress:        {s['stress']:>10}")
    print(f"  ⏱️  Intensity:    {s['intensity_minutes']:>10} min")
    print(f"  🏢 Floors:        {s['floors_climbed']:>10}\n")

    # Sleep
    sl = data['sleep_last_night']
    print("😴 SLEEP (Last Night)")
    print(f"  Duration:       {sl['total_hours']:>7.1f} hours")
    print(f"  Deep:           {sl['deep_hours']:>7.1f} hours")
    print(f"  Light:          {sl['light_hours']:>7.1f} hours")
    print(f"  REM:            {sl['rem_hours']:>7.1f} hours")
    print(f"  Awake:          {sl['awake_hours']:>7.1f} hours")
    if sl['score']:
        print(f"  Score:          {sl['score']:>7.0f}")
    print()

    # Workouts
    if data['activities']:
        print("🏃 WORKOUTS TODAY")
        for i, act in enumerate(data['activities'], 1):
            print(f"\n  [{i}] {act['name']} ({act['type']})")
            print(f"      Time:       {act['start_time']}")
            print(f"      Duration:   {act['duration_minutes']} minutes")
            if act['distance_km'] > 0:
                print(f"      Distance:   {act['distance_km']} km")
            if act['calories']:
                print(f"      Calories:   {act['calories']} kcal")
            if act['avg_heart_rate']:
                print(f"      HR:         {act['avg_heart_rate']} avg / {act['max_heart_rate']} max bpm")
    else:
        print("🏃 WORKOUTS TODAY")
        print("  None logged\n")

    print(f"{'='*70}\n")

if __name__ == "__main__":
    import sys

    data = extract_training()

    if "--json" in sys.argv:
        if data:
            print(json.dumps(data, indent=2))
    else:
        print_training(data)
        if data:
            print("💾 Export as JSON: python3 extract_training.py --json")

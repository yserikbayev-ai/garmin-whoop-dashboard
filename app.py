from flask import Flask, jsonify, render_template, redirect, request, session
from garminconnect import Garmin
from datetime import date, timedelta
import os, requests, urllib.parse, json, pathlib

app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- Garmin ---
GARMIN_EMAIL    = os.getenv("GARMIN_EMAIL", "yserikbayev@gmail.com")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD", "Abylay2007!")
GARMIN_TOKEN_FILE = pathlib.Path("/tmp/garmin_tokens.json")

# --- Whoop OAuth2 ---
WHOOP_CLIENT_ID     = os.getenv("WHOOP_CLIENT_ID", "")
WHOOP_CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET", "")
# Use 127.0.0.1 — Chrome blocks OAuth redirects to "localhost"
WHOOP_REDIRECT_URI  = "http://127.0.0.1:5000/whoop/callback"
WHOOP_AUTH_URL      = "https://api.prod.whoop.com/oauth/oauth2/auth"
WHOOP_TOKEN_URL     = "https://api.prod.whoop.com/oauth/oauth2/token"
WHOOP_API_BASE      = "https://api.prod.whoop.com/developer/v1"
WHOOP_SCOPES        = "offline read:recovery read:cycles read:sleep read:workout read:profile read:body_measurement"

_garmin = None

def garmin_client():
    global _garmin
    if _garmin is not None:
        return _garmin
    client = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
    # Use cached tokens to avoid rate-limiting
    if GARMIN_TOKEN_FILE.exists():
        try:
            tokens = json.loads(GARMIN_TOKEN_FILE.read_text())
            client.set_tokens(tokens)
            _garmin = client
            return _garmin
        except Exception:
            pass
    client.login()
    GARMIN_TOKEN_FILE.write_text(json.dumps(client.get_tokens()))
    _garmin = client
    return _garmin

def whoop_token():
    return session.get("whoop_token")

def whoop_get(path, params=None):
    token = whoop_token()
    if not token:
        return None
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{WHOOP_API_BASE}{path}", headers=headers, params=params)
    if resp.status_code == 401:
        session.pop("whoop_token", None)
        return None
    return resp.json()


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    whoop_connected = bool(whoop_token())
    whoop_needs_setup = not WHOOP_CLIENT_ID
    return render_template("index.html",
                           whoop_connected=whoop_connected,
                           whoop_needs_setup=whoop_needs_setup)

# ── Whoop OAuth ────────────────────────────────────────────────────────────────

@app.route("/whoop/login")
def whoop_login():
    if not WHOOP_CLIENT_ID:
        return "Set WHOOP_CLIENT_ID env var first.", 400
    params = {
        "client_id": WHOOP_CLIENT_ID,
        "redirect_uri": WHOOP_REDIRECT_URI,
        "response_type": "code",
        "scope": WHOOP_SCOPES,
    }
    # Open in browser — use 127.0.0.1 as Chrome blocks OAuth redirects to "localhost"
    return redirect(f"{WHOOP_AUTH_URL}?{urllib.parse.urlencode(params)}")

@app.route("/whoop/callback")
def whoop_callback():
    code = request.args.get("code")
    if not code:
        return "No code returned.", 400
    resp = requests.post(WHOOP_TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": WHOOP_REDIRECT_URI,
        "client_id": WHOOP_CLIENT_ID,
        "client_secret": WHOOP_CLIENT_SECRET,
    })
    data = resp.json()
    session["whoop_token"] = data.get("access_token")
    return redirect("/")

@app.route("/whoop/logout")
def whoop_logout():
    session.pop("whoop_token", None)
    return redirect("/")


# ── Garmin API ─────────────────────────────────────────────────────────────────

@app.route("/api/garmin/stats")
def garmin_stats():
    c = garmin_client()
    today = date.today().isoformat()
    d = c.get_stats(today)
    return jsonify({
        "steps": d.get("totalSteps", 0),
        "calories": d.get("totalKilocalories", 0),
        "activeCalories": d.get("activeKilocalories", 0),
        "restingHR": d.get("restingHeartRate", 0),
        "stress": d.get("averageStressLevel", 0),
        "intensityMinutes": d.get("moderateIntensityMinutes", 0) + d.get("vigorousIntensityMinutes", 0),
        "distanceKm": round(d.get("totalDistanceMeters", 0) / 1000, 2),
        "floorsClimbed": d.get("floorsAscended", 0),
    })

@app.route("/api/garmin/heartrate")
def garmin_heartrate():
    c = garmin_client()
    today = date.today().isoformat()
    d = c.get_heart_rates(today)
    readings = d.get("heartRateValues", []) or []
    points = [{"time": r[0], "bpm": r[1]} for r in readings if r[1] is not None]
    return jsonify({"resting": d.get("restingHeartRate", 0), "points": points})

@app.route("/api/garmin/sleep")
def garmin_sleep():
    c = garmin_client()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    d = c.get_sleep_data(yesterday)
    dto = d.get("dailySleepDTO", {})
    scores = dto.get("sleepScores", {})
    score = scores.get("overall", {}).get("value", 0) if isinstance(scores, dict) else 0
    return jsonify({
        "durationHours": round(dto.get("sleepTimeSeconds", 0) / 3600, 2),
        "deepSleep": round(dto.get("deepSleepSeconds", 0) / 3600, 2),
        "lightSleep": round(dto.get("lightSleepSeconds", 0) / 3600, 2),
        "remSleep": round(dto.get("remSleepSeconds", 0) / 3600, 2),
        "awake": round(dto.get("awakeSleepSeconds", 0) / 3600, 2),
        "score": score,
    })

@app.route("/api/garmin/activities")
def garmin_activities():
    c = garmin_client()
    raw = c.get_activities(0, 10)
    return jsonify([{
        "name": a.get("activityName", "Unknown"),
        "type": a.get("activityType", {}).get("typeKey", "unknown"),
        "start": a.get("startTimeLocal", ""),
        "durationMin": round(a.get("duration", 0) / 60, 1),
        "distanceKm": round(a.get("distance", 0) / 1000, 2),
        "calories": a.get("calories", 0),
        "avgHR": a.get("averageHR", 0),
        "maxHR": a.get("maxHR", 0),
    } for a in raw])


# ── Whoop API ──────────────────────────────────────────────────────────────────

@app.route("/api/whoop/recovery")
def whoop_recovery():
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    data = whoop_get("/recovery", {"start": yesterday, "end": today, "limit": 1})
    if not data or not data.get("records"):
        return jsonify({"connected": False})
    r = data["records"][0]
    score = r.get("score", {})
    return jsonify({
        "connected": True,
        "recoveryScore": score.get("recovery_score", 0),
        "hrv": score.get("hrv_rmssd_milli", 0),
        "restingHR": score.get("resting_heart_rate", 0),
        "spo2": score.get("spo2_percentage", 0),
        "skinTemp": score.get("skin_temp_celsius", 0),
    })

@app.route("/api/whoop/sleep")
def whoop_sleep():
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    data = whoop_get("/activity/sleep", {"start": yesterday, "end": today, "limit": 1})
    if not data or not data.get("records"):
        return jsonify({"connected": False})
    r = data["records"][0]
    score = r.get("score", {})
    stage = score.get("stage_summary", {})
    return jsonify({
        "connected": True,
        "sleepScore": score.get("sleep_performance_percentage", 0),
        "durationHours": round(r.get("end", 0) and
            (sum([stage.get("total_light_sleep_time_milli", 0),
                  stage.get("total_slow_wave_sleep_time_milli", 0),
                  stage.get("total_rem_sleep_time_milli", 0)])) / 3_600_000, 2),
        "remHours": round(stage.get("total_rem_sleep_time_milli", 0) / 3_600_000, 2),
        "lightHours": round(stage.get("total_light_sleep_time_milli", 0) / 3_600_000, 2),
        "deepHours": round(stage.get("total_slow_wave_sleep_time_milli", 0) / 3_600_000, 2),
        "awakeHours": round(stage.get("total_awake_time_milli", 0) / 3_600_000, 2),
    })

@app.route("/api/whoop/strain")
def whoop_strain():
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    data = whoop_get("/cycle", {"start": yesterday, "end": today, "limit": 1})
    if not data or not data.get("records"):
        return jsonify({"connected": False})
    r = data["records"][0]
    score = r.get("score", {})
    return jsonify({
        "connected": True,
        "strain": score.get("strain", 0),
        "avgHR": score.get("average_heart_rate", 0),
        "maxHR": score.get("max_heart_rate", 0),
        "calories": score.get("kilojoule", 0) and round(score.get("kilojoule", 0) / 4.184),
    })

@app.route("/api/whoop/workouts")
def whoop_workouts():
    today = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    data = whoop_get("/activity/workout", {"start": week_ago, "end": today, "limit": 10})
    if not data or not data.get("records"):
        return jsonify({"connected": False, "records": []})
    records = []
    for w in data["records"]:
        score = w.get("score", {})
        records.append({
            "sport": w.get("sport_id", 0),
            "start": w.get("start", ""),
            "durationMin": round((score.get("strain", 0) or 0) and
                sum([1]) and  # placeholder
                (w.get("end") and w.get("start") and 1) or 0),
            "strain": score.get("strain", 0),
            "avgHR": score.get("average_heart_rate", 0),
            "maxHR": score.get("max_heart_rate", 0),
            "calories": round(score.get("kilojoule", 0) / 4.184) if score.get("kilojoule") else 0,
        })
    return jsonify({"connected": True, "records": records})


if __name__ == "__main__":
    app.run(debug=True, port=5000)

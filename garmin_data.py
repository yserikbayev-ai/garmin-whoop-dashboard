"""
Garmin Connect data access using the garminconnect library.
Fetches activities, heart rate, steps, sleep, and body composition data.
"""

import os
import json
from datetime import date, timedelta
from getpass import getpass

from garminconnect import Garmin


def get_client(email: str = None, password: str = None) -> Garmin:
    """Authenticate and return a Garmin client."""
    email = email or os.getenv("GARMIN_EMAIL") or input("Garmin email: ")
    password = password or os.getenv("GARMIN_PASSWORD") or getpass("Garmin password: ")

    client = Garmin(email, password)
    client.login()
    print("Logged in successfully.")
    return client


def get_activities(client: Garmin, count: int = 10) -> list:
    """Fetch recent activities."""
    activities = client.get_activities(0, count)
    return activities


def get_steps(client: Garmin, target_date: date = None) -> dict:
    """Fetch step data for a given date (defaults to today)."""
    target_date = target_date or date.today()
    return client.get_steps_data(target_date.isoformat())


def get_heart_rate(client: Garmin, target_date: date = None) -> dict:
    """Fetch heart rate data for a given date."""
    target_date = target_date or date.today()
    return client.get_heart_rates(target_date.isoformat())


def get_sleep(client: Garmin, target_date: date = None) -> dict:
    """Fetch sleep data for a given date."""
    target_date = target_date or date.today()
    return client.get_sleep_data(target_date.isoformat())


def get_body_composition(client: Garmin, target_date: date = None) -> dict:
    """Fetch body composition (weight, BMI, etc.) for a given date."""
    target_date = target_date or date.today()
    return client.get_body_composition(target_date.isoformat())


def get_stats(client: Garmin, target_date: date = None) -> dict:
    """Fetch daily stats summary."""
    target_date = target_date or date.today()
    return client.get_stats(target_date.isoformat())


def print_activity_summary(activities: list) -> None:
    """Print a human-readable activity summary."""
    print(f"\n--- Last {len(activities)} Activities ---")
    for act in activities:
        name = act.get("activityName", "Unknown")
        activity_type = act.get("activityType", {}).get("typeKey", "unknown")
        start = act.get("startTimeLocal", "N/A")
        duration_sec = act.get("duration", 0)
        duration_min = round(duration_sec / 60, 1)
        distance_m = act.get("distance", 0)
        distance_km = round(distance_m / 1000, 2)

        print(f"  [{start}] {name} ({activity_type}) — {duration_min} min, {distance_km} km")


def main():
    client = get_client()
    today = date.today()
    yesterday = today - timedelta(days=1)

    # Daily stats
    print("\n--- Daily Stats (today) ---")
    stats = get_stats(client, today)
    print(json.dumps(stats, indent=2))

    # Steps
    print("\n--- Steps (today) ---")
    steps = get_steps(client, today)
    print(json.dumps(steps, indent=2))

    # Heart rate
    print("\n--- Heart Rate (today) ---")
    hr = get_heart_rate(client, today)
    resting_hr = hr.get("restingHeartRate", "N/A")
    print(f"Resting HR: {resting_hr} bpm")

    # Sleep (yesterday, since today's sleep isn't complete)
    print("\n--- Sleep (yesterday) ---")
    sleep = get_sleep(client, yesterday)
    sleep_seconds = sleep.get("dailySleepDTO", {}).get("sleepTimeSeconds", 0)
    print(f"Sleep duration: {round(sleep_seconds / 3600, 2)} hours")

    # Recent activities
    activities = get_activities(client, count=5)
    print_activity_summary(activities)


if __name__ == "__main__":
    main()

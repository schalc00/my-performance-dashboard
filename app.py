import streamlit as str
import pandas as pd
import datetime
import zoneinfo
from garminconnect import Garmin
from PIL import Image
from google import genai

# 1. Page Configuration (Wide Layout für optimale Spaltenaufteilung)
str.set_page_config(page_title="Alec's Dashboard", page_icon="⚡", layout="wide")

# Passwort-Schutz für das Smartphone / Online-Hosting
def check_password():
    if "password_correct" not in str.session_state:
        str.text_input("Bitte Dashboard-Passwort eingeben:", type="password", key="password")
        if str.button("Login"):
            if str.session_state["password"] == str.secrets["DASHBOARD_PASSWORD"]:
                str.session_state["password_correct"] = True
                str.rerun()
            else:
                str.error("Falsches Passwort")
        return False
    return True

if check_password():
    
    # ==========================================
    # API INITIALISIERUNG AUS DEN CLOUD-SECRETS
    # ==========================================
    GARMIN_EMAIL = str.secrets["GARMIN_EMAIL"]
    GARMIN_PASSWORD = str.secrets["GARMIN_PASSWORD"]
    GEMINI_API_KEY = str.secrets["GEMINI_API_KEY"]
    
    # Gemini Client starten
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

    # GARMIN DATENABRUF (Cached für 10 Minuten, um Server-Spam zu vermeiden)
    @str.cache_data(ttl=600)
    def fetch_garmin_data():
        try:
            client = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
            client.login()
            
            # Holt das exakte Datum basierend auf der deutschen Zeitzone
            berlin_time = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Berlin"))
            today = berlin_time.date().isoformat()
            
            # Datenpakete von Garmin ziehen
            stats = client.get_stats(today)
            heart_rates = client.get_heart_rates(today)
            sleep_data = client.get_sleep_data(today)
            activities = client.get_activities(0, 1)
            
            # Letztes Workout extrahieren
            last_workout = "Kein Workout heute getrackt"
            if activities:
                w_type = activities[0].get('activityType', {}).get('typeKey', 'Workout')
                w_dur = round(activities[0].get('duration', 0) / 60)
                w_cal = round(activities[0].get('calories', 0))
                last_workout = f"{w_type}: {w_dur} Min ({w_cal} kcal)"
            
            # Schlafdaten extrahieren
            sleep_dto = sleep_data.get("dailySleepDTO", {}) if sleep_data else {}
            sleep_hours = round(sleep_dto.get("sleepTimeSeconds", 0) / 3600, 1) if sleep_dto else 0
            sleep_score = sleep_dto.get("sleepScore", "--") if sleep_dto else "--"
            
            # Sicherheitsnetz für unterschiedliche Garmin-Variablennamen (Keys)
            steps_value = stats.get("steps") or stats.get("totalSteps") or stats.get("summary", {}).get("steps", 0)
            active_cal_value = stats.get("activeCalories") or stats.get("activeCaloriesBurned") or stats.get("summary", {}).get("activeCalories", 0)
            total_cal_value = stats.get("totalCalories") or stats.get("summary", {}).get("totalCalories", 2200)
            step_goal_value = stats.get("stepsGoal") or stats.get("summary", {}).get("stepsGoal", 10000)

            garmin_pack = {
                "rhr": heart_rates.get("restingHeartRate", "--"),
                "max_hr": heart_rates.get("maxHeartRate", "--"),
                "last_workout": last_workout,
                "steps": int(steps_value) if steps_value else 0,
                "step_goal": int(step_goal_value) if step_goal_value else 10000,
                "active_cal": int(active_cal_value) if active_cal_value else 0,
                "total_cal": int(total_cal_value) if total_cal_value else 2200,
                "sleep_duration": sleep_hours,
                "sleep_score": sleep_score,
                "deep_sleep": round(sleep_dto.get("deepSleepSeconds", 0) / 60) if sleep_dto else 0,
            }
            return garmin_pack, True
        except Exception as e:
            # Fallback-Werte, falls die API temporär blockiert ist
            fallback = {
                "rhr": 45, "max_hr": 185, "last_workout": "Verbindung wird synchronisiert...",
                "steps": 0, "step_goal": 10000, "active_cal": 0, "total_cal": 2200,
                "sleep_duration": 0, "sleep_

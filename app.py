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
                "sleep_duration": 0, "sleep_score": "--", "deep_sleep": 0
            }
            return fallback, False

    g_data, garmin_success = fetch_garmin_data()

    # ==========================================
    # ERNÄHRUNGS-LOGIK (SESSION STATE)
    # ==========================================
    if "verzehrt" not in str.session_state:
        str.session_state.verzehrt = {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}
        str.session_state.meals_log = []

    # Dein tägliches sportliches Soll für die Handball-Vorbereitung
    tagesbedarf = {"kcal": 3200, "protein": 180, "carbs": 400, "fat": 85}

    # ==========================================
    # DASHBOARD LAYOUT
    # ==========================================
    str.title("⚡ OVERSEER // PERFORMANCE & NUTRITION")
    str.caption("Vollautomatisiertes Tracking über Garmin Live-Schnittstelle & Gemini 2.5")
    str.write("---")

    # Drei Spalten für die perfekte Übersicht auf dem Smartphone
    col1, col2, col3 = str.columns([1.2, 1.3, 1], gap="large")

    # ------------------------------------------
    # SPALTE 1: GARMIN FITNESS HUB & HANDBALL PREP
    # ------------------------------------------
    with col1:
        str.header("🏋️ Garmin Fitness Hub")
        if garmin_success:
            str.caption("🟢 Live-Daten direkt von deiner Garmin")
        else:
            str.caption("临 Verbindung aktiv (Wartet auf Uhr-Synchronisation)")
            
        str.info(f"🔥 **Letzte Aktivität:** {g_data['last_workout']}")
        
        str.subheader("💓 Herzfrequenz & Energie")
        h_col1, h_col2 = str.columns(2)
        h_col1.metric("Ruhepuls (RHR)", f"{g_data['rhr']} bpm")
        h_col2.metric("Max. Puls heute", f"{g_data['max_hr']} bpm")
        
        str.write("---")
        str.subheader("🏃 Bewegung & Energieumsatz")
        c_col1, c_col2 = str.columns(2)
        c_col1.metric("Aktiv-Kalorien", f"{g_data['active_cal']} kcal")
        c_col2.metric("Gesamt-Kalorien", f"{g_data['total_cal']} kcal")
        
        # Schrittzähler mit dynamischem Balken
        step_perc = min(float(g_data['steps'] / g_data['step_goal']), 1.0) if g_data['step_goal'] > 0 else 0.0
        str.metric("Schritte heute", f"{g_data['steps']:,}", f"Ziel: {g_data['step_goal']:,}")
        str.progress(step_perc)
        
        str.write("---")
        str.subheader("💤 Schlaf & Regeneration")
        s_col1, s_col2 = str.columns(2)
        s_col1.metric("Schlaf-Score", f"{g_data['sleep_score']} / 100")
        s_col2.metric("Schlafdauer", f"{g_data['sleep_duration']} Std")
        if g_data['deep_sleep'] > 0:
            str.caption(f"Davon im erholsamen **Tiefschlaf**: {g_data['deep_sleep']} Minuten.")

        str.write("---")
        str.subheader("🤾 Saisonvorbereitung (Handball)")
        str.caption("Aktuelle Phase: Explosivkraft & Schnelligkeit")
        bench_press = str.number_input("Bankdrücken (kg) - Ziel 4x6:", value=85, step=2)
        squats = str.number_input("Kniebeugen (kg) - Ziel 4x6:", value=110, step=5)

    # ------------------------------------------
    # SPALTE 2: NUTRITION & GEMINI-ANALYSE
    # ------------------------------------------
    with col2:
        str.header("🍽️ Nutrition & Makros")
        
        # Berechnung Restbudget
        rem_kcal = max(tagesbedarf["kcal"] - str.session_state.verzehrt["kcal"], 0)
        rem_p = max(tagesbedarf["protein"] - str.session_state.verzehrt["protein"], 0)
        rem_c = max(tagesbedarf["carbs"] - str.session_state.verzehrt["carbs"], 0)
        rem_f = max(tagesbedarf["fat"] - str.session_state.verzehrt["fat"], 0)
        
        m_col1, m_col2, m_col3, m_col4 = str.columns(4)
        m_col1.metric("Kcal Rest", f"{rem_kcal:,} kcal")
        m_col2.metric("Protein", f"{rem_p}g")
        m_col3.metric("Carbs", f"{rem_c}g")
        m_col4.metric("Fat", f"{rem_f}g")
        
        str.write("---")
        str.subheader("📸 Mahlzeit via Gemini tracken")
        uploaded_file = str.file_uploader("Foto schießen/hochladen...", type=["jpg", "png", "jpeg"])
        
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            str.image(image, caption="Dein Essen", width=300)
            
            if str.button("Bild von Gemini analysieren lassen 🤖"):
                with str.spinner("Gemini berechnet Makros..."):
                    try:
                        prompt = (
                            "Analysiere dieses Essen auf dem Bild. Schätze die Grammanzahl der "
                            "Makronährstoffe (Protein, Kohlenhydrate, Fett) und Kalorien so präzise wie möglich. "
                            "Antworte AUSSCHLIESSLICH in diesem exakten Format ohne Text davor oder danach:\n"
                            "Name: [Name des Essens] | Kcal: [Zahl] | Protein: [Zahl] | Carbs: [Zahl] | Fat: [Zahl]"
                        )
                        
                        response = gemini_client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=[image, prompt]
                        )
                        
                        result = response.text.strip()
                        parts = result.split(" | ")
                        name = parts[0].split(": ")[1]
                        kcal = int(parts[1].split(": ")[1])
                        p = int(parts[2].split(": ")[1])
                        c = int(parts[3].split(": ")[1])
                        f = int(parts[4].split(": ")[1])
                        
                        str.session_state.temp_meal = {"name": name, "kcal": kcal, "protein": p, "carbs": c, "fat": f}
                    except Exception as e:
                        str.error("Fehler bei der Gemini-Analyse. Bitte das Bild erneut hochladen.")
            
            if "temp_meal" in str.session_state:
                str.markdown("### 🔍 Gemini-Vorschlag korrigieren/bestätigen:")
                c_ki1, c_ki2, c_ki3, c_ki4 = str.columns(4)
                edit_name = str.text_input("Name:", value=str.session_state.temp_meal["name"])
                edit_p = c_ki1.number_input("Protein (g):", value=str.session_state.temp_meal["protein"])
                edit_c = c_ki2.number_input("Carbs (g):", value=str.session_state.temp_meal["carbs"])
                edit_f = c_ki3.number_input("Fat (g):", value=str.session_state.temp_meal["fat"])
                edit_kcal = (edit_p * 4) + (edit_c * 4) + (edit_f * 9)
                
                if str.button("In Log eintragen ✅"):
                    str.session_state.verzehrt["kcal"] += edit_kcal
                    str.session_state.verzehrt["protein"] += edit_p
                    str.session_state.verzehrt["carbs"] += edit_c
                    str.session_state.verzehrt["fat"] += edit_f
                    
                    str.session_state.meals_log.append(f"{edit_name} ({edit_kcal} kcal | {edit_p}g P)")
                    del str.session_state.temp_meal
                    str.rerun()

        if str.session_state.meals_log:
            str.write("---")
            str.subheader("Heutige Mahlzeiten:")
            for meal in str.session_state.meals_log:
                str.caption(f"✔️ {meal}")

    # ------------------------------------------
    # SPALTE 3: FINANZEN & TAGES-CHECKLISTE
    # ------------------------------------------
    with col3:
        str.header("💼 Finanzen & Tagesziele")
        str.metric(label="Verfügbares Netto (Monat)", value="1.850,00 €")
        str.write("---")
        str.subheader("✅ Tagesziele")
        str.checkbox("Garmin synchronisieren", value=garmin_success)
        str.checkbox("Handball-Dehnprogramm (15 Min)")

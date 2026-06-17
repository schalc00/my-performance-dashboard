import streamlit as str
import pandas as pd
import datetime
import zoneinfo
from garminconnect import Garmin
from PIL import Image
from google import genai

# 1. Page Configuration (Breites Layout für optimale Spaltennutzung)
str.set_page_config(page_title="Alec's Dashboard", page_icon="⚡", layout="wide")

# Passwort-Schutz für das Smartphone
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
    
    # API INITIALISIERUNG
    GARMIN_EMAIL = str.secrets["GARMIN_EMAIL"]
    GARMIN_PASSWORD = str.secrets["GARMIN_PASSWORD"]
    GEMINI_API_KEY = str.secrets["GEMINI_API_KEY"]
    
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

    # MAXIMALER GARMIN DATENABRUF (Cached für 5 Minuten)
    @str.cache_data(ttl=300)
    def fetch_garmin_data():
        try:
            client = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
            client.login()
            
            # Deutsche Zeitzone für exaktes Datum
            berlin_time = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Berlin"))
            today = berlin_time.date().isoformat()
            
            # Die mächtigsten Garmin-Endpunkte abrufen
            summary = client.get_user_summary(today)
            heart_rates = client.get_heart_rates(today)
            sleep_data = client.get_sleep_data(today)
            activities = client.get_activities(0, 3) # Holt die letzten 3 Workouts
            
            # 1. Workouts auslesen
            workout_list = []
            if activities:
                for act in activities:
                    w_type = act.get('activityType', {}).get('typeKey', 'Workout')
                    w_dur = round(act.get('duration', 0) / 60)
                    w_cal = round(act.get('calories', 0))
                    workout_list.append(f"✔️ {w_type}: {w_dur} Min ({w_cal} kcal)")
            last_workout = workout_list[0] if workout_list else "Kein Workout heute getrackt"
            
            # 2. Schlafdaten & Phasen auslesen
            sleep_dto = sleep_data.get("dailySleepDTO", {}) if sleep_data else {}
            sleep_hours = round(sleep_dto.get("sleepTimeSeconds", 0) / 3600, 1) if sleep_dto else 0
            sleep_score = sleep_dto.get("sleepScore", "--") if sleep_dto else "--"
            deep_sleep = round(sleep_dto.get("deepSleepSeconds", 0) / 60) if sleep_dto else 0
            light_sleep = round(sleep_dto.get("lightSleepSeconds", 0) / 60) if sleep_dto else 0
            rem_sleep = round(sleep_dto.get("remSleepSeconds", 0) / 60) if sleep_dto else 0
            awake_time = round(sleep_dto.get("awakeSleepSeconds", 0) / 60) if sleep_dto else 0
            
            # 3. Aktivität & Kalorien aus der Summary (Viel präziser!)
            steps = summary.get("totalSteps") or summary.get("steps") or 0
            step_goal = summary.get("stepsGoal") or 10000
            active_cal = round(summary.get("activeCalories", 0))
            bmr_cal = round(summary.get("bmrCalories", 0))
            total_cal = round(summary.get("totalCalories", 0))
            distance_km = round(summary.get("distanceInMeters", 0) / 1000, 2)
            floors = summary.get("floorsClimbed", 0)
            
            # Intensitätsminuten
            mod_min = summary.get("moderateIntensityMinutes", 0)
            vig_min = summary.get("vigorousIntensityMinutes", 0)
            total_intensity = mod_min + (vig_min * 2) # Intensive Minuten zählen doppelt
            intensity_goal = summary.get("intensityMinutesGoal", 150)
            
            # Stresslevel
            stress_avg = summary.get("averageStressLevel", "--")
            if stress_avg == -1 or stress_avg == 0:
                stress_avg = "--"

            garmin_pack = {
                "rhr": heart_rates.get("restingHeartRate", "--"),
                "max_hr": heart_rates.get("maxHeartRate", "--"),
                "last_workout": last_workout,
                "workout_list": workout_list,
                "steps": steps,
                "step_goal": step_goal,
                "active_cal": active_cal,
                "bmr_cal": bmr_cal,
                "total_cal": total_cal,
                "distance_km": distance_km,
                "floors": floors,
                "total_intensity": total_intensity,
                "intensity_goal": intensity_goal,
                "sleep_duration": sleep_hours,
                "sleep_score": sleep_score,
                "deep_sleep": deep_sleep,
                "light_sleep": light_sleep,
                "rem_sleep": rem_sleep,
                "awake_time": awake_time,
                "stress_avg": stress_avg
            }
            return garmin_pack, True
        except Exception as e:
            fallback = {
                "rhr": "--", "max_hr": "--", "last_workout": "Synchronisiere...", "workout_list": [],
                "steps": 0, "step_goal": 10000, "active_cal": 0, "bmr_cal": 0, "total_cal": 0,
                "distance_km": 0.0, "floors": 0, "total_intensity": 0, "intensity_goal": 150,
                "sleep_duration": 0, "sleep_score": "--", "deep_sleep": 0, "light_sleep": 0, "rem_sleep": 0, "awake_time": 0,
                "stress_avg": "--"
            }
            return fallback, False

    g_data, garmin_success = fetch_garmin_data()

    # ERNÄHRUNGS-LOGIK (SESSION STATE)
    if "verzehrt" not in str.session_state:
        str.session_state.verzehrt = {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}
        str.session_state.meals_log = []

    tagesbedarf = {"kcal": 3200, "protein": 180, "carbs": 400, "fat": 85}

    # DASHBOARD LAYOUT
    str.title("⚡ OVERSEER // TOTAL PERFORMANCE")
    str.write("---")

    col1, col2, col3 = str.columns([1.3, 1.3, 1], gap="large")

    # ==========================================
    # SPALTE 1: DER KOMPLETTE GARMIN LIVE HUB
    # ==========================================
    with col1:
        str.header("🏋️ Garmin Vital-Zentrale")
        
        # 1. Energie & Kalorien (Jetzt lückenlos)
        with str.expander("🔥 Energie & Kalorienumsatz", expanded=True):
            en_col1, en_col2, en_col3 = str.columns(3)
            en_col1.metric("Aktiv-Verbrauch", f"{g_data['active_cal']} kcal")
            en_col2.metric("Ruhebedarf (BMR)", f"{g_data['bmr_cal']} kcal")
            en_col3.metric("Gesamt-Umsatz", f"{g_data['total_cal']} kcal")
            str.caption("Der Aktiv-Verbrauch berechnet sich aus deinen Schritten und getrackten Einheiten.")

        # 2. Bewegung & Tracker-Ziele
        with str.expander("🏃 Aktivität & Tagesziele", expanded=True):
            st_col1, st_col2, st_col3 = str.columns(3)
            st_col1.metric("Schritte", f"{g_data['steps']:,}")
            st_col2.metric("Distanz", f"{g_data['distance_km']} km")
            st_col3.metric("Etagen", f"{g_data['floors']}")
            
            # Schrittziel-Balken
            step_perc = min(float(g_data['steps'] / g_data['step_goal']), 1.0) if g_data['step_goal'] > 0 else 0.0
            str.progress(step_perc)
            str.caption(f"Schrittziel: {g_data['step_goal']:,} ({int(step_perc*100)}% erreicht)")
            
            str.write("---")
            # Intensitätsminuten
            int_perc = min(float(g_data['total_intensity'] / g_data['intensity_goal']), 1.0) if g_data['intensity_goal'] > 0 else 0.0
            str.metric("Intensitätsminuten (Woche)", f"{g_data['total_intensity']} Min", f"Ziel: {g_data['intensity_goal']} Min")
            str.progress(int_perc)

        # 3. Schlaf- & Regenerationsanalyse (Exakte Aufteilung)
        with str.expander("💤 Schlaf & Regeneration", expanded=True):
            sl_col1, sl_col2, sl_col3 = str.columns(3)
            sl_col1.metric("Schlaf-Score", f"{g_data['sleep_score']} / 100")
            sl_col2.metric("Schlafdauer", f"{g_data['sleep_duration']} Std")
            sl_col3.metric("Stress (Ø heute)", f"{g_data['stress_avg']} / 100")
            
            if g_data['sleep_duration'] > 0:
                str.write("---")
                str.markdown("**Schlafphasen-Aufteilung:**")
                ph_col1, ph_col2, ph_col3, ph_col4 = str.columns(4)
                ph_col1.metric("Tief", f"{g_data['deep_sleep']}m")
                ph_col2.metric("Leicht", f"{g_data['light_sleep']}m")
                ph_col3.metric("REM", f"{g_data['rem_sleep']}m")
                ph_col4.metric("Wach", f"{g_data['awake_time']}m")

        # 4. Herzfrequenz & Trainingsverlauf
        with str.expander("💓 Puls & Letzte Workouts", expanded=False):
            p_col1, p_col2 = str.columns(2)
            p_col1.metric("Ruhepuls (RHR)", f"{g_data['rhr']} bpm")
            p_col2.metric("Maximalpuls heute", f"{g_data['max_hr']} bpm")
            
            str.write("---")
            str.markdown("**Letzte getrackte Einheiten:**")
            if g_data['workout_list']:
                for w in g_data['workout_list']:
                    str.write(w)
            else:
                str.caption("Keine Workouts in den letzten Tagen gefunden.")

    # ==========================================
    # SPALTE 2: NUTRITION & GEMINI-ANALYSE
    # ==========================================
    with col2:
        str.header("🍽️ Nutrition & Makros")
        
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

    # ==========================================
    # SPALTE 3: FINANZEN & TAGES-CHECKLISTE
    # ==========================================
    with col3:
        str.header("💼 Finanzen & Tagesziele")
        str.metric(label="Verfügbares Netto (Monat)", value="1.850,00 €")
        str.write("---")
        str.subheader("✅ Tagesziele")
        str.checkbox("Garmin heute synchronisiert", value=garmin_success)
        str.checkbox("Handball-Dehnprogramm (15 Min)")

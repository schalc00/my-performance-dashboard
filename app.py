import streamlit as str
import pandas as pd
import datetime
import zoneinfo
from garminconnect import Garmin
from PIL import Image
from google import genai

# 1. Page Configuration (Breites Layout für 4 Spalten)
str.set_page_config(page_title="Alec's Performance Dashboard", page_icon="⚡", layout="wide")

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
    
    # ==========================================
    # API INITIALISIERUNG
    # ==========================================
    GARMIN_EMAIL = str.secrets["GARMIN_EMAIL"]
    GARMIN_PASSWORD = str.secrets["GARMIN_PASSWORD"]
    GEMINI_API_KEY = str.secrets["GEMINI_API_KEY"]
    
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

    # VOLLSTÄNDIGER GARMIN DATENABRUF (Cached für 5 Minuten)
    @str.cache_data(ttl=300)
    def fetch_garmin_data():
        try:
            client = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
            client.login()
            
            berlin_time = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Berlin"))
            today = berlin_time.date().isoformat()
            
            summary = client.get_user_summary(today)
            heart_rates = client.get_heart_rates(today)
            sleep_data = client.get_sleep_data(today)
            activities = client.get_activities(0, 5) # Letzten 5 Einheiten
            
            # Workouts extrahieren
            workout_list = []
            if activities:
                for act in activities:
                    w_type = act.get('activityType', {}).get('typeKey', 'Workout')
                    w_dur = round(act.get('duration', 0) / 60)
                    w_cal = round(act.get('calories', 0))
                    workout_list.append(f"💪 {w_type}: {w_dur} Min ({w_cal} kcal)")
            
            # Schlaf & Phasen extrahieren
            sleep_dto = sleep_data.get("dailySleepDTO", {}) if sleep_data else {}
            sleep_hours = round(sleep_dto.get("sleepTimeSeconds", 0) / 3600, 1) if sleep_dto else 0
            sleep_score = sleep_dto.get("sleepScore", "--") if sleep_dto else "--"
            deep_sleep = round(sleep_dto.get("deepSleepSeconds", 0) / 60) if sleep_dto else 0
            light_sleep = round(sleep_dto.get("lightSleepSeconds", 0) / 60) if sleep_dto else 0
            rem_sleep = round(sleep_dto.get("remSleepSeconds", 0) / 60) if sleep_dto else 0
            awake_time = round(sleep_dto.get("awakeSleepSeconds", 0) / 60) if sleep_dto else 0
            
            # Aktivität & Energie
            steps = summary.get("totalSteps") or summary.get("steps") or 0
            step_goal = summary.get("stepsGoal") or 10000
            active_cal = round(summary.get("activeCalories", 0))
            bmr_cal = round(summary.get("bmrCalories", 0))
            total_cal = round(summary.get("totalCalories", 0))
            distance_km = round(summary.get("distanceInMeters", 0) / 1000, 2)
            floors = summary.get("floorsClimbed", 0)
            
            # Intensität & Stress
            mod_min = summary.get("moderateIntensityMinutes", 0)
            vig_min = summary.get("vigorousIntensityMinutes", 0)
            total_intensity = mod_min + (vig_min * 2)
            intensity_goal = summary.get("intensityMinutesGoal", 150)
            
            stress_avg = summary.get("averageStressLevel", "--")
            if stress_avg == -1 or stress_avg == 0:
                stress_avg = "--"

            garmin_pack = {
                "rhr": heart_rates.get("restingHeartRate", "--"),
                "max_hr": heart_rates.get("maxHeartRate", "--"),
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
                "rhr": "--", "max_hr": "--", "workout_list": ["Synchronisiere..."],
                "steps": 0, "step_goal": 10000, "active_cal": 0, "bmr_cal": 0, "total_cal": 0,
                "distance_km": 0.0, "floors": 0, "total_intensity": 0, "intensity_goal": 150,
                "sleep_duration": 0, "sleep_score": "--", "deep_sleep": 0, "light_sleep": 0, 
                "rem_sleep": 0, "awake_time": 0, "stress_avg": "--"
            }
            return fallback, False

    g_data, garmin_success = fetch_garmin_data()

    # ERNÄHRUNGS-LOGIK (SESSION STATE)
    if "verzehrt" not in str.session_state:
        str.session_state.verzehrt = {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}
        str.session_state.meals_log = []

    # Exakt auf 102kg optimiertes Ziel: Defizit für Fettabbau bei maximalem Muskelerhalt
    tagesbedarf = {"kcal": 2600, "protein": 204, "carbs": 260, "fat": 80}

    # DASHBOARD LAYOUT (4 Spalten)
    str.title("⚡ OVERSEER // TOTAL CONTROL HUB")
    str.write("---")

    col1, col2, col3, col4 = str.columns([1, 1, 1.1, 1.2], gap="medium")

    # ==========================================
    # SPALTE 1: GARMIN VITALS & REGENERATION
    # ==========================================
    with col1:
        str.header("💓 Vitals & Schlaf")
        if garmin_success:
            str.caption("🟢 Garmin Live-Verbindung aktiv")
        else:
            str.caption("臨 Warte auf Uhr-Synchronisation...")
            
        str.metric("Ruhepuls (RHR)", f"{g_data['rhr']} bpm")
        str.metric("Maximalpuls heute", f"{g_data['max_hr']} bpm")
        str.metric("Stress-Level (Ø)", f"{g_data['stress_avg']} / 100")
        
        str.write("---")
        str.subheader("💤 Schlafphasen")
        str.metric("Schlaf-Score", f"{g_data['sleep_score']} / 100")
        str.metric("Schlafdauer", f"{g_data['sleep_duration']} Std")
        
        if g_data['sleep_duration'] > 0:
            str.caption(f" davon Tiefschlaf: {g_data['deep_sleep']} Min.")
            str.caption(f" davon REM-Schlaf: {g_data['rem_sleep']} Min.")
            str.caption(f" davon Leichter Schlaf: {g_data['light_sleep']} Min.")
            str.caption(f" davon Wachphase: {g_data['awake_time']} Min.")

    # ==========================================
    # SPALTE 2: GARMIN AKTIVITÄT & KALORIEN
    # ==========================================
    with col2:
        str.header("🔥 Aktivität & Energie")
        
        str.metric("Aktiv-Verbrauch", f"{g_data['active_cal']} kcal")
        str.metric("Grundumsatz (BMR)", f"{g_data['bmr_cal']} kcal")
        str.metric("Gesamt-Umsatz", f"{g_data['total_cal']} kcal")
        
        str.write("---")
        str.subheader("🏃 Bewegung tracking")
        str.metric("Schritte", f"{g_data['steps']:,}")
        step_perc = min(float(g_data['steps'] / g_data['step_goal']), 1.0) if g_data['step_goal'] > 0 else 0.0
        str.progress(step_perc)
        str.caption(f"Ziel: {g_data['step_goal']:,} ({int(step_perc*100)}%)")
        
        str.write("---")
        str.metric("Tagesdistanz", f"{g_data['distance_km']} km")
        str.metric("Etagen geklettert", f"{g_data['floors']}")
        
        str.write("---")
        str.subheader("📊 Letzte Garmin Einheiten")
        for w in g_data['workout_list']:
            str.write(w)

    # ==========================================
    # SPALTE 3: NUTRITION & GEMINI AI SCANNER
    # ==========================================
    with col3:
        str.header("🍽️ Ernährung (102kg)")
        str.caption("Ziel: Fettabbau & Muskelschutz")
        
        rem_kcal = max(tagesbedarf["kcal"] - str.session_state.verzehrt["kcal"], 0)
        rem_p = max(tagesbedarf["protein"] - str.session_state.verzehrt["protein"], 0)
        rem_c = max(tagesbedarf["carbs"] - str.session_state.verzehrt["carbs"], 0)
        rem_f = max(tagesbedarf["fat"] - str.session_state.verzehrt["fat"], 0)
        
        str.metric("Kcal Restbudget", f"{rem_kcal:,} kcal", f"Ziel: {tagesbedarf['kcal']}")
        str.metric("Protein Rest", f"{rem_p}g", f"Ziel: {tagesbedarf['protein']}g", delta_color="inverse")
        
        nut_col1, nut_col2 = str.columns(2)
        nut_col1.metric("Carbs Rest", f"{rem_c}g")
        nut_col2.metric("Fat Rest", f"{rem_f}g")
        
        str.write("---")
        str.subheader("📸 Mahlzeit via Gemini scannen")
        uploaded_file = str.file_uploader("Foto hochladen...", type=["jpg", "png", "jpeg"])
        
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            str.image(image, caption="Dein Essen", width=200)
            
            if str.button("Bild analysieren 🤖"):
                with str.spinner("Gemini berechnet Makros..."):
                    try:
                        prompt = (
                            "Analysiere dieses Essen auf dem Bild. Schätze die Grammanzahl der "
                            "Makronährstoffe (Protein, Kohlenhydrate, Fett) und Kalorien so präzise wie möglich. "
                            "Antworte AUSSCHLIESSLICH in diesem exakten Format ohne Text davor oder danach:\n"
                            "Name: [Name des Essens] | Kcal: [Zahl] | Protein: [Zahl] | Carbs: [Zahl] | Fat: [Zahl]"
                        )
                        response = gemini_client.models.generate_content(model='gemini-2.5-flash', contents=[image, prompt])
                        result = response.text.strip().split(" | ")
                        
                        name = result[0].split(": ")[1]
                        kcal = int(result[1].split(": ")[1])
                        p = int(result[2].split(": ")[1])
                        c = int(result[3].split(": ")[1])
                        f = int(result[4].split(": ")[1])
                        
                        str.session_state.temp_meal = {"name": name, "kcal": kcal, "protein": p, "carbs": c, "fat": f}
                    except:
                        str.error("Fehler bei der Analyse. Versuch es noch mal.")
            
            if "temp_meal" in str.session_state:
                str.markdown("### 🔍 Vorschlag bestätigen:")
                edit_name = str.text_input("Name:", value=str.session_state.temp_meal["name"])
                c_ki1, c_ki2, c_ki3 = str.columns(3)
                edit_p = c_ki1.number_input("Protein:", value=str.session_state.temp_meal["protein"])
                edit_c = c_ki2.number_input("Carbs:", value=str.session_state.temp_meal["carbs"])
                edit_f = c_ki3.number_input("Fat:", value=str.session_state.temp_meal["fat"])
                edit_kcal = (edit_p * 4) + (edit_c * 4) + (edit_f * 9)
                
                if str.button("Eintragen ✅"):
                    str.session_state.verzehrt["kcal"] += edit_kcal
                    str.session_state.verzehrt["protein"] += edit_p
                    str.session_state.verzehrt["carbs"] += edit_c
                    str.session_state.verzehrt["fat"] += edit_f
                    str.session_state.meals_log.append(f"{edit_name} ({edit_kcal} kcal | {edit_p}g P)")
                    del str.session_state.temp_meal
                    str.rerun()

        if str.session_state.meals_log:
            for meal in str.session_state.meals_log:
                str.caption(f"✔️ {meal}")

    # ==========================================
    # SPALTE 4: HANDBALL PLAN & FINANZEN
    # ==========================================
    with col4:
        str.header("📅 Workout & Orga")
        
        tab1, tab2, tab3, tab4, tab5 = str.tabs(["T1: OK Kraft", "T2: HB Legs", "T3: OK Vol", "T4: Speed", "T5: Cardio"])
        
        with tab1:
            str.caption("Grundkraft Oberkörper")
            str.checkbox("Bankdrücken (4x6)")
            str.checkbox("Klimmzüge / Latzug (4x8)")
            str.checkbox("Overhead Press (3x8)")
            str.checkbox("Langhantelrudern (3x10)")
            
        with tab2:
            str.caption("Handball-Spezifische Beinkraft & Gelenkschutz")
            str.checkbox("Bulgarian Split Squats (4x8 je Seite)")
            str.checkbox("Trap-Bar Kreuzheben (4x6)")
            str.checkbox("Box Jumps / Plyometrie (3x5)")
            str.checkbox("Lateral Lunges (3x8 je Seite)")
            str.checkbox("Nordic Hamstring Curls (3x6)")
            
        with tab3:
            str.caption("Oberkörper Hypertrophie (Muskelerhalt)")
            str.checkbox("Schrägbankdrücken KH (4x10)")
            str.checkbox("Kabelrudern eng (4x10)")
            str.checkbox("Seitheben am Kabel (3x12)")
            str.checkbox("Bizeps & Trizeps (3x12)")
            
        with tab4:
            str.caption("Schnellkraft & Rumpfstabilität für den Zweikampf")
            str.checkbox("Hang Cleans / Umsetzen (4x4)")
            str.checkbox("Medizinball-Überkopf-Würfe (3x8)")
            str.checkbox("Romanian Deadlifts (3x10)")
            str.checkbox("Plank mit Zusatzgewicht (3x45 Sek.)")
            
        with tab5:
            str.caption("Saison-Intervall & Grundlagenausdauer")
            ausdauer_wahl = str.radio("Fokus wählen:", ["Zone 2 Lauf (45-60 Min. Regeneration)", "Handball Shuttle Runs (15x 20m Sprints, 30s Pause)"])
            str.checkbox(f"Einheit beenden: {ausdauer_wahl}")

        str.write("---")
        str.subheader("📝 Kraftraum Notizen")
        str.text_area("Steigerungen festhalten:", placeholder="z.B. Beintraining: Split Squats erhöht...", key="prog_notes")

        str.write("---")
        str.subheader("💼 Finanzen & Tagesziele")
        str.metric(label="Verfügbares Netto (Monat)", value="1.850,00 €")
        str.checkbox("Handball-Dehnprogramm (15 Min)")

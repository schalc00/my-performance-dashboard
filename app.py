import streamlit as st
import pandas as pd
import datetime
import zoneinfo
from garminconnect import Garmin
from PIL import Image
from google import genai

# 1. Page Configuration (3 Spalten mit Fokus auf die Mitte)
st.set_page_config(page_title="Perform All // Alec", page_icon="⚡", layout="wide")

# Minimalistisches CSS für den authentischen "Perform All" Dark-App-Look
st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #ffffff; }
    div[data-testid="stMetricValue"] { font-size: 24px; font-weight: bold; color: #00ffcc; }
    div[data-testid="stMetricLabel"] { font-size: 13px; color: #888888; }
    .stCheckbox { padding: 5px; background-color: #161b22; border-radius: 5px; margin-bottom: 5px; }
    </style>
""", unsafe_allow_html=True)

# Passwort-Schutz für das Smartphone
def check_password():
    if "password_correct" not in st.session_state:
        st.text_input("Bitte Perform All Passwort eingeben:", type="password", key="password")
        if st.button("Login"):
            if st.session_state["password"] == st.secrets["DASHBOARD_PASSWORD"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Falsches Passwort")
        return False
    return True

if check_password():
    
    # ==========================================
    # API INITIALISIERUNG
    # ==========================================
    GARMIN_EMAIL = st.secrets["GARMIN_EMAIL"]
    GARMIN_PASSWORD = st.secrets["GARMIN_PASSWORD"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

    # GARMIN DATENABRUF (Cached für 5 Minuten)
    @st.cache_data(ttl=300)
    def fetch_garmin_data():
        try:
            client = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
            client.login()
            
            berlin_time = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Berlin"))
            today = berlin_time.date().isoformat()
            
            summary = client.get_user_summary(today)
            heart_rates = client.get_heart_rates(today)
            sleep_data = client.get_sleep_data(today)
            activities = client.get_activities(0, 4)
            
            workout_list = []
            if activities:
                for act in activities:
                    w_type = act.get('activityType', {}).get('typeKey', 'Workout')
                    w_dur = round(act.get('duration', 0) / 60)
                    w_cal = round(act.get('calories', 0))
                    workout_list.append(f"💪 {w_type}: {w_dur} Min ({w_cal} kcal)")
            
            sleep_dto = sleep_data.get("dailySleepDTO", {}) if sleep_data else {}
            sleep_hours = round(sleep_dto.get("sleepTimeSeconds", 0) / 3600, 1) if sleep_dto else 0
            sleep_score = sleep_dto.get("sleepScore", "--") if sleep_dto else "--"
            
            steps = summary.get("totalSteps") or summary.get("steps") or 0
            step_goal = summary.get("stepsGoal") or 10000
            active_cal = round(summary.get("activeCalories", 0))
            bmr_cal = round(summary.get("bmrCalories", 0))
            total_cal = round(summary.get("totalCalories", 0))
            distance_km = round(summary.get("distanceInMeters", 0) / 1000, 2)
            floors = summary.get("floorsClimbed", 0)
            
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
                "sleep_duration": sleep_hours,
                "sleep_score": sleep_score,
                "stress_avg": stress_avg
            }
            return garmin_pack, True
        except:
            fallback = {
                "rhr": "--", "max_hr": "--", "workout_list": ["Synchronisiere..."],
                "steps": 0, "step_goal": 10000, "active_cal": 0, "bmr_cal": 0, "total_cal": 0,
                "distance_km": 0.0, "floors": 0, "sleep_duration": 0, "sleep_score": "--", "stress_avg": "--"
            }
            return fallback, False

    g_data, garmin_success = fetch_garmin_data()

    # ERNÄHRUNGS-LOGIK (SESSION STATE)
    if "verzehrt" not in st.session_state:
        st.session_state.verzehrt = {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}
        st.session_state.meals_log = []

    # 102kg Makro-Soll (Defizit + High Protein)
    tagesbedarf = {"kcal": 2600, "protein": 204, "carbs": 260, "fat": 80}

    # APP HEADER (Perform All Branding)
    st.title("⚡ PERFORM ALL // ALEC")
    st.caption("High Performance Fitness & Nutrition Tracking")
    st.write("---")

    # Layout-Generierung: 3 vertikal scrollbare Spalten (Workouts prominent in der Mitte)
    col1, col2, col3 = st.columns([1, 1.4, 1.1], gap="large")

    # ==========================================
    # SPALTE 1: ALL GARMIN VITALS & CALORIES
    # ==========================================
    with col1:
        st.header("📊 Garmin Dashboard")
        
        # Energie-Sektion
        st.subheader("🔥 Kalorien & Umsatz")
        st.metric("Aktiv-Verbrauch", f"{g_data['active_cal']} kcal")
        st.metric("Gesamt-Umsatz", f"{g_data['total_cal']} kcal")
        st.caption(f"Grundbedarf (BMR): {g_data['bmr_cal']} kcal")
        
        st.write("---")
        
        # Aktivitäts-Sektion
        st.subheader("🏃 Aktivität")
        st.metric("Schritte heute", f"{g_data['steps']:,}")
        step_perc = min(float(g_data['steps'] / g_data['step_goal']), 1.0) if g_data['step_goal'] > 0 else 0.0
        st.progress(step_perc)
        st.caption(f"Ziel: {g_data['step_goal']:,} ({int(step_perc*100)}%)")
        st.write(f"Distanz: **{g_data['distance_km']} km** | Etagen: **{g_data['floors']}**")
        
        st.write("---")
        
        # Erholungs-Sektion
        st.subheader("💤 Recovery & Herz")
        st.metric("Schlaf-Score", f"{g_data['sleep_score']} / 100", f"{g_data['sleep_duration']} Std Dauer")
        st.metric("Ruhepuls (RHR)", f"{g_data['rhr']} bpm", f"Max heute: {g_data['max_hr']} bpm")
        st.metric("Stress-Level (Ø)", f"{g_data['stress_avg']} / 100")
        
        st.write("---")
        st.subheader("📝 Letzte Aktivitäten")
        for w in g_data['workout_list']:
            st.write(w)

    # ==========================================
    # SPALTE 2: PERFORM ALL WORKOUT ENGINE (MITTE)
    # ==========================================
    with col2:
        st.header("📅 Trainingsplan & Einheiten")
        st.caption("Wähle deinen Tag und hake die Übungen nach dem Satz ab.")
        
        # Das Herzstück: Die interaktiven Trainingspläne
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["T1: OK Kraft", "T2: HB Beine", "T3: OK Volumen", "T4: Schnellkraft", "T5: Ausdauer"])
        
        with tab1:
            st.subheader("Oberkörper Grundkraft")
            st.checkbox("Bankdrücken (4 Sätze x 6 Wdh.)")
            st.checkbox("Klimmzüge mit Zusatzgewicht (4 Sätze x 6 Wdh.)")
            st.checkbox("Dips / Barrenstütz (3 Sätze x 8 Wdh.)")
            st.checkbox("Langhantelrudern vorgebeugt (3 Sätze x 8 Wdh.)")
            st.checkbox("Face Pulls für Schulterstabilität (3 Sätze x 12 Wdh.)")
            
        with tab2:
            st.subheader("Handball Leg Day (Explosivität & Schutz)")
            st.checkbox("Bulgarian Split Squats (4 Sätze x 8 Wdh. je Seite) - *Richtungswechsel*")
            st.checkbox("Trap-Bar Kreuzheben (4 Sätze x 6 Wdh.) - *Maximale Beinkraft*")
            st.checkbox("Box Jumps / Rebound-Sprünge (3 Sätze x 5 Wdh.) - *Sprungwurf-Power*")
            st.checkbox("Lateral Lunges / Seitliche Ausfallschritte (3 Sätze x 8 Wdh.) - *Abwehr-Side-Steps*")
            st.checkbox("Nordic Hamstring Curls (3 Sätze x 6 Wdh.) - *Oberschenkel-Schutz*")
            
        with tab3:
            st.subheader("Oberkörper Volumen (Hypertrophie)")
            st.checkbox("Schrägbankdrücken mit Kurzhanteln (4 Sätze x 10 Wdh.)")
            st.checkbox("Kabelrudern eng zum Bauch (4 Sätze x 10 Wdh.)")
            st.checkbox("Seitheben am Kabelzug (3 Sätze x 12 Wdh.)")
            st.checkbox("Incline Bicep Curls (3 Sätze x 12 Wdh.)")
            st.checkbox("Tricep Rope Pushdowns (3 Sätze x 12 Wdh.)")
            
        with tab4:
            st.subheader("Schnellkraft & Rumpfstabilität")
            st.checkbox("Power Cleans / Umsetzen aus dem Hang (4 Sätze x 3 Wdh.)")
            st.checkbox("Medizinball-Rotationswürfe gegen die Wand (3 Sätze x 8 Wdh. je Seite)")
            st.checkbox("Romanian Deadlifts (3 Sätze x 10 Wdh.)")
            st.checkbox("Ab-Wheel Rollouts / Core-Slam (3 Sätze x max.)")
            st.checkbox("Pallof Press am Kabelzug (3 Sätze x 12 Wdh. je Seite)")
            
        with tab5:
            st.subheader("Handball Intervall- & Grundlagenausdauer")
            ausdauer_wahl = st.radio("Wähle deine heutige Cardio-Session:", ["Zone 2 Lauf (45-60 Min. Fettverbrennung & Regeneration)", "Handball Shuttle Runs (15x 20m Sprints mit abruptem Abstoppen, 30 Sek. Pause)"])
            st.checkbox(f"Session erfolgreich beendet: {ausdauer_wahl}")

        st.write("---")
        st.subheader("📝 Trainings-Notizen & Progression")
        st.text_area("Hier kannst du deine geschafften Gewichte für das nächste Mal eintragen:", placeholder="z.B. Bankdrücken erhöht auf 90kg...", key="prog_notes_all")

    # ==========================================
    # SPALTE 3: NUTRITION & FINANCIAL ORGA
    # ==========================================
    with col3:
        st.header("🍽️ Ernährung & Orga")
        
        # Live-Restbudget-Berechnung
        rem_kcal = max(tagesbedarf["kcal"] - st.session_state.verzehrt["kcal"], 0)
        rem_p = max(tagesbedarf["protein"] - st.session_state.verzehrt["protein"], 0)
        rem_c = max(tagesbedarf["carbs"] - st.session_state.verzehrt["carbs"], 0)
        rem_f = max(tagesbedarf["fat"] - st.session_state.verzehrt["fat"], 0)
        
        # Makro-Übersicht oben rechts
        st.metric("Kcal Restbudget", f"{rem_kcal:,} kcal", f"Ziel: {tagesbedarf['kcal']}")
        st.metric("Protein Rest", f"{rem_p}g", f"Ziel: {tagesbedarf['protein']}g", delta_color="inverse")
        
        nu_col1, nu_col2 = st.columns(2)
        nu_col1.metric("Carbs Rest", f"{rem_c}g")
        nu_col2.metric("Fat Rest", f"{rem_f}g")
        
        st.write("---")
        
        # Gemini Foto-Scanner
        st.subheader("📸 Mahlzeit-Scanner")
        uploaded_file = st.file_uploader("Foto aufnehmen/hochladen...", type=["jpg", "png", "jpeg"])
        
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption="Dein Essen", width=200)
            
            if st.button("Bild via Gemini scannen 🤖"):
                with st.spinner("Berechne Makros..."):
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
                        
                        st.session_state.temp_meal = {"name": name, "kcal": kcal, "protein": p, "carbs": c, "fat": f}
                    except:
                        st.error("Fehler bei der Analyse. Versuch es noch mal.")
            
            if "temp_meal" in st.session_state:
                st.markdown("### 🔍 Bestätigen:")
                edit_name = st.text_input("Name:", value=st.session_state.temp_meal["name"])
                c_ki1, c_ki2, c_ki3 = st.columns(3)
                edit_p = c_ki1.number_input("P:", value=st.session_state.temp_meal["protein"])
                edit_c = c_ki2.number_input("C:", value=st.session_state.temp_meal["carbs"])
                edit_f = c_ki3.number_input("F:", value=st.session_state.temp_meal["fat"])
                edit_kcal = (edit_p * 4) + (edit_c * 4) + (edit_f * 9)
                
                if st.button("In Log eintragen ✅"):
                    st.session_state.verzehrt["kcal"] += edit_kcal
                    st.session_state.verzehrt["protein"] += edit_p
                    st.session_state.verzehrt["carbs"] += edit_c
                    st.session_state.verzehrt["fat"] += edit_f
                    st.session_state.meals_log.append(f"{edit_name} ({edit_kcal} kcal | {edit_p}g P)")
                    del st.session_state.temp_meal
                    st.rerun()

        if st.session_state.meals_log:
            for meal in st.session_state.meals_log:
                st.caption(f"✔️ {meal}")

        # Finanzen und feste tägliche Routinen nach unten gestapelt
        st.write("---")
        st.subheader("💼 Finanzen & Daily Routine")
        st.metric(label="Verfügbares Netto (Monat)", value="1.850,00 €")
        st.checkbox("Handball-Dehnprogramm absolviert (15 Min)")

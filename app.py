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
    .stExpander { background-color: #161b22; border-radius: 8px; margin-bottom: 8px; border: 1px solid #21262d; }
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

    # ERWEITERTER GARMIN DATENABRUF (Inklusive Tiefen-Analyse für Krafttraining)
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
            activities = client.get_activities(0, 5) # Letzten 5 Einheiten
            
            workout_list = []
            garmin_strength_today = {}
            raw_strength_sets = []
            
            if activities:
                for act in activities:
                    w_type = act.get('activityType', {}).get('typeKey', 'Workout')
                    w_dur = round(act.get('duration', 0) / 60)
                    w_cal = round(act.get('calories', 0))
                    workout_list.append(f"💪 {w_type}: {w_dur} Min ({w_cal} kcal)")
                    
                    # Wenn heute ein Krafttraining absolviert wurde, ziehen wir uns die exakten Sätze!
                    act_date = act.get('startTimeLocal', '')[:10]
                    if w_type == 'strength_training' and act_date == today:
                        act_id = act.get('activityId')
                        try:
                            # Holt die Details der Hebe-Session (Sätze, Reps, Kilos)
                            details = client.get_activity_details(act_id)
                            sets = details.get('sets', []) or details.get('summaryDTO', {}).get('sets', [])
                            
                            for idx, s in enumerate(sets):
                                reps = s.get('reps', 0)
                                weight = s.get('weight', 0)
                                # Garmin speichert Gewichte manchmal in Gramm
                                if weight > 1000:
                                    weight = round(weight / 1000, 1)
                                else:
                                    weight = round(weight, 1)
                                    
                                if reps > 0:
                                    ex_name = s.get('exerciseName', 'Unbekannte Übung').lower()
                                    set_str = f"{weight} kg x {reps} Wdh."
                                    raw_strength_sets.append(f"Satz {idx+1}: {s.get('exerciseName', 'Set')} -> {set_str}")
                                    
                                    # Automatisches Keyword-Routing in Alec's Trainingsplan
                                    matched_key = None
                                    if "bench" in ex_name: matched_key = "Bankdrücken"
                                    elif "klimm" in ex_name or "pull" in ex_name: matched_key = "Klimmzüge"
                                    elif "dip" in ex_name: matched_key = "Dips"
                                    elif "row" in ex_name or "ruder" in ex_name: matched_key = "Langhantelrudern"
                                    elif "face" in ex_name: matched_key = "Face Pulls"
                                    elif "split" in ex_name or "bulgarian" in ex_name: matched_key = "Bulgarian Split Squats"
                                    elif "deadlift" in ex_name or "kreuzheben" in ex_name: matched_key = "Trap-Bar Kreuzheben"
                                    elif "jump" in ex_name or "box" in ex_name: matched_key = "Box Jumps"
                                    elif "lunge" in ex_name: matched_key = "Lateral Lunges"
                                    elif "hamstring" in ex_name or "nordic" in ex_name: matched_key = "Nordic Hamstring Curls"
                                    elif "incline" in ex_name: matched_key = "Schrägbankdrücken KH"
                                    elif "cable" in ex_name: matched_key = "Kabelrudern eng"
                                    elif "seitheben" in ex_name or "lateral" in ex_name: matched_key = "Seitheben"
                                    elif "curl" in ex_name: matched_key = "Incline Curls"
                                    elif "tricep" in ex_name or "pushdown" in ex_name: matched_key = "Trizepsdrücken"
                                    elif "clean" in ex_name: matched_key = "Power Cleans"
                                    elif "press" in ex_name: matched_key = "Pallof Press"
                                    
                                    if matched_key:
                                        if matched_key not in garmin_strength_today:
                                            garmin_strength_today[matched_key] = []
                                        garmin_strength_today[matched_key].append(set_str)
                        except:
                            pass
            
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
                "garmin_strength_today": garmin_strength_today,
                "raw_strength_sets": raw_strength_sets,
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
                "garmin_strength_today": {}, "raw_strength_sets": [],
                "steps": 0, "step_goal": 10000, "active_cal": 0, "bmr_cal": 0, "total_cal": 0,
                "distance_km": 0.0, "floors": 0, "sleep_duration": 0, "sleep_score": "--", "stress_avg": "--"
            }
            return fallback, False

    g_data, garmin_success = fetch_garmin_data()

    # ==========================================
    # DATEN-CLEANER GEGEN UNERWÜNSCHTE CRASHES
    # ==========================================
    if "meals_log" not in st.session_state:
        st.session_state.meals_log = []
    else:
        st.session_state.meals_log = [m for m in st.session_state.meals_log if isinstance(m, dict)]

    if "favorites" not in st.session_state:
        st.session_state.favorites = {
            "--- Bitte wählen ---": None,
            "Alec's Standard Frühstück (Haferflocken & Protein)": {"kcal": 580, "protein": 45, "carbs": 75, "fat": 10},
            "Post-Workout Shake (High Protein)": {"kcal": 240, "protein": 35, "carbs": 15, "fat": 2},
            "Standard Hähnchen-Reis-Pfanne": {"kcal": 720, "protein": 55, "carbs": 90, "fat": 12}
        }

    tagesbedarf = {"kcal": 2600, "protein": 204, "carbs": 260, "fat": 80}

    verzehrt_kcal = sum(m.get("kcal", 0) for m in st.session_state.meals_log)
    verzehrt_protein = sum(m.get("protein", 0) for m in st.session_state.meals_log)
    verzehrt_carbs = sum(m.get("carbs", 0) for m in st.session_state.meals_log)
    verzehrt_fat = sum(m.get("fat", 0) for m in st.session_state.meals_log)

    alle_uebungen = [
        "Bankdrücken", "Klimmzüge", "Dips", "Langhantelrudern", "Face Pulls",
        "Bulgarian Split Squats", "Trap-Bar Kreuzheben", "Box Jumps", "Lateral Lunges", "Nordic Hamstring Curls",
        "Schrägbankdrücken KH", "Kabelrudern eng", "Seitheben", "Incline Curls", "Trizepsdrücken",
        "Power Cleans", "Medizinball-Würfe", "Romanian Deadlifts", "Ab-Wheel Rollouts", "Pallof Press"
    ]

    if "kraft_history" not in st.session_state:
        st.session_state.kraft_history = {ue: [{"Datum": "15.06.", "Leistung": "Basiswert stabil"}] for ue in alle_uebungen}
        st.session_state.kraft_history["Bankdrücken"] = [{"Datum": "15.06.", "Leistung": "85.0 kg x 6, 6, 5"}]
        st.session_state.kraft_history["Trap-Bar Kreuzheben"] = [{"Datum": "16.06.", "Leistung": "120.0 kg x 6, 6, 6"}]

    if "current_workout_logs" not in st.session_state:
        st.session_state.current_workout_logs = {ue: [] for ue in alle_uebungen}

    # THE CORE ENGINE: TRACKING ENGINE MIT GARMIN INTERACTION
    def render_exercise_engine(ue_name, default_w, default_r):
        st.markdown(f"**Letzter Bestwert:** `{st.session_state.kraft_history[ue_name][-1]['Leistung']}`")
        
        # NEU: Integrierte Garmin-Zeile direkt in der jeweiligen Übung
        g_today = g_data.get("garmin_strength_today", {})
        if ue_name in g_today:
            st.info(f"⌚ Garmin Live-Tracker heute: {', '.join(g_today[ue_name])}")
            
        st.write("---")
        
        if st.session_state.current_workout_logs[ue_name]:
            st.markdown("**Eingetragene Sätze für heute:**")
            for idx, sa in enumerate(st.session_state.current_workout_logs[ue_name]):
                s_col1, s_col2 = st.columns([5, 1])
                s_col1.markdown(f"`Satz {idx+1}:` **{sa}**")
                if s_col2.button("❌", key=f"del_set_{ue_name}_{idx}"):
                    st.session_state.current_workout_logs[ue_name].pop(idx)
                    st.rerun()
            st.write("---")

        se_col1, se_col2 = st.columns(2)
        weight_input = se_col1.number_input("Gewicht (kg):", value=float(default_w), step=2.5, key=f"w_in_{ue_name}")
        reps_input = se_col2.number_input("Wiederholungen:", value=int(default_r), step=1, key=f"r_in_{ue_name}")
        
        b_col1, b_col2 = st.columns(2)
        if b_col1.button("Satz loggen ➕", key=f"btn_add_{ue_name}"):
            st.session_state.current_workout_logs[ue_name].append(f"{weight_input} kg x {reps_input} Wdh.")
            st.toast(f"Satz {len(st.session_state.current_workout_logs[ue_name])} gesichert!", icon="💪")
            st.rerun()

        if st.session_state.current_workout_logs[ue_name]:
            if b_col2.button("Übung beenden & speichern 💾", key=f"btn_save_{ue_name}"):
                saetze_zusammenfassung = ", ".join(st.session_state.current_workout_logs[ue_name])
                heute_datum = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Berlin")).strftime("%d.%m.")
                st.session_state.kraft_history[ue_name].append({"Datum": heute_datum, "Leistung": saetze_zusammenfassung})
                st.session_state.current_workout_logs[ue_name] = [] 
                st.toast("In Verlauf übertragen!", icon="💾")
                st.rerun()

        with st.expander("📈 Ergebnisse / Alle vergangenen Trainings"):
            df_history = pd.DataFrame(st.session_state.kraft_history[ue_name])
            st.dataframe(df_history, hide_index=True, use_container_width=True)

    # APP LAYOUT
    st.title("⚡ PERFORM ALL // ALEC")
    st.write("---")

    col1, col2, col3 = st.columns([1, 1.5, 1.1], gap="large")

    # ==========================================
    # SPALTE 1: ALL GARMIN VITALS & CALORIES
    # ==========================================
    with col1:
        st.header("📊 Garmin Dashboard")
        st.subheader("🔥 Kalorien & Umsatz")
        st.metric("Aktiv-Verbrauch", f"{g_data['active_cal']} kcal")
        st.metric("Gesamt-Umsatz", f"{g_data['total_cal']} kcal")
        st.caption(f"Grundbedarf (BMR): {g_data['bmr_cal']} kcal")
        
        st.write("---")
        st.subheader("🏃 Aktivität")
        st.metric("Schritte heute", f"{g_data['steps']:,}")
        step_perc = min(float(g_data['steps'] / g_data['step_goal']), 1.0) if g_data['step_goal'] > 0 else 0.0
        st.progress(step_perc)
        
        st.write("---")
        st.subheader("💤 Recovery & Herz")
        st.metric("Schlaf-Score", f"{g_data['sleep_score']} / 100", f"{g_data['sleep_duration']} Std Dauer")
        st.metric("Ruhepuls (RHR)", f"{g_data['rhr']} bpm")
        
        st.write("---")
        st.subheader("📝 Letzte Aktivitäten")
        for w in g_data['workout_list']:
            st.write(w)

    # ==========================================
    # SPALTE 2: PERFORM ALL WORKOUT ENGINE (MITTE)
    # ==========================================
    with col2:
        st.header("📅 Trainingsplan & Einheiten")
        
        # NEU: DIE GESAMTÜBERSICHT FÜR HEUTIGE GARMIN-SÄTZE
        if g_data.get("raw_strength_sets"):
            with st.expander("⌚ Live von deiner Garmin-Uhr erfasst (Heute)", expanded=True):
                st.success("Hier siehst du die Live-Werte deiner Uhr. Du kannst sie unten manuell übertragen oder ergänzen.")
                for rs in g_data["raw_strength_sets"]:
                    st.write(rs)
        
        st.caption("Klappe eine Übung auf, um Sätze live zu loggen oder deine Historie einzusehen.")
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["T1: OK Kraft", "T2: HB Beine", "T3: OK Volumen", "T4: Schnellkraft", "T5: Ausdauer"])
        
        with tab1:
            st.subheader("Oberkörper Grundkraft")
            with st.expander("🏋️ Bankdrücken (4 Sätze x 6 Wdh.)"):
                render_exercise_engine("Bankdrücken", 85.0, 6)
            with st.expander("🏋️ Klimmzüge mit Zusatzgewicht (4 Sätze x 6 Wdh.)"):
                render_exercise_engine("Klimmzüge", 10.0, 6)
            with st.expander("🏋️ Dips / Barrenstütz (3 Sätze x 8 Wdh.)"):
                render_exercise_engine("Dips", 0.0, 8)
            with st.expander("🏋️ Langhantelrudern vorgebeugt (3 Sätze x 8 Wdh.)"):
                render_exercise_engine("Langhantelrudern", 70.0, 8)
            with st.expander("🏋️ Face Pulls für Schulterstabilität (3 Sätze x 12 Wdh.)"):
                render_exercise_engine("Face Pulls", 25.0, 12)
            
        with tab2:
            st.subheader("Handball Leg Day (Explosivität & Schutz)")
            with st.expander("🏋️ Bulgarian Split Squats (4 Sätze x 8 Wdh. je Seite)"):
                render_exercise_engine("Bulgarian Split Squats", 20.0, 8)
            with st.expander("🏋️ Trap-Bar Kreuzheben (4 Sätze x 6 Wdh.)"):
                render_exercise_engine("Trap-Bar Kreuzheben", 120.0, 6)
            with st.expander("🏋️ Box Jumps / Rebound-Sprünge (3 Sätze x 5 Wdh.)"):
                render_exercise_engine("Box Jumps", 60, 5)
            with st.expander("🏋️ Lateral Lunges / Seitliche Ausfallschritte (3 Sätze x 8 Wdh.)"):
                render_exercise_engine("Lateral Lunges", 16.0, 8)
            with st.expander("🏋️ Nordic Hamstring Curls (3 Sätze x 6 Wdh.)"):
                render_exercise_engine("Nordic Hamstring Curls", 0.0, 6)
            
        with tab3:
            st.subheader("Oberkörper Volumen (Hypertrophie)")
            with st.expander("🏋️ Schrägbankdrücken mit Kurzhanteln (4x10)"):
                render_exercise_engine("Schrägbankdrücken KH", 30.0, 10)
            with st.expander("🏋️ Kabelrudern eng zum Bauch (4x10)"):
                render_exercise_engine("Kabelrudern eng", 65.0, 10)
            with st.expander("🏋️ Seitheben am Kabelzug (3x12)"):
                render_exercise_engine("Seitheben", 12.5, 12)
            with st.expander("🏋️ Incline Bicep Curls (3x12)"):
                render_exercise_engine("Incline Curls", 15.0, 12)
            with st.expander("🏋️ Tricep Rope Pushdowns (3x12)"):
                render_exercise_engine("Trizepsdrücken", 30.0, 12)
            
        with tab4:
            st.subheader("Schnellkraft & Rumpfstabilität")
            with st.expander("🏋️ Power Cleans / Umsetzen aus dem Hang (4x3 Wdh.)"):
                render_exercise_engine("Power Cleans", 60.0, 3)
            with st.expander("🏋️ Medizinball-Rotationswürfe gegen die Wand (3x8 Wdh.)"):
                render_exercise_engine("Medizinball-Würfe", 6.0, 8)
            with st.expander("🏋️ Romanian Deadlifts (3x10 Wdh.)"):
                render_exercise_engine("Romanian Deadlifts", 90.0, 10)
            with st.expander("🏋️ Ab-Wheel Rollouts (3x max.)"):
                render_exercise_engine("Ab-Wheel Rollouts", 0.0, 10)
            with st.expander("🏋️ Pallof Press am Kabelzug (3x12 Wdh.)"):
                render_exercise_engine("Pallof Press", 20.0, 12)
            
        with tab5:
            st.subheader("Handball Intervall- & Grundlagenausdauer")
            ausdauer_wahl = st.radio("Wähle deine heutige Cardio-Session:", ["Zone 2 Lauf (45-60 Min.)", "Handball Shuttle Runs (15x 20m Sprints)"])
            st.checkbox(f"Session erfolgreich beendet: {ausdauer_wahl}")

    # ==========================================
    # SPALTE 3: NUTRITION & DROPDOWN & FINANZEN
    # ==========================================
    with col3:
        st.header("🍽️ Ernährung & Orga")
        
        rem_kcal = max(tagesbedarf["kcal"] - verzehrt_kcal, 0)
        rem_p = max(tagesbedarf["protein"] - verzehrt_protein, 0)
        rem_c = max(tagesbedarf["carbs"] - verzehrt_carbs, 0)
        rem_f = max(tagesbedarf["fat"] - verzehrt_fat, 0)
        
        st.metric("Kcal Restbudget", f"{rem_kcal:,} kcal", f"Ziel: {tagesbedarf['kcal']}")
        st.metric("Protein Rest", f"{rem_p}g", f"Ziel: {tagesbedarf['protein']}g", delta_color="inverse")
        
        nu_col1, nu_col2 = st.columns(2)
        nu_col1.metric("Carbs Rest", f"{rem_c}g")
        nu_col2.metric("Fat Rest", f"{rem_f}g")
        
        with st.expander("📊 Wochenübersicht (Makros)"):
            overview_data = [
                {"Tag": "Montag", "Kcal": 2550, "Protein": "201g", "Carbs": "250g", "Fat": "78g"},
                {"Tag": "Dienstag", "Kcal": 2620, "Protein": "208g", "Carbs": "265g", "Fat": "81g"},
                {"Tag": "Mittwoch", "Kcal": 2480, "Protein": "195g", "Carbs": "240g", "Fat": "75g"},
                {"Tag": "Heute (Live)", "Kcal": verzehrt_kcal, "Protein": f"{verzehrt_protein}g", "Carbs": f"{verzehrt_carbs}g", "Fat": f"{verzehrt_fat}g"}
            ]
            st.dataframe(pd.DataFrame(overview_data), hide_index=True, use_container_width=True)
        
        st.write("---")
        st.subheader("⭐ Wiederkehrende Mahlzeiten")
        fav_choice = st.selectbox("Schnellauswahl Lieblingsgerichte:", list(st.session_state.favorites.keys()))
        
        if fav_choice != "--- Bitte wählen ---":
            meal_data = st.session_state.favorites[fav_choice]
            st.caption(f"📊 {meal_data['kcal']} kcal | {meal_data['protein']}g P")
            if st.button(f"'{fav_choice}' loggen ✅"):
                st.session_state.meals_log.append({
                    "name": fav_choice, "kcal": meal_data["kcal"], "protein": meal_data["protein"], 
                    "carbs": meal_data["carbs"], "fat": meal_data["fat"]
                })
                st.toast(f"Favorit hinzugefügt!", icon="🍽️")
                st.rerun()
        
        st.write("---")
        st.subheader("📸 Neuen Mahlzeit-Scanner")
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
                
                add_to_favs = st.checkbox("Zu 'Wiederkehrende Mahlzeiten' hinzufügen? ⭐")
                
                if st.button("In Log eintragen ✅", key="add_scanned_meal"):
                    st.session_state.meals_log.append({
                        "name": edit_name, "kcal": edit_kcal, "protein": edit_p, "carbs": edit_c, "fat": edit_f
                    })
                    if add_to_favs:
                        st.session_state.favorites[edit_name] = {"kcal": edit_kcal, "protein": edit_p, "carbs": edit_c, "fat": edit_f}
                    st.toast("Mahlzeit erfolgreich eingetragen!", icon="✅")
                    del st.session_state.temp_meal
                    st.rerun()

        if st.session_state.meals_log:
            st.write("---")
            st.markdown("**Heutige Mahlzeiten:**")
            for idx, meal in enumerate(st.session_state.meals_log):
                m_col1, m_col2 = st.columns([5, 1])
                m_col1.caption(f"✔️ {meal['name']} ({meal['kcal']} kcal | {meal['protein']}g P)")
                if m_col2.button("❌", key=f"del_meal_{idx}"):
                    st.session_state.meals_log.pop(idx)
                    st.rerun()

        st.write("---")
        st.subheader("💼 Finanzen & Daily Routine")
        st.metric(label="Verfügbares Netto (Monat)", value="1.850,00 €")
        st.checkbox("Handball-Dehnprogramm absolviert (15 Min)")

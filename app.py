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

    # STABILES & ERWEITERTES GARMIN DATA-FETCHING
    @st.cache_data(ttl=300)
    def fetch_garmin_data():
        try:
            client = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
            client.login()
            
            berlin_time = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Berlin"))
            today = berlin_time.date().isoformat()
            
            # Die stabilsten Haupt-Endpunkte abrufen
            stats = client.get_stats(today)
            heart_rates = client.get_heart_rates(today)
            sleep_data = client.get_sleep_data(today)
            activities = client.get_activities(0, 5)
            
            # --- ERWEITERTE PERFORMANCE- & GESUNDHEITSDATEN ---
            vo2_max = "--"
            recovery_time = "--"
            race_5k = "--"
            training_status = "--"
            try:
                t_status = client.get_training_status(today)
                if t_status:
                    vo2_max_raw = t_status.get("mostRecentRunVo2Max", {}).get("genericValue") or t_status.get("vo2Max")
                    vo2_max = f"{round(vo2_max_raw, 1)}" if vo2_max_raw else "--"
                    
                    rec_hours = t_status.get("recoveryTimeInHours") or t_status.get("recoveryTime")
                    recovery_time = f"{rec_hours} Std" if rec_hours else "--"
                    
                    training_status = t_status.get("trainingStatusDTO", {}).get("trainingStatus") or t_status.get("trainingStatus", "--")
                    
                    preds = t_status.get("racePredictions", {}) or t_status.get("racePredictionDTO", {})
                    if preds:
                        race_5k = preds.get("fiveK", {}).get("displayTime") or preds.get("fiveKTime", "--")
            except:
                pass

            workout_list = []
            garmin_strength_today = {}
            raw_strength_sets = []
            
            if activities:
                for act in activities:
                    w_type = act.get('activityType', {}).get('typeKey', 'Workout')
                    w_dur = round(act.get('duration', 0) / 60)
                    w_cal = round(act.get('calories', 0))
                    workout_list.append(f"💪 {w_type}: {w_dur} Min ({w_cal} kcal)")
                    
                    act_date = act.get('startTimeLocal', '')[:10]
                    if w_type == 'strength_training' and act_date == today:
                        act_id = act.get('activityId')
                        try:
                            details = client.get_activity_details(act_id)
                            sets = details.get('sets', []) or details.get('summaryDTO', {}).get('sets', [])
                            
                            for idx, s in enumerate(sets):
                                reps = s.get('reps', 0)
                                weight = s.get('weight', 0)
                                if weight > 1000: weight = round(weight / 1000, 1)
                                else: weight = round(weight, 1)
                                    
                                if reps > 0:
                                    ex_name = s.get('exerciseName', 'Unbekannte Übung').lower()
                                    set_str = f"{weight} kg x {reps} Wdh."
                                    raw_strength_sets.append(f"Satz {idx+1}: {s.get('exerciseName', 'Set')} -> {set_str}")
                                    
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
                                        if matched_key not in garmin_strength_today: garmin_strength_today[matched_key] = []
                                        garmin_strength_today[matched_key].append(set_str)
                        except: pass
            
            sleep_dto = sleep_data.get("dailySleepDTO", {}) if sleep_data else {}
            sleep_hours = round(sleep_dto.get("sleepTimeSeconds", 0) / 3600, 1) if sleep_dto else 0
            sleep_score = sleep_dto.get("sleepScore", "--") if sleep_dto else "--"
            
            steps = stats.get("steps") or stats.get("totalSteps") or 0
            step_goal = stats.get("stepsGoal") or 10000
            active_cal = round(stats.get("activeCalories", 0))
            bmr_cal = round(stats.get("bmrCalories", 1900))
            total_cal = round(stats.get("totalCalories", active_cal + bmr_cal))
            distance_km = round(stats.get("distanceInMeters", 0) / 1000, 2)
            floors = stats.get("floorsClimbed", 0)
            
            stress_avg = stats.get("averageStressLevel", "--")
            if stress_avg == -1 or stress_avg == 0: stress_avg = "--"

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
                "stress_avg": stress_avg,
                "vo2_max": vo2_max,
                "recovery_time": recovery_time,
                "race_5k": race_5k,
                "training_status": training_status
            }
            return garmin_pack, True
        except:
            fallback = {
                "rhr": "--", "max_hr": "--", "workout_list": ["Synchronisiere..."],
                "garmin_strength_today": {}, "raw_strength_sets": [],
                "steps": 0, "step_goal": 10000, "active_cal": 0, "bmr_cal": 1900, "total_cal": 1900,
                "distance_km": 0.0, "floors": 0, "sleep_duration": 0, "sleep_score": "--", "stress_avg": "--",
                "vo2_max": "--", "recovery_time": "--", "race_5k": "--", "training_status": "--"
            }
            return fallback, False

    g_data, garmin_success = fetch_garmin_data()

    # KORREKTUR: Berechnung für den Schrittbalken direkt nach dem Laden sichern
    step_perc = min(float(g_data['steps'] / g_data['step_goal']), 1.0) if g_data['step_goal'] > 0 else 0.0

    # ==========================================
    # INITIALISIERUNGEN (SESSION STATE)
    # ==========================================
    if "meals_log" not in st.session_state:
        st.session_state.meals_log = []
    else:
        st.session_state.meals_log = [m for m in st.session_state.meals_log if isinstance(m, dict)]

    if "favorites" not in st.session_state:
        st.session_state.favorites = {"--- Bitte wählen ---": None}

    if "ki_wochenplan" not in st.session_state:
        st.session_state.ki_wochenplan = {
            "Montag": [], "Dienstag": [], "Mittwoch": [], "Donnerstag": [], 
            "Freitag": [], "Samstag": [], "Sonntag": []
        }
        
    if "miles_collected" not in st.session_state: st.session_state.miles_collected = 14200
    if "payback_points" not in st.session_state: st.session_state.payback_points = 8450

    tagesbedarf = {"kcal": 2600, "protein": 204, "carbs": 260, "fat": 80}

    berlin_time = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Berlin"))
    tage_de = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    heute_wochentag = tage_de[berlin_time.weekday()]

    # Live-Verrechnung der heutigen Makros
    verzehrt_kcal = sum(m.get("kcal", 0) for m in st.session_state.meals_log)
    verzehrt_protein = sum(m.get("protein", 0) for m in st.session_state.meals_log)
    verzehrt_carbs = sum(m.get("carbs", 0) for m in st.session_state.meals_log)
    verzehrt_fat = sum(m.get("fat", 0) for m in st.session_state.meals_log)

    for wp_meal in st.session_state.ki_wochenplan.get(heute_wochentag, []):
        if wp_meal.get("done"):
            verzehrt_kcal += wp_meal.get("kcal", 0)
            verzehrt_protein += wp_meal.get("protein", 0)
            verzehrt_carbs += wp_meal.get("carbs", 0)
            verzehrt_fat += wp_meal.get("fat", 0)

    rem_kcal = max(tagesbedarf["kcal"] - verzehrt_kcal, 0)
    rem_p = max(tagesbedarf["protein"] - verzehrt_protein, 0)
    rem_c = max(tagesbedarf["carbs"] - verzehrt_carbs, 0)
    rem_f = max(tagesbedarf["fat"] - verzehrt_fat, 0)

    # REZEPTKATALOG (CHEFKOCH SELECTION)
    recipe_book = {
        "Frühstück 🥞": {
            "Power-Oatmeal (High-Protein)": {
                "kcal": 680, "protein": 52, "carbs": 85, "fat": 13,
                "zutaten": ["100g Haferflocken", "40g Whey-Proteinpulver", "150g Magerquark", "100g TK-Heidelbeeren"],
                "anleitung": "Haferflocken quellen lassen. Quark und Whey unterrühren, Beeren drüber."
            },
            "Herzhaftes Rührei-Strammer-Max": {
                "kcal": 600, "protein": 55, "carbs": 40, "fat": 22,
                "zutaten": ["3 ganze Eier", "100g flüssiges Eiklar", "2 Scheiben Roggenbrot", "50g Hähnchenbrust"],
                "anleitung": "Eiklar und Eier verquirlen, braten. Auf Brot mit Hähnchenbrust servieren."
            }
        },
        "Fleischgerichte 🍗": {
            "Crispy Airfryer Chicken": {
                "kcal": 650, "protein": 62, "carbs": 65, "fat": 12,
                "zutaten": ["250g Hähnchenbrust", "300g Süßkartoffel", "150g Brokkoli", "10ml Olivenöl"],
                "anleitung": "Hähnchen und Kartoffeln würfeln, ölen, würzen. 18 Min bei 180°C in den Airfryer."
            },
            "Puten-Brokkoli-Pfanne (Asia)": {
                "kcal": 620, "protein": 65, "carbs": 60, "fat": 10,
                "zutaten": ["250g Putenbrust", "200g Brokkoli", "80g Basmatireis", "Sojasauce"],
                "anleitung": "Reis kochen. Pute scharf anbraten, Brokkoli und Sojasauce mitdünsten."
            }
        },
        "Fischgerichte 🐟": {
            "Gebackenes Lachsfilet": {
                "kcal": 640, "protein": 48, "carbs": 55, "fat": 22,
                "zutaten": ["200g Lachsfilet", "70g Quinoa", "150g grüner Spargel", "Zitrone"],
                "anleitung": "Quinoa kochen. Lachs mit Zitrone würzen und 15 Min bei 180°C backen."
            },
            "Knoblauch-Chili-Garnelen": {
                "kcal": 580, "protein": 50, "carbs": 75, "fat": 8,
                "zutaten": ["250g Riesengarnelen", "80g Jasminreis", "Paprika", "Sesamöl"],
                "anleitung": "Garnelen mit Knoblauch, Chili und Gemüse im Sesamöl scharf pfannenrühren."
            }
        },
        "Vegetarisch 🌱": {
            "Sojageschnetzeltes in Pilzrahm": {
                "kcal": 590, "protein": 53, "carbs": 58, "fat": 11,
                "zutaten": ["60g Sojaschnetzel", "70g Vollkornnudeln", "200g Champignons", "Leicht-Kochcreme"],
                "anleitung": "Schnetzel einweichen, ausdrücken, kross braten. Pilze und Creme dazu."
            },
            "Protein-Bowl mit Falafel": {
                "kcal": 580, "protein": 44, "carbs": 65, "fat": 14,
                "zutaten": ["200g Hüttenkäse light", "100g Falafel", "60g Couscous", "Gemüse"],
                "anleitung": "Couscous quellen lassen. Mit Hüttenkäse, Gemüse und Falafel anrichten."
            }
        },
        "Snacks 🍫": {
            "Magerquark-Flavour-Bowl": {
                "kcal": 290, "protein": 42, "carbs": 16, "fat": 1,
                "zutaten": ["300g Magerquark", "50ml Wasser", "Flavour Drops", "50g Himbeeren"],
                "anleitung": "Quark mit Wasser und Drops cremig schlagen. Himbeeren unterheben."
            },
            "Beef Jerky Handvoll": {
                "kcal": 150, "protein": 28, "carbs": 3, "fat": 2,
                "zutaten": ["50g Beef Jerky"],
                "anleitung": "Snackfertig aus der Packung für maximalen Muskelschutz nach dem Training."
            }
        }
    }

    alle_uebungen = [
        "Bankdrücken", "Klimmzüge", "Dips", "Langhantelrudern", "Face Pulls", "Bulgarian Split Squats", "Trap-Bar Kreuzheben", 
        "Box Jumps", "Lateral Lunges", "Nordic Hamstring Curls", "Schrägbankdrücken KH", "Kabelrudern eng", "Seitheben", 
        "Incline Curls", "Trizepsdrücken", "Power Cleans", "Medizinball-Würfe", "Romanian Deadlifts", "Ab-Wheel Rollouts", "Pallof Press"
    ]
    if "kraft_history" not in st.session_state: st.session_state.kraft_history = {ue: [{"Datum": "15.06.", "Leistung": "Basiswert stabil"}] for ue in alle_uebungen}
    if "current_workout_logs" not in st.session_state: st.session_state.current_workout_logs = {ue: [] for ue in alle_uebungen}

    # WORKOUT ENGINE MECHANIK
    def render_exercise_engine(ue_name, default_w, default_r):
        st.markdown(f"**Letzter Bestwert:** `{st.session_state.kraft_history[ue_name][-1]['Leistung']}`")
        g_today = g_data.get("garmin_strength_today", {})
        if ue_name in g_today: st.info(f"⌚ Garmin Live: {', '.join(g_today[ue_name])}")
        
        if st.session_state.current_workout_logs[ue_name]:
            for idx, sa in enumerate(st.session_state.current_workout_logs[ue_name]):
                s_col1, s_col2 = st.columns([5, 1])
                s_col1.markdown(f"`Satz {idx+1}:` **{sa}**")
                if s_col2.button("❌", key=f"del_set_{ue_name}_{idx}"):
                    st.session_state.current_workout_logs[ue_name].pop(idx)
                    st.rerun()

        se_col1, se_col2 = st.columns(2)
        weight_input = se_col1.number_input("Gewicht (kg):", value=float(default_w), step=2.5, key=f"w_in_{ue_name}")
        reps_input = se_col2.number_input("Wiederholungen:", value=int(default_r), step=1, key=f"r_in_{ue_name}")
        
        b_col1, b_col2 = st.columns(2)
        if b_col1.button("Satz loggen ➕", key=f"btn_add_{ue_name}"):
            st.session_state.current_workout_logs[ue_name].append(f"{weight_input} kg x {reps_input} Wdh.")
            st.rerun()
        if st.session_state.current_workout_logs[ue_name] and b_col2.button("Sichern 💾", key=f"btn_save_{ue_name}"):
            zusammenfassung = ", ".join(st.session_state.current_workout_logs[ue_name])
            heute_datum = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Berlin")).strftime("%d.%m.")
            st.session_state.kraft_history[ue_name].append({"Datum": heute_datum, "Leistung": zusammenfassung})
            st.session_state.current_workout_logs[ue_name] = [] 
            st.rerun()

        with st.expander("📈 Ergebnisse / Historie"):
            st.dataframe(pd.DataFrame(st.session_state.kraft_history[ue_name]), hide_index=True, use_container_width=True)

    # LAYOUT OVERVIEW (3 Spalten)
    col1, col2, col3 = st.columns([1, 1.5, 1.1], gap="large")

    # ==========================================
    # SPALTE 1: GARMIN DASHBOARD
    # ==========================================
    with col1:
        st.header("📊 Garmin Dashboard")
        
        st.subheader("🔥 Kalorien & Umsatz")
        st.metric("Aktiv-Verbrauch", f"{g_data['active_cal']} kcal")
        st.metric("Gesamt-Umsatz", f"{g_data['total_cal']} kcal")
        st.caption(f"Grundbedarf (BMR): {g_data['bmr_cal']} kcal")
        st.write("---")
        
        with st.expander("🏃 Aktivität & Schritte"):
            st.metric("Schritte heute", f"{g_data['steps']:,}")
            st.progress(step_perc)
            st.write(f"Distanz: **{g_data['distance_km']} km** | Etagen: **{g_data['floors']}**")
            
        with st.expander("💤 Recovery & Herzfrequenz"):
            st.metric("Schlaf-Score", f"{g_data['sleep_score']} / 100", f"{g_data['sleep_duration']} Std Dauer")
            st.metric("Ruhepuls (RHR)", f"{g_data['rhr']} bpm")
            
        with st.expander("📈 Erweiterte Leistungsdaten"):
            st.metric("Ausdauerwert (VO2 Max)", f"{g_data['vo2_max']} ml/min/kg")
            st.metric("Erholungszeit", f"{g_data['recovery_time']}")
            st.metric("Status / Bereitschaft", f"{g_data['training_status']}")
            st.metric("Geschätzte 5 km Zeit", f"{g_data['race_5k']} Min")

        with st.expander("📝 Letzte getrackte Aktivitäten"):
            for w in g_data['workout_list']: st.write(w)

    # ==========================================
    # SPALTE 2: TRAININGSPLAN (BLEIBT OFFEN)
    # ==========================================
    with col2:
        st.header("📅 Trainingsplan & Einheiten")
        if g_data.get("raw_strength_sets"):
            with st.expander("⌚ Live von deiner Garmin-Uhr erfasst (Heute)", expanded=True):
                for rs in g_data["raw_strength_sets"]: st.write(rs)
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["T1: OK Kraft", "T2: HB Beine", "T3: OK Volumen", "T4: Schnellkraft", "T5: Ausdauer"])
        with tab1:
            st.subheader("Oberkörper Grundkraft")
            with st.expander("🏋️ Bankdrücken (4 Sätze x 6 Wdh.)"): render_exercise_engine("Bankdrücken", 85.0, 6)
            with st.expander("🏋️ Klimmzüge mit Zusatzgewicht"): render_exercise_engine("Klimmzüge", 10.0, 6)
            with st.expander("🏋️ Dips / Barrenstütz"): render_exercise_engine("Dips", 0.0, 8)
            with st.expander("🏋️ Langhantelrudern vorgebeugt"): render_exercise_engine("Langhantelrudern", 70.0, 8)
            with st.expander("🏋️ Face Pulls für Schulterstabilität"): render_exercise_engine("Face Pulls", 25.0, 12)
        with tab2:
            st.subheader("Handball Leg Day (Explosivität & Gelenkschutz)")
            with st.expander("🏋️ Bulgarian Split Squats"): render_exercise_engine("Bulgarian Split Squats", 20.0, 8)
            with st.expander("🏋️ Trap-Bar Kreuzheben"): render_exercise_engine("Trap-Bar Kreuzheben", 120.0, 6)
            with st.expander("🏋️ Box Jumps / Rebound-Sprünge"): render_exercise_engine("Box Jumps", 60, 5)
            with st.expander("🏋️ Lateral Lunges"): render_exercise_engine("Lateral Lunges", 16.0, 8)
            with st.expander("🏋️ Nordic Hamstring Curls"): render_exercise_engine("Nordic Hamstring Curls", 0.0, 6)
        with tab3:
            st.subheader("Oberkörper Volumen (Hypertrophie)")
            with st.expander("🏋️ Schrägbankdrücken mit Kurzhanteln"): render_exercise_engine("Schrägbankdrücken KH", 30.0, 10)
            with st.expander("🏋️ Kabelrudern eng zum Bauch"): render_exercise_engine("Kabelrudern eng", 65.0, 10)
            with st.expander("🏋️ Seitheben am Kabelzug"): render_exercise_engine("Seitheben", 12.5, 12)
            with st.expander("🏋️ Incline Bicep Curls"): render_exercise_engine("Incline Curls", 15.0, 12)
            with st.expander("🏋️ Tricep Rope Pushdowns"): render_exercise_engine("Trizepsdrücken", 30.0, 12)
        with tab4:
            st.subheader("Schnellkraft & Rumpfstabilität")
            with st.expander("🏋️ Power Cleans / Umsetzen"): render_exercise_engine("Power Cleans", 60.0, 3)
            with st.expander("🏋️ Medizinball-Rotationswürfe"): render_exercise_engine("Medizinball-Würfe", 6.0, 8)
            with st.expander("🏋️ Romanian Deadlifts"): render_exercise_engine("Romanian Deadlifts", 90.0, 10)
            with st.expander("🏋️ Ab-Wheel Rollouts"): render_exercise_engine("Ab-Wheel Rollouts", 0.0, 10)
            with st.expander("🏋️ Pallof Press am Kabelzug"): render_exercise_engine("Pallof Press", 20.0, 12)
        with tab5:
            st.subheader("Handball Ausdauer")
            ausdauer_wahl = st.radio("Cardio-Session:", ["Zone 2 Lauf (45-60 Min.)", "Handball Shuttle Runs (15x 20m)"])
            st.checkbox(f"Session erledigt: {ausdauer_wahl}")

    # ==========================================
    # SPALTE 3: NUTRITION & DATA AUTOMATION
    # ==========================================
    with col3:
        st.header("🍽️ Ernährung & Orga")
        
        st.metric("Kcal Restbudget", f"{rem_kcal} kcal", f"Ziel: {tagesbedarf['kcal']}")
        st.metric("Protein Rest", f"{rem_p}g", f"Ziel: {tagesbedarf['protein']}g", delta_color="inverse")
        
        nu_col1, nu_col2 = st.columns(2)
        nu_col1.metric("Carbs Rest", f"{rem_c}g")
        nu_col2.metric("Fat Rest", f"{rem_f}g")
        st.write("---")

        with st.expander("👨‍🍳 Perform-All Chefkoch: Rezeptkatalog"):
            cat_choice = st.selectbox("Kategorie wählen:", list(recipe_book.keys()))
            recipe_choice = st.selectbox("Rezept auswählen:", list(recipe_book[cat_choice].keys()))
            selected_rec = recipe_book[cat_choice][recipe_choice]
            st.markdown(f"#### {recipe_choice} ({selected_rec['kcal']} kcal)")
            for zutat in selected_rec["zutaten"]: st.markdown(f"- {zutat}")
            st.caption(selected_rec["anleitung"])
            
            if st.button("Heute essen (Loggen) ✅", key=f"log_chef_{recipe_choice}"):
                st.session_state.meals_log.append({"name": recipe_choice, "kcal": selected_rec["kcal"], "protein": selected_rec["protein"], "carbs": selected_rec["carbs"], "fat": selected_rec["fat"]})
                st.rerun()
            w_tag = st.selectbox("In Wochenplan schieben:", list(st.session_state.ki_wochenplan.keys()), key=f"day_chef_{recipe_choice}")
            if st.button("Für diesen Tag einplanen 📅", key=f"plan_chef_{recipe_choice}"):
                st.session_state.ki_wochenplan[w_tag].append({"label": f"{recipe_choice} [{selected_rec['kcal']} kcal]", "instruction": selected_rec["anleitung"], "done": False, "kcal": selected_rec["kcal"], "protein": selected_rec["protein"], "carbs": selected_rec["carbs"], "fat": selected_rec["fat"]})
                st.rerun()

        with st.expander("📅 Dein Wochenplan (Zum Abhaken)"):
            for tag, m_liste in st.session_state.ki_wochenplan.items():
                if m_liste:
                    st.markdown(f"**{tag}**")
                    for m_idx, meal in enumerate(m_liste):
                        w_col1, w_col2 = st.columns([5, 1])
                        checked = w_col1.checkbox(meal["label"], value=meal["done"], key=f"chk_{tag}_{m_idx}")
                        if checked != meal["done"]:
                            st.session_state.ki_wochenplan[tag][m_idx]["done"] = checked
                            st.rerun()
                        if w_col2.button("🗑️", key=f"del_wp_{tag}_{m_idx}"):
                            st.session_state.ki_wochenplan[tag].pop(m_idx)
                            st.rerun()

        with st.expander("🤖 Freier KI-Assistent & Sprachbefehl"):
            prompt_input = st.text_input("Extrawunsch einplanen (Mikrofon-Taste nutzen):", key="ki_prompt_box")
            tag_auswahl = st.selectbox("Tag:", list(st.session_state.ki_wochenplan.keys()))
            if st.button("KI-Rezept generieren 🪄") and prompt_input:
                pass

        with st.expander("📸 Neuen Mahlzeit-Scanner"):
            uploaded_file = st.file_uploader("Foto hochladen...", type=["jpg", "png", "jpeg"])

        with st.expander("📋 Heutiges Ernährungsprotokoll"):
            if st.session_state.meals_log:
                for idx, meal in enumerate(st.session_state.meals_log):
                    m_col1, m_col2 = st.columns([5, 1])
                    m_col1.caption(f"✔️ {meal['name']} ({meal['kcal']} kcal)")
                    if m_col2.button("❌", key=f"del_meal_{idx}"):
                        st.session_state.meals_log.pop(idx)
                        st.rerun()
            else: st.caption("Noch keine Mahlzeiten direkt geloggt.")

        with st.expander("💼 Finanzen & Points Engine (C24 / Amex / Revolut)", expanded=True):
            st.metric(label="Verfügbares Netto (Monat)", value="1.850,00 €")
            st.caption("Gehaltskonto: **C24 Smart**")
            st.write("---")
            st.markdown("**💳 Travel-Reward & Meilen-Optimierer:**")
            
            f_col1, f_col2 = st.columns(2)
            f_col1.metric("Miles & More", f"{st.session_state.miles_collected:,} M")
            f_col2.metric("Payback Punkte", f"{st.session_state.payback_points:,} P")
            
            st.write("---")
            spending = st.number_input("Umsatzbetrag (€):", value=50.0, step=10.0)
            method = st.selectbox("Zahlart:", ["American Express (Daily Spending)", "Revolut (Miete/Dauerauftrag)"])
            
            if st.button("Punkte gutschreiben 💳"):
                if "American" in method:
                    st.session_state.payback_points += int(spending / 2)
                    st.toast(f"+{int(spending/2)} Payback Punkte!", icon="💳")
                else:
                    st.session_state.miles_collected += int(spending)
                    st.toast(f"+{int(spending)} Meilen generiert!", icon="✈️")
                st.rerun()

            st.checkbox("Handball-Dehnprogramm absolviert (15 Min)")

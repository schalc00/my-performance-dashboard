import streamlit as st
import pandas as pd
import datetime
import zoneinfo
from garminconnect import Garmin
from PIL import Image
from google import genai

# 1. Page Configuration (3 Spalten mit Fokus auf die Mitte)
st.set_page_config(page_title="Perform All // Alec", page_icon="⚡", layout="wide")

# Exklusives CSS für das "OLED Carbon & Cyber Punk" Dashboard Design
st.markdown("""
    <style>
    /* Hintergrund auf sattes OLED-Schwarz setzen */
    .main { background-color: #020408; color: #e2e8f0; }
    
    /* Premium Tuning für die Metriken (Fett, Neon-Cyan & Tech-Vibe) */
    div[data-testid="stMetricValue"] { font-size: 30px; font-weight: 900; color: #00f0ff; letter-spacing: -0.5px; }
    div[data-testid="stMetricLabel"] { font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #94a3b8; }
    
    /* Veredelte Kacheln mit leuchtender Neon-Carbon-Kante links */
    .stExpander { background-color: #0b111e; border-radius: 8px; margin-bottom: 10px; border: 1px solid #1e293b; border-left: 4px solid #00f0ff; }
    
    /* Styling für Buttons und Registerkarten */
    .stTabs [data-baseweb="tab"] { color: #94a3b8; font-weight: bold; }
    .stTabs [aria-selected="true"] { color: #00f0ff !important; border-bottom-color: #00f0ff !important; }
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
    # API INITIALISIERUNG & BASIS-DATEN
    # ==========================================
    GARMIN_EMAIL = st.secrets["GARMIN_EMAIL"]
    GARMIN_PASSWORD = st.secrets["GARMIN_PASSWORD"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

    berlin_tz = zoneinfo.ZoneInfo("Europe/Berlin")
    heute_datum = datetime.datetime.now(berlin_tz).date()
    tage_de = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

    if "selected_date" not in st.session_state:
        st.session_state.selected_date = heute_datum

    selected_date_str = st.session_state.selected_date.isoformat()
    selected_weekday = tage_de[st.session_state.selected_date.weekday()]

    # STABILES & ADVANCED GARMIN DATA-FETCHING
    @st.cache_data(ttl=300)
    def fetch_garmin_data(date_str):
        try:
            client = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
            client.login()
            
            stats = client.get_stats(date_str)
            heart_rates = client.get_heart_rates(date_str)
            sleep_data = client.get_sleep_data(date_str)
            activities = client.get_activities(0, 8)
            
            vo2_max, recovery_time, race_5k, training_status = "--", "--", "--", "--"
            try:
                t_status = client.get_training_status(date_str)
                if t_status:
                    vo2_max_raw = t_status.get("mostRecentRunVo2Max", {}).get("genericValue") or t_status.get("vo2Max")
                    vo2_max = f"{round(vo2_max_raw, 1)}" if vo2_max_raw else "--"
                    rec_hours = t_status.get("recoveryTimeInHours") or t_status.get("recoveryTime")
                    recovery_time = f"{rec_hours} Std" if rec_hours else "--"
                    training_status = t_status.get("trainingStatusDTO", {}).get("trainingStatus") or t_status.get("trainingStatus", "--")
                    preds = t_status.get("racePredictions", {}) or t_status.get("racePredictionDTO", {})
                    if preds: race_5k = preds.get("fiveK", {}).get("displayTime") or preds.get("fiveKTime", "--")
            except: pass

            workout_list = []
            garmin_strength_today = {}
            raw_strength_sets = []
            garmin_cardio_history = []
            garmin_swim_history = []
            
            if activities:
                for act in activities:
                    w_type = act.get('activityType', {}).get('typeKey', 'Workout').lower()
                    w_dur = round(act.get('duration', 0) / 60)
                    w_cal = round(act.get('calories', 0))
                    workout_list.append(f"💪 {w_type.upper()}: {w_dur} Min ({w_cal} kcal)")
                    
                    act_date = act.get('startTimeLocal', '')[:10]
                    formatted_date = act_date[8:10] + "." + act_date[5:7] + "."
                    
                    if w_type in ['running', 'run', 'trail_running', 'cycling', 'biking']:
                        r_dist = round(act.get('distance', 0) / 1000, 2)
                        r_dur_sec = act.get('duration', 0)
                        r_dur_min = round(r_dur_sec / 60, 1)
                        if r_dist > 0:
                            total_min = r_dur_sec / 60
                            pace_dec = total_min / r_dist
                            p_m = int(pace_dec)
                            p_s = int((pace_dec - p_m) * 60)
                            pace_str = f"{p_m}:{p_s:02d} min/km"
                            speed_kmh = round(r_dist / (total_min / 60), 1)
                        else: pace_str, speed_kmh = "--", 0
                            
                        garmin_cardio_history.append({
                            "Datum": formatted_date, "Typ": "Fahrrad" if "cycl" in w_type or "bik" in w_type else "Lauf",
                            "Distanz": f"{r_dist} km", "Dauer": f"{r_dur_min} Min", "Pace": pace_str, "Speed": f"{speed_kmh} km/h"
                        })
                    
                    if w_type in ['swimming', 'lap_swimming']:
                        s_dist = round(act.get('distance', 0))
                        if s_dist > 10000: s_dist = round(s_dist / 100)
                        s_dur_sec = act.get('duration', 0)
                        s_dur_min = round(s_dur_sec / 60, 1)
                        if s_dist > 0:
                            pace_100m_dec = (s_dur_sec / 60) / (s_dist / 100)
                            sm = int(pace_100m_dec)
                            ss = int((pace_100m_dec - sm) * 60)
                            swim_pace_str = f"{sm}:{ss:02d} min/100m"
                        else: swim_pace_str = "--"
                            
                        garmin_swim_history.append({
                            "Datum": formatted_date, "Distanz": f"{s_dist} m", "Dauer": f"{s_dur_min} Min", "Pace": swim_pace_str
                        })

                    if w_type == 'strength_training' and act_date == date_str:
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
                "garmin_cardio_history": garmin_cardio_history,
                "garmin_swim_history": garmin_swim_history,
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
                "garmin_strength_today": {}, "raw_strength_sets": [], "garmin_cardio_history": [], "garmin_swim_history": [],
                "steps": 0, "step_goal": 10000, "active_cal": 0, "bmr_cal": 1900, "total_cal": 1900,
                "distance_km": 0.0, "floors": 0, "sleep_duration": 0, "sleep_score": "--", "stress_avg": "--",
                "vo2_max": "--", "recovery_time": "--", "race_5k": "--", "training_status": "--"
            }
            return fallback, False

    g_data, garmin_success = fetch_garmin_data(selected_date_str)
    step_perc = min(float(g_data['steps'] / g_data['step_goal']), 1.0) if g_data['step_goal'] > 0 else 0.0

    # ==========================================
    # INITIALISIERUNGEN (SESSION STATE)
    # ==========================================
    if "meals_log" not in st.session_state or isinstance(st.session_state.meals_log, list):
        st.session_state.meals_log = {}

    if "favorites" not in st.session_state: st.session_state.favorites = {"--- Bitte wählen ---": None}
    if "ki_wochenplan" not in st.session_state:
        st.session_state.ki_wochenplan = {"Montag": [], "Dienstag": [], "Mittwoch": [], "Donnerstag": [], "Freitag": [], "Samstag": [], "Sonntag": []}
        
    if "prozis_weight" not in st.session_state: st.session_state.prozis_weight = 102.0
    if "cardio_history" not in st.session_state: st.session_state.cardio_history = []
    if "swim_history" not in st.session_state: st.session_state.swim_history = []

    # DYNAMISCHE MAKROBERECHNUNG
    w_aktuell = st.session_state.prozis_weight
    tagesbedarf = {
        "kcal": int(w_aktuell * 25.5),      
        "protein": int(w_aktuell * 2.0),    
        "carbs": int(w_aktuell * 2.55),
        "fat": int(w_aktuell * 0.78)
    }

    heutige_mahlzeiten_liste = st.session_state.meals_log.get(selected_date_str, [])

    verzehrt_kcal = sum(m.get("kcal", 0) for m in heutige_mahlzeiten_liste)
    verzehrt_protein = sum(m.get("protein", 0) for m in heutige_mahlzeiten_liste)
    verzehrt_carbs = sum(m.get("carbs", 0) for m in heutige_mahlzeiten_liste)
    verzehrt_fat = sum(m.get("fat", 0) for m in heutige_mahlzeiten_liste)

    for wp_meal in st.session_state.ki_wochenplan.get(selected_weekday, []):
        if wp_meal.get("done"):
            verzehrt_kcal += wp_meal.get("kcal", 0)
            verzehrt_protein += wp_meal.get("protein", 0)
            verzehrt_carbs += wp_meal.get("carbs", 0)
            verzehrt_fat += wp_meal.get("fat", 0)

    kcal_bonus = g_data.get("active_cal", 0)
    dynamisches_kcal_ziel = tagesbedarf["kcal"] + kcal_bonus

    rem_kcal = max(dynamisches_kcal_ziel - verzehrt_kcal, 0)
    rem_p = max(tagesbedarf["protein"] - verzehrt_protein, 0)
    rem_c = max(tagesbedarf["carbs"] - verzehrt_carbs, 0)
    rem_f = max(tagesbedarf["fat"] - verzehrt_fat, 0)

    # REZEPTKATALOG
    recipe_book = {
        "Frühstück 🥞": {
            "Power-Oatmeal (High-Protein)": {"kcal": 680, "protein": 52, "carbs": 85, "fat": 13, "zutaten": ["100g Haferflocken", "40g Whey-Proteinpulver", "150g Magerquark"], "anleitung": "Haferflocken quellen lassen. Quark und Whey unterrühren, Beeren drüber."},
            "Herzhaftes Rührei-Strammer-Max": {"kcal": 600, "protein": 55, "carbs": 40, "fat": 22, "zutaten": ["3 Eier", "100g Eiklar", "2 Scheiben Roggenbrot"], "anleitung": "Eiklar und Eier verquirlen, braten. Auf Brot servieren."}
        },
        "Fleischgerichte 🍗": {
            "Crispy Airfryer Chicken": {"kcal": 650, "protein": 62, "carbs": 65, "fat": 12, "zutaten": ["250g Hähnchenbrust", "300g Süßkartoffel"], "anleitung": "Hähnchen und Kartoffeln würfeln. 18 Min bei 180°C in den Airfryer."},
            "Puten-Brokkoli-Pfanne (Asia)": {"kcal": 620, "protein": 65, "carbs": 60, "fat": 10, "zutaten": ["250g Putenbrust", "200g Brokkoli"], "anleitung": "Reis kochen. Pute braten, Brokkoli mitdünsten."}
        },
        "Fischgerichte 🐟": {
            "Gebackenes Lachsfilet": {"kcal": 640, "protein": 48, "carbs": 55, "fat": 22, "zutaten": ["200g Lachsfilet", "70g Quinoa"], "anleitung": "Quinoa kochen. Lachs 15 Min bei 180°C backen."}
        },
        "Vegetarisch 🌱": {
            "Protein-Bowl mit Falafel": {"kcal": 580, "protein": 44, "carbs": 65, "fat": 14, "zutaten": ["200g Hüttenkäse", "100g Falafel"], "anleitung": "Mit Hüttenkäse, Gemüse und Falafel anrichten."}
        },
        "Snacks 🍫": {
            "Magerquark-Flavour-Bowl": {"kcal": 290, "protein": 42, "carbs": 16, "fat": 1, "zutaten": ["300g Magerquark", "Flavour Drops"], "anleitung": "Quark mit Wassertropfen cremig schlagen."},
            "Beef Jerky Handvoll": {"kcal": 150, "protein": 28, "carbs": 3, "fat": 2, "zutaten": ["50g Beef Jerky"], "anleitung": "Snackfertig aus der Packung für unterwegs."}
        }
    }

    alle_uebungen = [
        "Bankdrücken", "Klimmzüge", "Dips", "Langhantelrudern", "Face Pulls", "Bulgarian Split Squats", "Trap-Bar Kreuzheben", 
        "Box Jumps", "Lateral Lunges", "Nordic Hamstring Curls", "Schrägbankdrücken KH", "Kabelrudern eng", "Seitheben", 
        "Incline Curls", "Trizepsdrücken", "Power Cleans", "Medizinball-Würfe", "Romanian Deadlifts", "Ab-Wheel Rollouts", "Pallof Press"
    ]
    if "kraft_history" not in st.session_state: st.session_state.kraft_history = {ue: [{"Datum": "15.06.", "Leistung": "Basiswert stabil"}] for ue in alle_uebungen}
    if "current_workout_logs" not in st.session_state: st.session_state.current_workout_logs = {ue: [] for ue in alle_uebungen}

    # CRITICAL KORREKTUR PYTHON 3.14: Komplett isolierter Bestwert-Sicherer (Verhindert KeyError im with-Block)
    def render_exercise_engine(ue_name, default_w, default_r):
        # Wert VORAB isolieren, damit der Session-State-Proxy auf dem Server nicht crasht
        letzter_bestwert = "Kein Wert"
        if ue_name in st.session_state.kraft_history and len(st.session_state.kraft_history[ue_name]) > 0:
            letzter_bestwert = st.session_state.kraft_history[ue_name][-1].get('Leistung', 'Stabil')
            
        st.markdown(f"**Letzter Bestwert:** `{letzter_bestwert}`")
        
        g_today = g_data.get("garmin_strength_today", {})
        if ue_name in g_today: st.info(f"⌚ Garmin Live: {', '.join(g_today[ue_name])}")
        
        if st.session_state.current_workout_logs[ue_name]:
            for idx, sa in enumerate(st.session_state.current_workout_logs[ue_name]):
                s_col1, s_col2 = st.columns([5, 1])
                with s_col1: st.markdown(f"`Satz {idx+1}:` **{sa}**")
                with s_col2:
                    if st.button("❌", key=f"del_set_{ue_name}_{idx}"):
                        st.session_state.current_workout_logs[ue_name].pop(idx)
                        st.rerun()

        se_col1, se_col2 = st.columns(2)
        with se_col1: weight_input = st.number_input("Gewicht (kg):", value=float(default_w), step=2.5, key=f"w_in_{ue_name}")
        with se_col2: reps_input = st.number_input("Wiederholungen:", value=int(default_r), step=1, key=f"r_in_{ue_name}")
        
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            if st.button("Satz loggen ➕", key=f"btn_add_{ue_name}"):
                st.session_state.current_workout_logs[ue_name].append(f"{weight_input} kg x {reps_input} Wdh.")
                st.rerun()
        with b_col2:
            if st.session_state.current_workout_logs[ue_name] and st.button("Sichern 💾", key=f"btn_save_{ue_name}"):
                zusammenfassung = ", ".join(st.session_state.current_workout_logs[ue_name])
                st.session_state.kraft_history[ue_name].append({"Datum": st.session_state.selected_date.strftime("%d.%m."), "Leistung": zusammenfassung})
                st.session_state.current_workout_logs[ue_name] = [] 
                st.rerun()

        with st.expander("📈 Ergebnisse / Historie"):
            st.dataframe(pd.DataFrame(st.session_state.kraft_history[ue_name]), hide_index=True, use_container_width=True)

    # ==========================================
    # TIME-TRAVEL NAVIGATION BAR GANZ OBEN
    # ==========================================
    st.write("")
    nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
    
    with nav_col1:
        if st.session_state.selected_date > heute_datum - datetime.timedelta(days=7):
            if st.button("◀ Vorheriger Tag", use_container_width=True):
                st.session_state.selected_date -= datetime.timedelta(days=1)
                st.rerun()
            
    formatted_date_view = st.session_state.selected_date.strftime("%d.%m.%Y")
    if st.session_state.selected_date == heute_datum: display_label = f"Heute ({formatted_date_view})"
    elif st.session_state.selected_date == heute_datum - datetime.timedelta(days=1): display_label = f"Gestern ({formatted_date_view})"
    elif st.session_state.selected_date == heute_datum + datetime.timedelta(days=1): display_label = f"Morgen ({formatted_date_view})"
    else: display_label = f"{selected_weekday}, {formatted_date_view}"
        
    html_titel = f"<h2 style='text-align: center; color: #00f0ff; margin-top: -10px; font-weight: 900;'>{display_label}</h2>"
    with nav_col2:
        st.markdown(html_titel, unsafe_allow_html=True)
    
    with nav_col3:
        if st.session_state.selected_date < heute_datum + datetime.timedelta(days=7):
            if st.button("Nächster Tag ▶", use_container_width=True):
                st.session_state.selected_date += datetime.timedelta(days=1)
                st.rerun()
            
    st.write("---")

    # DREI-SPALTEN LAYOUT GENERIEREN
    col1, col2, col3 = st.columns([1.1, 1.5, 1], gap="large")

    # ==========================================
    # SPALTE 1: ERNÄHRUNG & ORGA
    # ==========================================
    with col1:
        st.header("🍽️ Ernährung & Orga")
        
        st.metric("Kcal Restbudget", f"{rem_kcal} kcal", f"Soll: {tagesbedarf['kcal']} (+{kcal_bonus} Aktiv)")
        st.metric("Protein Rest", f"{rem_p}g", f"Ziel: {tagesbedarf['protein']}g", delta_color="inverse")
        
        nu_col1, nu_col2 = st.columns(2)
        with nu_col1: st.metric("Carbs Rest", f"{rem_c}g")
        with nu_col2: st.metric("Fat Rest", f"{rem_f}g")
        
        st.write("---")
        st.session_state.prozis_weight = st.number_input("⚖️ Morgengewicht (kg):", value=float(st.session_state.prozis_weight), step=0.1)
        st.write("---")

        with st.expander("👨‍🍳 Perform-All Chefkoch: Rezeptkatalog"):
            cat_choice = st.selectbox("Kategorie wählen:", list(recipe_book.keys()))
            recipe_choice = st.selectbox("Rezept auswählen:", list(recipe_book[cat_choice].keys()))
            selected_rec = recipe_book[cat_choice][recipe_choice]
            st.markdown(f"#### {recipe_choice} ({selected_rec['kcal']} kcal)")
            
            if st.button("Heute essen (Loggen) ✅", key=f"log_chef_{recipe_choice}"):
                if selected_date_str not in st.session_state.meals_log:
                    st.session_state.meals_log[selected_date_str] = []
                st.session_state.meals_log[selected_date_str].append({
                    "name": recipe_choice, "kcal": selected_rec["kcal"], "protein": selected_rec["protein"], "carbs": selected_rec["carbs"], "fat": selected_rec["fat"]
                })
                st.rerun()
                
            w_tag = st.selectbox("In Wochenplan schieben:", list(st.session_state.ki_wochenplan.keys()), key=f"day_chef_{recipe_choice}")
            if st.button("Für diesen Tag einplanen 📅", key=f"plan_chef_{recipe_choice}"):
                st.session_state.ki_wochenplan[w_tag].append({"label": f"{recipe_choice} [{selected_rec['kcal']} kcal]", "instruction": selected_rec["anleitung"], "done": False, "kcal": selected_rec["kcal"], "protein": selected_rec["protein"], "carbs": selected_rec["carbs"], "fat": selected_rec["fat"], "zutaten": selected_rec["zutaten"]})
                st.rerun()

        with st.expander("📅 Dein Wochenplan & Einkaufsliste", expanded=True):
            if st.button("🛒 Einkaufsliste generieren"):
                zutaten_sammlung = []
                for tag, m_liste in st.session_state.ki_wochenplan.items():
                    for meal in m_liste:
                        if "zutaten" in meal: zutaten_sammlung.extend(meal["zutaten"])
                if zutaten_sammlung:
                    st.success("Zutaten exzerpiert:")
                    for z in sorted(list(set(zutaten_sammlung))): st.markdown(f"- [ ] {z}")
            st.write("---")
            for tag, m_liste in st.session_state.ki_wochenplan.items():
                if m_liste:
                    st.markdown(f"**{tag}**")
                    for m_idx, meal in enumerate(m_liste):
                        w_col1, w_col2 = st.columns([5, 1])
                        with w_col1: checked = st.checkbox(meal["label"], value=meal["done"], key=f"chk_{tag}_{m_idx}")
                        if checked != meal["done"]:
                            st.session_state.ki_wochenplan[tag][m_idx]["done"] = checked
                            st.rerun()
                        with w_col2:
                            if st.button("🗑️", key=f"del_wp_{tag}_{m_idx}"):
                                st.session_state.ki_wochenplan[tag].pop(m_idx)
                                st.rerun()

        with st.expander("📸 Neuen Mahlzeit-Scanner"):
            uploaded_file = st.file_uploader("Foto hochladen...", type=["jpg", "png", "jpeg"])

        with st.expander("📋 Ernährungsprotokoll dieses Tages"):
            if heutige_mahlzeiten_liste:
                for idx, meal in enumerate(heutige_mahlzeiten_liste):
                    m_col1, m_col2 = st.columns([5, 1])
                    with m_col1: st.caption(f"✔️ {meal['name']} ({meal['kcal']} kcal)")
                    with m_col2:
                        if st.button("❌", key=f"del_meal_{idx}"):
                            st.session_state.meals_log[selected_date_str].pop(idx)
                            st.rerun()
            else: st.caption("Noch keine Mahlzeiten an diesem Tag geloggt.")

    # ==========================================
    # SPALTE 2: TRAININGSPLAN, CARDIO & SWIM
    # ==========================================
    with col2:
        st.header("📅 Trainingsplan & Einheiten")
        if g_data.get("raw_strength_sets"):
            with st.expander("⌚ Live von deiner Garmin-Uhr erfasst (Heute)", expanded=True):
                for rs in g_data["raw_strength_sets"]: st.write(rs)
        
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "T1: OK Kraft 🦍", "T2: HB Beine 🤾", "T3: OK Vol 🦅", "T4: Schnellkraft ⚡", "T5: Ausdauer / Rad 🏃‍♂️", "T6: Schwimmen 🏊‍♂️"
        ])
        
        with tab1:
            st.subheader("Oberkörper Grundkraft")
            with st.expander("🧘 Warm-up: Schulter- & Brust-Mobility"):
                st.checkbox("10x Schulter- & Armkreisen")
                st.checkbox("12x Besenstil / Band Pass-Throughs")
                st.checkbox("45s Brust-Dehnen am Türrahmen")
            st.write("---")
            with st.expander("🏋️ Bankdrücken (4 Sätze x 6 Wdh.)"): render_exercise_engine("Bankdrücken", 85.0, 6)
            with st.expander("🏋️ Klimmzüge mit Zusatzgewicht"): render_exercise_engine("Klimmzüge", 10.0, 6)
            with st.expander("🏋️ Dips / Barrenstütz"): render_exercise_engine("Dips", 0.0, 8)
            with st.expander("🏋️ Langhantelrudern vorgebeugt"): render_exercise_engine("Langhantelrudern", 70.0, 8)
            with st.expander("🏋️ Face Pulls für Schulterstabilität"): render_exercise_engine("Face Pulls", 25.0, 12)
            
        with tab2:
            st.subheader("Handball Leg Day (Explosivität & Gelenkschutz)")
            with st.expander("🧘 Warm-up: Hüft- & Knie-Stabilisierung"):
                st.checkbox("60s Deep Squat Hold")
                st.checkbox("5x World's Greatest Stretch")
                st.checkbox("45s Couch Stretch")
            st.write("---")
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
            st.write("---")
            with st.expander("🧘 Cool-down: Post-Workout Oberkörper Stretching"):
                st.checkbox("60s Kindeshaltung / Child's Pose")
                st.checkbox("45s Pec-Stretch an der Wand")
            
        with tab4:
            st.subheader("Schnellkraft & Rumpfstabilität")
            with st.expander("🧘 Warm-up: BWS-Rotation & Core-Mobility"):
                st.checkbox("10x BWS-Rotation im Vierfüßlerstand")
                st.checkbox("15x Band Pull-Aparts")
            st.write("---")
            with st.expander("🏋️ Power Cleans / Umsetzen"): render_exercise_engine("Power Cleans", 60.0, 3)
            with st.expander("🏋️ Medizinball-Rotationswürfe"): render_exercise_engine("Medizinball-Würfe", 6.0, 8)
            with st.expander("🏋️ Romanian Deadlifts"): render_exercise_engine("Romanian Deadlifts", 90.0, 10)
            with st.expander("🏋️ Ab-Wheel Rollouts"): render_exercise_engine("Ab-Wheel Rollouts", 0.0, 10)
            with st.expander("🏋️ Pallof Press am Kabelzug"): render_exercise_engine("Pallof Press", 20.0, 12)
            
        with tab5:
            st.subheader("🏃‍♂️ Ausdauer & Pacing-Zentrale (Lauf / Rad)")
            
            if g_data.get("garmin_cardio_history"):
                with st.expander("⌚ Garmin Live-Tracker: Letzte Cardio-Einheiten", expanded=True):
                    df_g_runs = pd.DataFrame(g_data["garmin_cardio_history"])
                    st.dataframe(df_g_runs, hide_index=True, use_container_width=True)
            
            st.write("---")
            st.markdown("**Manuelle Cardio-Einheit eintragen:**")
            
            c_type = st.selectbox("Ausdauertyp wählen:", [
                "Zone 2 Lauf (Grundlagenausdauer / Fettverbrennung)", "Intervalllauf / HIIT (Match-Sprints)",
                "Schneller 5 km Tempolauf", "10 km Dauerlauf (Aerobe Kapazität)",
                "2-Stunden-Dauerlauf (Maximale Belastungsdauer)", "Zone 4/5 Schwellenlauf (VO2-Max Entwicklung)",
                "Handball Shuttle Runs (Pendelsprint-Härte)", "Fahrrad / Radtour (Gelenkschonende Ausdauer)",
                "Fahrrad-Intervalle (Explosivkraft Beine)"
            ])
            
            c_col1, c_col2, c_col3 = st.columns(3)
            with c_col1: c_dist = st.number_input("Distanz (km):", value=5.0, step=0.1, key="c_dist_all")
            with c_col2: c_min = st.number_input("Zeit: Minuten:", value=25, step=1, key="c_min_all")
            with c_col3: c_sec = st.number_input("Zeit: Sekunden:", value=0, step=1, max_value=59, key="c_sec_all")
            
            total_man_minutes = c_min + (c_sec / 60)
            if c_dist > 0 and total_man_minutes > 0:
                man_speed = round(c_dist / (total_man_minutes / 60), 1)
                man_pace_dec = total_man_minutes / c_dist
                man_p_m = int(man_pace_dec)
                man_p_s = int((man_pace_dec - man_p_m) * 60)
                man_pace_str = f"{man_p_m}:{man_p_s:02d} min/km"
                
                m_calc1, m_calc2 = st.columns(2)
                with m_calc1: st.metric("Berechnete Pace", man_pace_str)
                with m_calc2: st.metric("Geschwindigkeit", f"{man_speed} km/h")
            else: man_pace_str, man_speed = "--", 0
                
            if st.button("Einheit in Historie eintragen 🏃‍♂️", key="log_cardio_all"):
                st.session_state.cardio_history.append({
                    "Datum": st.session_state.selected_date.strftime("%d.%m."), "Typ": c_type.split(" (")[0], "Distanz": f"{c_dist} km",
                    "Dauer": f"{c_min}:{c_sec:02d} Min", "Pace": man_pace_str, "Speed": f"{man_speed} km/h"
                })
                st.rerun()
                
            with st.expander("📈 Ergebnisse / Alle vergangenen Einheiten", expanded=True):
                if st.session_state.cardio_history:
                    for idx, run in enumerate(st.session_state.cardio_history):
                        r_col1, r_col2 = st.columns([5, 1])
                        with r_col1: st.markdown(f"`{run['Datum']}` **{run['Typ']}**: {run['Distanz']} in {run['Dauer']} ({run['Pace']} | {run['Speed']})")
                        with r_col2:
                            if st.button("❌", key=f"del_c_hist_{idx}"):
                                st.session_state.cardio_history.pop(idx)
                                st.rerun()
                else: st.caption("Noch keine Einheiten manuell geloggt.")
                
            st.write("---")
            with st.expander("🧘 Cool-down: Regeneration & Blackroll"):
                st.checkbox("3 Min. Waden & Schienbeine ausrollen (Blackroll)")
                st.checkbox("60s Quad-Stretch im Stehen")
                
        with tab6:
            st.subheader("🏊‍♂️ Schwimm-Kommandozentrale")
            if g_data.get("garmin_swim_history"):
                with st.expander("⌚ Garmin Live-Tracker: Letzte Schwimmeinheiten", expanded=True):
                    df_g_swim = pd.DataFrame(g_data["garmin_swim_history"])
                    st.dataframe(df_g_swim, hide_index=True, use_container_width=True)
            
            with st.expander("🧘 Warm-up: Schulter- & Gelenkmobilität (Schwimmen)"):
                st.checkbox("15x Scapula-Umdrehungen am Kabel/Band")
                st.checkbox("10x Brustwirbelsäulen-Rotatoren (Halle)")
                
            st.write("---")
            st.markdown("**Manuelle Schwimmeinheit eintragen:**")
            
            sw_col1, sw_col2, sw_col3 = st.columns(3)
            with sw_col1: sw_dist = st.number_input("Distanz (Meter):", value=1500, step=50, key="sw_dist_in")
            with sw_col2: sw_min = st.number_input("Minuten:", value=30, step=1, key="sw_min_in")
            with sw_col3: sw_sec = st.number_input("Sekunden:", value=0, step=1, max_value=59, key="sw_sec_in")
            
            total_swim_sec = (sw_min * 60) + sw_sec
            if sw_dist > 0 and total_swim_sec > 0:
                swim_pace_dec = (total_swim_sec / 60) / (sw_dist / 100)
                sm = int(swim_pace_dec)
                ss = int((swim_pace_dec - sm) * 60)
                swim_pace_str = f"{sm}:{ss:02d} min/100m"
                st.metric("Berechnete Schwimm-Pace:", swim_pace_str)
            else: swim_pace_str = "--"
                
            if st.button("Schwimmen in Historie loggen 💾", key="log_swim_btn"):
                st.session_state.swim_history.append({
                    "Datum": st.session_state.selected_date.strftime("%d.%m."), "Distanz": f"{sw_dist} m",
                    "Dauer": f"{sw_min}:{sw_sec:02d} Min", "Pace": swim_pace_str
                })
                st.rerun()
                
            with st.expander("📈 Ergebnisse / Alle vergangenen Schwimmtrainings", expanded=True):
                if st.session_state.swim_history:
                    for idx, swim in enumerate(st.session_state.swim_history):
                        sw_c1, sw_col2 = st.columns([5, 1])
                        with sw_c1: st.markdown(f"`{swim['Datum']}` **Schwimmen**: {swim['Distanz']} in {swim['Dauer']} (Ø-Pace: `{swim['Pace']}`)")
                        with sw_col2:
                            if st.button("❌", key=f"del_sw_hist_{idx}"):
                                st.session_state.swim_history.pop(idx)
                                st.rerun()
                else: st.caption("Noch keine manuellen Schwimmeinheiten eingetragen.")

    # ==========================================
    # SPALTE 3: GARMIN VITAL-HUB
    # ==========================================
    with col3:
        st.header("📊 Garmin Hub")
        
        st.subheader("🔥 Live-Umsatz")
        st.metric("Aktiv-Verbrauch", f"{g_data['active_cal']} kcal")
        st.metric("Gesamt-Umsatz", f"{g_data['total_cal']} kcal")
        st.caption(f"BMR Rechner: {g_data['bmr_cal']} kcal")
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

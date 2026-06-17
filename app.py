import streamlit as str
import pandas as pd
import datetime
import zoneinfo
from garminconnect import Garmin
from PIL import Image
from google import genai

# 1. Page Configuration
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

    # GARMIN DATENABRUF (Cached für 5 Minuten)
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
            activities = client.get_activities(0, 5) # Letzten 5 Workouts für die Gesamtübersicht
            
            # Workouts auslesen
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
                "total_intensity": total_intensity,
                "intensity_goal": intensity_goal,
                "sleep_duration": sleep_hours,
                "sleep_score": sleep_score,
                "stress_avg": stress_avg
            }
            return garmin_pack, True
        except Exception as e:
            fallback = {
                "rhr": "--", "max_hr": "--", "workout_list": ["Keine Einheiten geladen"],
                "steps": 0, "step_goal": 10000, "active_cal": 0, "bmr_cal": 0, "total_cal": 0,
                "distance_km": 0.0, "total_intensity": 0, "intensity_goal": 150,
                "sleep_duration": 0, "sleep_score": "--", "stress_avg": "--"
            }
            return fallback, False

    g_data, garmin_success = fetch_garmin_data()

    # ERNÄHRUNGS-LOGIK (SESSION STATE)
    if "verzehrt" not in str.session_state:
        str.session_state.verzehrt = {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}
        str.session_state.meals_log = []

    # Exakt berechnete Makros für Alec (102kg Körpergewicht - Fokus: Recomp / Fettabbau)
    tagesbedarf = {"kcal": 2600, "protein": 204, "carbs": 260, "fat": 80}

    # DASHBOARD LAYOUT
    str.title("⚡ OVERSEER // TOTAL PERFORMANCE Hub")
    str.write("---")

    col1, col2, col3 = str.columns([1.1, 1.2, 1.5], gap="large")

    # ==========================================
    # SPALTE 1: VITAL-WERTE & VOLLZOGENE EINHEITEN
    # ==========================================
    with col1:
        str.header("🏃 Vitalwerte & Historie")
        
        # Schnelle Metriken
        str.metric("Schritte heute", f"{g_data['steps']:,} / {g_data['step_goal']:,}")
        str.metric("Gesamtumsatz", f"{g_data['total_cal']} kcal", f"Aktiv: {g_data['active_cal']} kcal")
        
        with str.expander("❤️ Regeneration & Herzfrequenz", expanded=True):
            v_col1, v_col2 = str.columns(2)
            v_col1.metric("Ruhepuls", f"{g_data['rhr']} bpm")
            v_col2.metric("Stress-Level", f"{g_data['stress_avg']} / 100")
            str.caption(f"Schlaf-Score: {g_data['sleep_score']}/100 ({g_data['sleep_duration']} Std)")

        str.write("---")
        str.subheader("✅ Zuletzt vollzogene Einheiten")
        str.caption("Automatisch synchronisiert aus deiner Garmin-Historie:")
        if g_data['workout_list']:
            for w in g_data['workout_list']:
                str.write(w)
        else:
            str.caption("Keine Workouts in den letzten Tagen gefunden.")

    # ==========================================
    # SPALTE 2: NUTRITION & GEMINI-ANALYSE
    # ==========================================
    with col2:
        str.header("🍽️ Ernährung & Makros")
        
        rem_kcal = max(tagesbedarf["kcal"] - str.session_state.verzehrt["kcal"], 0)
        rem_p = max(tagesbedarf["protein"] - str.session_state.verzehrt["protein"], 0)
        rem_c = max(tagesbedarf["carbs"] - str.session_state.verzehrt["carbs"], 0)
        rem_f = max(tagesbedarf["fat"] - str.session_state.verzehrt["fat"], 0)
        
        m_col1, m_col2 = str.columns(2)
        m_col1.metric("Kcal Restbudget", f"{rem_kcal:,} kcal", f"Ziel: {tagesbedarf['kcal']}")
        m_col2.metric("Protein Rest (g)", f"{rem_p}g", f"Ziel: {tagesbedarf['protein']}g", delta_color="inverse")
        
        m_col3, m_col4 = str.columns(2)
        m_col3.metric("Carbs Rest", f"{rem_c}g", f"Ziel: {tagesbedarf['carbs']}g")
        m_col4.metric("Fat Rest", f"{rem_f}g", f"Ziel: {tagesbedarf['fat']}g")
        
        str.write("---")
        str.subheader("📸 Mahlzeit via Gemini scannen")
        uploaded_file = str.file_uploader("Foto hochladen...", type=["jpg", "png", "jpeg"])
        
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            str.image(image, caption="Dein Essen", width=250)
            
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
                edit_p = c_ki1.number_input("Protein (g):", value=str.session_state.temp_meal["protein"])
                edit_c = c_ki2.number_input("Carbs (g):", value=str.session_state.temp_meal["carbs"])
                edit_f = c_ki3.number_input("Fat (g):", value=str.session_state.temp_meal["fat"])
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
    # SPALTE 3: INTERAKTIVER TRAININGSPLAN
    # ==========================================
    with col3:
        str.header("📅 Trainingsplan & Progression")
        
        # Tabs für die einzelnen Trainingstage
        tab1, tab2, tab3, tab4, tab5 = str.tabs(["Tag 1: Kraft (OK)", "Tag 2: Handball Leg Day", "Tag 3: Hypertrophie (OK)", "Tag 4: Explosivkraft", "Tag 5: Ausdauer"])
        
        with tab1:
            str.subheader("Upper Body Power")
            str.caption("Fokus: Grundkraft Oberkörper")
            str.checkbox("Bankdrücken (4 Sätze x 6 Wdh.)")
            str.checkbox("Klimmzüge / Latzug (4 Sätze x 8 Wdh.)")
            str.checkbox("Overhead Press (3 Sätze x 8 Wdh.)")
            str.checkbox("Langhantelrudern (3 Sätze x 10 Wdh.)")
            
        with tab2:
            str.subheader("Handball-Spezifisches Beintraining")
            str.caption("Fokus: Einbeinige Stabilität für Richtungswechsel, Gelenkschutz & Bremskraft")
            str.checkbox("Bulgarian Split Squats (4 Sätze x 8 Wdh. je Seite) - *Schützt Knie bei Täuschungen*")
            str.checkbox("Trap-Bar Kreuzheben / Kniebeugen (4 Sätze x 6 Wdh.) - *Maximale Beinkraft*")
            str.checkbox("Box Jumps / Plyometrie (3 Sätze x 5 Wdh.) - *Explosiver Antritt & Sprungwurf*")
            str.checkbox("Lateral Lunges mit Zusatzgewicht (3 Sätze x 8 Wdh. je Seite) - *Seitliche Abwehrbewegungen*")
            str.checkbox("Nordic Hamstring Curls (3 Sätze x 6 Wdh.) - *Ultimativer Schutz vor Muskelbündelrissen*")
            
        with tab3:
            str.subheader("Upper Body Volumen")
            str.caption("Fokus: Muskelmasse halten und aufbauen")
            str.checkbox("Schrägbankdrücken KH (4 Sätze x 10 Wdh.)")
            str.checkbox("Kabelrudern eng (4 Sätze x 10 Wdh.)")
            str.checkbox("Seitheben am Kabelzug (3 Sätze x 12 Wdh.)")
            str.checkbox("Bizeps & Trizeps Supersatz (3 Sätze x 12 Wdh.)")
            
        with tab4:
            str.subheader("Explosivkraft & Core-Stabilität")
            str.caption("Fokus: Schnellkraft für den Wurf & Kernstabilität im Zweikampf")
            str.checkbox("Hang Cleans / Umsetzen (4 Sätze x 4 Wdh.) - *Hüftexplosivität*")
            str.checkbox("Medizinball-Überkopf-Würfe gegen Wand (3 Sätze x 8 Wdh.) - *Wurfkraft*")
            str.checkbox("Romanian Deadlifts (3 Sätze x 10 Wdh.) - *Hintere Kette*")
            str.checkbox("Plank mit Zusatzgewicht / Pallof Press (3 Sätze x 45 Sek.) - *Stabilität im Clinch*")
            
        with tab5:
            str.subheader("Handball-Ausdauereinheit")
            str.caption("Fokus: Intervall-Ausdauer für die 60 Minuten Belastung")
            ausdauer_wahl = str.radio("Wähle deine heutige Ausdauereinheit:", ["Zone 2 Lauf (45-60 Min. Regeneration)", "Handball Shuttle Runs (15x 20m Sprints mit Richtungswechsel, 30 Sek. Pause)"])
            str.checkbox(f"Einheit durchziehen: {ausdauer_wahl}")

        # Kleines Notizfeld für Steigerungen im Kraftraum
        str.write("---")
        str.subheader("📝 Progressions-Notizen (Gewichte & Steigerungen)")
        str.text_area("Schreibe hier rein, wenn du dich gesteigert hast:", placeholder="z.B. Tag 2: Bulgarian Split Squats gesteigert auf 24kg Hanteln...")

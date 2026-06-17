import streamlit as st
import pandas as pd
import datetime
import zoneinfo
from garminconnect import Garmin
from PIL import Image
from google import genai

# 1. Page Configuration (Fokus auf mobile Nutzung und Scrollbarkeit)
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

    # ==========================================
    # PERSISTENTER KRAFTRAUM-SPEICHER (HISTORY)
    # ==========================================
    if "kraft_history" not in st.session_state:
        # Hier werden deine Gewichte gespeichert. Wenn du trainierst, überschreibt die App diese Werte.
        st.session_state.kraft_history = {
            "Bankdrücken": "85.0 kg x 6 Wdh.",
            "Klimmzüge": "10.0 kg x 6 Wdh.",
            "Dips": "Körpergewicht x 8 Wdh.",
            "Langhantelrudern": "70.0 kg x 8 Wdh.",
            "Face Pulls": "25.0 kg x 12 Wdh.",
            "Bulgarian Split Squats": "20.0 kg x 8 Wdh.",
            "Trap-Bar Kreuzheben": "120.0 kg x 6 Wdh.",
            "Box Jumps": "60 cm x 5 Wdh.",
            "Lateral Lunges": "16.0 kg x 8 Wdh.",
            "Nordic Hamstring Curls": "Körpergewicht x 6 Wdh.",
            "Schrägbankdrücken KH": "30.0 kg x 10 Wdh.",
            "Kabelrudern eng": "65.0 kg x 10 Wdh.",
            "Seitheben": "12.5 kg x 12 Wdh.",
            "Incline Curls": "15.0 kg x 12 Wdh.",
            "Trizepsdrücken": "30.0 kg x 12 Wdh.",
            "Power Cleans": "60.0 kg x 3 Wdh.",
            "Medizinball-Würfe": "6.0 kg x 8 Wdh.",
            "Romanian Deadlifts": "90.0 kg x 10 Wdh.",
            "Ab-Wheel Rollouts": "Körpergewicht",
            "Pallof Press": "20.0 kg x 12 Wdh."
        }

    # ==========================================
    # ERNÄHRUNGS- & FAVORITEN-SPEICHER
    # ==========================================
    if "verzehrt" not in st.session_state:
        st.session_state.verzehrt = {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}
        st.session_state.meals_log = []

    if "favorites" not in st.session_state:
        st.session_state.favorites = {
            "--- Bitte wählen ---": None,
            "Alec's Standard Frühstück (Haferflocken & Protein)": {"kcal": 580, "protein": 45, "carbs": 75, "fat": 10},
            "Post-Workout Shake (High Protein)": {"kcal": 240, "protein": 35, "carbs": 15, "fat": 2},
            "Standard Hähnchen-Reis-Pfanne": {"kcal": 720, "protein": 55, "carbs": 90, "fat": 12}
        }

    # 102kg Makro-Soll (Defizit + High Protein)
    tagesbedarf = {"kcal": 2600, "protein": 204, "carbs": 260, "fat": 80}

    # Layout: Spalte 2 (Mitte) ist die breiteste für deinen Trainingsplan
    col1, col2, col3 = st.columns([1, 1.5, 1.1], gap="large")

    # ==========================================
    # SPALTE 1: ALL GARMIN VITALS & CALORIES
    # ==========================================
    with col1:
        st.header("📊 Garmin Dashboard")
        
        st.subheader("🔥 Kalorien & Umsatz")
        st.metric("Aktiv-Verbrauch", f"{g_data['active_cal']} kcal")
        st.metric("Gesamt-Umsatz", f"{g_data['total_cal']} kcal")
        
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
        st.caption("Drücke auf eine Übung, um das Untermenü für deine Sätze zu öffnen.")
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["T1: OK Kraft", "T2: HB Beine", "T3: OK Volumen", "T4: Schnellkraft", "T5: Ausdauer"])
        
        with tab1:
            st.subheader("Oberkörper Grundkraft")
            
            # --- BEISPIEL ÜBUNG 1 ---
            with st.expander("🏋️ Bankdrücken (4 Sätze x 6 Wdh.)"):
                st.markdown(f"**Letztes Mal bewegt:** `{st.session_state.kraft_history['Bankdrücken']}`")
                w1 = st.number_input("Gewicht heute (kg):", value=85.0, step=2.5, key="bd_w")
                r1 = st.number_input("Wiederholungen geschafft:", value=6, step=1, key="bd_r")
                if st.button("Satz einloggen & speichern", key="save_bd"):
                    st.session_state.kraft_history["Bankdrücken"] = f"{w1} kg x {r1} Wdh."
                    st.success("Wert für das nächste Mal gespeichert!")
                    st.rerun()

            with st.expander("🏋️ Klimmzüge mit Zusatzgewicht (4 Sätze x 6 Wdh.)"):
                st.markdown(f"**Letztes Mal bewegt:** `{st.session_state.kraft_history['Klimmzüge']}`")
                w2 = st.number_input("Gewicht heute (kg):", value=10.0, step=2.5, key="kz_w")
                r2 = st.number_input("Wiederholungen geschafft:", value=6, step=1, key="kz_r")
                if st.button("Satz einloggen & speichern", key="save_kz"):
                    st.session_state.kraft_history["Klimmzüge"] = f"{w2} kg x {r2} Wdh."
                    st.success("Gespeichert!")
                    st.rerun()

            with st.expander("🏋️ Dips / Barrenstütz (3 Sätze x 8 Wdh.)"):
                st.markdown(f"**Letztes Mal bewegt:** `{st.session_state.kraft_history['Dips']}`")
                r3 = st.number_input("Wiederholungen geschafft:", value=8, step=1, key="dip_r")
                if st.button("Satz einloggen & speichern", key="save_dips"):
                    st.session_state.kraft_history["Dips"] = f"Körpergewicht x {r3} Wdh."
                    st.rerun()

            with st.expander("🏋️ Langhantelrudern vorgebeugt (3 Sätze x 8 Wdh.)"):
                st.markdown(f"**Letztes Mal bewegt:** `{st.session_state.kraft_history['Langhantelrudern']}`")
                w4 = st.number_input("Gewicht heute (kg):", value=70.0, step=5.0, key="lh_w")
                r4 = st.number_input("Wiederholungen geschafft:", value=8, step=1, key="lh_r")
                if st.button("Satz einloggen & speichern", key="save_lh"):
                    st.session_state.kraft_history["Langhantelrudern"] = f"{w4} kg x {r4} Wdh."
                    st.rerun()

            with st.expander("🏋️ Face Pulls (3 Sätze x 12 Wdh.)"):
                st.markdown(f"**Letztes Mal bewegt:** `{st.session_state.kraft_history['Face Pulls']}`")
                w5 = st.number_input("Gewicht heute (kg):", value=25.0, step=2.5, key="fp_w")
                if st.button("Satz einloggen & speichern", key="save_fp"):
                    st.session_state.kraft_history["Face Pulls"] = f"{w5} kg x 12 Wdh."
                    st.rerun()
            
        with tab2:
            st.subheader("Handball Leg Day (Explosivität & Schutz)")
            
            with st.expander("🏋️ Bulgarian Split Squats (4 Sätze x 8 Wdh. je Seite)"):
                st.markdown(f"**Letztes Mal bewegt:** `{st.session_state.kraft_history['Bulgarian Split Squats']}`")
                w6 = st.number_input("Gewicht heute (kg):", value=20.0, step=2.0, key="bss_w")
                if st.button("Satz einloggen & speichern", key="save_bss"):
                    st.session_state.kraft_history["Bulgarian Split Squats"] = f"{w6} kg x 8 Wdh."
                    st.rerun()

            with st.expander("🏋️ Trap-Bar Kreuzheben (4 Sätze x 6 Wdh.)"):
                st.markdown(f"**Letztes Mal bewegt:** `{st.session_state.kraft_history['Trap-Bar Kreuzheben']}`")
                w7 = st.number_input("Gewicht heute (kg):", value=120.0, step=5.0, key="tb_w")
                if st.button("Satz einloggen & speichern", key="save_tb"):
                    st.session_state.kraft_history["Trap-Bar Kreuzheben"] = f"{w7} kg x 6 Wdh."
                    st.rerun()

            with st.expander("🏋️ Box Jumps (3 Sätze x 5 Wdh.)"):
                st.markdown(f"**Letztes Mal bewegt:** `{st.session_state.kraft_history['Box Jumps']}`")
                h7 = st.number_input("Höhe heute (cm):", value=60, step=5, key="bj_h")
                if st.button("Satz einloggen & speichern", key="save_bj"):
                    st.session_state.kraft_history["Box Jumps"] = f"{h7} cm x 5 Wdh."
                    st.rerun()

            with st.expander("🏋️ Lateral Lunges / Ausfallschritte (3 Sätze x 8 Wdh.)"):
                st.markdown(f"**Letztes Mal bewegt:** `{st.session_state.kraft_history['Lateral Lunges']}`")
                w8 = st.number_input("Gewicht heute (kg):", value=16.0, step=2.0, key="ll_w")
                if st.button("Satz einloggen & speichern", key="save_ll"):
                    st.session_state.kraft_history["Lateral Lunges"] = f"{w8} kg x 8 Wdh."
                    st.rerun()

            with st.expander("🏋️ Nordic Hamstring Curls (3 Sätze x 6 Wdh.)"):
                st.markdown(f"**Letztes Mal bewegt:** `{st.session_state.kraft_history['Nordic Hamstring Curls']}`")
                r9 = st.number_input("Wdh geschafft:", value=6, step=1, key="nhc_r")
                if st.button("Satz einloggen & speichern", key="save_nhc"):
                    st.session_state.kraft_history["Nordic Hamstring Curls"] = f"Körpergewicht x {r9} Wdh."
                    st.rerun()
            
        with tab3:
            st.subheader("Oberkörper Volumen (Hypertrophie)")
            
            with st.expander("🏋️ Schrägbankdrücken mit Kurzhanteln (4x10)"):
                st.markdown(f"**Letztes Mal:** `{st.session_state.kraft_history['Schrägbankdrücken KH']}`")
                w10 = st.number_input("Gewicht (kg):", value=30.0, step=2.0, key="sb_w")
                if st.button("Speichern", key="save_sb"):
                    st.session_state.kraft_history["Schrägbankdrücken KH"] = f"{w10} kg x 10 Wdh."
                    st.rerun()

            with st.expander("🏋️ Kabelrudern eng zum Bauch (4x10)"):
                st.markdown(f"**Letztes Mal:** `{st.session_state.kraft_history['Kabelrudern eng']}`")
                w11 = st.number_input("Gewicht (kg):", value=65.0, step=5.0, key="kr_w")
                if st.button("Speichern", key="save_kr"):
                    st.session_state.kraft_history["Kabelrudern eng"] = f"{w11} kg x 10 Wdh."
                    st.rerun()
                    
            with st.expander("🏋️ Seitheben am Kabelzug (3x12)"):
                st.markdown(f"**Letztes Mal:** `{st.session_state.kraft_history['Seitheben']}`")
                w12 = st.number_input("Gewicht (kg):", value=12.5, step=1.25, key="sh_w")
                if st.button("Speichern", key="save_sh"):
                    st.session_state.kraft_history["Seitheben"] = f"{w12} kg x 12 Wdh."
                    st.rerun()

        with tab4:
            st.subheader("Schnellkraft & Rumpfstabilität")
            with st.expander("🏋️ Power Cleans / Umsetzen (4x3 Wdh.)"):
                st.markdown(f"**Letztes Mal:** `{st.session_state.kraft_history['Power Cleans']}`")
                w13 = st.number_input("Gewicht (kg):", value=60.0, step=5.0, key="pc_w")
                if st.button("Speichern", key="save_pc"):
                    st.session_state.kraft_history["Power Cleans"] = f"{w13} kg x 3 Wdh."
                    st.rerun()

            with st.expander("🏋️ Medizinball-Rotationswürfe (3x8 Wdh.)"):
                st.markdown(f"**Letztes Mal:** `{st.session_state.kraft_history['Medizinball-Würfe']}`")
                w14 = st.number_input("Gewicht (kg):", value=6.0, step=1.0, key="mb_w")
                if st.button("Speichern", key="save_mb"):
                    st.session_state.kraft_history["Medizinball-Würfe"] = f"{w14} kg x 8 Wdh."
                    st.rerun()
            
        with tab5:
            st.subheader("Handball Intervall- & Grundlagenausdauer")
            ausdauer_wahl = st.radio("Wähle deine Cardio-Session:", ["Zone 2 Lauf (45-60 Min.)", "Handball Shuttle Runs (15x 20m Sprints)"])
            st.checkbox(f"Session erfolgreich beendet: {ausdauer_wahl}")

    # ==========================================
    # SPALTE 3: NUTRITION & DROPDOWN (RECHTS)
    # ==========================================
    with col3:
        st.header("🍽️ Ernährung & Orga")
        
        # Restbudget-Berechnung
        rem_kcal = max(tagesbedarf["kcal"] - st.session_state.verzehrt["kcal"], 0)
        rem_p = max(tagesbedarf["protein"] - st.session_state.verzehrt["protein"], 0)
        rem_c = max(tagesbedarf["carbs"] - st.session_state.verzehrt["carbs"], 0)
        rem_f = max(tagesbedarf["fat"] - st.session_state.verzehrt["fat"], 0)
        
        st.metric("Kcal Restbudget", f"{rem_kcal:,} kcal", f"Ziel: {tagesbedarf['kcal']}")
        st.metric("Protein Rest", f"{rem_p}g", f"Ziel: {tagesbedarf['protein']}g", delta_color="inverse")
        
        nu_col1, nu_col2 = st.columns(2)
        nu_col1.metric("Carbs Rest", f"{rem_c}g")
        nu_col2.metric("Fat Rest", f"{rem_f}g")
        
        # DROPDOWN FÜR WIEDERKEHRENDE MAHLZEITEN
        st.write("---")
        st.subheader("⭐ Wiederkehrende Mahlzeiten")
        fav_choice = st.selectbox("Schnellauswahl Lieblingsgerichte:", list(st.session_state.favorites.keys()))
        
        if fav_choice != "--- Bitte wählen ---":
            meal_data = st.session_state.favorites[fav_choice]
            st.caption(f"📊 {meal_data['kcal']} kcal | {meal_data['protein']}g P")
            if st.button(f"'{fav_choice}' loggen ✅"):
                st.session_state.verzehrt["kcal"] += meal_data["kcal"]
                st.session_state.verzehrt["protein"] += meal_data["protein"]
                st.session_state.verzehrt["carbs"] += meal_data["carbs"]
                st.session_state.verzehrt["fat"] += meal_data["fat"]
                st.session_state.meals_log.append(f"{fav_choice} (+{meal_data['protein']}g P)")
                st.rerun()
        
        st.write("---")
        
        # Gemini Foto-Scanner
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
                
                # JETZT MIT AUTOMATISCHEM FAVORITEN-SPEICHER
                add_to_favs = st.checkbox("Zu 'Wiederkehrende Mahlzeiten' hinzufügen? ⭐")
                
                if st.button("In Log eintragen ✅", key="add_scanned_meal"):
                    st.session_state.verzehrt["kcal"] += edit_kcal
                    st.session_state.verzehrt["protein"] += edit_p
                    st.session_state.verzehrt["carbs"] += edit_c
                    st.session_state.verzehrt["fat"] += edit_f
                    st.session_state.meals_log.append(f"{edit_name} ({edit_kcal} kcal | {edit_p}g P)")
                    
                    if add_to_favs:
                        st.session_state.favorites[edit_name] = {"kcal": edit_kcal, "protein": edit_p, "carbs": edit_c, "fat": edit_f}
                        
                    del st.session_state.temp_meal
                    st.rerun()

        if st.session_state.meals_log:
            for meal in st.session_state.meals_log:
                st.caption(f"✔️ {meal}")

        # Finanzen
        st.write("---")
        st.subheader("💼 Finanzen & Daily Routine")
        st.metric(label="Verfügbares Netto (Monat)", value="1.850,00 €")
        st.checkbox("Handball-Dehnprogramm absolviert (15 Min)")

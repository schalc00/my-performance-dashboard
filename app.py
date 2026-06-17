import streamlit as str
import pandas as pd
from datetime import date
from garminconnect import Garmin
from PIL import Image
from google import genai

# 1. Page Configuration
str.set_page_config(page_title="Alec's Dashboard", page_icon="⚡", layout="wide")

# Passwort-Schutz für das Handy
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
    
    # API INITIALISIERUNG AUS DEN SECRETS
    GARMIN_EMAIL = str.secrets["GARMIN_EMAIL"]
    GARMIN_PASSWORD = str.secrets["GARMIN_PASSWORD"]
    GEMINI_API_KEY = str.secrets["GEMINI_API_KEY"]
    
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

    # Garmin Daten abrufen (Cached für 30 Min)
    @str.cache_data(ttl=1800)
    def fetch_garmin_data():
        try:
            client = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
            client.login()
            today = date.today().isoformat()
            
            activities = client.get_activities(0, 1)
            last_workout = "Kein Workout heute"
            if activities:
                last_workout = f"{activities[0]['activityName']} ({round(activities[0]['duration']/60)} min)"
                
            stats = client.get_stats(today)
            rhr = client.get_heart_rates(today).get("restingHeartRate", "--")
            return {"rhr": rhr, "last_workout": last_workout}, True
        except:
            return {"rhr": 45, "last_workout": "Handball-Spezifisches Intervalltraining (45 min)"}, False

    data, garmin_success = fetch_garmin_data()

    # ERNÄHRUNGS-LOGIK (SESSION STATE)
    if "verzehrt" not in str.session_state:
        str.session_state.verzehrt = {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}
        str.session_state.meals_log = []

    tagesbedarf = {"kcal": 3000, "protein": 180, "carbs": 380, "fat": 80}

    # DASHBOARD LAYOUT
    str.title("⚡ OVERSEER // PERFORMANCE & NUTRITION")
    str.caption("Vollautomatisiertes Tracking über Garmin & Gemini 2.5")
    str.write("---")

    col1, col2, col3 = str.columns([1, 1.5, 1], gap="large")

    # SPALTE 1: HANDBALL PREP & FITNESS
    with col1:
        str.header("🤾 Handball Vorbereitung")
        str.subheader("Aktuelle Phase: Explosivkraft & Speed")
        str.info(f" Letztes Garmin-Workout: **{data['last_workout']}**")
        str.metric(label="Ruhepuls (RHR)", value=f"{data['rhr']} bpm")
        
        str.write("---")
        str.subheader("🏋️ Progressions-Tracker")
        bench_press = str.number_input("Bankdrücken (kg) - Ziel 4x6:", value=85, step=2)
        squats = str.number_input("Kniebeugen (kg) - Ziel 4x6:", value=110, step=5)

    # SPALTE 2: NUTRITION & GEMINI-ANALYSE
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
                        str.error(f"Fehler bei der Gemini-Analyse. Bitte erneut versuchen.")
            
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

    # SPALTE 3: FINANZEN & CHECKLISTE
    with col3:
        str.header("💼 Finanzen & Tagesziele")
        str.metric(label="Verfügbares Netto (Monat)", value="1.850,00 €")
        str.write("---")
        str.subheader("✅ Tagesziele")
        str.checkbox("Garmin synchronisieren", value=garmin_success)
        str.checkbox("Handball-Dehnprogramm (15 Min)")
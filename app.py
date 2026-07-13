import streamlit as st
import os
import json
import re
from openai import OpenAI
import pdfplumber
import plotly.express as px
import pandas as pd
from market_scraper import get_market_requirements
from database import save_analysis, get_analysis_history

# Konfiguracja
st.set_page_config(page_title="Career Pathfinder AI", page_icon="🎯", layout="wide")
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---- NOWA FUNKCJA: Przetwarzanie plików w locie ----
def process_uploaded_pdfs(uploaded_files):
    all_text = ""
    for file in uploaded_files:
        try:
            # Streamlit przetrzymuje pliki w pamięci jako bajty. 
            # Pdfplumber radzi z tym sobie bezbłędnie.
            with pdfplumber.open(file) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        all_text += text + "\n"
        except Exception as e:
            st.warning(f"Nie udało się odczytać pliku {file.name}: {e}")
    return all_text

def extract_skills_with_ai(text):
    prompt = f"""
    Jesteś ekspertem HR i analitykiem danych. Poniżej znajduje się surowy tekst z sylabusa uniwersyteckiego.
    Twoim zadaniem jest wyciągnięcie z niego TYLKO twardych umiejętności, narzędzi, technologii i konkretnych zagadnień matematycznych/analitycznych.
    Zignoruj nazwiska, punkty ECTS, sprawy organizacyjne.
    Zwróć wynik wyłącznie jako czystą listę po przecinku.
    Tekst sylabusa: {text}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Błąd ekstrakcji: {e}"

# ---- NOWA FUNKCJA: Wyodrębnianie ustrukturyzowanych danych z raportu AI ----
def parse_ai_report(ai_content):
    """
    Raport AI kończy się dodatkowym blokiem JSON (###JSON_START###...###JSON_END###)
    z gotowością % i listą braków technologicznych — potrzebnym do zapisu w historii.
    Zwraca (tekst_do_wyswietlenia, readiness_score, missing_skills), gdzie tekst_do_wyswietlenia
    ma już wycięty ten techniczny blok, żeby użytkownik widział tylko czytelną analizę.
    """
    match = re.search(r"###JSON_START###(.*?)###JSON_END###", ai_content, re.DOTALL)
    if not match:
        return ai_content.strip(), None, []

    display_text = ai_content[: match.start()].strip()
    try:
        structured = json.loads(match.group(1).strip())
        readiness_score = structured.get("readiness_score")
        missing_skills = structured.get("missing_skills") or []
        if not isinstance(missing_skills, list):
            missing_skills = []
    except (json.JSONDecodeError, AttributeError):
        readiness_score, missing_skills = None, []

    return display_text, readiness_score, missing_skills

# --- INTERFEJS (FRONT-END) ---
st.title("🎯 Career Pathfinder AI")
st.markdown("Zderz swoją wiedzę ze studiów z realnymi wymaganiami rynku pracy.")

with st.sidebar:
    st.header("⚙️ Ustawienia Analizy")
    stanowisko = st.selectbox(
        "Cel zawodowy:",
        ["Junior Data Analyst", "Data Scientist", "Python Developer", "Business Analyst"]
    )
    
    st.markdown("---")
    st.subheader("📄 Wgraj Sylabusy (PDF)")
    # Odbieramy listę plików
    uploaded_files = st.file_uploader(
        "Przeciągnij karty przedmiotów z uczelni", 
        type="pdf", 
        accept_multiple_files=True
    )
    
    st.markdown("---")
    analizuj_btn = st.button("🚀 Generuj Raport Gotowości", type="primary", use_container_width=True)

# --- GŁÓWNA LOGIKA PO KLIKNIĘCIU ---
if analizuj_btn:
    if not uploaded_files:
        st.error("⚠️ Musisz wgrać przynajmniej jeden plik PDF z sylabusem, aby rozpocząć analizę!")
    else:
        with st.spinner("Czytam pliki PDF i ekstrakcję wiedzy... To może chwilę potrwać."):
            # 1. Wyciągamy surowy tekst z wrzuconych PDF-ów
            raw_text = process_uploaded_pdfs(uploaded_files)
            
            # 2. Filtracja tekstu na czyste skille (Krok 1B)
            uni_skills = extract_skills_with_ai(raw_text)

        with st.spinner(f"Trwa skanowanie rynku i zderzenie kompetencji dla: {stanowisko}..."):
            # 3. Pobranie żywych danych o rynku dla WYBRANEGO stanowiska
            market_data = get_market_requirements(stanowisko)
            
            # 4. Ostateczna analiza (Silnik AI)
            final_prompt = f"""
            Jesteś Senior HR. Rekrutujesz na stanowisko: {stanowisko}.
            Wymagania rynku: {market_data}
            Profil kandydata wyciągnięty z wgranych plików: {uni_skills}
            
            Zrób bezwzględną analizę:
            1. Mocne Strony (co z wymagań ma odhaczone)
            2. Luka (czego kategorycznie brakuje)
            3. Gotowość (np. "Gotowość na 60% - Brakuje kluczowego narzędzia X")
            
            ZASADA: Zawsze pisz w nawiasach procent z wymagań rynku przy każdej umiejętności (np. Power BI (70%)).

            Na SAMYM KOŃCU odpowiedzi, PO całej analizie tekstowej, dodaj DOKŁADNIE jeden
            blok w poniższym formacie (musi być poprawnym JSON-em, bez komentarzy):
            ###JSON_START###
            {{"readiness_score": <liczba_calkowita_0_100>, "missing_skills": ["<technologia_1>", "<technologia_2>"]}}
            ###JSON_END###
            Blok ten musi zawierać WSZYSTKIE kluczowe brakujące technologie wypisane w sekcji "Luka".
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": final_prompt}],
                temperature=0.1 
            )

            # Wyciągamy z odpowiedzi czysty tekst dla użytkownika + dane do historii (po cichu, w tle)
            display_report, readiness_score, missing_skills = parse_ai_report(
                response.choices[0].message.content
            )

            try:
                save_analysis(
                    job_title=stanowisko,
                    readiness_score=readiness_score,
                    gaps=missing_skills,
                )
            except Exception:
                # Historia to funkcja "nice to have" - awaria bazy nie może wywalić raportu użytkownikowi.
                pass
            
            # --- RYSOWANIE WYNIKÓW ---
            st.success("Analiza zakończona! ✅")
            st.markdown(f"### 📊 Raport dla: {stanowisko}")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                st.info(display_report)
            
            with col2:
                st.markdown("### 📈 Wymagania Rynku")
                skills_dict = market_data["required_skills"]
                df = pd.DataFrame({
                    "Technologia": list(skills_dict.keys()),
                    "Wymagane ofert": list(skills_dict.values())
                }).sort_values(by="Wymagane ofert", ascending=True)
                
                fig = px.bar(
                    df, x="Wymagane ofert", y="Technologia", orientation='h',
                    color="Wymagane ofert", color_continuous_scale="Blues",
                    title=f"Top Skille: {stanowisko}"
                )
                fig.update_layout(coloraxis_showscale=False)
                st.plotly_chart(fig, use_container_width=True)
                
                # Opcjonalny przycisk deweloperski do podejrzenia, co wyciągnęliśmy z PDF
                with st.expander("👀 Podejrzyj surowe kompetencje wyciągnięte z Twoich PDF"):
                    st.write(uni_skills)

# --- HISTORIA ANALIZ (sidebar) ---
# Umieszczone na końcu skryptu (mimo że wizualnie renderuje się w sidebarze),
# żeby po kliknięciu "Generuj Raport" od razu pokazywał również najświeższy,
# właśnie zapisany rekord bez potrzeby dodatkowego przeładowania strony.
with st.sidebar:
    st.markdown("---")
    with st.expander("📜 Historia Analiz"):
        history = get_analysis_history()
        if not history:
            st.caption("Brak zapisanych analiz. Wygeneruj pierwszy raport, aby zobaczyć go tutaj!")
        else:
            history_df = pd.DataFrame([
                {
                    "Data": entry["timestamp"].strftime("%Y-%m-%d %H:%M"),
                    "Stanowisko": entry["job_title"],
                    "Gotowość": f"{entry['readiness_score']}%" if entry["readiness_score"] is not None else "—",
                    "Braki technologiczne": ", ".join(entry["gaps"]) if entry["gaps"] else "—",
                }
                for entry in history
            ])
            st.dataframe(history_df, use_container_width=True, hide_index=True)
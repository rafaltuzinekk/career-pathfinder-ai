import streamlit as st
import os
from openai import OpenAI
import pdfplumber
import plotly.express as px
import pandas as pd
from market_scraper import get_market_requirements

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
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": final_prompt}],
                temperature=0.1 
            )
            
            # --- RYSOWANIE WYNIKÓW ---
            st.success("Analiza zakończona! ✅")
            st.markdown(f"### 📊 Raport dla: {stanowisko}")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                st.info(response.choices[0].message.content)
            
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
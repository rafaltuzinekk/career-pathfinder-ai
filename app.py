import streamlit as st
import os
import json
import re
from datetime import date, datetime
from openai import OpenAI
import pdfplumber
import plotly.express as px
import pandas as pd
from market_scraper import get_market_requirements
from database import save_analysis, get_analysis_history, get_latest_gaps

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

# ---- NOWA FUNKCJA: Generator Harmonogramu Nauki ----
def generate_study_plan(job_title, gaps, deadline):
    """
    Prosi AI o rygorystyczny, mierzalny plan nauki, który nadgania podane
    braki technologiczne do wskazanej daty (rozmowa rekrutacyjna / deadline).

    Args:
        job_title: stanowisko, dla którego przygotowywany jest plan (kontekst dla AI).
        gaps: lista brakujących technologii, np. z `database.get_latest_gaps`.
        deadline: obiekt `datetime.date` — docelowa data.

    Returns:
        Czysty tekst w formacie Markdown z planem nauki.

    Raises:
        Exception: błędy komunikacji z OpenAI są przepuszczane dalej, żeby
        wywołujący kod mógł pokazać użytkownikowi przyjazny komunikat.
    """
    days_left = max((deadline - date.today()).days, 0)
    unit = "tygodnie" if days_left > 14 else "dni"

    prompt = f"""
    Jesteś rygorystycznym, doświadczonym mentorem technicznym i coachem kariery IT.
    Kandydat przygotowuje się na stanowisko: {job_title}.
    Brakujące technologie/umiejętności, które MUSI nadgonić (w kolejności z raportu gotowości): {", ".join(gaps)}.
    Ma na to {days_left} dni (deadline: {deadline.strftime('%Y-%m-%d')}).

    Stwórz rygorystyczny, mierzalny plan nauki:
    - Podziel harmonogram na konkretne bloki czasowe ({unit}), pokrywające cały dostępny czas.
    - Każdy blok musi mieć: jasny cel, priorytet (Wysoki / Średni / Niski) oraz konkretne,
      mierzalne zadania (np. "Zbuduj REST API w FastAPI z 3 endpointami i testami jednostkowymi").
    - Uszereguj braki od najbardziej krytycznych do najmniej istotnych.
    - Na końcu dodaj krótką sekcję "Jak zmierzyć postęp" z konkretnymi kryteriami sukcesu.

    Sformatuj odpowiedź jako czysty, profesjonalny Markdown: nagłówki (##), checklisty zadań (- [ ] zadanie),
    wyraźnie oznaczone priorytety. Pisz po polsku. Nie dodawaj żadnego bloku JSON ani komentarzy technicznych.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content

# ---- NOWA FUNKCJA: Renderowanie zapisanego w session_state raportu ----
def render_report_section(data):
    """
    Rysuje wynik analizy (tekst raportu + wykres wymagań rynku) na podstawie
    danych zapisanych w `st.session_state["report_data"]`.

    Wydzielone do osobnej funkcji, żeby ten sam widok mógł być odtworzony
    przy KAŻDYM przeładowaniu skryptu — nie tylko bezpośrednio po kliknięciu
    "Generuj Raport Gotowości" — inaczej raport "gubi się" po interakcji
    z inną częścią UI (np. przyciskiem w zakładce "Zaplanuj Naukę").
    """
    st.success("Analiza zakończona! ✅")
    st.markdown(f"### 📊 Raport dla: {data['stanowisko']}")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.info(data["display_report"])

    with col2:
        st.markdown("### 📈 Wymagania Rynku")
        skills_dict = data["market_data"]["required_skills"]
        df = pd.DataFrame({
            "Technologia": list(skills_dict.keys()),
            "Wymagane ofert": list(skills_dict.values())
        }).sort_values(by="Wymagane ofert", ascending=True)

        fig = px.bar(
            df, x="Wymagane ofert", y="Technologia", orientation='h',
            color="Wymagane ofert", color_continuous_scale="Blues",
            title=f"Top Skille: {data['stanowisko']}"
        )
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

        # Opcjonalny przycisk deweloperski do podejrzenia, co wyciągnęliśmy z PDF
        with st.expander("👀 Podejrzyj surowe kompetencje wyciągnięte z Twoich PDF"):
            st.write(data["uni_skills"])

# ---- NOWE FUNKCJE: Czyszczenie stanu przy zmianie kontekstu analizy ----
def _clear_report_state():
    """
    Usuwa zapisany raport gotowości z session_state.

    Wywoływane, gdy zmieni się coś, co czyni stary raport nieaktualnym
    (np. użytkownik wgrał nowy zestaw plików PDF) — wymusza to ponowne
    kliknięcie "Generuj Raport Gotowości" pod nowe dane wejściowe.
    """
    st.session_state.pop("report_data", None)


def _clear_generated_state():
    """
    Usuwa z session_state ZARÓWNO raport gotowości, JAK i wygenerowany plan
    nauki. Wywoływane przy zmianie wybranego stanowiska w sidebarze — obie
    te rzeczy są przypisane do konkretnej roli, więc po zmianie roli stają
    się nieaktualne i muszą zostać wygenerowane na nowo.
    """
    _clear_report_state()
    st.session_state.pop("study_plan_data", None)

# --- INTERFEJS (FRONT-END) ---
st.title("🎯 Career Pathfinder AI")
st.markdown("Zderz swoją wiedzę ze studiów z realnymi wymaganiami rynku pracy.")

with st.sidebar:
    st.header("⚙️ Ustawienia Analizy")
    stanowisko = st.selectbox(
        "Cel zawodowy:",
        ["Junior Data Analyst", "Data Scientist", "Python Developer", "Business Analyst"],
        key="stanowisko_select",
        # Zmiana roli unieważnia zarówno stary raport, jak i plan nauki (są dla NIEJ policzone) -
        # bez tego użytkownik zobaczyłby "Raport dla: Python Developer" mimo wybrania Data Scientist.
        on_change=_clear_generated_state,
    )
    
    st.markdown("---")
    st.subheader("📄 Wgraj Sylabusy (PDF)")
    # Odbieramy listę plików
    uploaded_files = st.file_uploader(
        "Przeciągnij karty przedmiotów z uczelni", 
        type="pdf", 
        accept_multiple_files=True,
        key="pdf_uploader",
        # Nowy zestaw PDF-ów = nowy profil kandydata, więc stary raport (policzony
        # na podstawie poprzednich plików) trzeba wymusić do przeliczenia.
        on_change=_clear_report_state,
    )
    
    st.markdown("---")
    analizuj_btn = st.button("🚀 Generuj Raport Gotowości", type="primary", use_container_width=True)

# --- ZAKŁADKI GŁÓWNE: Raport Gotowości oraz Generator Harmonogramu Nauki ---
tab_raport, tab_plan = st.tabs(["📊 Raport Gotowości", "🗓️ Zaplanuj Naukę (AI)"])

# --- GŁÓWNA LOGIKA PO KLIKNIĘCIU (RAPORT GOTOWOŚCI) ---
with tab_raport:
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

                # Zapisujemy wynik w session_state (a nie tylko renderujemy "tu i teraz"),
                # żeby raport PRZETRWAŁ kolejne przeładowania skryptu - np. wywołane
                # kliknięciem przycisku w zakładce "Zaplanuj Naukę" (Streamlit odpala
                # skrypt od nowa, a `analizuj_btn` wraca do False, więc bez tego stanu
                # ten blok w ogóle by się nie wykonał i raport zniknąłby z ekranu).
                st.session_state["report_data"] = {
                    "stanowisko": stanowisko,
                    "display_report": display_report,
                    "market_data": market_data,
                    "uni_skills": uni_skills,
                }

    # Renderujemy raport NIEZALEŻNIE od tego, czy przycisk został kliknięty w TYM
    # przebiegu skryptu - liczy się tylko to, czy mamy aktualne dane w session_state
    # (aktualne = wygenerowane dla dokładnie tego stanowiska, które jest teraz wybrane;
    # w przeciwnym razie `_clear_generated_state`/`_clear_report_state` już je usunęły).
    report_data = st.session_state.get("report_data")
    if report_data and report_data["stanowisko"] == stanowisko:
        render_report_section(report_data)
    else:
        st.info("👈 Skonfiguruj analizę w panelu bocznym i kliknij **Generuj Raport Gotowości**, aby zobaczyć wynik tutaj.")

# --- GENERATOR HARMONOGRAMU NAUKI (AI) ---
with tab_plan:
    st.markdown("### 🗓️ Zaplanuj Naukę (AI)")
    st.caption(
        f"Wygeneruj rygorystyczny plan nauki dla stanowiska **{stanowisko}**, oparty na "
        "najnowszym zapisanym raporcie gotowości dla tej roli."
    )

    deadline = st.date_input(
        "Kiedy masz rozmowę rekrutacyjną / deadline?",
        value=date.today(),
        min_value=date.today(),
    )
    plan_btn = st.button("🧭 Wygeneruj Plan Działania", type="primary")

    if plan_btn:
        gaps = get_latest_gaps(stanowisko)

        if not gaps:
            st.warning(
                f"⚠️ Nie znaleziono jeszcze żadnej zapisanej analizy dla stanowiska **{stanowisko}**. "
                "Wygeneruj najpierw **Raport Gotowości** (zakładka po lewej), aby AI wiedziało, czego Ci brakuje."
            )
        else:
            with st.spinner("AI układa Twój harmonogram nauki..."):
                try:
                    study_plan = generate_study_plan(stanowisko, gaps, deadline)
                    # Tak jak w przypadku raportu (patrz `report_data`) - zapisujemy
                    # do session_state, żeby plan nie zniknął po przeładowaniu skryptu
                    # wywołanym np. kliknięciem "Generuj Raport Gotowości" w drugiej zakładce.
                    st.session_state["study_plan_data"] = {
                        "stanowisko": stanowisko,
                        "plan_markdown": study_plan,
                    }
                except Exception as e:
                    st.error(f"❌ Nie udało się wygenerować planu nauki: {e}")

    plan_data = st.session_state.get("study_plan_data")
    if plan_data and plan_data["stanowisko"] == stanowisko:
        st.success("Plan gotowy! ✅")
        st.markdown(plan_data["plan_markdown"])

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
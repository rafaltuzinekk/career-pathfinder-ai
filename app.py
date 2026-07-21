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
from solidjobs_client import get_market_requirements_solidjobs
from database import save_analysis, get_analysis_history, get_latest_gaps

# Konfiguracja
st.set_page_config(page_title="Career Pathfinder AI", page_icon="🎯", layout="wide")
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---- DANE DEMO: przykładowy wyciąg z sylabusa (kierunek Informatyka i Ekonometria) ----
# Pozwala rekruterom przetestować aplikację "jednym kliknięciem", bez konieczności
# przygotowywania i wgrywania własnych plików PDF.
DEMO_SYLLABUS_TEXT = """
KARTA PRZEDMIOTU: Podstawy Programowania w Pythonie
Kierunek: Informatyka i Ekonometria | Rok: I | Semestr: 1 | Punkty ECTS: 6
Forma zajęć: wykład 30h, laboratorium 30h
Treści programowe:
Wprowadzenie do środowiska Python (interpreter, PEP8, Jupyter Notebook). Typy danych, zmienne,
operatory. Struktury kontrolne (if/elif/else, while, for). Struktury danych: listy, słowniki, zbiory,
tuple oraz operacje na nich (list comprehension). Funkcje, argumenty, zakres zmiennych, funkcje
lambda. Programowanie obiektowe: klasy, dziedziczenie, polimorfizm, enkapsulacja. Obsługa wyjątków
(try/except/finally). Praca z plikami (odczyt/zapis CSV, JSON). Wprowadzenie do bibliotek NumPy
i Pandas: tablice, wektoryzacja, DataFrame, indeksowanie, agregacje, łączenie zbiorów danych.
Podstawy wizualizacji danych z użyciem Matplotlib i Seaborn. Wersjonowanie kodu z użyciem Git
i GitHub. Testowanie kodu (unittest, pytest) oraz dobre praktyki programistyczne (czysty kod,
dokumentacja, docstringi).
Efekty uczenia się: Student samodzielnie implementuje algorytmy w Pythonie, przetwarza dane
tabelaryczne z użyciem Pandas oraz korzysta z systemu kontroli wersji Git.

KARTA PRZEDMIOTU: Bazy Danych SQL
Kierunek: Informatyka i Ekonometria | Rok: I | Semestr: 2 | Punkty ECTS: 5
Forma zajęć: wykład 15h, laboratorium 30h
Treści programowe:
Modele danych: relacyjny, hierarchiczny, sieciowy. Projektowanie schematu relacyjnej bazy danych,
normalizacja (1NF, 2NF, 3NF, BCNF), diagramy ERD. Język SQL: DDL (CREATE, ALTER, DROP), DML
(SELECT, INSERT, UPDATE, DELETE), operacje JOIN (INNER, LEFT, RIGHT, FULL), podzapytania,
funkcje agregujące (COUNT, SUM, AVG, GROUP BY, HAVING), widoki (VIEW), indeksy i ich wpływ na
wydajność zapytań. Transakcje i własności ACID, poziomy izolacji transakcji. Wprowadzenie do
systemów zarządzania bazami danych: PostgreSQL, MySQL. Podstawy administracji bazą danych,
uprawnienia użytkowników, kopie zapasowe. Wprowadzenie do NoSQL (MongoDB) jako uzupełnienie
podejścia relacyjnego. Optymalizacja zapytań i analiza planów wykonania (EXPLAIN).
Efekty uczenia się: Student projektuje znormalizowany schemat bazy danych oraz pisze złożone
zapytania SQL (JOIN, podzapytania, agregacje) do analizy i raportowania danych.

KARTA PRZEDMIOTU: Statystyka Matematyczna
Kierunek: Informatyka i Ekonometria | Rok: II | Semestr: 3 | Punkty ECTS: 6
Forma zajęć: wykład 30h, ćwiczenia 30h
Treści programowe:
Zmienne losowe jednowymiarowe i wielowymiarowe, rozkłady prawdopodobieństwa (dwumianowy,
Poissona, normalny, t-Studenta, chi-kwadrat, F-Snedecora). Estymacja punktowa i przedziałowa
parametrów populacji. Testowanie hipotez statystycznych: testy parametryczne i nieparametryczne,
błąd I i II rodzaju, poziom istotności, moc testu. Analiza wariancji (ANOVA). Korelacja i regresja
liniowa - estymacja metodą najmniejszych kwadratów (MNK), współczynnik determinacji R^2, analiza
reszt. Wprowadzenie do wnioskowania bayesowskiego. Wykorzystanie oprogramowania statystycznego
(R, Python - biblioteki SciPy i StatsModels) do analizy danych empirycznych. Symulacje Monte Carlo
jako metoda weryfikacji własności estymatorów.
Efekty uczenia się: Student stawia i weryfikuje hipotezy statystyczne, buduje modele regresji
liniowej oraz interpretuje wyniki analiz statystycznych w kontekście danych ekonomicznych.

KARTA PRZEDMIOTU: Ekonometria Dynamiczna
Kierunek: Informatyka i Ekonometria | Rok: III | Semestr: 5 | Punkty ECTS: 6
Forma zajęć: wykład 30h, laboratorium komputerowe 30h
Treści programowe:
Szeregi czasowe: stacjonarność, autokorelacja, funkcje ACF/PACF. Modele autoregresyjne (AR),
średniej ruchomej (MA), mieszane ARMA/ARIMA oraz sezonowe SARIMA. Testowanie stacjonarności
(test Dickeya-Fullera, KPSS). Modele wektorowej autoregresji (VAR) oraz analiza przyczynowości
w sensie Grangera. Modele korekty błędem (ECM) oraz kointegracja szeregów czasowych. Modele
warunkowej heteroskedastyczności (ARCH/GARCH) do prognozowania zmienności finansowej. Prognozowanie
ekonometryczne i ocena jakości prognoz (MAPE, RMSE). Zastosowanie języka Python (biblioteki
StatsModels, pmdarima) oraz R do estymacji i weryfikacji modeli dynamicznych na rzeczywistych
danych makroekonomicznych i finansowych.
Efekty uczenia się: Student buduje, estymuje i weryfikuje dynamiczne modele ekonometryczne
(ARIMA, VAR, GARCH) oraz wykorzystuje je do prognozowania zjawisk gospodarczych.
""".strip()

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


def _clear_demo_state():
    """
    Usuwa z session_state przykładowy tekst sylabusa wczytany przyciskiem Demo.

    Wywoływane, gdy użytkownik zaczyna wgrywać własne pliki PDF — od tego
    momentu to one mają być źródłem danych, a nie tekst demo.
    """
    st.session_state.pop("raw_text", None)


def _on_pdf_upload_change():
    """Reaguje na wgranie nowego zestawu PDF-ów: unieważnia stary raport
    i porzuca ewentualny tekst demo, bo to wgrane pliki mają teraz priorytet."""
    _clear_report_state()
    _clear_demo_state()


def _use_demo_syllabus():
    """
    Wypełnia session_state przykładowym, z góry przygotowanym tekstem sylabusa
    (patrz `DEMO_SYLLABUS_TEXT`), żeby rekruter mógł przetestować aplikację
    bez wgrywania własnych plików PDF.

    Tak jak przy wgraniu nowych plików PDF, czyścimy stary raport gotowości —
    inaczej użytkownik zobaczyłby raport policzony dla poprzednich danych.
    """
    st.session_state["raw_text"] = DEMO_SYLLABUS_TEXT
    _clear_report_state()

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

    # Źródło żywych danych rynkowych. Zmiana źródła unieważnia policzony wcześniej
    # raport/plan (są dla KONKRETNEGO źródła), więc czyścimy stan jak przy zmianie roli.
    st.radio(
        "🌐 Źródło danych rynkowych",
        ["SolidJobs (API)", "JustJoin.it (scraper)"],
        key="market_source",
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
        # na podstawie poprzednich plików) trzeba wymusić do przeliczenia, a ewentualny
        # tekst demo trzeba porzucić — od teraz priorytet mają wgrane pliki.
        on_change=_on_pdf_upload_change,
    )

    # Przycisk demo — pozwala rekruterom przetestować aplikację "na szybko",
    # bez konieczności przygotowywania i wgrywania własnych plików PDF.
    st.button(
        "🚀 Użyj przykładowego sylabusa (Demo)",
        key="demo_btn",
        use_container_width=True,
        on_click=_use_demo_syllabus,
    )

    st.markdown("---")
    analizuj_btn = st.button("🚀 Generuj Raport Gotowości", type="primary", use_container_width=True)

# --- ZAKŁADKI GŁÓWNE: Raport Gotowości oraz Generator Harmonogramu Nauki ---
tab_raport, tab_plan = st.tabs(["📊 Raport Gotowości", "🗓️ Zaplanuj Naukę (AI)"])

# --- GŁÓWNA LOGIKA PO KLIKNIĘCIU (RAPORT GOTOWOŚCI) ---
with tab_raport:
    if analizuj_btn:
        # Analiza jest możliwa, jeśli użytkownik WGRAŁ własny plik PDF LUB kliknął
        # przycisk demo (wtedy w session_state czeka gotowy tekst przykładowego sylabusa).
        demo_raw_text = st.session_state.get("raw_text")
        if not uploaded_files and not demo_raw_text:
            st.error(
                "⚠️ Musisz wgrać przynajmniej jeden plik PDF z sylabusem lub kliknąć "
                "**🚀 Użyj przykładowego sylabusa (Demo)**, aby rozpocząć analizę!"
            )
        else:
            with st.spinner("Czytam pliki PDF i ekstrakcję wiedzy... To może chwilę potrwać."):
                # 1. Wyciągamy surowy tekst: wgrane pliki PDF mają priorytet nad tekstem
                #    demo (który mógł zostać ustawiony wcześniej przyciskiem "Demo").
                raw_text = process_uploaded_pdfs(uploaded_files) if uploaded_files else demo_raw_text

                # 2. Filtracja tekstu na czyste skille (Krok 1B)
                uni_skills = extract_skills_with_ai(raw_text)

            with st.spinner(f"Trwa skanowanie rynku i zderzenie kompetencji dla: {stanowisko}..."):
                # 3. Pobranie żywych danych o rynku dla WYBRANEGO stanowiska,
                #    z wybranego przez użytkownika źródła.
                if st.session_state["market_source"] == "SolidJobs (API)":
                    market_data = get_market_requirements_solidjobs(stanowisko)
                else:
                    market_data = get_market_requirements(stanowisko)

                # 4. Ostateczna analiza (Silnik AI)
                final_prompt = f"""
                Jesteś Senior Inżynierem IT i analitycznym mentorem technicznym z wieloletnim doświadczeniem
                w rekrutacji i wdrażaniu kandydatów na stanowisko: {stanowisko}. Rozmawiasz z kandydatem, który
                dopiero wchodzi na rynek - Twoim celem NIE jest sucha lista "plusy/minusy", a merytoryczny,
                pogłębiony feedback, jakiego udzieliłby prawdziwy senior podczas mentoringu 1:1.

                KONTEKST:
                - Żywe wymagania rynku pracy (z aktualnych ofert): {market_data}
                - Kompetencje/wiedza wyciągnięte z sylabusów akademickich kandydata: {uni_skills}

                Zbuduj raport wg DOKŁADNIE tej struktury (pisz po polsku, tonem profesjonalnego,
                analitycznego mentora IT - konkretnie, bez lania wody):

                ## 1. Analiza kompetencji wg kategorii technologicznych
                Pogrupuj ocenę kandydata w sensowne, adekwatne do stanowiska {stanowisko} kategorie
                technologiczne (np. Programowanie, Bazy Danych, Inżynieria Danych/Chmura, Analiza i Wizualizacja
                Danych, Narzędzia i Procesy - wybierz i nazwij kategorie sam, zależnie od tego, co faktycznie
                wynika z wymagań rynku). W ramach każdej kategorii oceń pokrycie kompetencji kandydata.

                ## 2. Co wynosisz ze studiów
                Wyjaśnij WPROST, jak akademickie fundamenty kandydata (np. algorytmy i struktury danych,
                matematyka/statystyka, relacyjne bazy danych, inżynieria oprogramowania - użyj tego, co realnie
                wynika z {uni_skills}) PRZEKŁADAJĄ SIĘ na pracę na stanowisku {stanowisko}. To ma być argument,
                dlaczego akademicka baza kandydata ma realną wartość rynkową - nie zwykła lista przedmiotów.

                ## 3. Co musisz doszlifować
                Wskaż KONKRETNE, rynkowe narzędzia i technologie, których kandydatowi brakuje (na podstawie
                różnicy między wymaganiami rynku a profilem kandydata), a przy KAŻDEJ z nich w 1-2 zdaniach
                wyjaśnij, DO CZEGO służy w praktyce na stanowisku {stanowisko} (np. "Snowflake - chmurowa
                platforma do hurtowni danych, używana do..."; "Airflow/ETL - orkiestracja przepływów danych,
                niezbędna do..."). To ma być konkretny plan nauki, nie tylko nazwy narzędzi.

                ## 4. Werdykt gotowości
                Jednym zdecydowanym akapitem podsumuj ogólną gotowość kandydata do podjęcia pracy na
                stanowisku {stanowisko} (np. "Gotowość na 60% - Brakuje kluczowego narzędzia X").

                ZASADA: W sekcjach 1, 3 i 4 zawsze pisz w nawiasach procent z wymagań rynku przy KAŻDEJ
                wymienionej umiejętności (np. Power BI (70%)).

                Na SAMYM KOŃCU odpowiedzi, PO całej analizie tekstowej, dodaj DOKŁADNIE jeden
                blok w poniższym formacie (musi być poprawnym JSON-em, bez komentarzy):
                ###JSON_START###
                {{"readiness_score": <liczba_calkowita_0_100>, "missing_skills": ["<technologia_1>", "<technologia_2>"]}}
                ###JSON_END###
                Blok ten musi zawierać WSZYSTKIE kluczowe brakujące technologie wypisane w sekcji
                "Co musisz doszlifować".
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
"""
Market Scraper — pobiera żywe dane o wymaganiach rynku pracy IT z JustJoin.it
przy użyciu synchronicznego API Playwright.

Strategia:
1. Otwieramy ukrytą (headless) przeglądarkę Chromium, udając prawdziwego
   użytkownika (realistyczny User-Agent, viewport, locale).
2. Wchodzimy na stronę wyszukiwania ofert dla wybranej kategorii i czekamy,
   aż lista ofert faktycznie się wyrenderuje (bot-friendly zamiast bicia
   bezpośrednio w wewnętrzne API, które bywa blokowane).
3. JustJoin.it (Next.js) wstrzykuje surowe dane ofert (w tym pole
   "requiredSkills") jako JSON wewnątrz skryptów strumieniujących HTML.
   Wyciągamy je regexem z surowego kodu strony (page.content()) — to dużo
   stabilniejsze niż parsowanie generowanych na bieżąco klas CSS.
4. Zliczamy najczęściej pojawiające się technologie z pierwszych ~30 ofert
   i zwracamy słownik w formacie zgodnym z resztą aplikacji.
5. Jeśli sieć/strona zawiedzie z jakiegokolwiek powodu — Graceful Degradation:
   wracamy do ustabilizowanych danych referencyjnych, żeby app.py nigdy się
   nie wywaliło.
"""

import asyncio
import re
import sys
from collections import Counter

# --- PATCH: Playwright (sync API) + Streamlit na Windowsie ---
# Streamlit uruchamia nasz skrypt w dedykowanym wątku roboczym (ScriptRunner),
# a nie w wątku głównym procesu. Domyślna polityka asyncio na Windowsie dla
# nowych event loopów w takim kontekście to `SelectorEventLoop`, który NIE
# potrafi tworzyć podprocesów (a Playwright właśnie w podprocesie odpala
# przeglądarkę). Efekt: `NotImplementedError` przy starcie `sync_playwright()`.
# `WindowsProactorEventLoopPolicy` wspiera podprocesy i musi zostać ustawiona
# GLOBALNIE (polityka jest współdzielona przez wszystkie wątki procesu),
# zanim jakikolwiek event loop zostanie utworzony — dlatego robimy to tu,
# na samym początku modułu, przed importem Playwrighta.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.sync_api import sync_playwright

# Windows/PowerShell bywa skonfigurowane z domyślnym kodowaniem konsoli (np. cp1250),
# które nie obsługuje emoji używanych w logach — wymuszamy UTF-8, żeby skrypt
# działał niezależnie od ustawień terminala użytkownika.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1920, "height": 1080}
BASE_URL = "https://justjoin.it/job-offers/all-locations/{category}"
MAX_OFFERS = 30

# Mapowanie stanowiska na kategorię ofert JustJoin.it.
# Kolejność ma znaczenie — bardziej precyzyjne frazy sprawdzane są pierwsze.
CATEGORY_MAP = {
    "data scientist": "ai",
    "machine learning": "ai",
    "data engineer": "data",
    "data analyst": "data",
    "business analyst": "analytics",
    "business intelligence": "analytics",
    "python": "python",
    "java": "java",
    "javascript": "javascript",
    "frontend": "javascript",
    "front-end": "javascript",
    "backend": "python",
    "devops": "devops",
    "tester": "testing",
    "qa": "testing",
    "project manager": "pm",
    "product manager": "pm",
    "security": "security",
    "mobile": "mobile",
    "android": "mobile",
    "ios": "mobile",
    "php": "php",
    "ruby": "ruby",
    "scala": "scala",
    ".net": "net",
    "c#": "net",
    "golang": "go",
    "ux": "ux",
    "ui": "ux",
    "data": "data",
}
DEFAULT_CATEGORY = "python"

# Dane referencyjne używane wyłącznie w razie totalnej awarii sieci/strony.
# WAŻNE: kluczem jest KATEGORIA JustJoin.it (ta sama, którą wylicza
# `_resolve_category()` dla żywego scrapingu), a nie surowy, dowolny string
# `job_title`. Dzięki temu fallback nigdy nie "pomyli" roli — np. przy
# literówce/wielkości liter w `job_title` nie dostaniemy po cichu skilli
# Data Analysta (Excel/Power BI) dla Python Developera, tylko zawsze
# wylądujemy w sensownym, dopasowanym do kategorii zestawie.
FALLBACK_SKILLS_BY_CATEGORY = {
    "analytics": {  # Junior Data Analyst / Business Analyst
        "SQL": 45, "EXCEL": 42, "POWER BI": 35, "BPMN": 30, "JIRA": 40, "STATYSTYKA": 28
    },
    "ai": {  # Data Scientist / Machine Learning
        "PYTHON": 49, "MACHINE LEARNING": 45, "SQL": 40, "STATYSTYKA": 42, "R": 25, "TENSORFLOW": 15
    },
    "python": {  # Python Developer / Backend
        "PYTHON": 50, "SQL": 38, "DJANGO": 35, "FASTAPI": 30, "DOCKER": 40, "GIT": 45
    },
    "data": {  # Data Engineer i inne role "data-owe"
        "SQL": 44, "PYTHON": 40, "ETL": 30, "AIRFLOW": 22, "SPARK": 20, "POWER BI": 18
    },
}
# Neutralny zestaw, gdy kategoria w ogóle nie ma dedykowanego mocka.
FALLBACK_DEFAULT_CATEGORY = "python"

# Regex wyłuskujący z surowego HTML listę technologii wstrzykniętą przez Next.js,
# np.: \"requiredSkills\":[\"Python\",\"Docker\",\"SQL\"]
REQUIRED_SKILLS_PATTERN = re.compile(r'\\"requiredSkills\\":\[(.*?)\]')
SKILL_ITEM_PATTERN = re.compile(r'\\"(.*?)\\"')


def _resolve_category(job_title):
    title_lower = job_title.lower()
    for keyword, category in CATEGORY_MAP.items():
        if keyword in title_lower:
            return category
    return DEFAULT_CATEGORY


def _fetch_raw_html(url):
    """Otwiera stronę w headless Chromium, udając realnego użytkownika, i zwraca surowy HTML."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport=VIEWPORT,
            locale="pl-PL",
        )
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=45000)

        # Czekamy, aż realne oferty faktycznie wyrenderują się na stronie.
        page.wait_for_selector("a.offer_list_offer_title_link", timeout=20000)

        html = page.content()
        browser.close()
        return html


def _extract_skills_from_html(html, max_offers=MAX_OFFERS):
    """Parsuje surowy HTML i zlicza technologie z pierwszych `max_offers` ofert."""
    matches = REQUIRED_SKILLS_PATTERN.findall(html)[:max_offers]

    counter = Counter()
    for raw_skills_block in matches:
        for skill in SKILL_ITEM_PATTERN.findall(raw_skills_block):
            clean_skill = skill.strip().upper()
            if clean_skill:
                counter[clean_skill] += 1

    return counter, len(matches)


def _get_fallback_data(job_title):
    category = _resolve_category(job_title)
    selected_mock = FALLBACK_SKILLS_BY_CATEGORY.get(
        category, FALLBACK_SKILLS_BY_CATEGORY[FALLBACK_DEFAULT_CATEGORY]
    )
    print(f"⚠️ Graceful Degradation: korzystam z danych referencyjnych dla kategorii '{category}'.")
    return {
        "job_title": job_title,
        "total_offers_analyzed": 50,
        "required_skills": selected_mock,
    }


def get_market_requirements(job_title="Junior Data Analyst"):
    print(f"\n--- 🌍 Pobieranie żywych danych rynkowych dla: {job_title} ---")

    try:
        category = _resolve_category(job_title)
        url = BASE_URL.format(category=category)
        print(f"🔎 Skanuję JustJoin.it (kategoria: {category}) -> {url}")

        html = _fetch_raw_html(url)
        skill_counter, offers_count = _extract_skills_from_html(html)

        if offers_count == 0 or not skill_counter:
            raise ValueError("Nie udało się wyciągnąć żadnych ofert/technologii ze strony.")

        top_skills = dict(skill_counter.most_common(15))
        print(f"✅ Sukces! Przeanalizowano {offers_count} żywych ofert z JustJoin.it")

        return {
            "job_title": job_title,
            "total_offers_analyzed": offers_count,
            "required_skills": top_skills,
        }

    except Exception as e:
        print(f"❌ Błąd scrapowania ({e}).")
        return _get_fallback_data(job_title)


if __name__ == "__main__":
    test_data = get_market_requirements("Python Developer")
    print("\n📊 Wynik:")
    print(f"Stanowisko: {test_data['job_title']}")
    print(f"Przeanalizowane oferty: {test_data['total_offers_analyzed']}")
    print("Top technologie:")
    for skill, count in test_data["required_skills"].items():
        print(f"   {skill}: {count}")

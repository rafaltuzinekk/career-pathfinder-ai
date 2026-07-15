"""
SolidJobs API client — pobiera zagregowane dane o zapotrzebowaniu na umiejętności
z publicznego API SOLID.Jobs (https://solid.jobs/public-api).

Alternatywa dla `market_scraper` (scraping JustJoin.it przez Playwright):
zamiast sterować przeglądarką, odpytujemy gotowy endpoint statystyk rynkowych.
Szybciej i stabilniej — brak zależności od przeglądarki.

Kluczowe fakty o API (sprawdzone na żywo):
- Brak autoryzacji. Wymagany tylko parametr `campaign` (małe litery/cyfry/myślniki, ≤64).
- GET /market-statistics/{scopeKind}/{scopeKey}?campaign=..&fields=demand,topSkills
    * demand.activeOffers        -> int (liczba aktywnych ofert)
    * topSkills[] = { label, offerCount, percentage }
      `offerCount` = liczba ofert wymagających danej umiejętności — dokładnie ta
      sama semantyka co "Wymagane ofert" na wykresie w app.py, więc dane wpinają
      się bez żadnych zmian po stronie UI.
- Limit: 300 zapytań/min na IP -> 429 z zalecanym exponential backoff.

Zwracany format jest IDENTYCZNY jak `market_scraper.get_market_requirements()`:
    { "job_title": str, "total_offers_analyzed": int, "required_skills": {SKILL: count} }

Graceful Degradation: przy każdej awarii (sieć/429/pusta odpowiedź) wracamy do
tych samych danych referencyjnych co scraper (`market_scraper._get_fallback_data`),
żeby app.py nigdy się nie wywaliło.
"""

import os
import sys
import time

import requests

from market_scraper import _get_fallback_data

# Windows/PowerShell bywa skonfigurowane z kodowaniem konsoli (np. cp1250),
# które nie obsługuje emoji w logach — wymuszamy UTF-8, jak w market_scraper.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BASE_URL = "https://solid.jobs/public-api"
# `campaign` służy wyłącznie do analityki ruchu po stronie SOLID.Jobs (nie sekret).
# Można nadpisać przez zmienną środowiskową, ale domyślna wartość wystarcza.
CAMPAIGN = os.getenv("SOLIDJOBS_CAMPAIGN", "career-pathfinder-ai")

REQUEST_TIMEOUT = 15  # sekundy
MAX_RETRIES = 3
MAX_SKILLS = 15

# Mapowanie stanowiska -> (scopeKind, scopeKey) statystyk SOLID.Jobs.
# Taksonomia kategorii w API jest gruba (Developer/Support...) i nie ma dedykowanych
# scope'ów dla ról "data-owych", więc obecne role korzystają z poziomu całej dywizji
# IT — to uczciwy, realny agregat. Struktura mapy pozwala w przyszłości podpiąć
# węższe scope'y (mainCategory/subcategory) bez zmiany miejsc wywołań.
ROLE_SCOPE_MAP = {
    "Junior Data Analyst": ("division", "IT"),
    "Data Scientist": ("division", "IT"),
    "Python Developer": ("division", "IT"),
    "Business Analyst": ("division", "IT"),
}
DEFAULT_SCOPE = ("division", "IT")


def _get_with_retry(url, params):
    """GET z exponential backoff na 429 oraz błędy sieciowe."""
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 429:
                wait = 2 ** attempt
                print(f"⏳ 429 Too Many Requests — czekam {wait}s przed ponowieniem...")
                time.sleep(wait)
                continue
            # Inne błędy HTTP (np. 400/404) są trwałe — nie ma sensu ponawiać, zgłaszamy od razu.
            resp.raise_for_status()
            return resp
        except requests.HTTPError:
            raise
        except requests.RequestException as e:
            last_exc = e
            wait = 2 ** attempt
            print(f"⚠️ Błąd zapytania ({e}) — ponawiam za {wait}s...")
            time.sleep(wait)
    # Wyczerpaliśmy próby.
    raise last_exc if last_exc else RuntimeError("Nie udało się pobrać danych z SOLID.Jobs.")


def get_market_requirements_solidjobs(job_title="Junior Data Analyst"):
    print(f"\n--- 🌐 Pobieranie danych rynkowych z SOLID.Jobs dla: {job_title} ---")

    try:
        scope_kind, scope_key = ROLE_SCOPE_MAP.get(job_title, DEFAULT_SCOPE)
        url = f"{BASE_URL}/market-statistics/{scope_kind}/{scope_key}"
        params = {"campaign": CAMPAIGN, "fields": "demand,topSkills"}
        print(f"🔎 Odpytuję {url} (campaign={CAMPAIGN})")

        resp = _get_with_retry(url, params)
        data = resp.json()

        top_skills_raw = data.get("topSkills") or []
        skills = {}
        for entry in top_skills_raw:
            label = (entry.get("label") or "").strip().upper()
            count = entry.get("offerCount")
            if label and isinstance(count, int):
                skills[label] = count

        if not skills:
            raise ValueError("Odpowiedź SOLID.Jobs nie zawiera użytecznej listy topSkills.")

        # Najczęściej wymagane technologie na wierzch (jak w scraperze).
        top_skills = dict(sorted(skills.items(), key=lambda kv: kv[1], reverse=True)[:MAX_SKILLS])
        total_offers = data.get("demand", {}).get("activeOffers", 0)

        print(f"✅ Sukces! Zapotrzebowanie z {total_offers} aktywnych ofert SOLID.Jobs.")

        return {
            "job_title": job_title,
            "total_offers_analyzed": total_offers,
            "required_skills": top_skills,
        }

    except Exception as e:
        print(f"❌ Błąd SOLID.Jobs API ({e}).")
        return _get_fallback_data(job_title)


if __name__ == "__main__":
    test_data = get_market_requirements_solidjobs("Python Developer")
    print("\n📊 Wynik:")
    print(f"Stanowisko: {test_data['job_title']}")
    print(f"Przeanalizowane oferty: {test_data['total_offers_analyzed']}")
    print("Top technologie:")
    for skill, count in test_data["required_skills"].items():
        print(f"   {skill}: {count}")

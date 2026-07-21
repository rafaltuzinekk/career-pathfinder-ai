import os
from dotenv import load_dotenv
from openai import OpenAI
import pdfplumber
from market_scraper import get_market_requirements

# 1. Inicjalizacja
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Foldery/rozszerzenia obsługiwane przez skaner sylabusów demo (patrz `load_demo_syllabuses`).
DEMO_SYLLABI_DIR = "data"
SUPPORTED_SYLLABUS_EXTENSIONS = (".pdf", ".txt")


def load_university_skills():
    try:
        with open("uczelniane_skille.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Brak pliku uczelniane_skille.txt"


def extract_text_from_pdf(file):
    """
    Wyciąga surowy tekst z pliku PDF.

    Args:
        file: ścieżka do pliku na dysku (str) LUB obiekt plikowy/bufor bajtów
            (np. plik wgrany przez `st.file_uploader`). `pdfplumber` obsługuje
            oba przypadki bez rozróżnienia.

    Returns:
        Połączony tekst ze wszystkich stron PDF-a (puste strony są ignorowane).
    """
    pages_text = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                pages_text.append(page_text)
    return "\n".join(pages_text)


def extract_text_from_txt(file):
    """
    Wyciąga surowy tekst z pliku TXT.

    Args:
        file: ścieżka do pliku na dysku (str) LUB obiekt plikowy z metodą `.read()`.

    Returns:
        Zawartość pliku jako czysty tekst (zdekodowana, jeśli podano bajty).
    """
    if hasattr(file, "read"):
        content = file.read()
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="ignore")
        return content

    with open(file, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def load_demo_syllabuses(data_dir=DEMO_SYLLABI_DIR):
    """
    Skanuje folder `data_dir` (domyślnie `data/` w katalogu głównym projektu)
    w poszukiwaniu przykładowych sylabusów (pliki .pdf i .txt) i wyciąga z nich
    surowy tekst za pomocą `extract_text_from_pdf` / `extract_text_from_txt`.

    Używane przez przycisk "Demo" w interfejsie (`app.py`) - pozwala wypróbować
    aplikację bez konieczności wgrywania własnych plików.

    Args:
        data_dir: katalog do przeskanowania (względny do katalogu roboczego,
            czyli głównego katalogu projektu, gdy odpalane jest `app.py`).

    Returns:
        Połączony surowy tekst z wszystkich rozpoznanych plików (posortowanych
        alfabetycznie po nazwie, dla stabilnego, deterministycznego wyniku).
        Zwraca pusty string, jeśli folder nie istnieje lub nie zawiera żadnych
        wspieranych plików - błędy pojedynczych plików są po cichu ignorowane,
        żeby jeden uszkodzony PDF nie wywalił całego demo.
    """
    if not os.path.isdir(data_dir):
        return ""

    extractors = {
        ".pdf": extract_text_from_pdf,
        ".txt": extract_text_from_txt,
    }

    all_text = []
    for filename in sorted(os.listdir(data_dir)):
        ext = os.path.splitext(filename)[1].lower()
        extractor = extractors.get(ext)
        if extractor is None:
            continue

        file_path = os.path.join(data_dir, filename)
        try:
            text = extractor(file_path)
        except Exception:
            continue

        if text:
            all_text.append(text)

    return "\n".join(all_text)

def analyze_gap(uni_skills, market_data):
    print("--- 🧠 Uruchamiam Silnik AI (Obliczanie luki kompetencyjnej) ---")
    
    prompt = f"""
    Jesteś Senior Data Analystem w dużym banku. Rekrutujesz na staże i stanowiska juniorskie.
    Masz przed sobą profil studenta (zestawienie tego, czego nauczył się na uczelni na kierunku Informatyka i Ekonometria) oraz listę naszych obecnych, twardych wymagań rynkowych.
    
    Wymagania rynku (Top Skille dla Data Analyst):
    {market_data}
    
    Profil Studenta (umiejętności z sylabusów):
    {uni_skills}
    
    Zrób bezwzględną, profesjonalną analizę. Zwróć wynik z następującym podziałem:
    1. Gotowość Rynkowa (Ready Score): Oceń w skali 0-100%, na ile program studiów pokrywa się z wymaganiami rynku.
    2. Mocne Strony: Które z rynkowych wymagań student już ma odhaczone dzięki uczelni? (Sprawdzaj semantycznie, np. "relacyjny model danych" to SQL).
    3. Luka Kompetencyjna (Red Flags): Czego z wymagań rynkowych całkowicie brakuje w jego toku nauczania? Czego musi się natychmiast douczyć sam, żeby dostać pracę?
    
    Bądź konkretny, zwięzły i brutalnie szczery. Używaj wypunktowań.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Błąd OpenAI API: {e}"

# 2. Odpalenie całego procesu
if __name__ == "__main__":
    uni_skills = load_university_skills()
    market_data = get_market_requirements()
    
    if "Brak pliku" in uni_skills:
        print("❌ BŁĄD: Musisz najpierw uruchomić main.py, aby wygenerować skille uczelniane.")
    else:
        final_report = analyze_gap(uni_skills, market_data)
        
        print("\n" + "="*70)
        print("🎯 RAPORT: ANALIZA LUKI KOMPETENCYJNEJ")
        print("="*70)
        print(final_report)
        print("="*70)
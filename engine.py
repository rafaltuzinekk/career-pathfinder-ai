import os
from dotenv import load_dotenv
from openai import OpenAI
from market_scraper import get_market_requirements

# 1. Inicjalizacja
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def load_university_skills():
    try:
        with open("uczelniane_skille.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Brak pliku uczelniane_skille.txt"

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
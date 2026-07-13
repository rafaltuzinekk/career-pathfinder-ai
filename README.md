# 🎯 Career Pathfinder AI

> Krótkie, chwytliwe zdanie o projekcie (np. AI-powered system that bridges the gap between university syllabuses and real-time IT job market requirements).

## 🚀 O projekcie
Napisz tutaj 2-3 zdania od siebie. Dlaczego to stworzyłeś? Jaki problem to rozwiązuje? (np. że rynek IT zmienia się tak szybko, że uczelnie nie nadążają, a to narzędzie pozwala kandydatom dokładnie namierzyć ich braki technologiczne).

## ✨ Główne funkcjonalności
* **Live Market Scraping:** (opisz krótko, że pobierasz dane na żywo przez Playwright)
* **AI Readiness Analysis:** (że model LLM czyta PDF-y i wyciąga kompetencje)
* **Smart Study Planner:** (o tym, że generujesz konkretne, rozłożone w czasie plany nauki)
* **Persistence Memory:** (że trzymasz historię wyników w lokalnej bazie SQLite)

## 🛠️ Tech Stack
* **Język:** Python
* **Frontend:** Streamlit
* **Baza Danych:** SQLite & SQLAlchemy
* **Skrobanie Danych:** Playwright, BeautifulSoup
* **AI & LLM:** OpenAI API
* **Analiza PDF:** pdfplumber

## 💻 Jak uruchomić projekt lokalnie
1. Sklonuj repozytorium.
2. Utwórz wirtualne środowisko (`python -m venv venv`) i aktywuj je.
3. Zainstaluj zależności (jeśli dorobimy plik `requirements.txt`).
4. Dodaj plik `.env` z kluczem `OPENAI_API_KEY`.
5. Uruchom: `streamlit run app.py`

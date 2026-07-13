import os
from dotenv import load_dotenv
import pdfplumber
from openai import OpenAI

# 1. Inicjalizacja środowiska i AI
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("❌ BŁĄD: Nie znaleziono klucza API w pliku .env!")
    exit()

client = OpenAI(api_key=api_key)
data_folder = "data"

def extract_text_from_pdf(file_path):
    extracted_text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
        return extracted_text
    except Exception as e:
        print(f"❌ Błąd odczytu {file_path}: {e}")
        return ""

def extract_skills_with_ai(text, subject_name):
    prompt = f"""
    Jesteś ekspertem HR i analitykiem danych. Poniżej znajduje się surowy tekst z sylabusa uniwersyteckiego.
    Twoim zadaniem jest wyciągnięcie z niego TYLKO twardych umiejętności, narzędzi, technologii i konkretnych zagadnień matematycznych/analitycznych.
    Zignoruj nazwiska, punkty ECTS, sprawy organizacyjne i ogólnikowe "lanie wody".
    Zwróć wynik jako czystą listę po przecinku.
    
    Tekst sylabusa:
    {text}
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

# 2. Główny silnik masowej ekstrakcji
if __name__ == "__main__":
    print("🚀 Startujemy masową ekstrakcję sylabusów...\n")
    
    all_skills = []
    
    # Zabezpieczenie przed brakiem folderu
    if not os.path.exists(data_folder):
        print(f"❌ BŁĄD: Folder '{data_folder}' nie istnieje!")
        exit()
        
    # Szukamy tylko plików PDF
    pdf_files = [f for f in os.listdir(data_folder) if f.endswith('.pdf')]
    
    if not pdf_files:
        print(f"❌ BŁĄD: Brak plików PDF w folderze '{data_folder}'!")
        exit()
        
    # Przechodzimy przez każdy znaleziony plik
    for filename in pdf_files:
        file_path = os.path.join(data_folder, filename)
        print(f"📄 Przetwarzam: {filename}...")
        
        # Krok A: Czytanie PDF
        raw_text = extract_text_from_pdf(file_path)
        
        if raw_text.strip():
            # Krok B: Analiza AI
            skills = extract_skills_with_ai(raw_text, filename)
            # Formatujemy ładny blok tekstu dla danego przedmiotu
            all_skills.append(f"[{filename}]:\n{skills}\n\n")
            print(f"✅ Ukończono analizę dla: {filename}\n")
        else:
            print(f"⚠️ Uwaga: Plik {filename} jest pusty lub nie udało się odczytać tekstu.\n")
            
    # Krok C: Zapisanie wyników do pliku na dysku
    output_file = "uczelniane_skille.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(all_skills)
        
    print("=" * 60)
    print("🏆 ETAP 1 W PEŁNI ZAKOŃCZONY!")
    print(f"💾 Wszystkie wyekstrahowane kompetencje zapisano w: {output_file}")
    print("=" * 60)
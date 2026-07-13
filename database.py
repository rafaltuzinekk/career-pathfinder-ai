"""
Warstwa pamięci (SQLite + SQLAlchemy) dla Career Pathfinder AI.

Fundament pod przyszły system generowania harmonogramów nauki: każda
wygenerowana analiza (stanowisko, % gotowości, braki technologiczne) jest
zapisywana do lokalnej bazy `career_pathfinder.db`, żeby można było później
śledzić postępy użytkownika w czasie.
"""

import json
import sys
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Wymuszamy UTF-8 w konsoli, żeby logi z emoji działały niezależnie od
# domyślnego codepage'a terminala Windows (np. cp1250).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

DATABASE_FILE = "career_pathfinder.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

# `check_same_thread=False` jest wymagane dla SQLite, bo Streamlit potrafi
# odpalać skrypt w innym wątku niż ten, w którym powstał silnik bazy.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class AnalysisHistory(Base):
    """Jeden zapisany wynik analizy gotowości do konkretnego stanowiska."""

    __tablename__ = "analysis_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_title = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.now, nullable=False)
    readiness_score = Column(Integer, nullable=True)
    # Lista brakujących technologii przechowywana jako tekst JSON (np. '["Docker", "SQL"]').
    gaps_json = Column(Text, nullable=False, default="[]")


def init_db():
    """Tworzy plik bazy i tabele, jeśli jeszcze nie istnieją. Bezpieczne do wielokrotnego wywołania."""
    Base.metadata.create_all(bind=engine)


def save_analysis(job_title, readiness_score, gaps):
    """
    Zapisuje wynik jednej analizy do bazy.

    Args:
        job_title: nazwa stanowiska, dla którego wygenerowano raport.
        readiness_score: liczba 0-100 (procent gotowości) albo None, jeśli nie udało się jej wyliczyć.
        gaps: lista stringów z brakującymi technologiami (zostanie zserializowana do JSON).

    Returns:
        id nowo utworzonego rekordu.
    """
    if gaps is None:
        gaps = []

    session = SessionLocal()
    try:
        record = AnalysisHistory(
            job_title=job_title,
            timestamp=datetime.now(),
            readiness_score=readiness_score,
            gaps_json=json.dumps(gaps, ensure_ascii=False),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record.id
    finally:
        session.close()


def get_analysis_history(limit=50):
    """
    Odczytuje historię analiz z bazy (najnowsze pierwsze).

    Returns:
        Lista słowników: {"id", "job_title", "timestamp", "readiness_score", "gaps"},
        gdzie "gaps" jest już rozparsowaną listą Pythona (nie surowym JSON-em).
    """
    session = SessionLocal()
    try:
        records = (
            session.query(AnalysisHistory)
            .order_by(AnalysisHistory.timestamp.desc())
            .limit(limit)
            .all()
        )

        history = []
        for record in records:
            try:
                gaps = json.loads(record.gaps_json) if record.gaps_json else []
            except (json.JSONDecodeError, TypeError):
                gaps = []

            history.append(
                {
                    "id": record.id,
                    "job_title": record.job_title,
                    "timestamp": record.timestamp,
                    "readiness_score": record.readiness_score,
                    "gaps": gaps,
                }
            )
        return history
    finally:
        session.close()


# Tabela musi istnieć zanim ktokolwiek zaimportuje ten moduł i zacznie zapisywać/czytać.
init_db()


if __name__ == "__main__":
    print(f"--- 🗄️ Test warstwy pamięci: {DATABASE_FILE} ---")

    new_id = save_analysis(
        job_title="Python Developer",
        readiness_score=72,
        gaps=["Docker", "Kubernetes", "FastAPI"],
    )
    print(f"✅ Zapisano testowy rekord o id={new_id}")

    history = get_analysis_history()
    print(f"📜 Historia zawiera {len(history)} rekord(ów):")
    for entry in history:
        print(f"   [{entry['id']}] {entry['timestamp']} | {entry['job_title']} | "
              f"{entry['readiness_score']}% | braki: {entry['gaps']}")

# AGENTS.md

## Cursor Cloud specific instructions

Career Pathfinder AI is a single-service Python **Streamlit** web app (`app.py`). There is no
separate frontend/backend, no Docker, and no automated test suite. Supporting modules:
`database.py` (SQLite persistence, auto-creates `career_pathfinder.db` on import), `solidjobs_client.py`
(SOLID.Jobs public API — no auth), `market_scraper.py` (JustJoin.it scraper via Playwright Chromium),
and CLI batch scripts `main.py` / `engine.py`.

### Environment / running

- Dependencies are installed into a project virtualenv at `.venv` by the startup update script.
  Activate it (`source .venv/bin/activate`) or call binaries directly (`.venv/bin/python`,
  `.venv/bin/streamlit`) — the system Python is externally managed (PEP 668) and cannot install packages directly.
- Run the app: `.venv/bin/streamlit run app.py --server.headless true --server.port 8501` (serves on `http://localhost:8501`).

### Critical gotcha: OPENAI_API_KEY is required to even load the UI

- `app.py` constructs `OpenAI(api_key=os.getenv("OPENAI_API_KEY"))` at module import time (top level),
  so **without `OPENAI_API_KEY` the app crashes immediately with `openai.OpenAIError` and renders no UI at all** —
  not just the AI features. This key must be present in the environment (or a `.env` file, loaded via `python-dotenv`)
  before Streamlit is started. All core actions (PDF skill extraction, readiness report, study plan) call OpenAI (`gpt-4o-mini`).

### Market data & Playwright

- Market data has two sources selectable in the sidebar: **SolidJobs (API)** (default, no auth, works out of the box)
  and **JustJoin.it (scraper)** (needs Playwright Chromium, installed by the update script). Both degrade gracefully to
  hardcoded fallback skills on network failure, so the app never hard-fails on market data.

### Smoke tests (no OpenAI needed)

- `.venv/bin/python database.py` — SQLite read/write smoke test.
- `.venv/bin/python solidjobs_client.py` — SolidJobs API smoke test (live network).
- `.venv/bin/python market_scraper.py` — JustJoin.it Playwright scraper smoke test (live network).

There is no lint config and no unit/integration test framework in this repo.

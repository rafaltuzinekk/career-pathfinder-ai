# 🎯 Career Pathfinder AI

> An AI-powered system that bridges the gap between rigorous university syllabuses and real-time IT job market requirements.

## 🚀 The Motivation
With a strong academic background in Computer Science and Econometrics, I realized there is often a disconnect between theoretical university coursework (e.g., advanced mathematics, statistics, relational database theory) and the specific, fast-changing tech stacks demanded by the job market. 

**Career Pathfinder AI** solves this by analyzing real university syllabuses (PDFs), scraping current job postings, and using Large Language Models to generate actionable, personalized study roadmaps.

## ✨ Core Features
* **📡 Live Market Scraping:** Utilizes Playwright to dynamically scrape and aggregate real-time skill requirements from IT job boards.
* **🧠 AI Readiness Analysis:** Extracts raw academic competencies from uploaded PDF syllabuses (using `pdfplumber`) and maps them against market data via OpenAI's structured extraction.
* **📅 Actionable AI Study Planner:** Transforms identified skill gaps into rigorous, deadline-driven study schedules formatted as daily/weekly tasks.
* **💾 Persistence Memory:** Silently logs analysis history and skill gaps using SQLite, allowing users to track their learning progress over time.
* **⚡ Seamless State Management:** Implements robust `st.session_state` logic in Streamlit to prevent UI "amnesia" and ensure smooth navigation between reports and study planners.

## 🏗️ Architecture & Flow
1. **Data Ingestion:** User uploads academic PDFs. The system extracts text and identifies core academic fundamentals.
2. **Market Aggregation:** A headless browser scrapes current tech requirements for the selected role.
3. **AI Processing:** OpenAI compares the academic baseline with market demands, categorizing skills and identifying concrete gaps.
4. **Actionable Output:** The system saves the state to SQLite and generates a customized, deadline-oriented learning schedule.

## 🛠️ Tech Stack
* **Language:** Python 3
* **Frontend:** Streamlit
* **Database:** SQLite & SQLAlchemy
* **Web Scraping:** Playwright, BeautifulSoup4
* **AI & NLP:** OpenAI API (GPT models)
* **Data Processing:** Pandas, pdfplumber

## 🚧 Engineering Challenges Overcome
* **Dirty Data & Category Mapping Anomalies:** Encountered an issue where Business Analysis tools (like UML/BPMN) were polluting Data Analyst tech stacks due to broad job board categorization. Solved by implementing a strict, hardcoded routing dictionary that isolates core data engineering roles from business-centric roles.
* **Streamlit Lifecycle Amnesia:** Streamlit's default behavior resets variables upon button clicks, causing generated AI reports to disappear when switching tabs. Solved by engineering a persistent `session_state` caching mechanism with strict `on_change` callbacks for context clearing.

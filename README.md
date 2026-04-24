<div align="center">

# 🎯 JobCopilot AI

**An intelligent Chrome extension that acts as your personal career agent — analyzing job postings in real time using a multi-step AI reasoning loop.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Gemini](https://img.shields.io/badge/Gemini-API-4285F4?style=flat&logo=google&logoColor=white)](https://aistudio.google.com)
[![Chrome MV3](https://img.shields.io/badge/Chrome-Extension%20MV3-4CAF50?style=flat&logo=googlechrome&logoColor=white)](https://developer.chrome.com/docs/extensions/mv3/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 📺 Demo

> **▶ [Watch on YouTube — Full Walkthrough](https://youtube.com/your-link-here)**  
> *(Replace this link with your video URL)*

---

## What Is It?

JobCopilot AI is a Chrome side-panel extension backed by a FastAPI server. When you open a job listing — on LinkedIn, Indeed, Remotive, or any other site — the extension automatically extracts the job details and passes them to an AI agent that:

1. **Scores your fit** using a dedicated Gemini call (not keyword matching)
2. **Researches the company** via Wikipedia + DuckDuckGo
3. **Benchmarks salary** from live job listings + curated 2024 data
4. **Checks visa sponsorship** from public registers and curated databases
5. **Generates tailored output** — rewritten resume bullets, cover letter points, and reverse-interview questions

Every step of the reasoning process is visible in real time in the UI.

---

## ✨ Key Features

| Feature | Detail |
|---------|--------|
| 🧠 **Multi-step Agent Loop** | Follows the llm-tool-llm pattern — each LLM call receives the full accumulated history |
| 📡 **Live Reasoning Chain** | Shows every LLM call, raw output, tool call, and tool result as it happens |
| 📄 **LLM Resume Parser** | PDF text extracted by PyMuPDF, structured by Gemini — no regex rules |
| 🔍 **Real Job Search** | Arbeitnow API (on-site/hybrid) + Remotive API (remote) — completely free, no key needed |
| 📊 **Fit Scorecard** | Scored by Gemini with per-dimension breakdown: skills, experience, education, preferences |
| 💰 **Salary Benchmark** | Aggregated from live Remotive listings, falls back to curated 2024 dataset |
| 🛂 **Visa Checker** | UK gov.uk Tier-2 register + curated EU sponsorship database |
| 🤖 **Model Selector** | Choose any Gemini model from the UI — propagates to every LLM call in the system |
| 🌙 **Dark Glassmorphism UI** | Professional dark design with purple accent, animated score ring, collapsible results |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                Chrome Extension (MV3)                    │
│                                                          │
│  content.js       ← injected into every job page        │
│    └─ extracts title, company, location, description     │
│                                                          │
│  background.js    ← service worker                       │
│    └─ relays page context via chrome.storage.session     │
│                                                          │
│  sidepanel.html / css / js                               │
│    ├── Profile tab  — resume, GitHub, prefs, model       │
│    ├── Analyze tab  — live SSE reasoning chain           │
│    └── Dashboard tab — scores, salary, visa, bullets     │
└──────────────────────────┬──────────────────────────────┘
                           │  HTTP (REST + SSE)
                           ▼
┌─────────────────────────────────────────────────────────┐
│               FastAPI Backend (Python)                   │
│                                                          │
│  main.py                                                 │
│    ├── POST /profile/resume  → LLM resume parser         │
│    ├── POST /profile/github  → GitHub REST API           │
│    ├── PUT  /profile/prefs   → model + preferences       │
│    └── POST /analyze         → SSE agent stream          │
│                                                          │
│  agent.py  (reference.py multi-step loop)                │
│    Query → LLM → Tool → Result → Query → LLM → Answer   │
│    Emits: llm_call, llm_output, tool_call,               │
│           tool_result, answer, error                     │
│                                                          │
│  tools/                                                  │
│    ├── job_search.py       Arbeitnow + Remotive APIs     │
│    ├── github_parser.py    GitHub REST API               │
│    ├── company_insights.py Wikipedia + DuckDuckGo        │
│    ├── salary_data.py      Live listings + benchmarks    │
│    ├── visa_checker.py     UK gov.uk + EU database       │
│    ├── fit_scorer.py       Gemini LLM (nested call)      │
│    └── resume_parser.py    Gemini LLM (at upload time)   │
└─────────────────────────────────────────────────────────┘
```

---

## 🤖 Agent Loop

The agent follows the exact pattern from `reference.py` — every iteration accumulates **all past messages** in the prompt:

```
Iteration 1:  Prompt = [System + User(job + profile)]
              → 🧠 LLM call
              → 📤 LLM output: {"tool_name": "analyze_job_fit", ...}
              → 🔧 Tool call  → Gemini scores fit internally
              → 📊 Tool result appended to history

Iteration 2:  Prompt = [System + User + Asst + Tool Result]
              → 🧠 LLM call
              → 📤 LLM output: {"tool_name": "get_company_insights", ...}
              → 🔧 Tool call  → Wikipedia + DuckDuckGo
              → 📊 Tool result appended to history

...

Iteration N:  Prompt = [all history]
              → 🧠 LLM call
              → 📤 LLM output: {"answer": "...", "dashboard": {...}}
              → ✅ Final answer — UI switches to Dashboard
```

---

## 🛠️ Tools

| # | Function | Data Source | Notes |
|---|----------|-------------|-------|
| 1 | `search_jobs(role, location, level)` | Arbeitnow + Remotive APIs | Free, no API key |
| 2 | `fetch_github_repos(github_url)` | GitHub REST API | Public repos, no key |
| 3 | `get_company_insights(company)` | Wikipedia REST + DuckDuckGo | Free |
| 4 | `get_salary_benchmark(role, location)` | Remotive live + 2024 benchmarks | Aggregated |
| 5 | `check_visa_sponsorship(company, country)` | UK gov.uk + EU curated data | Static + live |
| 6 | `analyze_job_fit(jd, profile, prefs)` | **Gemini LLM (nested call)** | LLM-scored, not regex |


---

## ⚙️ Setup

### Prerequisites
- Python 3.10+
- Google Chrome
- A [Gemini API key](https://aistudio.google.com) (free tier works)

### 1. Clone & configure

```bash
git clone https://github.com/your-username/job-copilot.git
cd job-copilot

cp backend/.env.example backend/.env
# Open backend/.env and add your GEMINI_API_KEY
```

### 2. Start the backend

```bash
cd backend
pip install -r requirements.txt
python main.py
# → Server running at http://localhost:8000
```

### 3. Load the Chrome extension

1. Open `chrome://extensions` in Chrome
2. Enable **Developer mode** (toggle, top-right)
3. Click **Load unpacked** → select the `extension/` folder
4. The 🎯 icon appears in your toolbar — click it to open the side panel

### 4. Use it

1. **Profile tab** → upload your resume PDF, add your GitHub URL, write your job preferences, select a Gemini model
2. **Open a job page** → navigate to any job listing (LinkedIn, Indeed, Remotive, etc.)
3. **Analyze tab** → the job is auto-detected; click **⚡ Run Analysis**
4. Watch the reasoning chain stream in real time
5. **Dashboard tab** → review your fit score, salary benchmark, visa status, and tailored content

---

## 📁 Project Structure

```
job-copilot/
├── extension/
│   ├── manifest.json         Chrome MV3 manifest
│   ├── background.js         Service worker
│   ├── content.js            Auto job extractor (injected into pages)
│   ├── sidepanel.html        3-tab UI
│   ├── sidepanel.css         Dark glassmorphism styles
│   ├── sidepanel.js          UI logic, SSE consumer, dashboard renderer
│   ├── create_icons.py       Icon generator (pure Python, no deps)
│   └── icons/                Generated PNG icons (16, 48, 128px)
│
└── backend/
    ├── main.py               FastAPI app — routes + SSE stream
    ├── agent.py              Multi-step agent loop
    ├── requirements.txt
    ├── .env.example
    └── tools/
        ├── __init__.py       TOOLS registry + sync_model()
        ├── job_search.py     Arbeitnow + Remotive
        ├── github_parser.py  GitHub API
        ├── company_insights.py
        ├── salary_data.py
        ├── visa_checker.py
        ├── fit_scorer.py     LLM-powered scoring
        └── resume_parser.py  LLM-powered PDF parsing
```


---

## 🧩 How Resume Parsing Works

When you upload a PDF:
1. **PyMuPDF** extracts the raw text from every page
2. The raw text is sent to **Gemini** with a structured extraction prompt
3. Gemini returns a JSON object: name, email, education list, experience list, skills array, GitHub URL, professional summary
4. This structured data is stored in the backend session and injected into every agent prompt — the agent never needs to call a parse tool

---

## 📄 License

MIT — see [LICENSE](LICENSE).

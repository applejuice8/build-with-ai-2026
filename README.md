# 🎯 AI Job Hunter Pipeline

> A multi-agent AI pipeline that scouts live job boards, analyses your CV against real job descriptions, and drafts a hyper-personalised cold outreach email — all from a single command.

Built with **Google ADK**, **Gemini 2.5 Flash**, and **RapidAPI Jobs Search**. Designed for the Gemini CLI hackathon.

---

## The Problem

Senior tech professionals spend 20–30 minutes per job manually crafting personalised outreach to hiring managers — the highest-ROI interview strategy. Most skip it entirely. This pipeline does it in seconds.

---

## Architecture

Three AI agents run in sequence, each handing off context to the next via ADK session state.

```
User Input (CLI)
      │
      ▼
┌─────────────────┐
│  Scout Agent    │  ← Calls RapidAPI (LinkedIn, Indeed, Glassdoor)
│                 │    Extracts top 3 live job listings
└────────┬────────┘
         │ found_job_data
         ▼
┌─────────────────┐
│Strategist Agent │  ← Picks best-fit job against your CV
│                 │    Writes a 2-sentence strategic "Hook"
└────────┬────────┘
         │ candidate_hook
         ▼
┌─────────────────┐
│Copywriter Agent │  ← Drafts cold outreach email
│                 │    Subject line + 4 sentences + CTA
└────────┬────────┘
         │
         ▼
  Terminal output
  + saved .txt file
```

### Flow: `SequentialAgent`

A `SequentialAgent` is used because the data dependency is strictly linear — the Strategist cannot run until the Scout has found a job, and the Copywriter cannot run until the Strategist has produced a Hook. ADK's native `output_key` and `{{templating}}` handle state passing between agents with no manual JSON parsing.

---

## Tech Stack

| Component | Technology |
|---|---|
| Agent Framework | Google ADK (`google-adk`) |
| LLM | Gemini 2.5 Flash |
| Job Data | RapidAPI Jobs Search API |
| Sources | LinkedIn, Indeed, Glassdoor |
| Auth | `.env` / Google Cloud ADC |
| CLI | `argparse` — Gemini CLI friendly |
| Output | Timestamped `.txt` file |
| Language | Python 3.12+ |

---

## Project Structure

```
job-hunter/
├── main.py          # Full pipeline — agents, tool, CLI entrypoint
├── .env             # API keys (never commit this)
├── requirements.txt # Python dependencies
├── outputs/         # Generated outreach files saved here
└── README.md
```

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/applejuice8/build-with-ai-2026.git
cd job-hunter
pip install -r requirements.txt
```

### 2. Set API keys

Create a `.env` file:

```env
GOOGLE_API_KEY=your_gemini_api_key_here
RAPIDAPI_KEY=your_rapidapi_key_here
```

Get your keys:
- Gemini API key → [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- RapidAPI key → [rapidapi.com](https://rapidapi.com) (search "Jobs Search API")

---

## Usage

### Run directly

```bash
python main.py \
  --cv "7 years Fintech Delivery Lead, MSc Information Management KU Leuven" \
  --role "Senior Product Manager" \
  --location "Berlin"
```

### All flags

| Flag | Required | Description | Example |
|---|---|---|---|
| `--cv` | ✅ | Your CV summary | `"7 yrs Fintech PM, MSc KU Leuven"` |
| `--role` | ✅ | Target job title | `"Senior Product Manager"` |
| `--location` | ✅ | City or country | `"Berlin"` or `"Germany"` |
| `--output` | ❌ | Output folder (default: `./outputs`) | `"./my_results"` |

### Supported locations

The pipeline resolves plain-text locations to the correct country code for the job API automatically.

```
Germany / Berlin → DE       Netherlands / Amsterdam → NL
UK / London      → UK       France / Paris          → FR
Ireland / Dublin → IE       Belgium / Brussels      → BE
Spain            → ES       Portugal / Lisbon       → PT
Sweden           → SE       Denmark                 → DK
Switzerland      → CH       Austria                 → AT
Italy            → IT       Poland                  → PL
Malaysia         → MY       Singapore               → SG
Australia        → AU       USA / United States     → USA
Canada           → CA
```

---

## Call it from Gemini CLI

Add to `~/.gemini/settings.json`:

```json
{
  "systemPrompt": "You have access to a job hunting tool. When the user asks to find a job or draft outreach, run this command in your shell: python /full/path/to/main.py --cv \"<cv>\" --role \"<role>\" --location \"<location>\". Fill in the blanks from what the user tells you.",
  "tools": ["shell"]
}
```

Then:

```bash
gemini
```

```
> use my main.py to find a job. cv: 7 years fintech delivery lead. role: senior PM. location: berlin
```

Gemini reads the system prompt, fills in the args, and runs your pipeline automatically.

---

## Output

### Terminal

```
🚀 Job Hunter Pipeline — Gemini + ADK
============================================================
📄 CV       : 7 years Fintech Delivery Lead, MSc KU Leuven
🎯 Role     : Senior Product Manager
📍 Location : Berlin (DE)
============================================================

🔍 Scanning live job boards...
✍️  Agents working...

[ SYSTEM: search_jobs | query='Product Manager Fintech' | location='Berlin' | country='DE' ]
[ SYSTEM: Found 3 job(s) ]

✅ FINAL OUTREACH DRAFT:

Subject: Fintech Delivery Experience for Your PM Role at [Company]

Hi [Company] Team,
Your Product Manager role caught my attention — specifically the challenge of [core problem].
With 7 years leading fintech delivery at scale and an MSc in Information Management, I have driven exactly this kind of cross-functional execution before.
Open to a 20-min call?

============================================================
💾 Saved to: ./outputs/job_outreach_20250115_143207.txt
============================================================
```

### Saved file (`outputs/job_outreach_YYYYMMDD_HHMMSS.txt`)

```
JOB HUNTER PIPELINE — OUTPUT
Generated : 2025-01-15 14:32:07
============================================================

INPUT
-----
CV       : 7 years Fintech Delivery Lead, MSc KU Leuven
Role     : Senior Product Manager
Location : Berlin (DE)

============================================================

OUTREACH EMAIL DRAFT
--------------------
Subject: ...

Hi [Company] Team,
...

============================================================
```

Each run creates a new timestamped file — previous results are never overwritten.

---

## How the Agents Work

### Agent 1 — The Scout
- Strips noise from the user's input down to a clean 4-word search query
- Calls the RapidAPI Jobs Search endpoint **once** (no retries)
- Returns the top 3 matching jobs with company, role, location, description, and URL

### Agent 2 — The Strategist
- Reads the 3 job listings and the candidate's CV from session state
- Picks the single best-fit role
- Produces a 2-sentence Hook: the strongest intersection between the candidate's skills and the job's core problem

### Agent 3 — The Copywriter
- Takes the Hook and the job data
- Drafts a cold outreach email: specific subject line, direct greeting, max 4 sentences, one clear CTA
- Never leaves placeholder text like `[Your Name]` — unknown fields are omitted cleanly

---

## Requirements

```
google-adk
google-genai
requests
pandas
openpyxl
python-dotenv
```

Install:
```bash
pip install -r requirements.txt
```

Python 3.12+ required.

---

## Path to Production

Because this strictly follows the ADK framework, the local code is **100% portable** to Vertex AI Agent Engine — no refactoring needed.

```
Local Python  →  Vertex AI Agent Engine  →  Auto-scaling serverless REST API
                                         →  React frontend (CV upload)
                                         →  Managed memory (track applied roles)
                                         →  Multi-channel (LinkedIn InMail, WhatsApp)
```

---


# Talk to Gemini-CLI

```
use my main.py to find a job. my cv is 7 years fintech delivery lead, msc ku leuven. role: senior product manager. location: berlin
```


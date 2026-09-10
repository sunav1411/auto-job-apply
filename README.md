# Daily Internship Search & Semi-Auto Apply System

An automated daily job search, ranking, draft generation, and semi-automatic application workflow tailored for a **3rd-year B.Tech CSE (AI & ML)** student targeting **SDE Intern** and **AI/ML Intern** roles (Java backend, full-stack, AI/ML, 470+ LeetCode solved, 1692 peak rating).

---

## Key Features

1. **Modular Connectors**:
   - **RemoteOK API**: Public remote engineering & intern API.
   - **Internshala Scraper**: Scrapes public SDE, Java, Fullstack, and AI/ML internship listing pages with polite rate-limiting.
   - **Company Careers Connector**: Parses careers portals and feeds for target priority companies (**Google, Microsoft, PayPal, CRED**).
2. **Hybrid Scoring Engine (0-100%)**:
   - **Skill & Role Keyword Matching (40%)**: Matches Java, Spring Boot, Python, PyTorch, Full Stack, and DSA against job requirements.
   - **TF-IDF & Cosine Similarity (60%)**: Calculates semantic embedding similarity between candidate resume text (`data/resume.txt`) and target job descriptions.
   - **Priority Target Bonus (+10 pts)**: Rewards postings from priority companies.
3. **SQLite Deduplication & State Tracking**:
   - Local database (`data/jobs.db`) tracks job states: `NEW` -> `SHORTLISTED` -> `DRAFT_READY` -> `APPLIED` -> `REJECTED`.
4. **Tailored Draft Generator**:
   - Creates a customized 1-paragraph *"Why I'm a fit"* blurb and short cover note highlighting candidate's 470+ LeetCode problem solving, 1692 rating, Java backend, and AI/ML project background.
5. **Playwright Form Pre-Filler Proof-of-Concept**:
   - Automated browser form filler using Playwright that fills standard form fields, **attaches the PDF resume file** (`data/resume.pdf`), and **safely halts before submission** for manual review.
6. **Telegram Notifier & Daily Digest**:
   - Posts daily markdown digest to Telegram channel or exports a local report to `reports/daily_digest_YYYY-MM-DD.md`.
7. **One-Click Status Update CLI**:
   - `python main.py mark-applied <job_id>` updates job status to `APPLIED` in the database.

---

## Directory Structure

```
auto_job_apply/
├── config/
│   ├── profile.yaml          # Profile, target roles, skills, LeetCode stats
│   └── sources.yaml          # Config-driven list of job sources & endpoints
├── data/
│   ├── resume.txt            # Resume text for semantic similarity matching
│   ├── resume.pdf            # PDF resume file attached by Playwright form filler
│   └── jobs.db               # SQLite database tracking seen/applied jobs
├── src/
│   ├── models.py              # Pydantic schemas (Job, Profile, MatchResult)
│   ├── database.py            # SQLite database manager
│   ├── connectors/            # Resilient source connectors (RemoteOK, Internshala, Companies)
│   ├── matching/              # Hybrid scoring & ranking engine
│   ├── drafting/              # Tailored fit blurb & cover note generator
│   ├── automation/            # Playwright form filler script
│   └── notifier/              # Telegram digest notifier
├── .github/workflows/
│   └── daily_apply_system.yml # Scheduled daily GitHub Actions cron workflow
├── main.py                    # Main CLI entrypoint
└── requirements.txt           # Dependencies
```

---

## Usage Commands

### 1. Test Run / Dry-Run Mode (First Run Verification)
Run the pipeline in test mode without modifying SQLite database or posting to Telegram:
```bash
python main.py --dry-run
# Or with a custom match threshold override (e.g. 65% or 75%):
python main.py run --dry-run --min-score 70
```

### 2. Full Daily Pipeline Run (Production)
```bash
python main.py run
```

### 3. Mark Job as Applied
```bash
python main.py mark-applied <job_id>
```

### 4. View Database Jobs Summary
```bash
python main.py list
# Or filter by status:
python main.py list --status APPLIED
```

### 5. Playwright Form Filler Test (Proof-of-Concept)
```bash
python main.py test-fill
```

---

## Secrets Setup (Telegram Notifications)

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Set your Telegram Bot Token and Chat ID:
   ```ini
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
   TELEGRAM_CHAT_ID=123456789
   ```
3. For GitHub Actions: Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` as Secrets in Repository Settings.

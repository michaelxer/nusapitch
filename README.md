# NusaPitch

**AI-powered local cold email writer and sender for B2B outreach.**

NusaPitch is a Windows-friendly local app for turning lead spreadsheets into researched, personalized, reviewable cold email drafts. It stores campaign state in SQLite, protects private business data by default, and is designed around safe sending through the user's own SMTP/IMAP email account.

> Status: early v1 foundation. The app can bootstrap its local database, import leads, deduplicate records, research websites, generate draft emails, approve queue items, and record dry-run sends with daily limit checks. Real SMTP sending is intentionally gated for later hardening.

## Why This Project Exists

Most cold outreach tools are either heavy CRMs or hosted SaaS platforms. NusaPitch is intentionally smaller:

- local-first
- privacy-first
- spreadsheet-friendly
- persistent after close/reopen
- focused on writing and sending relevant B2B outreach safely

The public repository contains only reusable source code, documentation, and fake sample data. Real leads, credentials, business profiles, local databases, and campaign history belong only in ignored local folders.

## Core Workflow

```text
Upload leads
-> map columns
-> clean and deduplicate
-> research recipient company
-> match recipient to product/service
-> generate a personalized email draft
-> review and approve
-> queue
-> send safely through SMTP/IMAP
-> persist history and daily limits in SQLite
```

## Features Implemented

- Local Streamlit app shell
- SQLite schema migrations for core outreach tables
- Runtime folder creation for local data and private files
- CSV/XLSX lead import
- Flexible column mapping
- Email, domain, and company normalization
- Lead deduplication
- Placeholder/invalid email detection
- Basic recipient website research with readable text extraction
- AI-draft pipeline hook for OpenAI-compatible chat completion APIs
- LLM draft JSON validation with retry and audited fallback handling
- Safe template fallback when no LLM is configured
- LLM and SMTP/IMAP configuration checks
- Manual draft review page
- Edit, duplicate, archive/restore, and active/inactive controls for setup records
- Queue approval flow
- Daily send ledger
- Sender/domain/campaign limit calculation
- Dry-run send recording
- Confirmed SMTP send flow with sent history and ledger persistence
- Optional IMAP Sent-folder save result tracking
- SQLite backup and CSV export actions
- Manual suppression-list management
- Privacy scanner for public files
- Initial pytest coverage

## Planned V1 Work

- Reply and bounce checking
- Broader tests for crash recovery, duplicate-send prevention, and profile switching

## Tech Stack

- Python
- Streamlit
- SQLite
- pandas
- openpyxl
- requests
- BeautifulSoup
- SMTP/IMAP standard libraries
- OpenAI-compatible chat completion API format

## Project Structure

```text
app/
  streamlit_app.py          # Local web UI
src/nusapitch/
  ai.py                     # Draft generation and LLM integration hook
  db.py                     # SQLite schema and helpers
  email_client.py           # SMTP/IMAP connection helpers
  imports.py                # CSV/XLSX import, cleaning, dedupe
  backups.py                # SQLite backups and CSV exports
  paths.py                  # Runtime folder paths
  privacy.py                # Public file privacy scan
  profiles.py               # Profile CRUD helpers
  queue.py                  # Queue safety and daily ledger logic
  research.py               # Website research
  suppression.py            # Manual opt-out/bounce/domain blocks
sample_leads/
  sample_leads.csv          # Fake demo leads
sample_profiles/
  example_business_profile.json
tests/
  test_imports.py
  test_queue_limits.py
```

## Quick Start

On Windows:

```powershell
.\start_app.bat
```

Manual setup:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

Then open:

```text
http://localhost:8501
```

## Configuration

Copy the example files and keep real secrets out of git:

```powershell
copy .env.example .credentials\llm.env
copy .env.example .credentials\email.env
```

Real API keys, email passwords, uploaded lead files, local databases, exports, logs, and private business profiles are ignored by git.

## Privacy Model

Ignored local folders:

- `.credentials/`
- `private/`
- `data/`
- `HANDOFF_DOC/`

Public-safe sample data:

- `sample_leads/sample_leads.csv`
- `sample_profiles/example_business_profile.json`
- `config.example.json`
- `.env.example`

The app is designed so a portfolio/public repo can stay clean while the local runtime keeps private business data on the user's machine.

## Safety Model

Before real sending, NusaPitch is designed to check:

- draft approval status
- valid recipient email
- suppression list
- duplicate recipient/domain contact history
- sender email daily limit
- sender domain daily limit
- campaign daily limit
- SMTP account availability

The current implementation records dry-run sends in the same ledger shape that real sends will use later.

## Development

Run tests:

```powershell
python -m pytest -q
```

Compile-check Python files:

```powershell
python -m compileall app src tests
```

Run a public privacy scan from Python:

```powershell
$env:PYTHONPATH="src"
python -c "from pathlib import Path; from nusapitch.privacy import scan_public_files; print(scan_public_files(Path('.')))"
```

## Portfolio Notes

This project demonstrates:

- local-first application architecture
- privacy-aware repository hygiene
- SQLite-backed workflow persistence
- data import and normalization
- safety checks for automated email workflows
- incremental product design for a focused B2B tool

## License

MIT

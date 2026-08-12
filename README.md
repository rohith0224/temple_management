# Temple Management System

A dashboard for managing temple operations — donations, assets, maintenance, and
finances — with a FastAPI + PostgreSQL backend, a Streamlit dashboard frontend,
and an LLM-powered natural-language analytics assistant.

## Features

- **Donations** — track donors, campaigns, categories, payment methods, and
  view trends, category/payment/campaign/location breakdowns, and full
  donation records with date-range filtering.
- **Assets** — track temple assets (equipment, vendors, condition, warranty,
  inspection dates) with breakdowns by category, location, and condition.
- **Maintenance** — track maintenance jobs against assets and vendors, with
  cost breakdowns by asset, vendor, category, and type.
- **Finance** — a combined view of donation income vs. maintenance expense,
  asset value, and campaign target-vs-raised performance over time.
- **AI Analyst** — ask questions in plain English (e.g. *"which campaign
  raised the most?"* or *"show donations by location last month"*). A Groq-hosted
  LLM interprets the question into a structured, validated query — it never
  writes SQL or invents data — PostgreSQL returns the real numbers, and the
  LLM explains the result in plain language. The assistant remembers recent
  conversation turns (so follow-ups like *"what about the second one?"* work)
  and suggests up to three follow-up questions after each answer.
- **Role-based dashboard views** — the sidebar role selector (Temple Admin,
  Finance Manager, Donation Manager, Asset Manager, Maintenance Staff,
  Auditor) changes which pages are visible. This is a UI convenience for
  demos, not access control — anyone hitting the API directly can reach all
  data.

## Tech Stack

| Layer      | Technology                                   |
|------------|-----------------------------------------------|
| Backend    | FastAPI, SQLAlchemy, PostgreSQL (`psycopg`)    |
| Frontend   | Streamlit, Plotly, Pandas                      |
| AI         | Groq (Llama 3.3 70B) via the `groq` SDK        |
| Demo data  | Faker (seeded, reproducible)                   |

## Project Structure

```
backend/
  app/
    main.py           FastAPI app, router registration, health check
    database.py       SQLAlchemy engine/session setup
    models.py         ORM models: Donor, Campaign, Donation, Vendor, Asset, MaintenanceRecord
    ai_service.py     Groq system prompt + intent parsing + result explanation
  routes/
    donations.py      /donations endpoints
    assets.py         /assets endpoints
    maintenance.py    /maintenance endpoints
    finance.py        /finance endpoints
    ai.py             /ai/query endpoint — executes AI-interpreted analytics
  seed_data.py        Generates realistic demo data with Faker
frontend/
  app.py              Streamlit dashboard (all pages)
requirements.txt
.env                  DATABASE_URL, GROQ_API_KEY (not committed)
```

## Setup

### 1. Prerequisites

- Python 3.12+
- A running PostgreSQL instance
- A [Groq API key](https://console.groq.com) for the AI Analyst feature

### 2. Clone and create a virtual environment

```bash
git clone https://github.com/rohith0224/temple_management.git
cd temple_management
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```
DATABASE_URL=postgresql+psycopg://<user>:<password>@localhost:5432/temple_management
GROQ_API_KEY=<your-groq-api-key>
```

### 4. Create the database

```bash
createdb temple_management
```

Tables are created automatically on first backend startup (`Base.metadata.create_all`).

### 5. (Optional) Seed demo data

```bash
python -m backend.seed_data
```

## Running the App

Run these in two separate terminals, both with the virtual environment
activated (`source venv/bin/activate`).

**Backend:**

```bash
uvicorn backend.app.main:app --reload
```

Runs on `http://127.0.0.1:8000`. Interactive API docs available at
`http://127.0.0.1:8000/docs`.

**Frontend:**

```bash
streamlit run frontend/app.py
```

Opens on `http://localhost:8501`. Start the backend first — the dashboard
calls it over HTTP for every page.

## API Overview

All routes are prefixed by domain (`/donations`, `/assets`, `/maintenance`,
`/finance`, `/ai`). A few examples:

| Endpoint                          | Description                                  |
|------------------------------------|-----------------------------------------------|
| `GET /donations/summary`          | Total, count, average, largest donation       |
| `GET /donations/records`          | Full donation records (date-range filtered)   |
| `GET /assets/by-condition`        | Asset counts grouped by condition             |
| `GET /maintenance/cost-by-asset`  | Highest maintenance-cost assets               |
| `GET /finance/summary`            | Donation income, maintenance expense, operating amount |
| `GET /finance/campaigns`          | Campaign target vs. raised amounts            |
| `POST /ai/query`                  | Natural-language question → structured analytics + explanation |
| `GET /health/database`            | Verifies the database connection              |

Full interactive documentation (all routes, request/response schemas) is
available at `/docs` once the backend is running.

## Notes on the AI Analyst

The LLM never generates SQL or touches the database directly. It only
selects from a fixed, whitelisted set of `domain` / `analysis` / `filter`
values (defined in `backend/app/ai_service.py`); the backend validates that
output and runs a corresponding, hand-written SQLAlchemy query. This keeps
the assistant flexible in how it's asked questions while keeping the actual
data access fully deterministic and injection-safe.

## Known Limitations

- No authentication/authorization — the role selector in the sidebar is a
  UI-only convenience, not real access control.
- No rate limiting on `/ai/query` — each request calls the Groq API.
- Schema changes are applied via `Base.metadata.create_all`, which creates
  new tables but does not migrate existing ones (no Alembic yet).

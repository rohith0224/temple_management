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
- **AI Analyst** — ask questions in plain English (e.g. *"what can be done
  to increase donations?"* or *"which assets need maintenance?"*). A
  Groq-hosted LLM answers by calling a small set of tools — it can query
  any whitelisted table/column/filter combination, and call tools multiple
  times per question (e.g. once per dimension) before synthesizing an
  answer. It never writes SQL or invents data: every tool call is validated
  and executed by plain SQLAlchemy, so the LLM only ever chooses *what* to
  look up, never *how*. The assistant remembers recent conversation turns
  (so follow-ups like *"what about the second one?"* work) and suggests up
  to three follow-up questions after each answer.
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
    query_catalog.py  Whitelisted tables/columns/joins + safe query builders (no raw SQL)
    ai_service.py     Groq tool-calling loop + system prompt + answer synthesis
  routes/
    donations.py      /donations endpoints
    assets.py         /assets endpoints
    maintenance.py    /maintenance endpoints
    finance.py        /finance endpoints
    ai.py             /ai/query endpoint — runs the AI tool-calling analysis
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

The LLM never generates or sees SQL. It's given 3 tools:

- `query_temple_data` — a generic tool over `donations`/`assets`/
  `maintenance_records`: pick a table, an optional group-by column, a
  metric + aggregation, and filters, all validated against a whitelist in
  `backend/app/query_catalog.py`.
- `query_finance_summary` — donation income vs. maintenance expense vs.
  asset value for a period.
- `query_campaign_performance` — target vs. raised per campaign.

The LLM's output for each tool call is a small JSON object (e.g. `{"table":
"donations", "group_by": "category", "metric_column": "amount",
"metric_aggregation": "sum"}`) — that's the entire extent of what it
controls. `query_catalog.py` resolves those fields against real SQLAlchemy
column objects and builds the actual query; the LLM never influences the
query text itself, and the query-building code is read-only by
construction (no insert/update/delete path exists anywhere in it).

It can call tools multiple times before answering — e.g. a question like
"what can be done to increase donations?" typically triggers 3-4 calls,
one per dimension (category, location, payment method, campaign), so the
answer can compare across them rather than reporting a single breakdown.

## Known Limitations

- No authentication/authorization — the role selector in the sidebar is a
  UI-only convenience, not real access control.
- No rate limiting on `/ai/query`, and each question can now trigger
  several Groq calls (one per tool call, plus a final synthesis call) —
  meaningfully more token usage per question than a single-call design.
  On Groq's free tier (100K tokens/day) this is reachable in normal use,
  not just abuse.
- Error handling around the Groq/DB calls in the AI tool-calling loop is
  minimal — a transient Groq failure (rate limit, network blip) or a
  malformed filter value currently surfaces as a raw 500 rather than a
  clean error response.
- Schema changes are applied via `Base.metadata.create_all`, which creates
  new tables but does not migrate existing ones (no Alembic yet).

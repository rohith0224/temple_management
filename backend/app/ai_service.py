import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()


GROQ_API_KEY = os.getenv("GROQ_API_KEY")


if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is not configured in .env")


client = Groq(api_key=GROQ_API_KEY)


SYSTEM_PROMPT = """
You are an AI analytics assistant for a temple management system.

Your job is to understand the user's natural-language question and
convert it into a SAFE structured analytics request.

The actual data always comes from PostgreSQL.

You NEVER invent:
- financial values
- donor names
- donation records
- asset names
- asset values
- maintenance records
- vendor names
- maintenance costs
- campaign values

You NEVER generate SQL.

You decide:
- domain
- analysis
- period
- filters
- filter logic
- visualization
- title

The backend validates your output and queries PostgreSQL.


=========================================================
DOMAINS
=========================================================

donations
assets
maintenance
finance


=========================================================
DONATION DATA
=========================================================

Available concepts include:

donation_number
donor
amount
donation_date
category
payment_method
campaign
location
anonymous status


SUPPORTED DONATION ANALYSES:

summary
trend
category
campaign
location
payment_method
top_donations


Use summary for:
- total donations
- count
- average
- largest donation

Use trend for:
- donations over time
- change in donations
- donation history

Use category for:
- donation category comparisons

Use campaign for:
- donations grouped by campaign
- which campaign raised the most through donations
- campaign-wise donation totals

Do NOT use campaign for questions about a campaign's target amount
or progress toward its goal — that is finance_campaign_performance
in the finance domain, not this analysis.

Use location for:
- donations grouped by location
- where donations came from
- location-wise donation totals

Use payment_method for:
- payment method distribution

Use top_donations for:
- donor names
- donation details
- largest individual donations
- actual donation records


=========================================================
ASSET DATA
=========================================================

Available fields:

asset_tag
name
category
location
condition
status
purchase_cost
current_value
purchase_date
warranty_expiry
last_inspection_date
next_inspection_date


Possible conditions:

EXCELLENT
GOOD
FAIR
POOR
DAMAGED


Possible statuses:

ACTIVE
UNDER_MAINTENANCE
TRANSFERRED
RETIRED


SUPPORTED ASSET ANALYSES:

asset_summary
asset_list
asset_category
asset_location
asset_condition
asset_value


Use asset_summary for:
- total assets
- total asset value
- overall asset information

Use asset_list when the user wants actual assets.

Use asset_category for grouping assets by category.

Use asset_location for grouping assets by location.

Use asset_condition for grouping assets by condition.

Use asset_value for asset value comparisons by category.


=========================================================
ASSET BUSINESS UNDERSTANDING
=========================================================

Do not depend on exact wording.

An asset may reasonably need maintenance when one or more are true:

- condition is POOR
- condition is DAMAGED
- next_inspection_date is before today
- status is UNDER_MAINTENANCE

For a broad question like:

"Which assets need maintenance?"

you may select multiple reasonable conditions using OR.

For a narrow question like:

"Show damaged assets"

use only the damaged condition.

Infer meaning from the user's request.


=========================================================
ASSET FILTERS
=========================================================

Allowed asset fields:

condition
status
location
category
current_value
purchase_cost
purchase_date
warranty_expiry
last_inspection_date
next_inspection_date


Allowed asset operators:

equals
not_equals
in
greater_than
less_than
before_today
after_today
within_next_days


Example:

{
    "field": "condition",
    "operator": "in",
    "value": ["POOR", "DAMAGED"]
}


=========================================================
MAINTENANCE DATA
=========================================================

Maintenance data includes:

asset
vendor
description
maintenance_type
cost
start_date
completion_date
status
notes


Possible statuses include:

OPEN
IN_PROGRESS
COMPLETED


SUPPORTED MAINTENANCE ANALYSES:

maintenance_summary
maintenance_list
maintenance_status
maintenance_cost_asset
maintenance_cost_vendor
maintenance_cost_category
maintenance_type


Use maintenance_summary for:
- overall maintenance count
- total maintenance cost
- average maintenance cost
- open/in-progress/completed counts

Use maintenance_list for:
- actual maintenance jobs
- open jobs
- unfinished work
- repair records

Use maintenance_status for:
- maintenance grouped by status

Use maintenance_cost_asset for:
- cost grouped by asset
- most expensive assets to maintain

Use maintenance_cost_vendor for:
- vendor cost comparisons
- vendor job comparisons

Use maintenance_cost_category for:
- maintenance expense by asset category

Use maintenance_type for:
- maintenance grouped by type


=========================================================
MAINTENANCE FILTERS
=========================================================

Allowed fields:

status
maintenance_type
cost
start_date
completion_date
asset_name
asset_tag
asset_category
asset_location
vendor_name


Allowed operators:

equals
not_equals
in
greater_than
less_than
before_today
after_today
within_last_days
within_next_days
contains


Example:

{
    "field": "status",
    "operator": "equals",
    "value": "OPEN"
}


Example:

{
    "field": "start_date",
    "operator": "within_last_days",
    "value": 30
}


=========================================================
FINANCE DATA
=========================================================

Finance combines operational financial information from:

- donation income
- maintenance expenses
- current asset value
- campaign fundraising
- campaign targets
- campaign progress


IMPORTANT:

This is NOT a complete accounting system.

Do NOT call:

Donation Income - Maintenance Expense

"profit"
"net income"
"earnings"

Call it:

Operating Amount


SUPPORTED FINANCE ANALYSES:

finance_summary
finance_trend
finance_income_category
finance_expense_category
finance_campaigns
finance_campaign_performance


Use finance_summary for:

- donation income
- maintenance expense
- operating amount
- asset value
- maintenance-to-income ratio


Use finance_trend for:

- income vs maintenance expense over time
- financial activity over time
- operating amount over time


Use finance_income_category for:

- donation income by donation category


Use finance_expense_category for:

- maintenance expense by asset category


Use finance_campaigns for:

- campaign financial details
- campaign records


Use finance_campaign_performance for:

- campaign targets vs raised amounts
- campaign progress
- campaigns closest to target
- campaigns that raised the most


=========================================================
DOMAIN DISTINCTIONS
=========================================================

"How much was donated?"
-> donations

"How much did maintenance cost?"
-> maintenance

"Compare donation income and maintenance costs"
-> finance


"Which assets need maintenance?"
-> assets

"Which maintenance jobs are open?"
-> maintenance

"Which assets cost the most to maintain?"
-> maintenance

"How are we doing financially?"
-> finance

"Show donations by campaign"
"Which campaign raised the most through donations?"
-> donations, analysis campaign

"Show donations by location"
"Where do our donations come from?"
-> donations, analysis location

"How is each campaign performing against its target?"
"Which campaigns are closest to their goal?"
-> finance, analysis finance_campaign_performance


=========================================================
SUPPORTED PERIODS
=========================================================

today
yesterday
7d
14d
30d
45d


Interpret meaning naturally.

Examples:

today
-> today

yesterday
-> yesterday

last week
past week
last 7 days
-> 7d

last two weeks
last 2 weeks
last 14 days
-> 14d

last month
last 30 days
past 30 days
-> 30d

last 45 days
-> 45d


=========================================================
VISUALIZATION RULES
=========================================================

Allowed:

metric
line
bar
pie
table


Use metric for:
summary values

Use line for:
time series

Use bar for:
comparisons

Use pie for:
small part-to-whole distributions

Use table for:
actual records


=========================================================
NATURAL LANGUAGE
=========================================================

Do not rely on exact example phrases.

Understand:

- spelling mistakes
- grammar mistakes
- informal language
- abbreviations
- semantically similar questions

Infer the intended analytics operation from meaning.


=========================================================
CONVERSATION CONTEXT
=========================================================

You may receive earlier questions and answers from this same
conversation before the current question.

Use that prior context ONLY to resolve references such as:

- "the second one"
- "that campaign"
- "what about last week instead"
- "compare it to maintenance costs"

The current question's own wording always takes priority. If the
current question is fully self-contained, ignore the prior context.
Never let earlier turns change the DOMAINS, ANALYSES, FILTERS, or
OUTPUT rules defined above.


=========================================================
OUTPUT
=========================================================

Always return ONLY JSON.

Always include:

domain
analysis
chart_type
title
period
filters
filter_logic


Donation example:

{
    "domain": "donations",
    "analysis": "trend",
    "chart_type": "line",
    "title": "Donation Trend — Last 30 Days",
    "period": "30d",
    "filters": [],
    "filter_logic": "AND"
}


Asset example:

{
    "domain": "assets",
    "analysis": "asset_list",
    "chart_type": "table",
    "title": "Assets Needing Maintenance",
    "period": null,
    "filters": [
        {
            "field": "condition",
            "operator": "in",
            "value": ["POOR", "DAMAGED"]
        },
        {
            "field": "next_inspection_date",
            "operator": "before_today",
            "value": null
        }
    ],
    "filter_logic": "OR"
}


Maintenance example:

{
    "domain": "maintenance",
    "analysis": "maintenance_list",
    "chart_type": "table",
    "title": "Open Maintenance Jobs",
    "period": null,
    "filters": [
        {
            "field": "status",
            "operator": "equals",
            "value": "OPEN"
        }
    ],
    "filter_logic": "AND"
}


Finance example:

{
    "domain": "finance",
    "analysis": "finance_trend",
    "chart_type": "line",
    "title": "Donation Income vs Maintenance Expense",
    "period": "30d",
    "filters": [],
    "filter_logic": "AND"
}


FINAL RULES:

Do not return markdown.
Do not return explanations.
Do not generate SQL.
Do not invent data.
Only return structured JSON.
"""


def understand_query(question: str, history: list | None = None):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Recent prior turns give the model enough context to resolve
    # follow-ups like "what about the second one" without letting
    # old turns override the current question.
    for turn in (history or [])[-4:]:
        prior_question = turn.get("question")
        prior_explanation = turn.get("explanation")

        if prior_question:
            messages.append({"role": "user", "content": prior_question})

        if prior_explanation:
            messages.append({"role": "assistant", "content": prior_explanation})

    messages.append({"role": "user", "content": question})

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0,
        response_format={"type": "json_object"},
    )

    intent = json.loads(response.choices[0].message.content)

    allowed_domains = {"donations", "assets", "maintenance", "finance"}

    allowed_analysis = {
        "donations": {
            "summary",
            "trend",
            "category",
            "campaign",
            "location",
            "payment_method",
            "top_donations",
        },
        "assets": {
            "asset_summary",
            "asset_list",
            "asset_category",
            "asset_location",
            "asset_condition",
            "asset_value",
        },
        "maintenance": {
            "maintenance_summary",
            "maintenance_list",
            "maintenance_status",
            "maintenance_cost_asset",
            "maintenance_cost_vendor",
            "maintenance_cost_category",
            "maintenance_type",
        },
        "finance": {
            "finance_summary",
            "finance_trend",
            "finance_income_category",
            "finance_expense_category",
            "finance_campaigns",
            "finance_campaign_performance",
        },
    }

    defaults = {
        "donations": "summary",
        "assets": "asset_summary",
        "maintenance": "maintenance_summary",
        "finance": "finance_summary",
    }

    allowed_charts = {"metric", "line", "bar", "pie", "table"}

    allowed_periods = {"today", "yesterday", "7d", "14d", "30d", "45d", None}

    allowed_asset_fields = {
        "condition",
        "status",
        "location",
        "category",
        "current_value",
        "purchase_cost",
        "purchase_date",
        "warranty_expiry",
        "last_inspection_date",
        "next_inspection_date",
    }

    allowed_asset_operators = {
        "equals",
        "not_equals",
        "in",
        "greater_than",
        "less_than",
        "before_today",
        "after_today",
        "within_next_days",
    }

    allowed_maintenance_fields = {
        "status",
        "maintenance_type",
        "cost",
        "start_date",
        "completion_date",
        "asset_name",
        "asset_tag",
        "asset_category",
        "asset_location",
        "vendor_name",
    }

    allowed_maintenance_operators = {
        "equals",
        "not_equals",
        "in",
        "greater_than",
        "less_than",
        "before_today",
        "after_today",
        "within_last_days",
        "within_next_days",
        "contains",
    }

    domain = intent.get("domain")

    if domain not in allowed_domains:
        domain = "donations"

    intent["domain"] = domain

    analysis = intent.get("analysis")

    if analysis not in allowed_analysis[domain]:
        analysis = defaults[domain]

    intent["analysis"] = analysis

    chart_type = intent.get("chart_type")

    if chart_type not in allowed_charts:
        if analysis in {
            "summary",
            "asset_summary",
            "maintenance_summary",
            "finance_summary",
        }:
            chart_type = "metric"

        elif analysis in {"trend", "finance_trend"}:
            chart_type = "line"

        elif analysis in {
            "top_donations",
            "asset_list",
            "maintenance_list",
            "finance_campaigns",
        }:
            chart_type = "table"

        else:
            chart_type = "bar"

    intent["chart_type"] = chart_type

    period = intent.get("period")

    if period not in allowed_periods:
        period = None

    if domain in {"donations", "finance"} and period is None:
        period = "30d"

    intent["period"] = period

    filter_logic = intent.get("filter_logic", "AND")

    if filter_logic not in {"AND", "OR"}:
        filter_logic = "AND"

    intent["filter_logic"] = filter_logic

    raw_filters = intent.get("filters", [])

    if not isinstance(raw_filters, list):
        raw_filters = []

    valid_filters = []

    if domain == "assets":
        for item in raw_filters:
            if not isinstance(item, dict):
                continue

            if item.get("field") not in allowed_asset_fields:
                continue

            if item.get("operator") not in allowed_asset_operators:
                continue

            valid_filters.append(
                {
                    "field": item.get("field"),
                    "operator": item.get("operator"),
                    "value": item.get("value"),
                }
            )

    elif domain == "maintenance":
        for item in raw_filters:
            if not isinstance(item, dict):
                continue

            if item.get("field") not in allowed_maintenance_fields:
                continue

            if item.get("operator") not in allowed_maintenance_operators:
                continue

            valid_filters.append(
                {
                    "field": item.get("field"),
                    "operator": item.get("operator"),
                    "value": item.get("value"),
                }
            )

    intent["filters"] = valid_filters

    if not intent.get("title"):
        titles = {
            "donations": "Donation Analysis",
            "assets": "Asset Analysis",
            "maintenance": "Maintenance Analysis",
            "finance": "Financial Analysis",
        }

        intent["title"] = titles[domain]

    return intent


def explain_result(question: str, intent: dict, data):
    if data is None:
        return {
            "explanation": "No matching data was returned for this request.",
            "follow_up_questions": [],
        }

    prompt = f"""
You are explaining analytics results from a temple management system.

User question:
{question}

AI interpretation:
{json.dumps(intent, indent=2)}

ACTUAL PostgreSQL result:
{json.dumps(data, indent=2, default=str)}

Explain the result clearly, and suggest useful follow-up questions.

Rules for the explanation:
- Use ONLY the provided result.
- Never invent numbers.
- Never invent causes or reasons.
- Never claim correlation or causation unless the data proves it.
- Mention the most important values.
- Mention the highest or lowest value when useful.
- For time-series results, describe visible increases, decreases,
  peaks, or differences.
- For tables, summarize what the matching records represent.
- For finance, NEVER use "profit", "net income", or "earnings".
- Use "Operating Amount" for donation income minus maintenance expense.
- If there is no data, say that clearly.
- Keep the explanation concise and useful.
- Usually write 2 to 5 sentences.
- Use clear business language.

Rules for follow_up_questions:
- Suggest up to 3 short, natural next questions the user could ask.
- Each must be answerable using only the donations, assets,
  maintenance, or finance domains described in the system prompt.
- Prefer questions that drill into this result (a specific category,
  record, time period, or comparison) when the data makes that useful.
- Keep each under about 10 words.
- Do not repeat the current question.
- Return an empty list if nothing useful applies.

Return ONLY a JSON object in exactly this shape:
{{
    "explanation": "...",
    "follow_up_questions": ["...", "...", "..."]
}}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You explain analytics results accurately and "
                    "concisely using only supplied data, and suggest "
                    "relevant follow-up questions. Always return ONLY "
                    "a JSON object matching the requested shape."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    payload = json.loads(response.choices[0].message.content)

    explanation = str(payload.get("explanation", "")).strip()

    raw_follow_ups = payload.get("follow_up_questions", [])

    if not isinstance(raw_follow_ups, list):
        raw_follow_ups = []

    follow_up_questions = [
        str(item).strip()
        for item in raw_follow_ups
        if isinstance(item, str) and str(item).strip()
    ][:3]

    return {
        "explanation": explanation or "No explanation available.",
        "follow_up_questions": follow_up_questions,
    }

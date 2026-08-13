import json
import os

from dotenv import load_dotenv
from groq import Groq

from backend.app.query_catalog import (
    OPERATORS,
    execute_campaign_performance,
    execute_finance_summary,
    execute_table_query,
)

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is not configured in .env")

client = Groq(api_key=GROQ_API_KEY)

MODEL = "llama-3.3-70b-versatile"

MAX_TOOL_CALLS = 6


SYSTEM_PROMPT = """
You are an AI analytics assistant for a temple management system.

You answer questions about donations, assets, maintenance, and finance
using real data from PostgreSQL — accessed ONLY through the tools you are
given. You never generate SQL and you never invent numbers, names, or
records. If you need a fact to answer the question, call a tool to get it
before answering.

You can call tools more than once. Many questions need several calls to
answer well — for example, evaluating patterns or comparing where
donations perform best usually means calling query_temple_data once per
dimension (category, location, payment method, campaign, etc.) so you can
compare them, not just grouping by one column and stopping.

RECOMMENDATIONS
When a question asks for advice, a recommendation, or "what should we do",
you may recommend focusing on whichever group already performs best in the
data you retrieved — but only as a direct reading of those numbers. Never
invent a reason WHY something performs well (no guessing at events,
marketing, timing, or donor behavior) unless that reason is explicitly
present in the data itself.

When grouping by a nullable relationship column (campaign_name, donor_name,
vendor_name, asset_name, asset_category) for a recommendation-type
question, set exclude_empty_groups=true on that tool call. Placeholder
groups like "No Campaign" or "No Vendor" represent an ABSENCE of a value,
not a real, actionable option — never recommend concentrating effort on
one of them.

FINANCE TERMINOLOGY
This is not a full accounting system. Never call donation income minus
maintenance expense "profit", "net income", or "earnings" — always call it
"Operating Amount".

DOMAIN KNOWLEDGE (do not guess filter values — use exactly these)
- assets.condition is one of: EXCELLENT, GOOD, FAIR, POOR, DAMAGED
- assets.status is one of: ACTIVE, UNDER_MAINTENANCE, TRANSFERRED, RETIRED
- maintenance_records.status is one of: OPEN, IN_PROGRESS, COMPLETED
- There is no "needs maintenance" status anywhere. "Which assets need
  maintenance" means: table=assets, mode=list, filters where condition is
  POOR or DAMAGED, OR status equals UNDER_MAINTENANCE, OR
  next_inspection_date is before_today — combine with filter_logic OR.
  Use only the conditions that make sense for how the question is asked
  (e.g. "damaged assets" alone should just filter condition=DAMAGED).
- "Open maintenance jobs" / "unfinished work" means table=maintenance_records,
  status equals OPEN (or OPEN and IN_PROGRESS together with "in" operator).

CONVERSATION CONTEXT
You may receive earlier questions and answers from this conversation. Use
that only to resolve references like "the second one" or "that campaign".
The current question's own wording always takes priority.

Once you have everything you need, stop calling tools and answer in plain
text, summarizing what you found. Every claim in your answer must be
backed by a tool result you actually received in this conversation.
"""


QUERY_TABLE_TOOL = {
    "type": "function",
    "function": {
        "name": "query_temple_data",
        "description": (
            "Query donations, assets, or maintenance_records from PostgreSQL. "
            "Use 'aggregate' mode to compute a total, count, or average, "
            "optionally grouped by a column. Use 'list' mode to return actual "
            "matching rows. Call this as many times as needed before answering."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "enum": ["donations", "assets", "maintenance_records"],
                },
                "mode": {"type": "string", "enum": ["aggregate", "list"]},
                "group_by": {
                    "type": "string",
                    "description": (
                        "Column to group by in aggregate mode. donations: "
                        "category, payment_method, location, campaign_name, "
                        "donor_name. assets: category, location, condition, "
                        "status, vendor_name. maintenance_records: status, "
                        "maintenance_type, asset_name, asset_category, "
                        "vendor_name. Omit for a single overall total."
                    ),
                },
                "metric_column": {
                    "type": "string",
                    "description": (
                        "Numeric column to aggregate. donations: amount. "
                        "assets: current_value, purchase_cost. "
                        "maintenance_records: cost. Omit to just count rows."
                    ),
                },
                "metric_aggregation": {
                    "type": "string",
                    "enum": ["sum", "count", "avg", "min", "max"],
                },
                "filters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string"},
                            "operator": {"type": "string", "enum": sorted(OPERATORS)},
                            "value": {},
                        },
                        "required": ["field", "operator"],
                    },
                },
                "filter_logic": {"type": "string", "enum": ["AND", "OR"]},
                "period": {
                    "type": "string",
                    "enum": ["today", "yesterday", "7d", "14d", "30d", "45d", "all"],
                    "description": "Restricts to the table's date column. Use 'all' for no restriction.",
                },
                "order": {"type": "string", "enum": ["asc", "desc"]},
                "limit": {"type": "integer"},
                "exclude_empty_groups": {
                    "type": "boolean",
                    "description": (
                        "Set true when grouping by a nullable relationship "
                        "column (campaign_name, donor_name, vendor_name, "
                        "asset_name, asset_category) for a recommendation-type "
                        "question, to drop placeholder groups like 'No "
                        "Campaign' from the results."
                    ),
                },
            },
            "required": ["table", "mode"],
        },
    },
}

FINANCE_SUMMARY_TOOL = {
    "type": "function",
    "function": {
        "name": "query_finance_summary",
        "description": (
            "Get donation income, maintenance expense, operating amount "
            "(income minus expense — never call this profit), and total "
            "asset value for a period."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "yesterday", "7d", "14d", "30d", "45d"],
                },
            },
            "required": ["period"],
        },
    },
}

CAMPAIGN_PERFORMANCE_TOOL = {
    "type": "function",
    "function": {
        "name": "query_campaign_performance",
        "description": (
            "Get every campaign's target amount, amount raised, and "
            "progress percent toward its goal."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}

TOOLS = [QUERY_TABLE_TOOL, FINANCE_SUMMARY_TOOL, CAMPAIGN_PERFORMANCE_TOOL]


def dispatch_tool_call(db, name, args):
    if name == "query_temple_data":
        return execute_table_query(db, args)

    if name == "query_finance_summary":
        return execute_finance_summary(db, period=args.get("period", "30d"))

    if name == "query_campaign_performance":
        return execute_campaign_performance(db)

    return {"error": f"Unknown tool '{name}'."}


def build_messages(question, history):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for turn in (history or [])[-4:]:
        prior_question = turn.get("question")
        prior_explanation = turn.get("explanation")

        if prior_question:
            messages.append({"role": "user", "content": prior_question})

        if prior_explanation:
            messages.append({"role": "assistant", "content": prior_explanation})

    messages.append({"role": "user", "content": question})

    return messages


def run_tool_loop(db, messages):
    executed_calls = []

    for _ in range(MAX_TOOL_CALLS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0,
        )

        message = response.choices[0].message

        if not message.tool_calls:
            break

        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            }
        )

        for tool_call in message.tool_calls:
            try:
                args = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            result = dispatch_tool_call(db, tool_call.function.name, args)

            executed_calls.append(
                {"tool": tool_call.function.name, "args": args, "result": result}
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, default=str),
                }
            )

            if len(executed_calls) >= MAX_TOOL_CALLS:
                break

        if len(executed_calls) >= MAX_TOOL_CALLS:
            break

    return executed_calls


def build_synthesis_prompt(question, executed_calls):
    if executed_calls:
        calls_text = "\n\n".join(
            f"Tool call {i + 1}: {call['tool']}({json.dumps(call['args'])})\n"
            f"Result: {json.dumps(call['result'], default=str)}"
            for i, call in enumerate(executed_calls)
        )
    else:
        calls_text = "No tool was called — no data is available."

    return f"""
User question:
{question}

Data retrieved via tool calls:
{calls_text}

Write the final response as a JSON object in exactly this shape:
{{
    "title": "short title for this analysis",
    "explanation": "2-5 sentences answering the question, using ONLY the data above. Never invent numbers, causes, or reasons not present in it. If no data was retrieved, say so rather than guessing.",
    "chart": {{
        "type": "metric" | "line" | "bar" | "pie" | "table",
        "source_call": <1-based index of the tool call whose result is most useful to visualize, or null>
    }},
    "follow_up_questions": ["...", "...", "..."]
}}

Chart type guidance:
- "metric": a single overall number.
- "line": a result grouped by date.
- "bar" or "pie": a categorical breakdown (few groups: pie; more groups or a ranking: bar).
- "table": a list of actual records.
- If several tool calls were made, pick the ONE most representative for source_call; the explanation can still reference all of them.
- follow_up_questions: up to 3 short, natural next questions, under ~10 words each. Empty list if nothing useful applies.
"""


def shape_chart_data(executed_calls, chart_spec):
    if not executed_calls or not chart_spec:
        return None

    source_call = chart_spec.get("source_call")
    chart_type = chart_spec.get("type")

    if not isinstance(source_call, int) or not (1 <= source_call <= len(executed_calls)):
        return None

    call = executed_calls[source_call - 1]
    tool_name = call["tool"]
    result = call["result"]

    if tool_name == "query_finance_summary":
        return {
            "type": "metric",
            "data": [
                {"label": "Donation Income", "value": result.get("donation_income", 0)},
                {
                    "label": "Maintenance Expense",
                    "value": result.get("maintenance_expense", 0),
                },
                {"label": "Operating Amount", "value": result.get("operating_amount", 0)},
                {"label": "Asset Value", "value": result.get("asset_value", 0)},
            ],
        }

    if tool_name == "query_campaign_performance":
        return {"type": "table", "data": result}

    if tool_name == "query_temple_data":
        if result.get("mode") == "list":
            return {"type": "table", "data": result.get("rows", [])}

        if result.get("mode") == "aggregate":
            if result.get("group_by"):
                safe_type = chart_type if chart_type in {"bar", "pie", "line"} else "bar"
                return {"type": safe_type, "data": result.get("rows", [])}

            return {
                "type": "metric",
                "data": [
                    {"label": result.get("metric", "total"), "value": result.get("value", 0)}
                ],
            }

    return None


def run_ai_analysis(question, history, db):
    messages = build_messages(question, history)

    executed_calls = run_tool_loop(db, messages)

    synthesis_prompt = build_synthesis_prompt(question, executed_calls)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You summarize retrieved data accurately and concisely. "
                    "Always return ONLY a JSON object matching the requested shape."
                ),
            },
            {"role": "user", "content": synthesis_prompt},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    payload = json.loads(response.choices[0].message.content)

    explanation = str(payload.get("explanation", "")).strip() or "No explanation available."
    title = str(payload.get("title", "")).strip() or "Analysis"

    raw_follow_ups = payload.get("follow_up_questions", [])

    if not isinstance(raw_follow_ups, list):
        raw_follow_ups = []

    follow_up_questions = [
        str(item).strip()
        for item in raw_follow_ups
        if isinstance(item, str) and str(item).strip()
    ][:3]

    chart = shape_chart_data(executed_calls, payload.get("chart"))

    steps = [
        {"tool": call["tool"], "args": call["args"]} for call in executed_calls
    ]

    return {
        "title": title,
        "explanation": explanation,
        "chart": chart,
        "follow_up_questions": follow_up_questions,
        "steps": steps,
    }

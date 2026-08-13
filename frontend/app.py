from datetime import date

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_BASE = "http://127.0.0.1:8000"


st.set_page_config(
    page_title="Temple Management Dashboard", page_icon="🛕", layout="wide"
)
ROLE_PERMISSIONS = {
    "Temple Admin": {
        "overview": True,
        "donations": True,
        "donation_records": True,
        "assets": True,
        "maintenance": True,
        "finance": True,
        "ai": True,
    },
    "Finance Manager": {
        "overview": True,
        "donations": True,
        "donation_records": True,
        "assets": False,
        "maintenance": False,
        "finance": True,
        "ai": True,
    },
    "Donation Manager": {
        "overview": False,
        "donations": True,
        "donation_records": True,
        "assets": False,
        "maintenance": False,
        "finance": False,
        "ai": True,
    },
    "Asset Manager": {
        "overview": False,
        "donations": False,
        "donation_records": False,
        "assets": True,
        "maintenance": True,
        "finance": False,
        "ai": True,
    },
    "Maintenance Staff": {
        "overview": False,
        "donations": False,
        "donation_records": False,
        "assets": True,
        "maintenance": True,
        "finance": False,
        "ai": True,
    },
    "Auditor": {
        "overview": True,
        "donations": True,
        "donation_records": True,
        "assets": True,
        "maintenance": True,
        "finance": True,
        "ai": False,
    },
}


def get_api(endpoint, params=None):
    try:
        response = requests.get(f"{API_BASE}{endpoint}", params=params, timeout=20)

        response.raise_for_status()

        return response.json()

    except requests.RequestException as e:
        st.error(f"API request failed: {e}")

        return None


def post_api(endpoint, payload):
    try:
        response = requests.post(f"{API_BASE}{endpoint}", json=payload, timeout=60)

        response.raise_for_status()

        return response.json()

    except requests.RequestException as e:
        st.error(f"AI request failed: {e}")

        return None


def show_donation_table(records):
    if not records:
        st.info("No donation records found.")
        return

    df = pd.DataFrame(records)

    df = df.rename(
        columns={
            "donation_number": "Donation #",
            "donor_name": "Donor",
            "amount": "Amount",
            "date": "Date",
            "category": "Category",
            "payment_method": "Payment Method",
            "campaign": "Campaign",
            "location": "Location",
        }
    )

    if "Amount" in df.columns:
        df["Amount"] = df["Amount"].apply(lambda value: f"${value:,.2f}")

    st.dataframe(df, width="stretch", hide_index=True)


def show_asset_table(records):
    if not records:
        st.info("No asset records found.")
        return

    df = pd.DataFrame(records)

    df = df.rename(
        columns={
            "asset_tag": "Asset Tag",
            "name": "Asset Name",
            "category": "Category",
            "location": "Location",
            "condition": "Condition",
            "status": "Status",
            "purchase_cost": "Purchase Cost",
            "current_value": "Current Value",
            "purchase_date": "Purchase Date",
            "warranty_expiry": "Warranty Expiry",
            "last_inspection_date": "Last Inspection",
            "next_inspection_date": "Next Inspection",
        }
    )

    for column in ["Purchase Cost", "Current Value"]:
        if column in df.columns:
            df[column] = df[column].apply(lambda value: f"${value:,.2f}")

    st.dataframe(df, width="stretch", hide_index=True)


def show_maintenance_table(records):
    if not records:
        st.info("No maintenance records found.")
        return

    df = pd.DataFrame(records)

    df = df.rename(
        columns={
            "id": "ID",
            "asset_tag": "Asset Tag",
            "asset_name": "Asset",
            "asset_category": "Category",
            "asset_location": "Location",
            "vendor_name": "Vendor",
            "maintenance_type": "Maintenance Type",
            "description": "Description",
            "cost": "Cost",
            "start_date": "Start Date",
            "completion_date": "Completion Date",
            "status": "Status",
            "notes": "Notes",
        }
    )

    if "Cost" in df.columns:
        df["Cost"] = df["Cost"].apply(lambda value: f"${value:,.2f}")

    st.dataframe(df, width="stretch", hide_index=True)


def get_date_params():
    st.sidebar.divider()

    range_label = st.sidebar.selectbox(
        "Date Range",
        [
            "Today",
            "Yesterday",
            "Last 7 Days",
            "Last 14 Days",
            "Last 30 Days",
            "Last 45 Days",
            "Custom",
        ],
    )

    period_map = {
        "Today": "today",
        "Yesterday": "yesterday",
        "Last 7 Days": "7d",
        "Last 14 Days": "14d",
        "Last 30 Days": "30d",
        "Last 45 Days": "45d",
    }

    if range_label == "Custom":
        start = st.sidebar.date_input("Start Date")

        end = st.sidebar.date_input("End Date")

        return (
            range_label,
            {"period": "custom", "start_date": str(start), "end_date": str(end)},
        )

    return (range_label, {"period": period_map[range_label]})


st.sidebar.title("🛕 Temple Management")


profile = st.sidebar.selectbox("Select Role", list(ROLE_PERMISSIONS.keys()))


permissions = ROLE_PERMISSIONS[profile]


pages = []


if permissions["overview"]:
    pages.append("Overview")

if permissions["donations"]:
    pages.append("Donations")

if permissions["assets"]:
    pages.append("Assets")

if permissions["maintenance"]:
    pages.append("Maintenance")

if permissions["finance"]:
    pages.append("Finance")

if permissions["ai"]:
    pages.append("AI Analyst")


page = st.sidebar.radio("Navigation", pages)


st.title("🛕 Temple Management Dashboard")

st.caption(f"Current profile: {profile}")
if page == "Overview":
    st.header("Temple Operations Overview")

    range_label, params = get_date_params()

    finance = get_api("/finance/summary", params=params)

    assets = get_api("/assets/summary")

    maintenance = get_api("/maintenance/summary")

    if finance:
        cols = st.columns(4)

        cols[0].metric("Donation Income", f"${finance['donation_income']:,.2f}")

        cols[1].metric("Maintenance Expense", f"${finance['maintenance_expense']:,.2f}")

        cols[2].metric("Operating Amount", f"${finance['net_operating_amount']:,.2f}")

        cols[3].metric("Asset Value", f"${finance['asset_value']:,.2f}")

    if assets:
        st.subheader("Assets")

        cols = st.columns(3)

        cols[0].metric("Total Assets", assets["total_assets"])

        cols[1].metric("Under Maintenance", assets["under_maintenance"])

        cols[2].metric("Damaged", assets["damaged_assets"])

    if maintenance:
        st.subheader("Maintenance")

        cols = st.columns(3)

        cols[0].metric("Maintenance Records", maintenance["total_records"])

        cols[1].metric("Open", maintenance["open_records"])

        cols[2].metric("Total Cost", f"${maintenance['total_cost']:,.2f}")
elif page == "Donations":
    st.header("Donation Management")

    range_label, params = get_date_params()

    summary = get_api("/donations/summary", params=params)

    if summary:
        cols = st.columns(5)

        cols[0].metric("Total", f"${summary['total_amount']:,.2f}")

        cols[1].metric("Count", summary["total_donations"])

        cols[2].metric("Average", f"${summary['average_donation']:,.2f}")

        cols[3].metric("Largest", f"${summary['largest_donation']:,.2f}")

        cols[4].metric("Unique Donors", summary["unique_donors"])

    daily = get_api("/donations/daily", params=params)

    if daily:
        df = pd.DataFrame(daily)

        fig = px.line(df, x="date", y="total", markers=True, title="Donation Trend")

        st.plotly_chart(fig, width="stretch")

    left, right = st.columns(2)

    with left:
        categories = get_api("/donations/categories", params=params)

        if categories:
            df = pd.DataFrame(categories)

            st.plotly_chart(
                px.bar(df, x="category", y="total", title="Donations by Category"),
                width="stretch",
            )

    with right:
        payment = get_api("/donations/payment-methods", params=params)

        if payment:
            df = pd.DataFrame(payment)

            st.plotly_chart(
                px.pie(
                    df, names="payment_method", values="total", title="Payment Methods"
                ),
                width="stretch",
            )

    records = get_api("/donations/records", params=params)

    show_donation_table(records)
elif page == "Assets":
    st.header("Asset Management")

    summary = get_api("/assets/summary")

    if summary:
        cols = st.columns(4)

        cols[0].metric("Total Assets", summary["total_assets"])

        cols[1].metric("Asset Value", f"${summary['total_value']:,.2f}")

        cols[2].metric("Under Maintenance", summary["under_maintenance"])

        cols[3].metric("Damaged", summary["damaged_assets"])

    category = get_api("/assets/by-category")

    location = get_api("/assets/by-location")

    condition = get_api("/assets/by-condition")

    left, right = st.columns(2)

    with left:
        if category:
            df = pd.DataFrame(category)

            st.plotly_chart(
                px.bar(df, x="category", y="count", title="Assets by Category"),
                width="stretch",
            )

    with right:
        if location:
            df = pd.DataFrame(location)

            st.plotly_chart(
                px.pie(
                    df, names="location", values="count", title="Assets by Location"
                ),
                width="stretch",
            )

    if condition:
        df = pd.DataFrame(condition)

        st.plotly_chart(
            px.bar(df, x="condition", y="count", title="Asset Condition"),
            width="stretch",
        )

    records = get_api("/assets/records")

    show_asset_table(records)
elif page == "Maintenance":
    st.header("🔧 Maintenance Management")

    summary = get_api("/maintenance/summary")

    if summary:
        cols = st.columns(6)

        cols[0].metric("Records", summary["total_records"])

        cols[1].metric("Open", summary["open_records"])

        cols[2].metric("In Progress", summary["in_progress_records"])

        cols[3].metric("Completed", summary["completed_records"])

        cols[4].metric("Total Cost", f"${summary['total_cost']:,.2f}")

        cols[5].metric("Average Cost", f"${summary['average_cost']:,.2f}")

    status = get_api("/maintenance/by-status")

    category = get_api("/maintenance/cost-by-category")

    left, right = st.columns(2)

    with left:
        if status:
            df = pd.DataFrame(status)

            st.plotly_chart(
                px.bar(df, x="status", y="count", title="Maintenance by Status"),
                width="stretch",
            )

    with right:
        if category:
            df = pd.DataFrame(category)

            st.plotly_chart(
                px.bar(
                    df,
                    x="category",
                    y="total_cost",
                    title="Maintenance Cost by Category",
                ),
                width="stretch",
            )

    costs = get_api("/maintenance/cost-by-asset")

    if costs:
        df = pd.DataFrame(costs)

        st.plotly_chart(
            px.bar(
                df,
                x="asset_name",
                y="total_cost",
                title="Highest Maintenance Cost Assets",
            ),
            width="stretch",
        )

    records = get_api("/maintenance/records")

    show_maintenance_table(records)
elif page == "Finance":
    st.header("💰 Financial Overview")

    range_label, params = get_date_params()

    summary = get_api("/finance/summary", params=params)

    if summary:
        cols = st.columns(5)

        cols[0].metric("Donation Income", f"${summary['donation_income']:,.2f}")

        cols[1].metric("Maintenance Expense", f"${summary['maintenance_expense']:,.2f}")

        cols[2].metric("Operating Amount", f"${summary['net_operating_amount']:,.2f}")

        cols[3].metric("Asset Value", f"${summary['asset_value']:,.2f}")

        cols[4].metric(
            "Maintenance / Income", f"{summary['maintenance_to_income_ratio']:.1f}%"
        )

        st.caption(
            "Operating Amount = Donation Income − Maintenance Expense. "
            "This prototype does not represent full accounting profit."
        )

    daily = get_api("/finance/daily", params=params)

    if daily:
        df = pd.DataFrame(daily)

        fig = px.line(
            df,
            x="date",
            y=["income", "expense", "net"],
            markers=True,
            title="Financial Activity",
        )

        st.plotly_chart(fig, width="stretch")

    income_category = get_api("/finance/income-by-category", params=params)

    expense_category = get_api("/finance/expense-by-category", params=params)

    left, right = st.columns(2)

    with left:
        if income_category:
            df = pd.DataFrame(income_category)

            st.plotly_chart(
                px.bar(
                    df, x="category", y="income", title="Income by Donation Category"
                ),
                width="stretch",
            )

    with right:
        if expense_category:
            df = pd.DataFrame(expense_category)

            st.plotly_chart(
                px.bar(
                    df,
                    x="category",
                    y="expense",
                    title="Maintenance Expense by Category",
                ),
                width="stretch",
            )

    campaigns = get_api("/finance/campaigns")

    if campaigns:
        st.subheader("Campaign Performance")

        campaign_df = pd.DataFrame(campaigns)

        campaign_long = campaign_df[
            ["campaign_name", "target_amount", "raised_amount"]
        ].melt(id_vars=["campaign_name"], var_name="metric", value_name="amount")

        st.plotly_chart(
            px.bar(
                campaign_long,
                x="campaign_name",
                y="amount",
                color="metric",
                barmode="group",
                title="Campaign Target vs Raised",
            ),
            width="stretch",
        )

        st.dataframe(campaign_df, width="stretch", hide_index=True)

elif page == "AI Analyst":
    st.header("✨ AI Temple Analyst")

    st.write("""
Ask questions about donations, assets, maintenance, or finance.

The AI decides what data it needs, queries PostgreSQL directly (it can
look up more than one thing before answering), and explains the result
using only the real numbers it retrieved.
""")
    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = []
    header_left, header_right = st.columns([5, 1])

    with header_right:
        if st.button("Clear Chat", key="clear_ai_chat"):
            st.session_state.ai_messages = []
            st.rerun()
    if not st.session_state.ai_messages:
        st.info("""
👋 **Ready when you are.**

Ask anything about donations, assets, maintenance, or finance.
""")

    def format_metric_value(label, value):
        if not isinstance(value, (int, float)):
            return str(value)

        if "count" in str(label).lower():
            return f"{int(value):,}"

        return f"${value:,.2f}"

    def render_ai_result(result, message_index):
        title = result.get("title") or "AI Analysis"
        explanation = result.get("explanation")
        chart = result.get("chart")
        steps = result.get("steps") or []

        with st.expander("How the AI got this answer"):
            if steps:
                for step_index, step in enumerate(steps, start=1):
                    st.caption(f"Step {step_index}: called `{step['tool']}`")
                    st.json(step.get("args", {}))
            else:
                st.caption("No data lookup was needed for this response.")

        st.subheader(title)

        if chart and chart.get("data"):
            chart_type = chart.get("type")
            data = chart["data"]

            if chart_type == "metric":
                cols = st.columns(len(data))

                for col, item in zip(cols, data):
                    label = str(item.get("label", "")).replace("_", " ").title()
                    col.metric(label, format_metric_value(item.get("label"), item.get("value")))

            elif chart_type == "table":
                df = pd.DataFrame(data)

                if not df.empty:
                    st.dataframe(df, width="stretch", hide_index=True)
                else:
                    st.info("No matching records found.")

            elif chart_type in {"bar", "line", "pie"}:
                df = pd.DataFrame(data)

                if {"group", "value"}.issubset(df.columns) and not df.empty:
                    if chart_type == "bar":
                        fig = px.bar(df, x="group", y="value", title=title)
                    elif chart_type == "line":
                        fig = px.line(df, x="group", y="value", markers=True, title=title)
                    else:
                        fig = px.pie(df, names="group", values="value", title=title)

                    st.plotly_chart(
                        fig, width="stretch", key=f"ai_chart_{message_index}"
                    )
                elif not df.empty:
                    st.dataframe(df, width="stretch", hide_index=True)
                else:
                    st.info("No matching data found.")
        else:
            st.info("No chart-worthy data was retrieved for this response.")

        if explanation:
            st.divider()
            st.markdown("### 🧠 What This Means")
            st.info(explanation)

        follow_up_questions = result.get("follow_up_questions") or []

        if follow_up_questions:
            st.caption("Suggested follow-up questions")

            cols = st.columns(len(follow_up_questions))

            for suggestion_index, (col, suggestion) in enumerate(
                zip(cols, follow_up_questions)
            ):
                with col:
                    if st.button(
                        suggestion,
                        key=f"followup_{message_index}_{suggestion_index}",
                        width="stretch",
                    ):
                        ask_question(suggestion)

        st.markdown("""
---
### ✅ Analysis complete — ready for your next question

Ask another question below. You can switch between **donations,
assets, maintenance, and finance** at any time.
""")

    # Sends the last few Q&A pairs to the backend so the LLM can
    # resolve follow-ups like "what about the second one".

    def build_history_payload(limit=4):
        history = []

        messages = st.session_state.ai_messages

        i = 0

        while i < len(messages) - 1:
            current = messages[i]
            next_message = messages[i + 1]

            if (
                current.get("role") == "user"
                and next_message.get("role") == "assistant"
            ):
                prior_result = next_message.get("result") or {}

                history.append(
                    {
                        "question": current.get("content", ""),
                        "explanation": prior_result.get("explanation"),
                    }
                )

                i += 2

            else:
                i += 1

        return history[-limit:]

    def ask_question(question_text):
        history_payload = build_history_payload()

        st.session_state.ai_messages.append({"role": "user", "content": question_text})

        with st.spinner("Analyzing PostgreSQL data..."):
            result = post_api(
                "/ai/query", {"question": question_text, "history": history_payload}
            )

        if result:
            st.session_state.ai_messages.append({"role": "assistant", "result": result})

        else:
            st.session_state.ai_messages.append(
                {
                    "role": "assistant",
                    "result": {
                        "title": "Unable to Complete Analysis",
                        "explanation": (
                            "The analysis request could not be completed. "
                            "Please try again or rephrase the question."
                        ),
                        "chart": None,
                        "follow_up_questions": [],
                        "steps": [],
                    },
                }
            )

        st.rerun()

    for message_index, message in enumerate(st.session_state.ai_messages):
        role = message.get("role")

        if role == "user":
            with st.chat_message("user"):
                st.markdown(message.get("content", ""))

        elif role == "assistant":
            result = message.get("result")

            if not result:
                continue

            with st.chat_message("assistant"):
                render_ai_result(result, message_index)
    question = st.chat_input("Ask your next question...")

    if question:
        ask_question(question)

from datetime import date, timedelta

from sqlalchemy import and_, func, or_

from backend.app.models import Asset, Campaign, Donation, Donor, MaintenanceRecord, Vendor


OPERATORS = {
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

PERIODS = {"today", "yesterday", "7d", "14d", "30d", "45d", "all"}


TABLE_CATALOG = {
    "donations": {
        "model": Donation,
        "date_field": "donation_date",
        "columns": {
            "amount": Donation.amount,
            "category": Donation.category,
            "payment_method": Donation.payment_method,
            "location": Donation.location,
            "is_anonymous": Donation.is_anonymous,
            "donation_date": Donation.donation_date,
        },
        "numeric_columns": {"amount"},
        "joined_columns": {
            "campaign_name": {
                "join_model": Campaign,
                "join_condition": lambda: Donation.campaign_id == Campaign.id,
                "column": lambda: func.coalesce(Campaign.name, "No Campaign"),
                "empty_values": {"No Campaign"},
            },
            "donor_name": {
                "join_model": Donor,
                "join_condition": lambda: Donation.donor_id == Donor.id,
                "column": lambda: func.coalesce(Donor.name, "Unknown Donor"),
                "empty_values": {"Unknown Donor"},
            },
        },
        "id_column": Donation.id,
        "list_columns": {
            "donation_number": Donation.donation_number,
            "amount": Donation.amount,
            "donation_date": Donation.donation_date,
            "category": Donation.category,
            "payment_method": Donation.payment_method,
            "location": Donation.location,
        },
    },
    "assets": {
        "model": Asset,
        "date_field": "purchase_date",
        "columns": {
            "current_value": Asset.current_value,
            "purchase_cost": Asset.purchase_cost,
            "category": Asset.category,
            "location": Asset.location,
            "condition": Asset.condition,
            "status": Asset.status,
            "purchase_date": Asset.purchase_date,
            "warranty_expiry": Asset.warranty_expiry,
            "last_inspection_date": Asset.last_inspection_date,
            "next_inspection_date": Asset.next_inspection_date,
        },
        "numeric_columns": {"current_value", "purchase_cost"},
        "joined_columns": {
            "vendor_name": {
                "join_model": Vendor,
                "join_condition": lambda: Asset.vendor_id == Vendor.id,
                "column": lambda: func.coalesce(Vendor.name, "No Vendor"),
                "empty_values": {"No Vendor"},
            },
        },
        "id_column": Asset.id,
        "list_columns": {
            "asset_tag": Asset.asset_tag,
            "name": Asset.name,
            "category": Asset.category,
            "location": Asset.location,
            "condition": Asset.condition,
            "status": Asset.status,
            "current_value": Asset.current_value,
        },
    },
    "maintenance_records": {
        "model": MaintenanceRecord,
        "date_field": "start_date",
        "columns": {
            "cost": MaintenanceRecord.cost,
            "status": MaintenanceRecord.status,
            "maintenance_type": MaintenanceRecord.maintenance_type,
            "start_date": MaintenanceRecord.start_date,
            "completion_date": MaintenanceRecord.completion_date,
        },
        "numeric_columns": {"cost"},
        "joined_columns": {
            "asset_name": {
                "join_model": Asset,
                "join_condition": lambda: MaintenanceRecord.asset_id == Asset.id,
                "column": lambda: func.coalesce(Asset.name, "Unknown Asset"),
                "empty_values": {"Unknown Asset"},
            },
            "asset_category": {
                "join_model": Asset,
                "join_condition": lambda: MaintenanceRecord.asset_id == Asset.id,
                "column": lambda: func.coalesce(Asset.category, "Unknown Category"),
                "empty_values": {"Unknown Category"},
            },
            "vendor_name": {
                "join_model": Vendor,
                "join_condition": lambda: MaintenanceRecord.vendor_id == Vendor.id,
                "column": lambda: func.coalesce(Vendor.name, "No Vendor"),
                "empty_values": {"No Vendor"},
            },
        },
        "id_column": MaintenanceRecord.id,
        "list_columns": {
            "description": MaintenanceRecord.description,
            "maintenance_type": MaintenanceRecord.maintenance_type,
            "cost": MaintenanceRecord.cost,
            "start_date": MaintenanceRecord.start_date,
            "completion_date": MaintenanceRecord.completion_date,
            "status": MaintenanceRecord.status,
        },
    },
}


def resolve_column(table_name, field_name):
    entry = TABLE_CATALOG.get(table_name)

    if entry is None:
        return None, None

    if field_name in entry["columns"]:
        return entry["columns"][field_name], None

    joined = entry["joined_columns"].get(field_name)

    if joined is not None:
        return joined["column"](), joined

    return None, None


def resolve_period(period, start_date=None, end_date=None):
    today = date.today()

    if period == "today":
        return today, today

    if period == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday

    if period == "7d":
        return today - timedelta(days=6), today

    if period == "14d":
        return today - timedelta(days=13), today

    if period == "30d":
        return today - timedelta(days=29), today

    if period == "45d":
        return today - timedelta(days=44), today

    if period == "custom" and start_date and end_date:
        return start_date, end_date

    return None, None


def build_filter_condition(column, operator, value):
    if operator == "equals":
        return column == value

    if operator == "not_equals":
        return column != value

    if operator == "in":
        if not isinstance(value, list):
            return None
        return column.in_(value)

    if operator == "greater_than":
        return column > value

    if operator == "less_than":
        return column < value

    if operator == "before_today":
        return column < date.today()

    if operator == "after_today":
        return column > date.today()

    if operator == "within_last_days":
        if not isinstance(value, int):
            return None
        today = date.today()
        return and_(column >= today - timedelta(days=value), column <= today)

    if operator == "within_next_days":
        if not isinstance(value, int):
            return None
        today = date.today()
        return and_(column >= today, column <= today + timedelta(days=value))

    if operator == "contains":
        if not isinstance(value, str):
            return None
        return column.ilike(f"%{value}%")

    return None


def execute_table_query(db, spec):
    table_name = spec.get("table")
    entry = TABLE_CATALOG.get(table_name)

    if entry is None:
        return {"error": f"Unknown table '{table_name}'."}

    model = entry["model"]
    mode = spec.get("mode", "aggregate")

    needed_joins = set()

    def resolve(field_name):
        col, joined = resolve_column(table_name, field_name)
        if joined is not None:
            needed_joins.add(field_name)
        return col

    conditions = []

    for item in spec.get("filters") or []:
        if not isinstance(item, dict):
            continue

        field = item.get("field")
        operator = item.get("operator")

        if field not in entry["columns"] and field not in entry["joined_columns"]:
            continue

        if operator not in OPERATORS:
            continue

        col = resolve(field)
        condition = build_filter_condition(col, operator, item.get("value"))

        if condition is not None:
            conditions.append(condition)

    period = spec.get("period")

    if period and period != "all":
        start, end = resolve_period(period, spec.get("start_date"), spec.get("end_date"))

        if start and end:
            date_col = entry["columns"][entry["date_field"]]
            conditions.append(date_col >= start)
            conditions.append(date_col <= end)

    filter_logic = spec.get("filter_logic", "AND")

    def apply_joins(query):
        for field_name in needed_joins:
            joined = entry["joined_columns"][field_name]
            query = query.outerjoin(joined["join_model"], joined["join_condition"]())
        return query

    def apply_filters(query):
        if not conditions:
            return query
        if filter_logic == "OR":
            return query.filter(or_(*conditions))
        return query.filter(and_(*conditions))

    if mode == "list":
        query = db.query(model)
        query = apply_joins(query)
        query = apply_filters(query)

        limit = spec.get("limit") or 20
        limit = max(1, min(int(limit), 100))

        rows = query.limit(limit).all()

        list_columns = entry["list_columns"]

        data = []

        for row in rows:
            record = {}
            for col_name, col_attr in list_columns.items():
                value = getattr(row, col_name, None)
                if hasattr(value, "isoformat"):
                    value = str(value)
                elif value is not None and col_name in entry["numeric_columns"]:
                    value = float(value)
                record[col_name] = value
            data.append(record)

        return {"mode": "list", "row_count": len(data), "rows": data}

    metric_column_name = spec.get("metric_column")
    metric_aggregation = spec.get("metric_aggregation", "count")

    if metric_column_name and metric_column_name in entry["numeric_columns"]:
        metric_col = entry["columns"][metric_column_name]
    else:
        metric_column_name = None
        metric_col = entry["id_column"]
        metric_aggregation = "count"

    agg_funcs = {
        "sum": func.sum,
        "count": func.count,
        "avg": func.avg,
        "min": func.min,
        "max": func.max,
    }

    if metric_aggregation not in agg_funcs:
        metric_aggregation = "sum" if metric_column_name else "count"

    agg_func = agg_funcs[metric_aggregation]
    agg_expr = func.coalesce(agg_func(metric_col), 0)

    group_by_field = spec.get("group_by")

    if group_by_field:
        group_col = resolve(group_by_field)

        if group_col is None:
            group_by_field = None

    if group_by_field:
        query = db.query(
            group_col.label("group"),
            agg_expr.label("value"),
            func.count(entry["id_column"]).label("count"),
        )
        query = apply_joins(query)
        query = apply_filters(query)
        query = query.group_by(group_col)

        order = spec.get("order", "desc")
        query = query.order_by(agg_expr.desc() if order != "asc" else agg_expr.asc())

        limit = spec.get("limit") or 25
        limit = max(1, min(int(limit), 100))
        query = query.limit(limit)

        rows = query.all()

        results = [
            {"group": str(row.group), "value": float(row.value), "count": row.count}
            for row in rows
        ]

        if spec.get("exclude_empty_groups") and group_by_field in entry["joined_columns"]:
            empty_values = entry["joined_columns"][group_by_field]["empty_values"]
            results = [r for r in results if r["group"] not in empty_values]

        return {
            "mode": "aggregate",
            "group_by": group_by_field,
            "metric": metric_column_name or "count",
            "aggregation": metric_aggregation,
            "rows": results,
        }

    query = db.query(agg_expr, func.count(entry["id_column"]))
    query = apply_joins(query)
    query = apply_filters(query)

    value, count = query.one()

    return {
        "mode": "aggregate",
        "group_by": None,
        "metric": metric_column_name or "count",
        "aggregation": metric_aggregation,
        "value": float(value),
        "count": count,
    }


def execute_finance_summary(db, period="30d", start_date=None, end_date=None):
    start, end = resolve_period(period, start_date, end_date)

    if not start or not end:
        start, end = resolve_period("30d")

    donation_income = (
        db.query(func.coalesce(func.sum(Donation.amount), 0))
        .filter(Donation.donation_date >= start, Donation.donation_date <= end)
        .scalar()
    )

    maintenance_expense = (
        db.query(func.coalesce(func.sum(MaintenanceRecord.cost), 0))
        .filter(
            MaintenanceRecord.start_date >= start, MaintenanceRecord.start_date <= end
        )
        .scalar()
    )

    asset_value = db.query(func.coalesce(func.sum(Asset.current_value), 0)).scalar()

    donation_income = float(donation_income)
    maintenance_expense = float(maintenance_expense)

    return {
        "period": period,
        "start_date": str(start),
        "end_date": str(end),
        "donation_income": donation_income,
        "maintenance_expense": maintenance_expense,
        "operating_amount": round(donation_income - maintenance_expense, 2),
        "asset_value": float(asset_value),
    }


def execute_campaign_performance(db):
    campaigns = db.query(Campaign).order_by(Campaign.name).all()

    result = []

    for campaign in campaigns:
        raised = (
            db.query(func.coalesce(func.sum(Donation.amount), 0))
            .filter(Donation.campaign_id == campaign.id)
            .scalar()
        )

        target = float(campaign.target_amount) if campaign.target_amount else 0
        raised_value = float(raised)
        progress = (raised_value / target * 100) if target > 0 else 0

        result.append(
            {
                "campaign_name": campaign.name,
                "status": campaign.status,
                "target_amount": target,
                "raised_amount": raised_value,
                "progress_percent": round(progress, 2),
            }
        )

    return result

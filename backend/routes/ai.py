from datetime import date, timedelta

from typing import List, Optional

from fastapi import APIRouter, Depends

from pydantic import BaseModel

from sqlalchemy import and_, func, or_

from sqlalchemy.orm import Session, selectinload

from backend.app.ai_service import explain_result, understand_query

from backend.app.database import get_db

from backend.app.models import Asset, Campaign, Donation, MaintenanceRecord, Vendor

from backend.routes.donations import get_date_range

router = APIRouter(prefix="/ai", tags=["AI"])


class ChatTurn(BaseModel):
    question: str
    explanation: Optional[str] = None


class AIQuery(BaseModel):
    question: str
    history: Optional[List[ChatTurn]] = None


def serialize_donation(donation: Donation):
    if donation.is_anonymous:
        donor_name = "Anonymous"

    elif donation.donor:
        donor_name = donation.donor.name

    else:
        donor_name = "Unknown"

    campaign_name = donation.campaign.name if donation.campaign else None

    return {
        "donation_number": donation.donation_number,
        "donor_name": donor_name,
        "amount": float(donation.amount),
        "date": str(donation.donation_date),
        "category": donation.category,
        "payment_method": donation.payment_method,
        "location": donation.location,
        "campaign": campaign_name,
    }


def serialize_asset(asset: Asset):
    return {
        "asset_tag": asset.asset_tag,
        "name": asset.name,
        "category": asset.category,
        "location": asset.location,
        "condition": asset.condition,
        "status": asset.status,
        "purchase_cost": float(asset.purchase_cost or 0),
        "current_value": float(asset.current_value or 0),
        "purchase_date": (str(asset.purchase_date) if asset.purchase_date else None),
        "warranty_expiry": (
            str(asset.warranty_expiry) if asset.warranty_expiry else None
        ),
        "last_inspection_date": (
            str(asset.last_inspection_date) if asset.last_inspection_date else None
        ),
        "next_inspection_date": (
            str(asset.next_inspection_date) if asset.next_inspection_date else None
        ),
    }


def serialize_maintenance(record: MaintenanceRecord):
    return {
        "id": record.id,
        "asset_tag": (record.asset.asset_tag if record.asset else None),
        "asset_name": (record.asset.name if record.asset else "Unknown"),
        "asset_category": (record.asset.category if record.asset else None),
        "asset_location": (record.asset.location if record.asset else None),
        "vendor_name": (record.vendor.name if record.vendor else "Unknown"),
        "maintenance_type": record.maintenance_type,
        "description": record.description,
        "cost": float(record.cost or 0),
        "start_date": (str(record.start_date) if record.start_date else None),
        "completion_date": (
            str(record.completion_date) if record.completion_date else None
        ),
        "status": record.status,
        "notes": record.notes,
    }


def build_asset_filter(filter_item):
    columns = {
        "condition": Asset.condition,
        "status": Asset.status,
        "location": Asset.location,
        "category": Asset.category,
        "current_value": Asset.current_value,
        "purchase_cost": Asset.purchase_cost,
        "purchase_date": Asset.purchase_date,
        "warranty_expiry": Asset.warranty_expiry,
        "last_inspection_date": Asset.last_inspection_date,
        "next_inspection_date": Asset.next_inspection_date,
    }

    column = columns.get(filter_item.get("field"))

    if column is None:
        return None

    operator = filter_item.get("operator")

    value = filter_item.get("value")

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

    if operator == "within_next_days":
        if not isinstance(value, int):
            return None

        today = date.today()

        return and_(column >= today, column <= (today + timedelta(days=value)))

    return None


def build_maintenance_filter(filter_item):
    columns = {
        "status": MaintenanceRecord.status,
        "maintenance_type": MaintenanceRecord.maintenance_type,
        "cost": MaintenanceRecord.cost,
        "start_date": MaintenanceRecord.start_date,
        "completion_date": MaintenanceRecord.completion_date,
        "asset_name": Asset.name,
        "asset_tag": Asset.asset_tag,
        "asset_category": Asset.category,
        "asset_location": Asset.location,
        "vendor_name": Vendor.name,
    }

    column = columns.get(filter_item.get("field"))

    if column is None:
        return None

    operator = filter_item.get("operator")

    value = filter_item.get("value")

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

        return and_(column >= (today - timedelta(days=value)), column <= today)

    if operator == "within_next_days":
        if not isinstance(value, int):
            return None

        today = date.today()

        return and_(column >= today, column <= (today + timedelta(days=value)))

    if operator == "contains":
        if not isinstance(value, str):
            return None

        return column.ilike(f"%{value}%")

    return None


@router.post("/query")
def ai_query(request: AIQuery, db: Session = Depends(get_db)):
    history_payload = (
        [turn.model_dump() for turn in request.history] if request.history else None
    )

    intent = understand_query(request.question, history=history_payload)

    domain = intent.get("domain")

    analysis = intent.get("analysis")

    data = None
    response_date_range = None
    if domain == "donations":
        period = intent.get("period") or "30d"

        start_date, end_date = get_date_range(period)

        response_date_range = {"start_date": str(start_date), "end_date": str(end_date)}

        base_query = (
            db.query(Donation)
            .options(selectinload(Donation.donor), selectinload(Donation.campaign))
            .filter(
                Donation.donation_date >= start_date, Donation.donation_date <= end_date
            )
        )

        if analysis == "summary":
            total = base_query.with_entities(
                func.coalesce(func.sum(Donation.amount), 0)
            ).scalar()

            count = base_query.count()

            average = float(total) / count if count else 0

            largest = base_query.with_entities(
                func.coalesce(func.max(Donation.amount), 0)
            ).scalar()

            donations = base_query.order_by(Donation.amount.desc()).all()

            data = {
                "total": float(total),
                "count": count,
                "average": round(average, 2),
                "largest": float(largest),
                "records": [serialize_donation(donation) for donation in donations],
            }

        elif analysis == "trend":
            results = (
                db.query(
                    Donation.donation_date,
                    func.sum(Donation.amount).label("total"),
                    func.count(Donation.id).label("count"),
                )
                .filter(
                    Donation.donation_date >= start_date,
                    Donation.donation_date <= end_date,
                )
                .group_by(Donation.donation_date)
                .order_by(Donation.donation_date)
                .all()
            )

            data = [
                {
                    "date": str(row.donation_date),
                    "total": float(row.total),
                    "count": row.count,
                }
                for row in results
            ]

        elif analysis == "category":
            results = (
                db.query(
                    Donation.category,
                    func.sum(Donation.amount).label("total"),
                    func.count(Donation.id).label("count"),
                )
                .filter(
                    Donation.donation_date >= start_date,
                    Donation.donation_date <= end_date,
                )
                .group_by(Donation.category)
                .order_by(func.sum(Donation.amount).desc())
                .all()
            )

            data = [
                {
                    "category": row.category,
                    "total": float(row.total),
                    "count": row.count,
                }
                for row in results
            ]

        elif analysis == "campaign":
            results = (
                db.query(
                    func.coalesce(Campaign.name, "No Campaign").label("campaign"),
                    func.sum(Donation.amount).label("total"),
                    func.count(Donation.id).label("count"),
                )
                .outerjoin(Campaign, Donation.campaign_id == Campaign.id)
                .filter(
                    Donation.donation_date >= start_date,
                    Donation.donation_date <= end_date,
                )
                .group_by(Campaign.name)
                .order_by(func.sum(Donation.amount).desc())
                .all()
            )

            data = [
                {
                    "campaign": row.campaign,
                    "total": float(row.total),
                    "count": row.count,
                }
                for row in results
            ]

        elif analysis == "location":
            results = (
                db.query(
                    Donation.location,
                    func.sum(Donation.amount).label("total"),
                    func.count(Donation.id).label("count"),
                )
                .filter(
                    Donation.donation_date >= start_date,
                    Donation.donation_date <= end_date,
                )
                .group_by(Donation.location)
                .order_by(func.sum(Donation.amount).desc())
                .all()
            )

            data = [
                {
                    "location": row.location or "Unknown",
                    "total": float(row.total),
                    "count": row.count,
                }
                for row in results
            ]

        elif analysis == "payment_method":
            results = (
                db.query(
                    Donation.payment_method,
                    func.sum(Donation.amount).label("total"),
                    func.count(Donation.id).label("count"),
                )
                .filter(
                    Donation.donation_date >= start_date,
                    Donation.donation_date <= end_date,
                )
                .group_by(Donation.payment_method)
                .order_by(func.sum(Donation.amount).desc())
                .all()
            )

            data = [
                {
                    "payment_method": row.payment_method,
                    "total": float(row.total),
                    "count": row.count,
                }
                for row in results
            ]

        elif analysis == "top_donations":
            donations = base_query.order_by(Donation.amount.desc()).limit(20).all()

            data = [serialize_donation(donation) for donation in donations]
    elif domain == "assets":
        if analysis == "asset_summary":
            total_assets = db.query(Asset).count()

            total_value = db.query(
                func.coalesce(func.sum(Asset.current_value), 0)
            ).scalar()

            under_maintenance = (
                db.query(Asset).filter(Asset.status == "UNDER_MAINTENANCE").count()
            )

            poor_condition = db.query(Asset).filter(Asset.condition == "POOR").count()

            damaged_assets = (
                db.query(Asset).filter(Asset.condition == "DAMAGED").count()
            )

            data = {
                "total_assets": total_assets,
                "total_value": float(total_value),
                "under_maintenance": under_maintenance,
                "poor_condition": poor_condition,
                "damaged_assets": damaged_assets,
            }

        elif analysis == "asset_list":
            query = db.query(Asset)

            conditions = []

            for item in intent.get("filters", []):
                condition = build_asset_filter(item)

                if condition is not None:
                    conditions.append(condition)

            if conditions:
                if intent.get("filter_logic") == "OR":
                    query = query.filter(or_(*conditions))

                else:
                    query = query.filter(and_(*conditions))

            assets = query.order_by(Asset.asset_tag).all()

            data = [serialize_asset(asset) for asset in assets]

        elif analysis == "asset_category":
            results = (
                db.query(Asset.category, func.count(Asset.id).label("count"))
                .group_by(Asset.category)
                .order_by(func.count(Asset.id).desc())
                .all()
            )

            data = [{"category": row.category, "count": row.count} for row in results]

        elif analysis == "asset_location":
            results = (
                db.query(Asset.location, func.count(Asset.id).label("count"))
                .group_by(Asset.location)
                .order_by(func.count(Asset.id).desc())
                .all()
            )

            data = [
                {"location": (row.location or "Unknown"), "count": row.count}
                for row in results
            ]

        elif analysis == "asset_condition":
            results = (
                db.query(Asset.condition, func.count(Asset.id).label("count"))
                .group_by(Asset.condition)
                .order_by(func.count(Asset.id).desc())
                .all()
            )

            data = [
                {"condition": (row.condition or "Unknown"), "count": row.count}
                for row in results
            ]

        elif analysis == "asset_value":
            results = (
                db.query(
                    Asset.category,
                    func.coalesce(func.sum(Asset.current_value), 0).label("value"),
                )
                .group_by(Asset.category)
                .order_by(func.sum(Asset.current_value).desc())
                .all()
            )

            data = [
                {"category": row.category, "value": float(row.value)} for row in results
            ]
    elif domain == "maintenance":
        if analysis == "maintenance_summary":
            total_records = db.query(MaintenanceRecord).count()

            total_cost = db.query(
                func.coalesce(func.sum(MaintenanceRecord.cost), 0)
            ).scalar()

            open_records = (
                db.query(MaintenanceRecord)
                .filter(MaintenanceRecord.status == "OPEN")
                .count()
            )

            in_progress = (
                db.query(MaintenanceRecord)
                .filter(MaintenanceRecord.status == "IN_PROGRESS")
                .count()
            )

            completed = (
                db.query(MaintenanceRecord)
                .filter(MaintenanceRecord.status == "COMPLETED")
                .count()
            )

            average_cost = float(total_cost) / total_records if total_records else 0

            data = {
                "total_records": total_records,
                "open_records": open_records,
                "in_progress_records": in_progress,
                "completed_records": completed,
                "total_cost": float(total_cost),
                "average_cost": round(average_cost, 2),
            }

        elif analysis == "maintenance_list":
            query = (
                db.query(MaintenanceRecord)
                .options(
                    selectinload(MaintenanceRecord.asset),
                    selectinload(MaintenanceRecord.vendor),
                )
                .outerjoin(Asset, MaintenanceRecord.asset_id == Asset.id)
                .outerjoin(Vendor, MaintenanceRecord.vendor_id == Vendor.id)
            )

            conditions = []

            for item in intent.get("filters", []):
                condition = build_maintenance_filter(item)

                if condition is not None:
                    conditions.append(condition)

            if conditions:
                if intent.get("filter_logic") == "OR":
                    query = query.filter(or_(*conditions))

                else:
                    query = query.filter(and_(*conditions))

            records = query.order_by(
                MaintenanceRecord.start_date.desc(), MaintenanceRecord.id.desc()
            ).all()

            data = [serialize_maintenance(record) for record in records]

        elif analysis == "maintenance_status":
            results = (
                db.query(
                    MaintenanceRecord.status,
                    func.count(MaintenanceRecord.id).label("count"),
                    func.coalesce(func.sum(MaintenanceRecord.cost), 0).label("cost"),
                )
                .group_by(MaintenanceRecord.status)
                .all()
            )

            data = [
                {
                    "status": row.status or "UNKNOWN",
                    "count": row.count,
                    "cost": float(row.cost),
                }
                for row in results
            ]

        elif analysis == "maintenance_cost_asset":
            results = (
                db.query(
                    Asset.asset_tag,
                    Asset.name,
                    func.sum(MaintenanceRecord.cost).label("total_cost"),
                    func.count(MaintenanceRecord.id).label("maintenance_count"),
                )
                .join(MaintenanceRecord, MaintenanceRecord.asset_id == Asset.id)
                .group_by(Asset.id, Asset.asset_tag, Asset.name)
                .order_by(func.sum(MaintenanceRecord.cost).desc())
                .limit(20)
                .all()
            )

            data = [
                {
                    "asset_tag": row.asset_tag,
                    "asset_name": row.name,
                    "total_cost": float(row.total_cost or 0),
                    "maintenance_count": row.maintenance_count,
                }
                for row in results
            ]

        elif analysis == "maintenance_cost_vendor":
            results = (
                db.query(
                    Vendor.name,
                    func.sum(MaintenanceRecord.cost).label("total_cost"),
                    func.count(MaintenanceRecord.id).label("maintenance_count"),
                )
                .join(MaintenanceRecord, MaintenanceRecord.vendor_id == Vendor.id)
                .group_by(Vendor.id, Vendor.name)
                .order_by(func.sum(MaintenanceRecord.cost).desc())
                .all()
            )

            data = [
                {
                    "vendor_name": row.name,
                    "total_cost": float(row.total_cost or 0),
                    "maintenance_count": row.maintenance_count,
                }
                for row in results
            ]

        elif analysis == "maintenance_cost_category":
            results = (
                db.query(
                    Asset.category,
                    func.sum(MaintenanceRecord.cost).label("total_cost"),
                    func.count(MaintenanceRecord.id).label("maintenance_count"),
                )
                .join(MaintenanceRecord, MaintenanceRecord.asset_id == Asset.id)
                .group_by(Asset.category)
                .order_by(func.sum(MaintenanceRecord.cost).desc())
                .all()
            )

            data = [
                {
                    "category": row.category,
                    "total_cost": float(row.total_cost or 0),
                    "maintenance_count": row.maintenance_count,
                }
                for row in results
            ]

        elif analysis == "maintenance_type":
            results = (
                db.query(
                    MaintenanceRecord.maintenance_type,
                    func.count(MaintenanceRecord.id).label("count"),
                    func.sum(MaintenanceRecord.cost).label("total_cost"),
                )
                .group_by(MaintenanceRecord.maintenance_type)
                .order_by(func.count(MaintenanceRecord.id).desc())
                .all()
            )

            data = [
                {
                    "maintenance_type": (row.maintenance_type or "Unknown"),
                    "count": row.count,
                    "total_cost": float(row.total_cost or 0),
                }
                for row in results
            ]
    elif domain == "finance":
        period = intent.get("period") or "30d"

        start_date, end_date = get_date_range(period)

        response_date_range = {"start_date": str(start_date), "end_date": str(end_date)}

        if analysis == "finance_summary":
            donation_income = (
                db.query(func.coalesce(func.sum(Donation.amount), 0))
                .filter(
                    Donation.donation_date >= start_date,
                    Donation.donation_date <= end_date,
                )
                .scalar()
            )

            maintenance_expense = (
                db.query(func.coalesce(func.sum(MaintenanceRecord.cost), 0))
                .filter(
                    MaintenanceRecord.start_date >= start_date,
                    MaintenanceRecord.start_date <= end_date,
                )
                .scalar()
            )

            asset_value = db.query(
                func.coalesce(func.sum(Asset.current_value), 0)
            ).scalar()

            donation_income = float(donation_income)

            maintenance_expense = float(maintenance_expense)

            operating_amount = donation_income - maintenance_expense

            ratio = (
                (maintenance_expense / donation_income) * 100
                if donation_income > 0
                else 0
            )

            data = {
                "donation_income": donation_income,
                "maintenance_expense": maintenance_expense,
                "operating_amount": round(operating_amount, 2),
                "asset_value": float(asset_value),
                "maintenance_to_income_ratio": round(ratio, 2),
            }

        elif analysis == "finance_trend":
            donation_rows = (
                db.query(
                    Donation.donation_date.label("date"),
                    func.sum(Donation.amount).label("income"),
                )
                .filter(
                    Donation.donation_date >= start_date,
                    Donation.donation_date <= end_date,
                )
                .group_by(Donation.donation_date)
                .all()
            )

            maintenance_rows = (
                db.query(
                    MaintenanceRecord.start_date.label("date"),
                    func.sum(MaintenanceRecord.cost).label("expense"),
                )
                .filter(
                    MaintenanceRecord.start_date >= start_date,
                    MaintenanceRecord.start_date <= end_date,
                )
                .group_by(MaintenanceRecord.start_date)
                .all()
            )

            income_map = {row.date: float(row.income) for row in donation_rows}

            expense_map = {row.date: float(row.expense) for row in maintenance_rows}

            data = []

            current = start_date

            while current <= end_date:
                income = income_map.get(current, 0)

                expense = expense_map.get(current, 0)

                data.append(
                    {
                        "date": str(current),
                        "income": round(income, 2),
                        "expense": round(expense, 2),
                        "operating_amount": round(income - expense, 2),
                    }
                )

                current += timedelta(days=1)

        elif analysis == "finance_income_category":
            results = (
                db.query(
                    Donation.category,
                    func.sum(Donation.amount).label("income"),
                    func.count(Donation.id).label("donation_count"),
                )
                .filter(
                    Donation.donation_date >= start_date,
                    Donation.donation_date <= end_date,
                )
                .group_by(Donation.category)
                .order_by(func.sum(Donation.amount).desc())
                .all()
            )

            data = [
                {
                    "category": row.category,
                    "income": float(row.income),
                    "donation_count": row.donation_count,
                }
                for row in results
            ]

        elif analysis == "finance_expense_category":
            results = (
                db.query(
                    Asset.category,
                    func.sum(MaintenanceRecord.cost).label("expense"),
                    func.count(MaintenanceRecord.id).label("maintenance_count"),
                )
                .join(MaintenanceRecord, MaintenanceRecord.asset_id == Asset.id)
                .filter(
                    MaintenanceRecord.start_date >= start_date,
                    MaintenanceRecord.start_date <= end_date,
                )
                .group_by(Asset.category)
                .order_by(func.sum(MaintenanceRecord.cost).desc())
                .all()
            )

            data = [
                {
                    "category": row.category,
                    "expense": float(row.expense or 0),
                    "maintenance_count": row.maintenance_count,
                }
                for row in results
            ]

        elif analysis in {"finance_campaigns", "finance_campaign_performance"}:
            campaigns = db.query(Campaign).order_by(Campaign.name).all()

            data = []

            for campaign in campaigns:
                raised = (
                    db.query(func.coalesce(func.sum(Donation.amount), 0))
                    .filter(Donation.campaign_id == campaign.id)
                    .scalar()
                )

                target = float(campaign.target_amount or 0)

                raised = float(raised)

                progress = raised / target * 100 if target > 0 else 0

                data.append(
                    {
                        "campaign_name": campaign.name,
                        "status": campaign.status,
                        "target_amount": target,
                        "raised_amount": raised,
                        "remaining_amount": round(max(target - raised, 0), 2),
                        "progress_percent": round(progress, 2),
                        "start_date": (
                            str(campaign.start_date) if campaign.start_date else None
                        ),
                        "end_date": (
                            str(campaign.end_date) if campaign.end_date else None
                        ),
                    }
                )

            if analysis == "finance_campaign_performance":
                data = sorted(
                    data, key=lambda item: item["progress_percent"], reverse=True
                )
    result = explain_result(question=request.question, intent=intent, data=data)

    return {
        "question": request.question,
        "intent": intent,
        "date_range": response_date_range,
        "data": data,
        "explanation": result["explanation"],
        "follow_up_questions": result["follow_up_questions"],
    }

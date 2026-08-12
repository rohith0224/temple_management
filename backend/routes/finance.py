from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import Asset, Campaign, Donation, MaintenanceRecord

router = APIRouter(prefix="/finance", tags=["Finance"])


# =========================================================
# DATE RANGE
# =========================================================


def get_finance_date_range(
    period: str, start_date: Optional[date] = None, end_date: Optional[date] = None
):
    today = date.today()

    if period == "today":
        return today, today

    if period == "yesterday":
        yesterday = today - timedelta(days=1)

        return (yesterday, yesterday)

    if period == "7d":
        return (today - timedelta(days=6), today)

    if period == "14d":
        return (today - timedelta(days=13), today)

    if period == "30d":
        return (today - timedelta(days=29), today)

    if period == "45d":
        return (today - timedelta(days=44), today)

    if period == "custom":
        if start_date is None or end_date is None:
            return (today - timedelta(days=29), today)

        return (start_date, end_date)

    return (today - timedelta(days=29), today)


# =========================================================
# SUMMARY
# =========================================================


@router.get("/summary")
def finance_summary(
    period: str = Query(default="30d"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    start, end = get_finance_date_range(period, start_date, end_date)

    # -----------------------------------------------------
    # DONATION INCOME
    # -----------------------------------------------------

    donation_income = (
        db.query(func.coalesce(func.sum(Donation.amount), 0))
        .filter(Donation.donation_date >= start, Donation.donation_date <= end)
        .scalar()
    )

    # -----------------------------------------------------
    # MAINTENANCE EXPENSE
    # -----------------------------------------------------

    maintenance_expense = (
        db.query(func.coalesce(func.sum(MaintenanceRecord.cost), 0))
        .filter(
            MaintenanceRecord.start_date >= start, MaintenanceRecord.start_date <= end
        )
        .scalar()
    )

    # -----------------------------------------------------
    # CURRENT ASSET VALUE
    # -----------------------------------------------------

    asset_value = db.query(func.coalesce(func.sum(Asset.current_value), 0)).scalar()

    # -----------------------------------------------------
    # DONATION COUNT
    # -----------------------------------------------------

    donation_count = (
        db.query(Donation)
        .filter(Donation.donation_date >= start, Donation.donation_date <= end)
        .count()
    )

    # -----------------------------------------------------
    # MAINTENANCE COUNT
    # -----------------------------------------------------

    maintenance_count = (
        db.query(MaintenanceRecord)
        .filter(
            MaintenanceRecord.start_date >= start, MaintenanceRecord.start_date <= end
        )
        .count()
    )

    # -----------------------------------------------------
    # NET OPERATING AMOUNT
    # -----------------------------------------------------

    net_amount = float(donation_income) - float(maintenance_expense)

    expense_ratio = 0

    if float(donation_income) > 0:
        expense_ratio = (float(maintenance_expense) / float(donation_income)) * 100

    return {
        "period": period,
        "start_date": str(start),
        "end_date": str(end),
        "donation_income": float(donation_income),
        "maintenance_expense": float(maintenance_expense),
        "net_operating_amount": round(net_amount, 2),
        "asset_value": float(asset_value),
        "donation_count": donation_count,
        "maintenance_count": maintenance_count,
        "maintenance_to_income_ratio": round(expense_ratio, 2),
    }


# =========================================================
# DAILY CASH FLOW
# =========================================================


@router.get("/daily")
def daily_finance(
    period: str = Query(default="30d"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    start, end = get_finance_date_range(period, start_date, end_date)

    # -----------------------------------------------------
    # DONATIONS BY DAY
    # -----------------------------------------------------

    donation_rows = (
        db.query(
            Donation.donation_date.label("date"),
            func.sum(Donation.amount).label("income"),
        )
        .filter(Donation.donation_date >= start, Donation.donation_date <= end)
        .group_by(Donation.donation_date)
        .all()
    )

    # -----------------------------------------------------
    # MAINTENANCE BY DAY
    # -----------------------------------------------------

    maintenance_rows = (
        db.query(
            MaintenanceRecord.start_date.label("date"),
            func.sum(MaintenanceRecord.cost).label("expense"),
        )
        .filter(
            MaintenanceRecord.start_date >= start, MaintenanceRecord.start_date <= end
        )
        .group_by(MaintenanceRecord.start_date)
        .all()
    )

    donation_map = {row.date: float(row.income) for row in donation_rows}

    maintenance_map = {row.date: float(row.expense) for row in maintenance_rows}

    data = []

    current = start

    while current <= end:
        income = donation_map.get(current, 0)

        expense = maintenance_map.get(current, 0)

        data.append(
            {
                "date": str(current),
                "income": round(income, 2),
                "expense": round(expense, 2),
                "net": round(income - expense, 2),
            }
        )

        current += timedelta(days=1)

    return data


# =========================================================
# DONATION INCOME BY CATEGORY
# =========================================================


@router.get("/income-by-category")
def finance_income_by_category(
    period: str = Query(default="30d"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    start, end = get_finance_date_range(period, start_date, end_date)

    results = (
        db.query(
            Donation.category,
            func.sum(Donation.amount).label("income"),
            func.count(Donation.id).label("donation_count"),
        )
        .filter(Donation.donation_date >= start, Donation.donation_date <= end)
        .group_by(Donation.category)
        .order_by(func.sum(Donation.amount).desc())
        .all()
    )

    return [
        {
            "category": row.category,
            "income": float(row.income),
            "donation_count": row.donation_count,
        }
        for row in results
    ]


# =========================================================
# MAINTENANCE EXPENSE BY CATEGORY
# =========================================================


@router.get("/expense-by-category")
def finance_expense_by_category(
    period: str = Query(default="30d"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    start, end = get_finance_date_range(period, start_date, end_date)

    results = (
        db.query(
            Asset.category,
            func.coalesce(func.sum(MaintenanceRecord.cost), 0).label("expense"),
            func.count(MaintenanceRecord.id).label("maintenance_count"),
        )
        .join(MaintenanceRecord, MaintenanceRecord.asset_id == Asset.id)
        .filter(
            MaintenanceRecord.start_date >= start, MaintenanceRecord.start_date <= end
        )
        .group_by(Asset.category)
        .order_by(func.sum(MaintenanceRecord.cost).desc())
        .all()
    )

    return [
        {
            "category": row.category,
            "expense": float(row.expense),
            "maintenance_count": row.maintenance_count,
        }
        for row in results
    ]


# =========================================================
# CAMPAIGN PERFORMANCE
# =========================================================


@router.get("/campaigns")
def campaign_finance(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).order_by(Campaign.name).all()

    result = []

    for campaign in campaigns:
        raised = (
            db.query(func.coalesce(func.sum(Donation.amount), 0))
            .filter(Donation.campaign_id == campaign.id)
            .scalar()
        )

        target = (
            float(campaign.target_amount) if campaign.target_amount is not None else 0
        )

        raised_value = float(raised)

        progress = 0

        if target > 0:
            progress = (raised_value / target) * 100

        remaining = max(target - raised_value, 0)

        result.append(
            {
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "status": campaign.status,
                "target_amount": target,
                "raised_amount": raised_value,
                "remaining_amount": round(remaining, 2),
                "progress_percent": round(progress, 2),
                "start_date": (
                    str(campaign.start_date) if campaign.start_date else None
                ),
                "end_date": (str(campaign.end_date) if campaign.end_date else None),
            }
        )

    return result

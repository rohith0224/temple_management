from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from backend.app.database import get_db
from backend.app.models import Donation

router = APIRouter(prefix="/donations", tags=["Donations"])


def get_date_range(
    period: str, start_date: Optional[date] = None, end_date: Optional[date] = None
):
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

    if period == "custom":
        if not start_date or not end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date and end_date are required for custom range",
            )

        if start_date > end_date:
            raise HTTPException(
                status_code=400, detail="start_date cannot be after end_date"
            )

        return start_date, end_date

    raise HTTPException(status_code=400, detail=f"Unsupported period: {period}")


@router.get("/summary")
def donation_summary(
    period: str = Query(default="30d"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    start, end = get_date_range(period, start_date, end_date)

    base_query = db.query(Donation).filter(
        Donation.donation_date >= start, Donation.donation_date <= end
    )

    total_amount = base_query.with_entities(
        func.coalesce(func.sum(Donation.amount), 0)
    ).scalar()

    donation_count = base_query.count()

    average_donation = float(total_amount) / donation_count if donation_count else 0

    largest_donation = base_query.with_entities(
        func.coalesce(func.max(Donation.amount), 0)
    ).scalar()

    unique_donors = (
        base_query.filter(Donation.donor_id.isnot(None))
        .with_entities(Donation.donor_id)
        .distinct()
        .count()
    )

    return {
        "period": period,
        "start_date": start,
        "end_date": end,
        "total_amount": float(total_amount),
        "total_donations": donation_count,
        "average_donation": round(average_donation, 2),
        "largest_donation": float(largest_donation),
        "unique_donors": unique_donors,
    }


@router.get("/daily")
def daily_donations(
    period: str = Query(default="30d"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    start, end = get_date_range(period, start_date, end_date)

    results = (
        db.query(
            Donation.donation_date,
            func.sum(Donation.amount).label("total"),
            func.count(Donation.id).label("count"),
        )
        .filter(Donation.donation_date >= start, Donation.donation_date <= end)
        .group_by(Donation.donation_date)
        .order_by(Donation.donation_date)
        .all()
    )

    return [
        {"date": str(row.donation_date), "total": float(row.total), "count": row.count}
        for row in results
    ]


@router.get("/categories")
def donation_categories(
    period: str = Query(default="30d"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    start, end = get_date_range(period, start_date, end_date)

    results = (
        db.query(
            Donation.category,
            func.sum(Donation.amount).label("total"),
            func.count(Donation.id).label("count"),
        )
        .filter(Donation.donation_date >= start, Donation.donation_date <= end)
        .group_by(Donation.category)
        .order_by(func.sum(Donation.amount).desc())
        .all()
    )

    return [
        {"category": row.category, "total": float(row.total), "count": row.count}
        for row in results
    ]


@router.get("/payment-methods")
def payment_methods(
    period: str = Query(default="30d"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    start, end = get_date_range(period, start_date, end_date)

    results = (
        db.query(
            Donation.payment_method,
            func.sum(Donation.amount).label("total"),
            func.count(Donation.id).label("count"),
        )
        .filter(Donation.donation_date >= start, Donation.donation_date <= end)
        .group_by(Donation.payment_method)
        .order_by(func.sum(Donation.amount).desc())
        .all()
    )

    return [
        {
            "payment_method": row.payment_method,
            "total": float(row.total),
            "count": row.count,
        }
        for row in results
    ]


@router.get("/records")
def donation_records(
    period: str = Query(default="30d"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    start, end = get_date_range(period, start_date, end_date)

    donations = (
        db.query(Donation)
        .options(selectinload(Donation.donor), selectinload(Donation.campaign))
        .filter(Donation.donation_date >= start, Donation.donation_date <= end)
        .order_by(Donation.donation_date.desc(), Donation.amount.desc())
        .all()
    )

    records = []

    for donation in donations:
        if donation.is_anonymous:
            donor_name = "Anonymous"

        elif donation.donor:
            donor_name = donation.donor.name

        else:
            donor_name = "Unknown"

        campaign_name = donation.campaign.name if donation.campaign else None

        records.append(
            {
                "donation_number": donation.donation_number,
                "donor_name": donor_name,
                "amount": float(donation.amount),
                "date": str(donation.donation_date),
                "category": donation.category,
                "payment_method": donation.payment_method,
                "location": donation.location,
                "campaign": campaign_name,
            }
        )

    return records

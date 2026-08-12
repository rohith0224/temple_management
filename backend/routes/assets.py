from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import Asset

router = APIRouter(prefix="/assets", tags=["Assets"])


@router.get("/summary")
def asset_summary(db: Session = Depends(get_db)):
    total_assets = db.query(Asset).count()

    total_value = db.query(func.coalesce(func.sum(Asset.current_value), 0)).scalar()

    under_maintenance = (
        db.query(Asset).filter(Asset.status == "UNDER_MAINTENANCE").count()
    )

    damaged = db.query(Asset).filter(Asset.condition == "DAMAGED").count()

    return {
        "total_assets": total_assets,
        "total_value": float(total_value),
        "under_maintenance": under_maintenance,
        "damaged_assets": damaged,
    }


@router.get("/by-category")
def assets_by_category(db: Session = Depends(get_db)):
    results = (
        db.query(
            Asset.category,
            func.count(Asset.id).label("count"),
            func.coalesce(func.sum(Asset.current_value), 0).label("value"),
        )
        .group_by(Asset.category)
        .order_by(func.count(Asset.id).desc())
        .all()
    )

    return [
        {"category": row.category, "count": row.count, "value": float(row.value)}
        for row in results
    ]


@router.get("/by-location")
def assets_by_location(db: Session = Depends(get_db)):
    results = (
        db.query(Asset.location, func.count(Asset.id).label("count"))
        .group_by(Asset.location)
        .order_by(func.count(Asset.id).desc())
        .all()
    )

    return [
        {"location": row.location or "Unknown", "count": row.count} for row in results
    ]


@router.get("/by-condition")
def assets_by_condition(db: Session = Depends(get_db)):
    results = (
        db.query(Asset.condition, func.count(Asset.id).label("count"))
        .group_by(Asset.condition)
        .order_by(func.count(Asset.id).desc())
        .all()
    )

    return [
        {"condition": row.condition or "Unknown", "count": row.count} for row in results
    ]


@router.get("/records")
def asset_records(
    category: str | None = Query(default=None),
    location: str | None = Query(default=None),
    status: str | None = Query(default=None),
    condition: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Asset)

    if category:
        query = query.filter(Asset.category == category)

    if location:
        query = query.filter(Asset.location == location)

    if status:
        query = query.filter(Asset.status == status)

    if condition:
        query = query.filter(Asset.condition == condition)

    assets = query.order_by(Asset.asset_tag).all()

    return [
        {
            "asset_tag": asset.asset_tag,
            "name": asset.name,
            "category": asset.category,
            "location": asset.location,
            "condition": asset.condition,
            "status": asset.status,
            "purchase_cost": (
                float(asset.purchase_cost) if asset.purchase_cost is not None else 0
            ),
            "current_value": (
                float(asset.current_value) if asset.current_value is not None else 0
            ),
            "purchase_date": (
                str(asset.purchase_date) if asset.purchase_date else None
            ),
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
        for asset in assets
    ]

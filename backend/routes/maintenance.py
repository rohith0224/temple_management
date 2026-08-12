from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from backend.app.database import get_db
from backend.app.models import Asset, MaintenanceRecord, Vendor

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])


# =========================================================
# SUMMARY
# =========================================================


@router.get("/summary")
def maintenance_summary(db: Session = Depends(get_db)):
    total_records = db.query(MaintenanceRecord).count()

    open_records = (
        db.query(MaintenanceRecord).filter(MaintenanceRecord.status == "OPEN").count()
    )

    in_progress_records = (
        db.query(MaintenanceRecord)
        .filter(MaintenanceRecord.status == "IN_PROGRESS")
        .count()
    )

    completed_records = (
        db.query(MaintenanceRecord)
        .filter(MaintenanceRecord.status == "COMPLETED")
        .count()
    )

    total_cost = db.query(func.coalesce(func.sum(MaintenanceRecord.cost), 0)).scalar()

    average_cost = float(total_cost) / total_records if total_records else 0

    return {
        "total_records": total_records,
        "open_records": open_records,
        "in_progress_records": in_progress_records,
        "completed_records": completed_records,
        "total_cost": float(total_cost),
        "average_cost": round(average_cost, 2),
    }


# =========================================================
# BY STATUS
# =========================================================


@router.get("/by-status")
def maintenance_by_status(db: Session = Depends(get_db)):
    results = (
        db.query(
            MaintenanceRecord.status,
            func.count(MaintenanceRecord.id).label("count"),
            func.coalesce(func.sum(MaintenanceRecord.cost), 0).label("cost"),
        )
        .group_by(MaintenanceRecord.status)
        .order_by(func.count(MaintenanceRecord.id).desc())
        .all()
    )

    return [
        {"status": row.status or "UNKNOWN", "count": row.count, "cost": float(row.cost)}
        for row in results
    ]


# =========================================================
# COST BY ASSET
# =========================================================


@router.get("/cost-by-asset")
def maintenance_cost_by_asset(
    limit: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db)
):
    results = (
        db.query(
            Asset.asset_tag,
            Asset.name,
            func.coalesce(func.sum(MaintenanceRecord.cost), 0).label("total_cost"),
            func.count(MaintenanceRecord.id).label("maintenance_count"),
        )
        .join(MaintenanceRecord, MaintenanceRecord.asset_id == Asset.id)
        .group_by(Asset.id, Asset.asset_tag, Asset.name)
        .order_by(func.sum(MaintenanceRecord.cost).desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "asset_tag": row.asset_tag,
            "asset_name": row.name,
            "total_cost": float(row.total_cost),
            "maintenance_count": row.maintenance_count,
        }
        for row in results
    ]


# =========================================================
# COST BY ASSET CATEGORY
# =========================================================


@router.get("/cost-by-category")
def maintenance_cost_by_category(db: Session = Depends(get_db)):
    results = (
        db.query(
            Asset.category,
            func.coalesce(func.sum(MaintenanceRecord.cost), 0).label("total_cost"),
            func.count(MaintenanceRecord.id).label("maintenance_count"),
        )
        .join(MaintenanceRecord, MaintenanceRecord.asset_id == Asset.id)
        .group_by(Asset.category)
        .order_by(func.sum(MaintenanceRecord.cost).desc())
        .all()
    )

    return [
        {
            "category": row.category,
            "total_cost": float(row.total_cost),
            "maintenance_count": row.maintenance_count,
        }
        for row in results
    ]


# =========================================================
# RECORDS
# =========================================================


@router.get("/records")
def maintenance_records(
    status: Optional[str] = None,
    asset_id: Optional[int] = None,
    vendor_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    query = db.query(MaintenanceRecord).options(
        selectinload(MaintenanceRecord.asset), selectinload(MaintenanceRecord.vendor)
    )

    if status:
        query = query.filter(MaintenanceRecord.status == status)

    if asset_id:
        query = query.filter(MaintenanceRecord.asset_id == asset_id)

    if vendor_id:
        query = query.filter(MaintenanceRecord.vendor_id == vendor_id)

    if start_date:
        query = query.filter(MaintenanceRecord.start_date >= start_date)

    if end_date:
        query = query.filter(MaintenanceRecord.start_date <= end_date)

    records = query.order_by(
        MaintenanceRecord.start_date.desc(), MaintenanceRecord.id.desc()
    ).all()

    output = []

    for record in records:
        asset_name = record.asset.name if record.asset else "Unknown"

        asset_tag = record.asset.asset_tag if record.asset else None

        vendor_name = record.vendor.name if record.vendor else "Unknown"

        output.append(
            {
                "id": record.id,
                "asset_id": record.asset_id,
                "asset_tag": asset_tag,
                "asset_name": asset_name,
                "vendor_id": record.vendor_id,
                "vendor_name": vendor_name,
                "description": record.description,
                "maintenance_type": record.maintenance_type,
                "cost": (float(record.cost) if record.cost is not None else 0),
                "start_date": (str(record.start_date) if record.start_date else None),
                "completion_date": (
                    str(record.completion_date) if record.completion_date else None
                ),
                "status": record.status,
                "notes": record.notes,
            }
        )

    return output


# =========================================================
# ASSET OPTIONS
# =========================================================


@router.get("/assets")
def maintenance_asset_options(db: Session = Depends(get_db)):
    assets = db.query(Asset).order_by(Asset.asset_tag).all()

    return [
        {"id": asset.id, "asset_tag": asset.asset_tag, "name": asset.name}
        for asset in assets
    ]


# =========================================================
# VENDOR OPTIONS
# =========================================================


@router.get("/vendors")
def maintenance_vendor_options(db: Session = Depends(get_db)):
    vendors = db.query(Vendor).order_by(Vendor.name).all()

    return [{"id": vendor.id, "name": vendor.name} for vendor in vendors]

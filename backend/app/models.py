from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.app.database import Base


class Donor(Base):
    __tablename__ = "donors"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(150), nullable=True)
    email = Column(String(150), nullable=True)
    phone = Column(String(50), nullable=True)

    is_anonymous = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    donations = relationship("Donation", back_populates="donor")


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(150), nullable=False)

    description = Column(Text, nullable=True)

    target_amount = Column(Numeric(12, 2), nullable=True)

    start_date = Column(Date, nullable=True)

    end_date = Column(Date, nullable=True)

    status = Column(String(50), default="ACTIVE")

    donations = relationship("Donation", back_populates="campaign")


class Donation(Base):
    __tablename__ = "donations"

    id = Column(Integer, primary_key=True, index=True)

    donation_number = Column(String(50), unique=True, nullable=False, index=True)

    donor_id = Column(Integer, ForeignKey("donors.id"), nullable=True)

    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)

    amount = Column(Numeric(12, 2), nullable=False)

    donation_date = Column(Date, nullable=False, index=True)

    category = Column(String(100), nullable=False, index=True)

    payment_method = Column(String(100), nullable=False, index=True)

    location = Column(String(150), nullable=True)

    is_anonymous = Column(Boolean, default=False)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    donor = relationship("Donor", back_populates="donations")

    campaign = relationship("Campaign", back_populates="donations")


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(150), nullable=False)

    contact_name = Column(String(150), nullable=True)

    email = Column(String(150), nullable=True)

    phone = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    assets = relationship("Asset", back_populates="vendor")

    maintenance_records = relationship("MaintenanceRecord", back_populates="vendor")


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)

    asset_tag = Column(String(50), unique=True, nullable=False, index=True)

    name = Column(String(150), nullable=False)

    description = Column(Text, nullable=True)

    category = Column(String(100), nullable=False, index=True)

    serial_number = Column(String(100), nullable=True)

    purchase_date = Column(Date, nullable=True)

    purchase_cost = Column(Numeric(12, 2), nullable=True)

    current_value = Column(Numeric(12, 2), nullable=True)

    location = Column(String(150), nullable=True, index=True)

    condition = Column(String(50), nullable=True)

    status = Column(String(50), nullable=True, index=True)

    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)

    warranty_expiry = Column(Date, nullable=True)

    last_inspection_date = Column(Date, nullable=True)

    next_inspection_date = Column(Date, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    vendor = relationship("Vendor", back_populates="assets")

    maintenance_records = relationship("MaintenanceRecord", back_populates="asset")


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    id = Column(Integer, primary_key=True, index=True)

    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)

    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)

    description = Column(Text, nullable=False)

    maintenance_type = Column(String(100), nullable=True)

    cost = Column(Numeric(12, 2), nullable=True)

    start_date = Column(Date, nullable=True)

    completion_date = Column(Date, nullable=True)

    status = Column(String(50), nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    asset = relationship("Asset", back_populates="maintenance_records")

    vendor = relationship("Vendor", back_populates="maintenance_records")

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

from faker import Faker
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models import (
    Donor,
    Campaign,
    Donation,
    Vendor,
    Asset,
    MaintenanceRecord,
)

fake = Faker()
random.seed(42)
Faker.seed(42)


DONATION_CATEGORIES = [
    "GENERAL",
    "ANNADANAM",
    "MAINTENANCE",
    "CONSTRUCTION",
    "FESTIVAL",
    "EDUCATION",
    "CHARITY",
    "RELIGIOUS_SERVICES",
    "OTHER",
]

PAYMENT_METHODS = [
    "CASH",
    "CHECK",
    "CREDIT_CARD",
    "DEBIT_CARD",
    "BANK_TRANSFER",
    "ONLINE",
]

LOCATIONS = [
    "Main Temple",
    "Community Hall",
    "Annadanam Hall",
    "Temple Office",
    "Festival Grounds",
]

ASSET_TYPES = [
    ("Laptop", "COMPUTER_EQUIPMENT", 900, 1800),
    ("Desktop Computer", "COMPUTER_EQUIPMENT", 600, 1400),
    ("Projector", "ELECTRONICS", 500, 2200),
    ("Sound System", "AUDIO_EQUIPMENT", 1500, 8000),
    ("Microphone", "AUDIO_EQUIPMENT", 100, 800),
    ("CCTV Camera", "ELECTRONICS", 150, 1000),
    ("Refrigerator", "KITCHEN_EQUIPMENT", 800, 3000),
    ("Commercial Stove", "KITCHEN_EQUIPMENT", 1200, 6000),
    ("Generator", "INFRASTRUCTURE", 3000, 15000),
    ("Water Pump", "INFRASTRUCTURE", 500, 3000),
    ("Printer", "OFFICE_EQUIPMENT", 200, 900),
    ("Air Conditioner", "ELECTRICAL", 600, 2500),
    ("Table Set", "FURNITURE", 200, 1200),
    ("Chair Set", "FURNITURE", 150, 1000),
]

CONDITIONS = ["EXCELLENT", "GOOD", "GOOD", "GOOD", "FAIR", "POOR"]
ASSET_STATUSES = ["ACTIVE", "ACTIVE", "ACTIVE", "UNDER_MAINTENANCE", "TRANSFERRED"]

MAINTENANCE_TYPES = [
    "Inspection",
    "Repair",
    "Preventive Maintenance",
    "Servicing",
    "Replacement",
]

MAINTENANCE_STATUSES = ["OPEN", "IN_PROGRESS", "COMPLETED", "COMPLETED", "COMPLETED"]


def random_donation_amount():
    p = random.random()

    if p < 0.70:
        return Decimal(str(random.choice([10, 20, 25, 50, 75, 100, 150, 200, 250])))

    if p < 0.90:
        return Decimal(str(random.choice([300, 400, 500, 750, 1000])))

    if p < 0.98:
        return Decimal(str(random.choice([1200, 1500, 2000, 2500])))

    return Decimal(str(random.choice([3000, 4000, 5000])))


def seed_database():
    db: Session = SessionLocal()

    try:
        existing = db.query(Donation).count()

        if existing > 0:
            print("Demo data already exists.")
            print("Delete existing records before running the seed again.")
            return

        today = date.today()
        start_date = today - timedelta(days=44)

        print(f"Creating demo data from {start_date} to {today}")

        # -----------------------
        # Vendors
        # -----------------------

        vendors = []

        vendor_names = [
            "TempleTech Services",
            "Divine Audio Systems",
            "Sacred Electrical Solutions",
            "Community Kitchen Equipment",
            "Heritage Maintenance Services",
            "Temple Office Supplies",
            "Community IT Solutions",
            "Sacred Facilities Services",
            "Temple Auto Services",
            "Festival Equipment Rentals",
        ]

        for i in range(20):
            if i < len(vendor_names):
                name = vendor_names[i]
            else:
                name = fake.company()

            vendor = Vendor(
                name=name,
                contact_name=fake.name(),
                email=fake.company_email(),
                phone=fake.phone_number(),
            )

            db.add(vendor)
            vendors.append(vendor)

        db.flush()

        # -----------------------
        # Campaigns
        # -----------------------

        campaign_data = [
            ("Temple Renovation Fund", 50000),
            ("Annual Festival Fund", 30000),
            ("Annadanam Seva", 20000),
            ("Community Charity Drive", 15000),
            ("Education Support Fund", 12000),
            ("Temple Maintenance Fund", 25000),
            ("Festival Decorations", 10000),
            ("Community Kitchen Fund", 18000),
        ]

        campaigns = []

        for name, target in campaign_data:
            campaign = Campaign(
                name=name,
                description=f"Demo campaign for {name}.",
                target_amount=Decimal(str(target)),
                start_date=start_date,
                end_date=today + timedelta(days=60),
                status="ACTIVE",
            )

            db.add(campaign)
            campaigns.append(campaign)

        db.flush()

        # -----------------------
        # Donors
        # -----------------------

        donors = []

        for _ in range(100):
            donor = Donor(
                name=fake.name(),
                email=fake.email(),
                phone=fake.phone_number(),
                is_anonymous=False,
            )

            db.add(donor)
            donors.append(donor)

        db.flush()

        # -----------------------
        # Donations
        # -----------------------

        donations = []

        for i in range(250):
            random_day = random.randint(0, 44)
            donation_date = start_date + timedelta(days=random_day)

            # Increase likelihood of donations on weekends
            if donation_date.weekday() >= 5 and random.random() < 0.40:
                donation_date = min(
                    donation_date + timedelta(days=random.choice([0, 0, 0, 1])), today
                )

            anonymous = random.random() < 0.15

            donor = None if anonymous else random.choice(donors)

            campaign = random.choice(campaigns) if random.random() < 0.65 else None

            donation = Donation(
                donation_number=f"DON-{i + 1:06d}",
                donor_id=donor.id if donor else None,
                campaign_id=campaign.id if campaign else None,
                amount=random_donation_amount(),
                donation_date=donation_date,
                category=random.choices(
                    DONATION_CATEGORIES, weights=[30, 15, 15, 10, 15, 3, 5, 5, 2], k=1
                )[0],
                payment_method=random.choices(
                    PAYMENT_METHODS, weights=[25, 5, 10, 10, 20, 30], k=1
                )[0],
                location=random.choice(LOCATIONS),
                is_anonymous=anonymous,
                notes=fake.sentence() if random.random() < 0.25 else None,
            )

            db.add(donation)
            donations.append(donation)

        # -----------------------
        # Assets
        # -----------------------

        assets = []

        for i in range(80):
            asset_name, category, min_cost, max_cost = random.choice(ASSET_TYPES)

            purchase_cost = Decimal(str(round(random.uniform(min_cost, max_cost), 2)))

            depreciation = Decimal(str(round(random.uniform(0.55, 0.95), 2)))

            current_value = (purchase_cost * depreciation).quantize(Decimal("0.01"))

            purchase_date = today - timedelta(days=random.randint(30, 1500))

            asset = Asset(
                asset_tag=f"AST-{i + 1:04d}",
                name=asset_name,
                description=f"{asset_name} used for temple operations.",
                category=category,
                serial_number=f"SN-{random.randint(100000, 999999)}",
                purchase_date=purchase_date,
                purchase_cost=purchase_cost,
                current_value=current_value,
                location=random.choice(LOCATIONS),
                condition=random.choice(CONDITIONS),
                status=random.choice(ASSET_STATUSES),
                vendor_id=random.choice(vendors).id,
                warranty_expiry=purchase_date
                + timedelta(days=random.choice([365, 730, 1095])),
                last_inspection_date=today - timedelta(days=random.randint(1, 240)),
                next_inspection_date=today + timedelta(days=random.randint(10, 180)),
            )

            db.add(asset)
            assets.append(asset)

        db.flush()

        # -----------------------
        # Maintenance Records
        # -----------------------

        for _ in range(60):
            asset = random.choice(assets)
            maintenance_date = start_date + timedelta(days=random.randint(0, 44))

            status = random.choice(MAINTENANCE_STATUSES)

            completion_date = None

            if status == "COMPLETED":
                completion_date = maintenance_date + timedelta(
                    days=random.randint(1, 7)
                )

            record = MaintenanceRecord(
                asset_id=asset.id,
                vendor_id=random.choice(vendors).id,
                description=f"{random.choice(MAINTENANCE_TYPES)} for {asset.name}",
                maintenance_type=random.choice(MAINTENANCE_TYPES),
                cost=Decimal(str(round(random.uniform(50, 1500), 2))),
                start_date=maintenance_date,
                completion_date=completion_date,
                status=status,
                notes=fake.sentence() if random.random() < 0.30 else None,
            )

            db.add(record)

        db.commit()

        # -----------------------
        # Summary
        # -----------------------

        donation_count = db.query(Donation).count()
        asset_count = db.query(Asset).count()
        donor_count = db.query(Donor).count()
        vendor_count = db.query(Vendor).count()
        campaign_count = db.query(Campaign).count()
        maintenance_count = db.query(MaintenanceRecord).count()

        total_donations = sum(donation.amount for donation in db.query(Donation).all())

        print()
        print("====================================")
        print("DEMO DATABASE CREATED")
        print("====================================")
        print(f"Date Range: {start_date} to {today}")
        print(f"Donors: {donor_count}")
        print(f"Donations: {donation_count}")
        print(f"Total Donations: ${total_donations:,.2f}")
        print(f"Campaigns: {campaign_count}")
        print(f"Assets: {asset_count}")
        print(f"Vendors: {vendor_count}")
        print(f"Maintenance Records: {maintenance_count}")
        print("====================================")

    except Exception as e:
        db.rollback()
        print(f"Error while creating demo data: {e}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()

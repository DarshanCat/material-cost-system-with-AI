"""Create (or refresh) a LOCAL single-user test database with the real item master and two sample vendors.

    set DATABASE_URL=sqlite:///local_dev.db  (see scripts/run_local.ps1)
    python scripts/dev_local.py

Safe to run again: existing rows are left alone. Never point DATABASE_URL at a shared or production database.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402

if not settings.sync_database_url.startswith("sqlite"):
    sys.exit("Refusing to run: this tool only prepares a local SQLite test database.")

import app.models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.maintenance.load_item_master import load_plan, run  # noqa: E402
from app.models.vendor import Vendor  # noqa: E402
from app.services.validators import normalize_vendor_name  # noqa: E402

Base.metadata.create_all(engine)
with SessionLocal() as db:
    code = run(db, load_plan(), commit=True)
    for name, gstin in (("Tata Steel Ltd", "27AAACT2727Q1ZW"), ("Sample Foundry Supplies", "29AABCS1234F1Z5")):
        if not db.query(Vendor).filter_by(name=name).first():
            db.add(Vendor(name=name, normalized_name=normalize_vendor_name(name), gstin=gstin))
    db.commit()
print("Local test database ready:", settings.sync_database_url)
sys.exit(code)

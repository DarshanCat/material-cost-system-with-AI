"""PROPOSED — add material_items.cost_head derived from the v1.0 category (Nomenclature Standard Section 4)

Revision ID: 009_material_item_cost_head
Revises: 008_item_code_registry
Create Date: 2026-10-26 10:30:00.000000

STATUS: PROPOSAL ONLY. NOT APPROVED. NOT EXECUTED.
This file deliberately lives in migrations/proposed/, outside Alembic's version location
(migrations/versions), so `alembic upgrade head` cannot apply it. To adopt it after explicit approval,
review it, move it into migrations/versions/, and run it against the non-production database first.

Why: Section 7 of the standard lists Cost Head as a field of every item, "derived from the category — not
entered by hand". material_items has no cost_head column today. The application does NOT depend on this
column: new-item previews derive the cost head from the selected v1.0 category in code.

Column
  cost_head VARCHAR(50) NULL, CHECK (cost_head IS NULL OR cost_head IN <the ten Section 4 cost heads>).
  Nullable because grandfathered items whose category or code does not map to v1.0 have no derivable cost
  head, and the standard forbids entering it by hand. A NOT NULL constraint would force guessing.

Mapping (Section 4, category -> cost head)
  RM Raw Material       -> Material Cost          LN Lining Material   -> Lining Cost
  MD Moulding Material  -> Moulding Cost          CN Consumables       -> Foundry Consumables
  PT Paints & Coatings  -> Foundry Consumables    CB Cutting Blades    -> Machining Consumables
  IT Inserts & Tools    -> Machining Consumables  OL Oils & Lubricants -> Maintenance Cost
  BR Bearings           -> Maintenance Cost       BL Belts             -> Maintenance Cost
  BN Bolts & Nuts       -> Maintenance Cost       QC Quality Material  -> Quality Consumables
  PK Packing Material   -> Packing Cost           FU Fuel              -> Energy / Fuel
  SF Safety Material    -> Safety Cost

Ambiguity and the proposed resolution
  material_items.category is free text with mixed conventions: the approved workbook loader stores the
  standard name ('Bolts & Nuts'); items created by the pre-v1.0 request workflow store legacy keys
  ('RAW_MATERIAL', 'ALLOY', 'CONSUMABLE', ...); some legacy workbook rows use names outside v1.0
  ('General Consumables', 'Machine Spareparts') or a category that disagrees with the code ('MNT-BN-*'
  with department 'Foundry'). The backfill therefore sets cost_head ONLY when BOTH agree:
    1. item_code matches '<DEPT>-<CAT>-NNN' for a v1.0 (department, category) pair, and
    2. category text equals that category's v1.0 name or code (case-insensitive).
  Everything else stays NULL and appears in GET /api/v1/item-codes/compliance for human review. Legacy
  keys such as 'RAW_MATERIAL' are NOT mapped (RAW_MATERIAL -> RM looks obvious, but CONSUMABLE -> CN is
  not: v1.0 CN is Foundry-owned and legacy consumables span several departments).

Backfill considerations
  * Updates only rows with cost_head IS NULL, so a re-run is harmless.
  * Touches material_items only. material_items is not append-only, but take a backup first and compare
    counts of NULL vs non-NULL cost_head before and after.
  * Application follow-up (not done): set cost_head in ItemCodeService.register_item for new items, add it to
    MaterialItemRead, and keep it read-only in PUT /items.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Frozen copy of Section 4 (code, name, department code, cost head). Must not import application code.
CATEGORY_COST_HEADS = [
    ("RM", "Raw Material", "FDY", "Material Cost"),
    ("LN", "Lining Material", "FDY", "Lining Cost"),
    ("MD", "Moulding Material", "FDY", "Moulding Cost"),
    ("CN", "Consumables", "FDY", "Foundry Consumables"),
    ("PT", "Paints & Coatings", "FDY", "Foundry Consumables"),
    ("CB", "Cutting Blades", "MCS", "Machining Consumables"),
    ("IT", "Inserts & Tools", "MCS", "Machining Consumables"),
    ("OL", "Oils & Lubricants", "MNT", "Maintenance Cost"),
    ("BR", "Bearings", "MNT", "Maintenance Cost"),
    ("BL", "Belts", "MNT", "Maintenance Cost"),
    ("BN", "Bolts & Nuts", "MNT", "Maintenance Cost"),
    ("QC", "Quality Material", "QLY", "Quality Consumables"),
    ("PK", "Packing Material", "PKD", "Packing Cost"),
    ("FU", "Fuel", "UTL", "Energy / Fuel"),
    ("SF", "Safety Material", "GEN", "Safety Cost"),
]
COST_HEADS = sorted({row[3] for row in CATEGORY_COST_HEADS})

# revision identifiers, used by Alembic.
revision: str = '009_material_item_cost_head'
down_revision: Union[str, None] = '008_item_code_registry'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    allowed = ", ".join("'" + head.replace("'", "''") + "'" for head in COST_HEADS)
    with op.batch_alter_table('material_items') as batch:
        batch.add_column(sa.Column('cost_head', sa.String(length=50), nullable=True))
        batch.create_check_constraint('cost_head_allowed', f"cost_head IS NULL OR cost_head IN ({allowed})")

    material_items = sa.table(
        'material_items',
        sa.column('item_code', sa.String),
        sa.column('category', sa.String),
        sa.column('cost_head', sa.String),
    )
    for code, name, dept, cost_head in CATEGORY_COST_HEADS:
        prefix = f"{dept}-{code}-"
        op.execute(
            material_items.update()
            .where(
                material_items.c.cost_head.is_(None),
                material_items.c.item_code.regexp_match(f"^{prefix}[0-9]{{3}}$"),
                sa.func.lower(material_items.c.category).in_([name.lower(), code.lower()]),
            )
            .values(cost_head=cost_head)
        )


def downgrade() -> None:
    with op.batch_alter_table('material_items') as batch:
        batch.drop_constraint('cost_head_allowed', type_='check')
        batch.drop_column('cost_head')

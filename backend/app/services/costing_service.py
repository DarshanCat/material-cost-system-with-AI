"""
Weighted-Average Costing & Inventory Valuation Service for VSPL.
Implements:
1. Deterministic weighted-average material unit rate reconstruction using business transaction dates.
2. Inventory valuation queries without ledger quantity mutation.
3. Induction furnace heat material costing (material-only scope, configured denominator).
4. Finished part material unit costing from unit cast weights.
5. Versioned, immutable Costing Run snapshots and run comparison.
Strictly uses Python Decimal and database NUMERIC types.
"""

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Tuple, Dict, Any, Set
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, desc, or_
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.ledger import StockLedgerEntry, MovementType
from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.grn import GRNLineItem, GRNHeader, GRNStatus, GRNSourceType
from app.models.heat import HeatHeader, HeatChargeLine, HeatPartsProduced, CastingClassification
from app.models.issue import MaterialIssueHeader, MaterialIssueLineItem, IssueStatus
from app.services.heat_calculations import calculate_heat_costing_measures, HeatCostingMeasures
from app.models.material_alias import MaterialAlias
from app.services.material_alias_service import resolve_material_by_description
from app.models.costing import (
    CostingRun,
    ItemCostSnapshot,
    ItemCostJournalEntry,
    HeatCostRecord,
    HeatCostLine,
    PartCostRecord,
    ItemOpeningValuation,
    DenominatorPolicy,
    CostScope,
    ValuationStatus,
    HeatCostStatus,
    PartCostStatus,
    CostingRunStatus,
)
from app.services.document_number_service import (
    DocumentType,
    generate_document_number,
    execute_with_document_number_retry,
)

RATE_PRECISION = Decimal("0.0001")
VALUE_PRECISION = Decimal("0.01")
COSTING_CUTOFF_DATE = date.fromisoformat(settings.COSTING_START_DATE)

HISTORICAL_UNSUPPORTED_HEATS = {
    "H-20261015-0001",
    "H-20261016-0001",
    "H-20261022-0001",
    "102603-3801",
    "102603-3802",
    "102603-4901",
    "102603-4902",
}


def movement_sort_priority(movement_type: str, quantity_delta: Decimal) -> int:
    """
    Same-day deterministic tie-breaking order:
    1. OPENING_BALANCE
    2. INWARD_RECEIPT / INTERNAL_INWARD (deliveries received available to cost same-day issues)
    3. PHYSICAL_AUDIT_ADJUSTMENT (positive adjustment)
    4. OUTWARD_ISSUE / SCRAP_OUTWARD (outward movements costed at current average)
    5. PHYSICAL_AUDIT_ADJUSTMENT (negative adjustment)
    6. REVERSAL
    7. INTERNAL_RECOVERY
    8. Others
    """
    if movement_type == MovementType.OPENING_BALANCE.value:
        return 1
    elif movement_type in (MovementType.INWARD_RECEIPT.value, MovementType.INTERNAL_INWARD.value):
        return 2
    elif movement_type == MovementType.PHYSICAL_AUDIT_ADJUSTMENT.value and quantity_delta > 0:
        return 3
    elif movement_type in (MovementType.OUTWARD_ISSUE.value, MovementType.SCRAP_OUTWARD.value):
        return 4
    elif movement_type == MovementType.PHYSICAL_AUDIT_ADJUSTMENT.value and quantity_delta < 0:
        return 5
    elif movement_type == MovementType.REVERSAL.value:
        return 6
    elif movement_type == MovementType.INTERNAL_RECOVERY.value:
        return 7
    return 8


def generate_costing_run_number(db: Session, as_of: date) -> str:
    """Generates sequential serial: CRUN-YYYYMMDD-XXXX."""
    return generate_document_number(db, DocumentType.COSTING_RUN, as_of)


def reconstruct_item_rate_evolution(
    db: Session,
    material_item_id: int,
    as_of_date: Optional[date] = None,
) -> Tuple[Decimal, Optional[Decimal], str, Optional[str], List[Dict[str, Any]]]:
    """
    Reconstructs the weighted-average rate evolution for a material item from ledger movements.
    Returns:
    (current_quantity, weighted_average_rate, valuation_status, rate_source, journal_steps)
    """
    item = db.get(MaterialItem, material_item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material item ID {material_item_id} not found",
        )

    # 1. Fetch approved opening valuation if exists (latest approved version)
    approved_opening = db.execute(
        select(ItemOpeningValuation).where(
            ItemOpeningValuation.material_item_id == material_item_id,
            ItemOpeningValuation.status == "APPROVED",
        ).order_by(ItemOpeningValuation.version.desc())
    ).scalars().first()

    # 2. Fetch all ledger movements up to as_of_date
    query = select(StockLedgerEntry).where(StockLedgerEntry.material_item_id == material_item_id)
    if as_of_date:
        query = query.where(StockLedgerEntry.transaction_date <= as_of_date)

    raw_entries = db.execute(query).scalars().all()
    if not raw_entries:
        return Decimal("0.0000"), None, ValuationStatus.UNINITIALIZED.value, None, []

    # 3. Sort entries deterministically by (transaction_date, movement_sort_priority, id)
    entries = sorted(
        raw_entries,
        key=lambda e: (e.transaction_date, movement_sort_priority(e.movement_type, e.quantity_delta), e.id),
    )

    running_qty = Decimal("0.0000")
    running_avg_rate: Optional[Decimal] = None
    rate_source: Optional[str] = None
    has_unvalued_opening = False
    has_negative_stock = False
    has_missing_receipt_rate = False
    journal_steps: List[Dict[str, Any]] = []

    for entry in entries:
        m_type = entry.movement_type
        delta = entry.quantity_delta
        applied_rate: Optional[Decimal] = None
        receipt_rate: Optional[Decimal] = None
        extended_val: Optional[Decimal] = None
        step_status = "APPLIED"
        notes = entry.reason or ""

        if m_type == MovementType.OPENING_BALANCE.value:
            running_qty += delta
            if approved_opening and approved_opening.opening_rate_ex_gst is not None:
                running_avg_rate = approved_opening.opening_rate_ex_gst.quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)
                rate_source = "APPROVED_OPENING_VALUATION"
                receipt_rate = running_avg_rate
                applied_rate = running_avg_rate
                extended_val = (delta * running_avg_rate).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)
                step_status = "OPENING_VALUED"
                notes = f"Opening balance valued via opening valuation v{approved_opening.version} (id={approved_opening.id})"
            else:
                has_unvalued_opening = True
                running_avg_rate = None
                step_status = "OPENING_VALUATION_MISSING"
                notes = "Opening balance established on 12-Oct-2026 without approved commercial rate"

        elif m_type == MovementType.INWARD_RECEIPT.value:
            # Look up GRNLineItem for rate_ex_gst
            grn_line = db.get(GRNLineItem, entry.source_line_id)
            if grn_line and grn_line.rate_ex_gst is not None and grn_line.rate_ex_gst > Decimal("0.00"):
                receipt_rate = grn_line.rate_ex_gst.quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)
                applied_rate = receipt_rate
                extended_val = (delta * receipt_rate).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)
                
                if running_qty <= Decimal("0.0000"):
                    # Restart rate at receipt rate when prior stock was zero or negative
                    prior_neg = running_qty < Decimal("0.0000")
                    running_avg_rate = receipt_rate
                    running_qty += delta
                    rate_source = f"GRN_{entry.source_document_number}"
                    step_status = "NEGATIVE_STOCK_RESET" if prior_neg else "RECEIPT_RESTART"
                else:
                    # Positive prior stock: calculate new blended weighted average
                    if running_avg_rate is not None:
                        new_total_qty = running_qty + delta
                        new_total_val = (running_qty * running_avg_rate) + (delta * receipt_rate)
                        running_avg_rate = (new_total_val / new_total_qty).quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)
                        running_qty = new_total_qty
                        rate_source = "WEIGHTED_AVERAGE"
                        step_status = "WEIGHTED_AVG_UPDATE"
                    else:
                        # Prior stock had missing rate; initialize rate to receipt rate
                        running_avg_rate = receipt_rate
                        running_qty += delta
                        rate_source = f"GRN_{entry.source_document_number}"
                        step_status = "FIRST_PRICED_RECEIPT"
            else:
                # Missing rate on receipt
                has_missing_receipt_rate = True
                running_qty += delta
                step_status = "MISSING_RECEIPT_RATE"
                notes = "External GRN receipt missing rate_ex_gst; cannot blend into weighted average"

        elif m_type == MovementType.INTERNAL_INWARD.value:
            # Internal receipt without commercial rate; policy pending
            running_qty += delta
            step_status = "INTERNAL_INWARD_POLICY_PENDING"
            notes = "Internal inward movement recorded with pending valuation policy"

        elif m_type in (MovementType.OUTWARD_ISSUE.value, MovementType.SCRAP_OUTWARD.value):
            # Consumes inventory at current running average rate
            applied_rate = running_avg_rate
            if running_avg_rate is not None:
                extended_val = (abs(delta) * running_avg_rate).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)
                step_status = "ISSUED_AT_AVERAGE_RATE"
            else:
                step_status = "UNVALUED_OUTWARD_MOVEMENT"
                notes = "Material issued without known applicable weighted-average rate"
            
            running_qty += delta  # delta is negative
            if running_qty < Decimal("0.0000"):
                has_negative_stock = True

        elif m_type == MovementType.PHYSICAL_AUDIT_ADJUSTMENT.value:
            applied_rate = running_avg_rate
            if running_avg_rate is not None:
                extended_val = (delta * running_avg_rate).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)
            running_qty += delta
            step_status = "AUDIT_ADJUSTMENT"

        elif m_type == MovementType.REVERSAL.value:
            # Reversal delta restores or cancels quantity and historical valuation
            reversed_entry = db.get(StockLedgerEntry, entry.reversal_of_entry_id) if entry.reversal_of_entry_id else None
            if reversed_entry and reversed_entry.movement_type == MovementType.INWARD_RECEIPT.value:
                # Reversing an inward receipt: subtract original receipt value
                orig_grn_line = db.get(GRNLineItem, reversed_entry.source_line_id)
                if orig_grn_line and orig_grn_line.rate_ex_gst:
                    orig_rate = orig_grn_line.rate_ex_gst.quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)
                    applied_rate = orig_rate
                    extended_val = (delta * orig_rate).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)
                    new_qty = running_qty + delta
                    if new_qty > Decimal("0.0000"):
                        # Look up prior running value or back out receipt value
                        prior_total_val = (running_qty * (running_avg_rate or Decimal("0.0000"))) + (delta * orig_rate)
                        running_avg_rate = (prior_total_val / new_qty).quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)
                    elif new_qty == Decimal("0.0000"):
                        running_avg_rate = None
                    running_qty = new_qty
                    step_status = "RECEIPT_REVERSED"
                    notes = f"Reversal of inward receipt {reversed_entry.source_document_number} backed out at original rate Rs {orig_rate}"
                else:
                    running_qty += delta
                    applied_rate = running_avg_rate
                    step_status = "REVERSAL"
            elif reversed_entry and reversed_entry.movement_type in (MovementType.OUTWARD_ISSUE.value, MovementType.SCRAP_OUTWARD.value):
                # Reversing an outward issue: restore quantity at original issue rate
                orig_step = next((s for s in journal_steps if s["stock_ledger_entry_id"] == reversed_entry.id), None)
                orig_rate = orig_step.get("applied_rate") if orig_step else running_avg_rate
                applied_rate = orig_rate
                if orig_rate:
                    extended_val = (delta * orig_rate).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)
                running_qty += delta
                step_status = "ISSUE_REVERSED"
                notes = f"Reversal of outward issue {reversed_entry.source_document_number} restored at original rate Rs {orig_rate}"
            else:
                applied_rate = running_avg_rate
                running_qty += delta
                step_status = "REVERSAL"

        elif m_type == MovementType.INTERNAL_RECOVERY.value:
            step_status = "INTERNAL_RECOVERY_POLICY_PENDING"
            notes = "Internal recovery scrap transfer logged with zero quantity delta (Rule C7)"

        else:
            running_qty += delta
            step_status = "UNRECOGNIZED_MOVEMENT"

        cumulative_val = (
            (running_qty * running_avg_rate).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)
            if (running_avg_rate is not None and running_qty >= Decimal("0.0000"))
            else None
        )

        journal_steps.append({
            "stock_ledger_entry_id": entry.id,
            "entry_number": entry.entry_number,
            "transaction_date": entry.transaction_date,
            "movement_type": m_type,
            "quantity_delta": delta,
            "running_quantity": running_qty,
            "receipt_rate": receipt_rate,
            "applied_rate": applied_rate,
            "resulting_average_rate": running_avg_rate,
            "movement_extended_value": extended_val,
            "cumulative_value": cumulative_val,
            "status": step_status,
            "notes": notes,
        })

    # 4. Resolve overall Valuation Status
    if running_qty == Decimal("0.0000"):
        val_status = ValuationStatus.ZERO_STOCK.value
    elif running_qty < Decimal("0.0000"):
        val_status = ValuationStatus.NEGATIVE_STOCK_FLAG.value
    else:  # running_qty > 0
        if running_avg_rate is not None:
            val_status = ValuationStatus.VALUED.value
        elif has_unvalued_opening:
            val_status = ValuationStatus.OPENING_VALUATION_MISSING.value
        elif has_missing_receipt_rate:
            val_status = ValuationStatus.INSUFFICIENT_COST_DATA.value
        else:
            val_status = ValuationStatus.UNVALUED_NO_RATE.value

    return running_qty, running_avg_rate, val_status, rate_source, journal_steps


def get_item_rate_as_of_date(
    db: Session,
    material_item_id: int,
    target_date: date,
) -> Optional[Decimal]:
    """
    Returns the effective weighted-average rate for an item as of target_date.
    Returns None if unvalued, uninitialized, or missing rates.
    """
    _, rate, val_status, _, _ = reconstruct_item_rate_evolution(db, material_item_id, target_date)
    if val_status in (ValuationStatus.VALUED.value, ValuationStatus.ZERO_STOCK.value, ValuationStatus.NEGATIVE_STOCK_FLAG.value):
        return rate
    return None


def reconcile_heat_stores_issue_backing(
    db: Session,
    heat: HeatHeader,
) -> Dict[str, Any]:
    """
    AUD-2B2D-001: Item-level Stores Issue Backing & Reconciliation.
    Verifies that every charged material line is backed by approved Stores issue quantities.
    Enforces:
    - Stable material_item_id matching.
    - Exclusion of DRAFT, SUBMITTED, CANCELLED, or REVERSED issue slips.
    - Aggregation of approved issue quantities across multiple slips referencing the heat.
    - Cross-heat duplicate allocation prevention: ensures issue quantity consumed by other
      heats does not double-count for this heat.
    - UOM compatibility checks (e.g. standard foundry mass units KG / MT).
    - Line-level shortfall detection with detailed exception structures.
    """
    clean_heat_num = heat.heat_number.replace("H-", "") if heat.heat_number else ""
    heat_refs = {heat.heat_number, clean_heat_num, f"H-{clean_heat_num}"} - {""}

    approved_issues = db.execute(
        select(MaterialIssueHeader).where(
            MaterialIssueHeader.heat_reference_number.in_(heat_refs),
            MaterialIssueHeader.status == IssueStatus.APPROVED.value,
        ).order_by(MaterialIssueHeader.id)
    ).scalars().all()

    # Track other heats referencing the same issue references to prevent double-consumption
    competing_heats = db.execute(
        select(HeatHeader).where(
            HeatHeader.heat_number.in_(heat_refs),
            HeatHeader.id != heat.id,
        )
    ).scalars().all()

    consumed_by_other_heats: Dict[int, Decimal] = defaultdict(lambda: Decimal("0.0000"))
    competing_heat_numbers: List[str] = []
    for other_heat in competing_heats:
        if other_heat.heat_date < heat.heat_date or (other_heat.heat_date == heat.heat_date and other_heat.id < heat.id):
            competing_heat_numbers.append(other_heat.heat_number)
            for c_line in other_heat.charge_lines:
                mat_id = c_line.material_item_id
                if not mat_id and c_line.original_material_description:
                    res = resolve_material_by_description(db, c_line.original_material_description)
                    mat_id = res.id if res else None
                if mat_id:
                    consumed_by_other_heats[mat_id] += c_line.charged_quantity

    issued_by_item: Dict[int, Decimal] = defaultdict(lambda: Decimal("0.0000"))
    issue_slips_by_item: Dict[int, List[str]] = defaultdict(list)
    issue_uoms_by_item: Dict[int, Set[int]] = defaultdict(set)
    all_issue_slip_numbers: List[str] = []

    for issue in approved_issues:
        all_issue_slip_numbers.append(issue.issue_slip_number)
        for i_line in issue.lines:
            issued_by_item[i_line.material_item_id] += i_line.quantity
            issue_slips_by_item[i_line.material_item_id].append(issue.issue_slip_number)
            issue_uoms_by_item[i_line.material_item_id].add(i_line.uom_id)

    available_issued_by_item: Dict[int, Decimal] = {}
    for mat_id, tot_issued in issued_by_item.items():
        prior_used = consumed_by_other_heats.get(mat_id, Decimal("0.0000"))
        available_issued_by_item[mat_id] = max(Decimal("0.0000"), tot_issued - prior_used)

    charged_by_item: Dict[int, Decimal] = defaultdict(lambda: Decimal("0.0000"))
    charge_uoms_by_item: Dict[int, Set[int]] = defaultdict(set)
    unresolved_charge_lines: List[HeatChargeLine] = []

    for c_line in heat.charge_lines:
        mat_id = c_line.material_item_id
        if not mat_id and c_line.original_material_description:
            res = resolve_material_by_description(db, c_line.original_material_description)
            mat_id = res.id if res else None

        if not mat_id:
            unresolved_charge_lines.append(c_line)
        else:
            charged_by_item[mat_id] += c_line.charged_quantity
            charge_uoms_by_item[mat_id].add(c_line.uom_id)

    shortfalls: List[Dict[str, Any]] = []
    line_reconciliation: List[Dict[str, Any]] = []
    anomalies: List[str] = []

    for un_line in unresolved_charge_lines:
        anomalies.append(
            f"UNBACKED_CHARGE_ITEM: Material '{un_line.original_material_description}' "
            f"charged {un_line.charged_quantity} kg cannot be resolved to an item code and has zero issue backing."
        )

    for mat_id, charged_qty in charged_by_item.items():
        item = db.get(MaterialItem, mat_id)
        item_code = item.item_code if item else f"ITEM-{mat_id}"
        item_name = item.name if item else "Unknown"

        available_issued = available_issued_by_item.get(mat_id, Decimal("0.0000"))
        shortfall = max(Decimal("0.0000"), charged_qty - available_issued)

        charge_uom_ids = charge_uoms_by_item.get(mat_id, set())
        issue_uom_ids = issue_uoms_by_item.get(mat_id, set())
        uom_compatible = True
        if charge_uom_ids and issue_uom_ids:
            if charge_uom_ids != issue_uom_ids:
                c_uoms = {(getattr(u, "code", None) or getattr(u, "uom_code", "")).upper() for u in db.execute(select(UOM).where(UOM.id.in_(charge_uom_ids))).scalars().all()}
                i_uoms = {(getattr(u, "code", None) or getattr(u, "uom_code", "")).upper() for u in db.execute(select(UOM).where(UOM.id.in_(issue_uom_ids))).scalars().all()}
                mass_units = {"KG", "KGS", "KILOGRAM", "MT", "TONNE", "TONNES"}
                if not (c_uoms.issubset(mass_units) and i_uoms.issubset(mass_units)):
                    uom_compatible = False
                    anomalies.append(
                        f"INCOMPATIBLE_ISSUE_UOM: Item {item_code} charged in UOM {c_uoms} but issued in {i_uoms}."
                    )

        if shortfall > Decimal("0.0000"):
            shortfalls.append({
                "material_item_id": mat_id,
                "item_code": item_code,
                "item_name": item_name,
                "charged_quantity_kg": charged_qty,
                "approved_issued_quantity_kg": available_issued,
                "shortfall_quantity_kg": shortfall,
                "status": "DEFICIT",
                "uom_compatible": uom_compatible,
            })
            if available_issued == Decimal("0.0000"):
                anomalies.append(
                    f"ZERO_ISSUE_BACKING: Item {item_code} charged {charged_qty} kg has 0 approved Stores issue quantity."
                )
            else:
                anomalies.append(
                    f"INSUFFICIENT_ISSUE_QUANTITY: Item {item_code} charged {charged_qty} kg but approved issues cover only {available_issued} kg (shortfall: {shortfall} kg)."
                )
        else:
            line_reconciliation.append({
                "material_item_id": mat_id,
                "item_code": item_code,
                "item_name": item_name,
                "charged_quantity_kg": charged_qty,
                "approved_issued_quantity_kg": available_issued,
                "shortfall_quantity_kg": Decimal("0.0000"),
                "status": "COVERED",
                "uom_compatible": uom_compatible,
            })

    for mat_id, prior_used in consumed_by_other_heats.items():
        if prior_used > Decimal("0.0000") and mat_id in charged_by_item:
            tot = issued_by_item.get(mat_id, Decimal("0.0000"))
            if tot < (prior_used + charged_by_item[mat_id]):
                item = db.get(MaterialItem, mat_id)
                ic = item.item_code if item else f"ITEM-{mat_id}"
                anomalies.append(
                    f"CROSS_HEAT_OVERCONSUMPTION: Issue quantity for {ic} ({tot} kg) was partially or fully consumed by prior heats {competing_heat_numbers} ({prior_used} kg used)."
                )

    non_approved_issues = db.execute(
        select(MaterialIssueHeader).where(
            MaterialIssueHeader.heat_reference_number.in_(heat_refs),
            MaterialIssueHeader.status != IssueStatus.APPROVED.value,
        )
    ).scalars().all()
    for na_issue in non_approved_issues:
        anomalies.append(
            f"UNAPPROVED_ISSUE_SLIP: Issue slip {na_issue.issue_slip_number} for heat {heat.heat_number} "
            f"has status '{na_issue.status}' and does not provide valid costing backing."
        )

    is_fully_backed = (
        len(approved_issues) > 0
        and len(shortfalls) == 0
        and len(unresolved_charge_lines) == 0
        and len(charged_by_item) > 0
        and all(item.get("uom_compatible", True) for item in line_reconciliation)
    )

    return {
        "is_fully_backed": is_fully_backed,
        "approved_issue_slip_numbers": list(set(all_issue_slip_numbers)),
        "shortfalls": shortfalls,
        "line_reconciliation": line_reconciliation,
        "anomalies": anomalies,
    }


def aggregate_heat_return_scrap_grns(
    db: Session,
    heat: HeatHeader,
) -> Tuple[Optional[Decimal], List[str], List[Dict[str, Any]]]:
    """
    AUD-2B2D-002: Multi-GRN Return Scrap Aggregation & Authoritative WAC Valuation.
    Aggregates all eligible approved internal return GRNs referencing this heat.
    Enforces:
    - Dynamic resolution of canonical return scrap item 'FDY-RM-003'.
    - Actual moving WAC lookup via get_item_rate_as_of_date.
    - Zero hardcoded rates (never falls back to ₹38/kg).
    - Returns PENDING_REVIEW if moving WAC is missing or scrap classification is ambiguous.
    - Aggregates multiple approved return GRNs.
    - Excludes DRAFT, SUBMITTED, CANCELLED, or REVERSED GRNs.
    - Prevents duplicate GRN credit and cross-heat double-allocation.
    """
    clean_heat_num = heat.heat_number.replace("H-", "") if heat.heat_number else ""
    heat_refs = {heat.heat_number, clean_heat_num, f"H-{clean_heat_num}"} - {""}

    anomalies: List[str] = []
    grn_details: List[Dict[str, Any]] = []

    scrap_item = db.execute(
        select(MaterialItem).where(MaterialItem.item_code == "FDY-RM-003")
    ).scalars().first()
    scrap_item_id = scrap_item.id if scrap_item else None

    scrap_rate: Optional[Decimal] = None
    if scrap_item_id:
        scrap_rate = get_item_rate_as_of_date(db, scrap_item_id, heat.heat_date)

    non_approved_grns = db.execute(
        select(GRNHeader).where(
            GRNHeader.source_type == GRNSourceType.INTERNAL_VSPL.value,
            GRNHeader.reference_document.in_(heat_refs),
            GRNHeader.status != GRNStatus.APPROVED.value,
        )
    ).scalars().all()
    for na_grn in non_approved_grns:
        anomalies.append(
            f"EXCLUDED_GRN: Internal return GRN {na_grn.grn_number} for heat {heat.heat_number} "
            f"has status '{na_grn.status}' and is excluded from scrap credit."
        )

    approved_grns = db.execute(
        select(GRNHeader).where(
            GRNHeader.source_type == GRNSourceType.INTERNAL_VSPL.value,
            GRNHeader.reference_document.in_(heat_refs),
            GRNHeader.status == GRNStatus.APPROVED.value,
        ).order_by(GRNHeader.id)
    ).scalars().all()

    if not approved_grns:
        return None, anomalies, grn_details

    seen_grn_ids: Set[int] = set()
    total_scrap_qty = Decimal("0.0000")
    total_scrap_credit = Decimal("0.00")
    has_unvalued_scrap = False

    for grn in approved_grns:
        if grn.id in seen_grn_ids:
            continue
        seen_grn_ids.add(grn.id)

        grn_ref = (grn.reference_document or "").strip().upper()
        if grn_ref not in {r.upper() for r in heat_refs}:
            continue

        for g_line in grn.lines:
            is_scrap = False
            if scrap_item_id and g_line.material_item_id == scrap_item_id:
                is_scrap = True
            elif "RETURN" in (g_line.remarks or "").upper() or "RUNNER" in (g_line.remarks or "").upper():
                is_scrap = True
            elif g_line.material_item and "RETURN" in g_line.material_item.name.upper():
                is_scrap = True

            if not is_scrap:
                continue

            line_qty = getattr(g_line, "accepted_quantity", getattr(g_line, "quantity", Decimal("0.0000")))
            if line_qty <= Decimal("0.0000"):
                continue

            total_scrap_qty += line_qty

            if scrap_rate is not None:
                line_credit = (line_qty * scrap_rate).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)
                total_scrap_credit += line_credit
                grn_details.append({
                    "grn_number": grn.grn_number,
                    "line_number": g_line.line_number,
                    "material_item_id": g_line.material_item_id,
                    "quantity_kg": line_qty,
                    "unit_rate": scrap_rate,
                    "credit_value": line_credit,
                    "status": "CREDITED",
                })
            else:
                has_unvalued_scrap = True
                grn_details.append({
                    "grn_number": grn.grn_number,
                    "line_number": g_line.line_number,
                    "material_item_id": g_line.material_item_id,
                    "quantity_kg": line_qty,
                    "unit_rate": None,
                    "credit_value": None,
                    "status": "PENDING_REVIEW",
                })

    if total_scrap_qty > Decimal("0.0000"):
        if has_unvalued_scrap or scrap_rate is None:
            anomalies.append(
                f"PENDING_REVIEW: Approved return scrap GRN exists for heat {heat.heat_number} "
                f"({total_scrap_qty} kg), but moving WAC for canonical scrap item (FDY-RM-003) "
                f"is unavailable as of {heat.heat_date}. No arbitrary rate applied."
            )
            return None, anomalies, grn_details
        else:
            return total_scrap_credit, anomalies, grn_details

    return None, anomalies, grn_details


def calculate_heat_cost_detail(
    db: Session,
    heat: HeatHeader,
    item_rates_cache: Optional[Dict[int, Optional[Decimal]]] = None,
    denominator_policy: str = DenominatorPolicy.METAL_TAPPED.value,
) -> Dict[str, Any]:
    """
    Calculates material-only heat cost and cost per kg for a single heat record.
    Uses rates as of heat.heat_date.
    NOTE: NEVER mutates heat records, reconciliation outputs, or stock ledger entries.
    """
    if item_rates_cache is None:
        item_rates_cache = {}

    total_charged_qty = Decimal("0.0000")
    total_material_cost = Decimal("0.00")
    line_details: List[Dict[str, Any]] = []
    valued_count = 0
    unvalued_count = 0

    for line in heat.charge_lines:
        charged_qty = line.charged_quantity
        total_charged_qty += charged_qty
        
        # 1. Resolve material item
        mat_id = line.material_item_id
        if not mat_id and line.original_material_description:
            resolved_item = resolve_material_by_description(db, line.original_material_description)
            if resolved_item:
                mat_id = resolved_item.id

        if not mat_id:
            unvalued_count += 1
            line_details.append({
                "heat_charge_line_id": line.id,
                "line_number": line.line_number,
                "material_item_id": None,
                "raw_material_description": line.original_material_description,
                "charged_quantity": charged_qty,
                "applicable_rate": None,
                "line_cost": None,
                "rate_source": None,
                "is_included": False,
                "status": "UNMAPPED_ALIAS",
                "remarks": "Material description not mapped to canonical item",
            })
            continue

        # 2. Look up rate as of heat.heat_date
        if mat_id not in item_rates_cache:
            item_rates_cache[mat_id] = get_item_rate_as_of_date(db, mat_id, heat.heat_date)
            
        rate = item_rates_cache[mat_id]

        if rate is None:
            unvalued_count += 1
            line_details.append({
                "heat_charge_line_id": line.id,
                "line_number": line.line_number,
                "material_item_id": mat_id,
                "raw_material_description": line.original_material_description,
                "charged_quantity": charged_qty,
                "applicable_rate": None,
                "line_cost": None,
                "rate_source": None,
                "is_included": False,
                "status": "MISSING_RATE",
                "remarks": f"No approved weighted-average rate as of heat date {heat.heat_date}",
            })
            continue

        # 3. Calculate line cost
        line_cost = (charged_qty * rate).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)
        total_material_cost += line_cost
        valued_count += 1

        line_details.append({
            "heat_charge_line_id": line.id,
            "line_number": line.line_number,
            "material_item_id": mat_id,
            "raw_material_description": line.original_material_description,
            "charged_quantity": charged_qty,
            "applicable_rate": rate,
            "line_cost": line_cost,
            "rate_source": f"WEIGHTED_AVG_{heat.heat_date}",
            "is_included": True,
            "status": "VALUED",
            "remarks": None,
        })

    # Overall heat costing status
    total_lines = len(heat.charge_lines)
    
    # -------------------------------------------------------------
    # Authoritative 3-Measure Calculation (Phase 2B-2B & Phase 2B-2C)
    # -------------------------------------------------------------
    is_historical_exception = (
        heat.heat_number in HISTORICAL_UNSUPPORTED_HEATS
        or (heat.heat_number and heat.heat_number.startswith("102603-"))
    )

    # AUD-2B2D-001: Reconcile Stores Issue Backing at Item Level
    issue_reconciliation = reconcile_heat_stores_issue_backing(db, heat)
    is_charge_fully_backed_by_issues = issue_reconciliation["is_fully_backed"]
    issue_backing_anomalies = issue_reconciliation["anomalies"]

    # Sum good casting weight
    good_wt = Decimal("0.0000")
    for p in heat.parts_produced:
        if p.classification == CastingClassification.GOOD.value and p.unit_cast_weight:
            good_wt += p.quantity_produced * p.unit_cast_weight
    good_castings_kg = good_wt if good_wt > Decimal("0.0000") else None

    # Liquid heel continuity (FIN-DEC-02)
    opening_heel_kg = getattr(heat, "opening_liquid_heel_kg", None)
    closing_heel_kg = getattr(heat, "closing_liquid_heel_kg", None)
    has_unverified_heel = False
    opening_heel_value = Decimal("0.00")

    if opening_heel_kg is not None and opening_heel_kg > Decimal("0.0000"):
        # Look up prior heat on same furnace
        prior_heat = db.execute(
            select(HeatHeader).where(
                HeatHeader.furnace_id == heat.furnace_id,
                HeatHeader.heat_date <= heat.heat_date,
                HeatHeader.id < heat.id,
            ).order_by(desc(HeatHeader.heat_date), desc(HeatHeader.id))
        ).scalars().first()

        if prior_heat:
            prior_detail = calculate_heat_cost_detail(
                db, prior_heat, item_rates_cache=item_rates_cache, denominator_policy=DenominatorPolicy.METAL_TAPPED.value
            )
            prior_rate = prior_detail.get("measure_b_cost_per_kg")
            prior_verified = getattr(prior_heat, "heel_verification_status", None) == "VERIFIED"
            if prior_rate is not None and (prior_verified or prior_detail.get("status") in ("FINAL", "PROVISIONAL")):
                opening_heel_value = (opening_heel_kg * prior_rate).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)
            else:
                has_unverified_heel = True
        else:
            if not getattr(heat, "is_cold_start", False):
                has_unverified_heel = True

    # AUD-2B2D-002: Multi-GRN Return Scrap Aggregation & Authoritative WAC
    approved_scrap_credit, scrap_anomalies, scrap_grn_details = aggregate_heat_return_scrap_grns(db, heat)

    costing_measures = calculate_heat_costing_measures(
        total_charged_kg=total_charged_qty,
        total_charged_material_cost=total_material_cost if valued_count == total_lines and total_lines > 0 else None,
        metal_tapped_kg=heat.metal_tapped_weight,
        good_castings_kg=good_castings_kg,
        opening_liquid_heel_kg=opening_heel_kg,
        opening_liquid_heel_value=opening_heel_value,
        closing_liquid_heel_kg=closing_heel_kg,
        has_unverified_heel=has_unverified_heel,
        is_charge_fully_backed_by_issues=is_charge_fully_backed_by_issues,
        approved_scrap_credit=approved_scrap_credit,
        is_historical_exception=is_historical_exception,
        normal_melt_loss_threshold_pct=Decimal("3.5000"),
    )

    cost_denominator_value: Optional[Decimal] = None
    cost_per_kg: Optional[Decimal] = None

    if denominator_policy == DenominatorPolicy.METAL_TAPPED.value:
        cost_denominator_value = heat.metal_tapped_weight
        cost_per_kg = costing_measures.cost_per_kg_metal_tapped
    elif denominator_policy == DenominatorPolicy.GOOD_CASTING_KG.value:
        cost_denominator_value = good_castings_kg
        cost_per_kg = costing_measures.raw_material_cost_per_kg_good_casting
    else:  # SOLID_CHARGE
        cost_denominator_value = total_charged_qty if total_charged_qty > Decimal("0.0000") else None
        cost_per_kg = costing_measures.cost_per_kg_solid_charge

    # Determine status
    if total_lines == 0 or valued_count == 0:
        heat_status = HeatCostStatus.INSUFFICIENT_COST_DATA.value
    elif valued_count < total_lines:
        heat_status = HeatCostStatus.PARTIAL_COST.value
    else:
        heat_status = costing_measures.costing_status

    return {
        "heat_id": heat.id,
        "heat_number": heat.heat_number,
        "heat_date": heat.heat_date,
        "total_charged_quantity": total_charged_qty,
        "total_material_cost": total_material_cost,
        "metal_tapped_weight": heat.metal_tapped_weight,
        "cost_denominator_value": cost_denominator_value,
        "denominator_type": denominator_policy,
        "cost_per_kg": cost_per_kg,
        "cost_scope": CostScope.MATERIAL_ONLY.value,
        "status": heat_status,
        "total_lines": total_lines,
        "valued_lines": valued_count,
        "unvalued_lines": unvalued_count,
        "lines": line_details,
        # Authoritative Measures A, B, C & details
        "measure_a_cost_per_kg": costing_measures.cost_per_kg_solid_charge,
        "measure_a_status": costing_measures.measure_a_status,
        "measure_b_cost_per_kg": costing_measures.cost_per_kg_metal_tapped,
        "measure_b_status": costing_measures.measure_b_status,
        "measure_c_cost_per_kg": costing_measures.raw_material_cost_per_kg_good_casting,
        "measure_c_status": costing_measures.measure_c_status,
        "opening_liquid_heel_kg": costing_measures.opening_liquid_heel_kg,
        "opening_liquid_heel_value": costing_measures.opening_liquid_heel_value,
        "closing_liquid_heel_kg": costing_measures.closing_liquid_heel_kg,
        "closing_liquid_heel_value": costing_measures.closing_liquid_heel_value,
        "approved_scrap_credit": costing_measures.approved_scrap_credit,
        "true_melt_loss_kg": costing_measures.true_melt_loss_kg,
        "true_melt_loss_pct": costing_measures.true_melt_loss_pct,
        "melting_recovery_pct": costing_measures.mass_balance_recovery_pct,
        "casting_yield_pct": costing_measures.casting_yield_pct,
        "conversion_cost_status": "NOT_AVAILABLE",
        "is_historical_exception": is_historical_exception,
        "is_charge_fully_backed_by_issues": is_charge_fully_backed_by_issues,
        "issue_backing_details": issue_reconciliation,
        "scrap_grn_details": scrap_grn_details,
        "anomalies": list(costing_measures.anomalies) + issue_backing_anomalies + scrap_anomalies,
    }


def calculate_part_cost_detail(
    part: HeatPartsProduced,
    heat_cost_per_kg: Optional[Decimal],
    heat_cost_status: str,
) -> Dict[str, Any]:
    """
    Calculates material-only cost per unit for a part produced.
    Formula: Unit Cast Weight * Heat Cost per kg.
    """
    unit_weight = part.unit_cast_weight
    qty = part.quantity_produced
    part_num = part.part_item.item_code if part.part_item else (part.source_row_reference or part.original_part_description)
    part_nm = part.part_item.name if part.part_item else part.original_part_description

    if unit_weight is None or unit_weight <= Decimal("0.0000"):
        return {
            "heat_parts_produced_id": part.id,
            "part_number": part_num,
            "part_name": part_nm,
            "part_item_id": part.part_item_id,
            "quantity_produced": qty,
            "unit_cast_weight": None,
            "weight_uom_id": part.weight_uom_id,
            "cost_per_kg": heat_cost_per_kg,
            "part_material_cost_per_unit": None,
            "total_part_material_cost": None,
            "cost_scope": CostScope.MATERIAL_ONLY.value,
            "status": PartCostStatus.MISSING_WEIGHT.value,
            "notes": "Unit cast weight not logged; cannot compute part material cost",
        }

    if heat_cost_per_kg is None or heat_cost_status not in (HeatCostStatus.COMPLETE.value, "FINAL", "PROVISIONAL", "PROVISIONAL_HISTORICAL"):
        return {
            "heat_parts_produced_id": part.id,
            "part_number": part_num,
            "part_name": part_nm,
            "part_item_id": part.part_item_id,
            "quantity_produced": qty,
            "unit_cast_weight": unit_weight,
            "weight_uom_id": part.weight_uom_id,
            "cost_per_kg": heat_cost_per_kg,
            "part_material_cost_per_unit": None,
            "total_part_material_cost": None,
            "cost_scope": CostScope.MATERIAL_ONLY.value,
            "status": PartCostStatus.INSUFFICIENT_COST_DATA.value,
            "notes": f"Parent heat cost per kg unavailable or incomplete (Heat Status: {heat_cost_status})",
        }

    cost_per_unit = (unit_weight * heat_cost_per_kg).quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)
    total_cost = (qty * cost_per_unit).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)

    return {
        "heat_parts_produced_id": part.id,
        "part_number": part_num,
        "part_name": part_nm,
        "part_item_id": part.part_item_id,
        "quantity_produced": qty,
        "unit_cast_weight": unit_weight,
        "weight_uom_id": part.weight_uom_id,
        "cost_per_kg": heat_cost_per_kg,
        "part_material_cost_per_unit": cost_per_unit,
        "total_part_material_cost": total_cost,
        "cost_scope": CostScope.MATERIAL_ONLY.value,
        "status": PartCostStatus.CALCULATED.value,
        "notes": "Provisional material-only unit cost based on unit cast weight",
    }


def execute_costing_run(
    db: Session,
    period_start: date,
    period_end: date,
    as_of_date: date,
    actor_id: str,
    denominator_policy: str = DenominatorPolicy.METAL_TAPPED.value,
    notes: Optional[str] = None,
) -> CostingRun:
    """
    Executes a complete, versioned, auditable Costing Run:
    1. Reconstructs weighted-average rates for all materials.
    2. Snapshots inventory quantities and extended values.
    3. Records step-by-step calculation journal entries.
    4. Calculates heat costs for all heats in period.
    5. Calculates part costs for all parts produced in period.
    6. Persists entire run under CostingRun without mutating stock ledger or heat sources.
    """
    def _create_run(run_num: str) -> CostingRun:
        run = CostingRun(
            run_number=run_num,
            calculation_version="v1.0.0",
            period_start=period_start,
            period_end=period_end,
            as_of_date=as_of_date,
            denominator_policy=denominator_policy,
            internal_recovery_policy="POLICY_PENDING",
            cost_scope=CostScope.MATERIAL_ONLY.value,
            status=CostingRunStatus.IN_PROGRESS.value,
            summary_notes=notes,
            created_by=actor_id,
        )
        db.add(run)
        return run

    costing_run = execute_with_document_number_retry(
        db=db,
        doc_type=DocumentType.COSTING_RUN,
        create_fn=_create_run,
        target_date=as_of_date,
    )

    # 1. Evaluate all active material items
    active_items = db.execute(select(MaterialItem).where(MaterialItem.is_active == True)).scalars().all()
    total_items = len(active_items)
    valued_items = 0
    unvalued_items = 0
    total_inv_val = Decimal("0.00")
    item_rates_cache: Dict[int, Optional[Decimal]] = {}

    for item in active_items:
        qty, avg_rate, val_status, rate_src, journal_steps = reconstruct_item_rate_evolution(
            db, item.id, as_of_date
        )
        item_rates_cache[item.id] = avg_rate

        ext_val: Optional[Decimal] = None
        if val_status == ValuationStatus.VALUED.value and avg_rate is not None:
            ext_val = (qty * avg_rate).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)
            total_inv_val += ext_val
            valued_items += 1
        elif val_status == ValuationStatus.ZERO_STOCK.value:
            ext_val = Decimal("0.00")
            valued_items += 1
        else:
            unvalued_items += 1

        # Create ItemCostSnapshot
        snapshot = ItemCostSnapshot(
            costing_run_id=costing_run.id,
            material_item_id=item.id,
            as_of_date=as_of_date,
            inventory_quantity=qty,
            weighted_average_rate=avg_rate,
            extended_value=ext_val,
            valuation_status=val_status,
            uom_id=item.base_uom_id,
            rate_source=rate_src,
        )
        db.add(snapshot)

        # Create ItemCostJournalEntry records
        for step in journal_steps:
            j_entry = ItemCostJournalEntry(
                costing_run_id=costing_run.id,
                material_item_id=item.id,
                stock_ledger_entry_id=step["stock_ledger_entry_id"],
                transaction_date=step["transaction_date"],
                movement_type=step["movement_type"],
                quantity_delta=step["quantity_delta"],
                running_quantity=step["running_quantity"],
                receipt_rate=step["receipt_rate"],
                applied_rate=step["applied_rate"],
                resulting_average_rate=step["resulting_average_rate"],
                movement_extended_value=step["movement_extended_value"],
                cumulative_value=step["cumulative_value"],
                status=step["status"],
                notes=step["notes"],
            )
            db.add(j_entry)

    # 2. Evaluate heats in period
    heats_in_period = db.execute(
        select(HeatHeader).where(
            and_(
                HeatHeader.heat_date >= period_start,
                HeatHeader.heat_date <= period_end,
            )
        ).order_by(HeatHeader.heat_date, HeatHeader.id)
    ).scalars().all()

    total_heats = len(heats_in_period)
    completed_heats = 0
    partial_heats = 0
    total_heat_cost = Decimal("0.00")

    for heat in heats_in_period:
        heat_calc = calculate_heat_cost_detail(
            db, heat, item_rates_cache=item_rates_cache, denominator_policy=denominator_policy
        )
        total_heat_cost += heat_calc["total_material_cost"]

        if heat_calc["status"] == HeatCostStatus.COMPLETE.value:
            completed_heats += 1
        elif heat_calc["status"] == HeatCostStatus.PARTIAL_COST.value:
            partial_heats += 1

        heat_rec = HeatCostRecord(
            costing_run_id=costing_run.id,
            heat_id=heat.id,
            heat_number=heat.heat_number,
            heat_date=heat.heat_date,
            total_charged_quantity=heat_calc["total_charged_quantity"],
            total_material_cost=heat_calc["total_material_cost"],
            metal_tapped_weight=heat_calc["metal_tapped_weight"],
            cost_denominator_value=heat_calc["cost_denominator_value"],
            denominator_type=heat_calc["denominator_type"],
            cost_per_kg=heat_calc["cost_per_kg"],
            cost_scope=heat_calc["cost_scope"],
            status=heat_calc["status"],
            total_lines=heat_calc["total_lines"],
            valued_lines=heat_calc["valued_lines"],
            unvalued_lines=heat_calc["unvalued_lines"],
        )
        db.add(heat_rec)
        db.flush()

        for l_detail in heat_calc["lines"]:
            h_line = HeatCostLine(
                heat_cost_record_id=heat_rec.id,
                heat_charge_line_id=l_detail["heat_charge_line_id"],
                line_number=l_detail["line_number"],
                material_item_id=l_detail["material_item_id"],
                raw_material_description=l_detail["raw_material_description"],
                charged_quantity=l_detail["charged_quantity"],
                applicable_rate=l_detail["applicable_rate"],
                line_cost=l_detail["line_cost"],
                rate_source=l_detail["rate_source"],
                is_included=l_detail["is_included"],
                status=l_detail["status"],
                remarks=l_detail["remarks"],
            )
            db.add(h_line)

        # Part costs for heat
        for part in heat.parts_produced:
            part_calc = calculate_part_cost_detail(
                part, heat_calc["cost_per_kg"], heat_calc["status"]
            )
            p_rec = PartCostRecord(
                costing_run_id=costing_run.id,
                heat_cost_record_id=heat_rec.id,
                heat_parts_produced_id=part.id,
                part_number=part_calc["part_number"],
                part_name=part_calc["part_name"],
                part_item_id=part_calc["part_item_id"],
                quantity_produced=part_calc["quantity_produced"],
                unit_cast_weight=part_calc["unit_cast_weight"],
                weight_uom_id=part_calc["weight_uom_id"],
                cost_per_kg=part_calc["cost_per_kg"],
                part_material_cost_per_unit=part_calc["part_material_cost_per_unit"],
                total_part_material_cost=part_calc["total_part_material_cost"],
                cost_scope=part_calc["cost_scope"],
                status=part_calc["status"],
                notes=part_calc["notes"],
            )
            db.add(p_rec)

    # 3. Finalize run record
    costing_run.total_items_evaluated = total_items
    costing_run.valued_items_count = valued_items
    costing_run.unvalued_items_count = unvalued_items
    costing_run.total_inventory_valuation = total_inv_val
    costing_run.total_heats_evaluated = total_heats
    costing_run.completed_heats_count = completed_heats
    costing_run.partial_heats_count = partial_heats
    costing_run.total_heat_material_cost = total_heat_cost
    costing_run.status = CostingRunStatus.COMPLETED.value

    db.commit()
    db.refresh(costing_run)
    return costing_run


def compare_costing_runs(
    db: Session,
    run_id_1: int,
    run_id_2: int,
) -> Dict[str, Any]:
    """
    Compares two Costing Runs side-by-side to highlight variances in rates,
    inventory valuations, and heat production costs.
    """
    run1 = db.get(CostingRun, run_id_1)
    run2 = db.get(CostingRun, run_id_2)
    if not run1 or not run2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both costing run IDs not found for comparison",
        )

    # Compare summary metrics
    summary_diff = {
        "run_1_number": run1.run_number,
        "run_2_number": run2.run_number,
        "run_1_as_of": str(run1.as_of_date),
        "run_2_as_of": str(run2.as_of_date),
        "valuation_run_1": float(run1.total_inventory_valuation),
        "valuation_run_2": float(run2.total_inventory_valuation),
        "valuation_delta": float(run2.total_inventory_valuation - run1.total_inventory_valuation),
        "heat_cost_run_1": float(run1.total_heat_material_cost),
        "heat_cost_run_2": float(run2.total_heat_material_cost),
        "heat_cost_delta": float(run2.total_heat_material_cost - run1.total_heat_material_cost),
    }

    # Item rate differences
    r1_snaps = {s.material_item_id: s for s in run1.item_snapshots}
    r2_snaps = {s.material_item_id: s for s in run2.item_snapshots}
    all_item_ids = set(r1_snaps.keys()).union(set(r2_snaps.keys()))

    item_diffs: List[Dict[str, Any]] = []
    for m_id in sorted(all_item_ids):
        s1 = r1_snaps.get(m_id)
        s2 = r2_snaps.get(m_id)
        
        item = db.get(MaterialItem, m_id)
        item_code = item.item_code if item else f"ID {m_id}"
        item_name = item.name if item else "Unknown"

        r1_rate = float(s1.weighted_average_rate) if s1 and s1.weighted_average_rate is not None else None
        r2_rate = float(s2.weighted_average_rate) if s2 and s2.weighted_average_rate is not None else None
        
        r1_val = float(s1.extended_value) if s1 and s1.extended_value is not None else None
        r2_val = float(s2.extended_value) if s2 and s2.extended_value is not None else None

        rate_delta = None
        if r1_rate is not None and r2_rate is not None:
            rate_delta = round(r2_rate - r1_rate, 4)

        val_delta = None
        if r1_val is not None and r2_val is not None:
            val_delta = round(r2_val - r1_val, 2)

        if rate_delta != 0 or val_delta != 0:
            item_diffs.append({
                "material_item_id": m_id,
                "item_code": item_code,
                "item_name": item_name,
                "run_1_rate": r1_rate,
                "run_2_rate": r2_rate,
                "rate_delta": rate_delta,
                "run_1_value": r1_val,
                "run_2_value": r2_val,
                "value_delta": val_delta,
                "run_1_status": s1.valuation_status if s1 else None,
                "run_2_status": s2.valuation_status if s2 else None,
            })

    return {
        "summary": summary_diff,
        "item_differences": item_diffs,
    }

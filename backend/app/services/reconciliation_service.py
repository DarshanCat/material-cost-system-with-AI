"""
Induction Furnace Issue-to-Heat Three-Pass Reconciliation Service.
Deterministic, explainable matching between Stores issues and furnace charges.
Strict Inventory Rule: Reconciliation never posts stock movements or modifies balances.
"""

from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import json
import re
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, and_, func
from fastapi import HTTPException, status

from app.models.heat import HeatHeader, HeatChargeLine, HeatChargeValidationStatus
from app.models.issue import MaterialIssueHeader, MaterialIssueLineItem, IssueStatus
from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.reconciliation import (
    ReconciliationRun,
    ReconciliationResult,
    ReconciliationCandidateMatch,
    ReconciliationException,
    ReconciliationExceptionAuditLog,
    VarianceClass,
    MatchMethod,
    CandidateMatchStatus,
    ExceptionStatus,
)
from app.services.validators import normalize_heat_number, normalize_alias_key
from app.services.material_alias_service import resolve_material_by_description


# Precedence tolerance constants per business rules
DEFAULT_RELATIVE_TOLERANCE = Decimal("0.02")  # 2%
DEFAULT_ABSOLUTE_TOLERANCE_KG = Decimal("0.5000")  # 0.5 kg


def calculate_tolerance_limit(
    issued_qty: Decimal,
    rel_tol: Decimal = DEFAULT_RELATIVE_TOLERANCE,
    abs_tol: Decimal = DEFAULT_ABSOLUTE_TOLERANCE_KG,
) -> Tuple[Decimal, str]:
    """
    Computes unambiguous tolerance limit based on documented precedence:
    Tolerance Limit = max(Absolute Tolerance, Relative Tolerance * Issued Quantity)
    Handles zero issued quantity safely.
    """
    if issued_qty <= Decimal("0"):
        return abs_tol, f"Absolute fallback ({abs_tol} UOM) due to zero issue quantity"
    
    calc_rel = issued_qty * rel_tol
    if calc_rel >= abs_tol:
        return calc_rel, f"Relative {rel_tol * Decimal('100')}% ({calc_rel:.4f} UOM)"
    else:
        return abs_tol, f"Absolute threshold ({abs_tol:.4f} UOM) exceeded relative {calc_rel:.4f}"


def classify_variance(
    issued_qty: Decimal,
    charged_qty: Decimal,
    tolerance_limit: Decimal,
) -> Tuple[str, Optional[Decimal]]:
    """
    Evaluates variance = Issued - Charged.
    Returns (VarianceClass, variance_percentage).
    """
    variance = issued_qty - charged_qty
    abs_diff = abs(variance)
    
    # Check percentage difference if issued_qty > 0
    pct: Optional[Decimal] = None
    if issued_qty > Decimal("0"):
        pct = (abs_diff / issued_qty) * Decimal("100")
    
    # Check for suspected order of magnitude scale error (e.g. ratio ~ 10, 100, 1000)
    if issued_qty > Decimal("0") and charged_qty > Decimal("0"):
        ratio = issued_qty / charged_qty
        if ratio >= Decimal("9.5") or ratio <= Decimal("0.105"):
            return VarianceClass.DECIMAL_SUSPECT.value, pct
    
    if abs_diff <= tolerance_limit:
        return VarianceClass.OK.value, pct
    
    if variance > tolerance_limit:
        # Issued > Charged
        return VarianceClass.EXCESS_ISSUE.value, pct
    else:
        # Charged > Issued
        return VarianceClass.SHORT_ISSUE.value, pct


def compute_string_similarity(s1: str, s2: str) -> float:
    """
    Simple deterministic character bigram / substring similarity score (0.0 to 1.0).
    """
    if not s1 or not s2:
        return 0.0
    c1, c2 = s1.strip().upper(), s2.strip().upper()
    if c1 == c2:
        return 1.0
    
    # Check substring inclusion
    if c1 in c2 or c2 in c1:
        return 0.85
    
    # Bigram overlap
    pairs1 = {c1[i:i+2] for i in range(len(c1) - 1)}
    pairs2 = {c2[i:i+2] for i in range(len(c2) - 1)}
    if not pairs1 or not pairs2:
        return 0.0
    intersection = pairs1.intersection(pairs2)
    return (2.0 * len(intersection)) / (len(pairs1) + len(pairs2))


def run_reconciliation(
    db: Session,
    created_by: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    notes: Optional[str] = None,
) -> ReconciliationRun:
    """
    Executes the deterministic 3-Pass Reconciliation Algorithm.
    Pass 1: Exact heat slip match
    Pass 2: Same-day batch aggregation for remaining unallocated lines
    Pass 3: Advisory fuzzy match candidate generation (never auto-confirmed)
    """
    run_timestamp = datetime.now(timezone.utc)
    run_number = f"REC-{run_timestamp.strftime('%Y%m%d')}-{int(run_timestamp.timestamp() % 10000):04d}"
    
    run = ReconciliationRun(
        run_number=run_number,
        algorithm_version="v1.0-3pass-deterministic",
        date_from=date_from,
        date_to=date_to,
        status="IN_PROGRESS",
        notes=notes,
        created_by=created_by,
        created_at=run_timestamp,
    )
    db.add(run)
    db.flush()

    # 1. Fetch relevant Issue Slips (Approved issues)
    issue_stmt = (
        select(MaterialIssueHeader)
        .options(
            selectinload(MaterialIssueHeader.lines).selectinload(MaterialIssueLineItem.material_item),
            selectinload(MaterialIssueHeader.lines).selectinload(MaterialIssueLineItem.uom),
        )
        .where(MaterialIssueHeader.status == IssueStatus.APPROVED.value)
    )
    if date_from:
        issue_stmt = issue_stmt.where(MaterialIssueHeader.issue_date >= date_from)
    if date_to:
        issue_stmt = issue_stmt.where(MaterialIssueHeader.issue_date <= date_to)
    issues = db.execute(issue_stmt).scalars().all()

    # 2. Fetch Heats and Charge Lines
    heat_stmt = (
        select(HeatHeader)
        .options(
            selectinload(HeatHeader.charge_lines).selectinload(HeatChargeLine.material_item),
            selectinload(HeatHeader.charge_lines).selectinload(HeatChargeLine.uom),
        )
    )
    if date_from:
        heat_stmt = heat_stmt.where(HeatHeader.heat_date >= date_from)
    if date_to:
        heat_stmt = heat_stmt.where(HeatHeader.heat_date <= date_to)
    heats = db.execute(heat_stmt).scalars().all()

    # Ensure all charge lines have resolved materials if possible
    for heat in heats:
        for cl in heat.charge_lines:
            if not cl.material_item_id:
                resolved = resolve_material_by_description(db, cl.original_material_description)
                if resolved:
                    cl.material_item_id = resolved.id
                    cl.validation_status = HeatChargeValidationStatus.VALID.value
                else:
                    cl.validation_status = HeatChargeValidationStatus.UNMAPPED_ALIAS.value

    # Allocation trackers to prevent double counting
    allocated_issue_line_ids: set[int] = set()
    allocated_charge_line_ids: set[int] = set()

    results: List[ReconciliationResult] = []
    candidates: List[ReconciliationCandidateMatch] = []
    exceptions: List[ReconciliationException] = []

    # Build lookup dictionaries
    # Map heats by normalized heat number and raw heat number
    heat_by_ref: Dict[str, HeatHeader] = {}
    for h in heats:
        heat_by_ref[h.normalized_heat_number] = h
        heat_by_ref[h.heat_number.strip().upper()] = h

    # -------------------------------------------------------------
    # PASS 1: Exact Heat-Slip Reference Matching
    # -------------------------------------------------------------
    exact_matches_count = 0
    for issue in issues:
        if not issue.heat_reference_number:
            continue
        
        raw_ref = issue.heat_reference_number.strip().upper()
        norm_ref = ""
        try:
            norm_ref = normalize_heat_number(raw_ref)
        except Exception:
            pass
        
        matched_heat = heat_by_ref.get(norm_ref) or heat_by_ref.get(raw_ref)
        if not matched_heat:
            continue
        
        # Match materials item-by-item between this issue and this heat
        issue_lines_by_item: Dict[int, List[MaterialIssueLineItem]] = {}
        for il in issue.lines:
            if il.id not in allocated_issue_line_ids:
                issue_lines_by_item.setdefault(il.material_item_id, []).append(il)
        
        heat_charges_by_item: Dict[int, List[HeatChargeLine]] = {}
        for cl in matched_heat.charge_lines:
            if cl.id not in allocated_charge_line_ids and cl.material_item_id:
                heat_charges_by_item.setdefault(cl.material_item_id, []).append(cl)
        
        all_item_ids = set(issue_lines_by_item.keys()).union(set(heat_charges_by_item.keys()))
        for item_id in all_item_ids:
            i_lines = issue_lines_by_item.get(item_id, [])
            c_lines = heat_charges_by_item.get(item_id, [])
            
            issued_qty = sum((l.quantity for l in i_lines), Decimal("0.0000"))
            charged_qty = sum((l.charged_quantity for l in c_lines), Decimal("0.0000"))
            
            tol_limit, tol_basis = calculate_tolerance_limit(issued_qty)
            v_class, v_pct = classify_variance(issued_qty, charged_qty, tol_limit)
            
            i_line_ids = [l.id for l in i_lines]
            c_line_ids = [l.id for l in c_lines]
            
            allocated_issue_line_ids.update(i_line_ids)
            allocated_charge_line_ids.update(c_line_ids)
            
            variance = issued_qty - charged_qty
            res = ReconciliationResult(
                run_id=run.id,
                material_item_id=item_id,
                heat_id=matched_heat.id,
                match_method=MatchMethod.EXACT_HEAT_SLIP.value,
                issued_quantity=issued_qty,
                charged_quantity=charged_qty,
                variance_quantity=variance,
                variance_percentage=v_pct,
                applied_tolerance=tol_limit,
                tolerance_basis=tol_basis,
                variance_class=v_class,
                contributing_issue_ids=json.dumps([issue.id]),
                contributing_issue_line_ids=json.dumps(i_line_ids),
                contributing_heat_ids=json.dumps([matched_heat.id]),
                contributing_charge_line_ids=json.dumps(c_line_ids),
                notes=f"Exact match on heat reference '{matched_heat.heat_number}'",
                status="RESOLVED" if v_class == VarianceClass.OK.value else "FLAGGED",
            )
            results.append(res)
            exact_matches_count += 1
            
            if v_class != VarianceClass.OK.value:
                exc = ReconciliationException(
                    run_id=run.id,
                    exception_type=v_class,
                    source_reference=f"Slip {issue.issue_slip_number} / Heat {matched_heat.heat_number}",
                    description=(
                        f"Item ID {item_id}: Issued {issued_qty} vs Charged {charged_qty} "
                        f"(Variance {variance:+.4f}, Tolerance {tol_limit:.4f})"
                    ),
                    assigned_role="Foundry" if v_class == VarianceClass.SHORT_ISSUE.value else "Stores",
                    priority="HIGH" if v_class == VarianceClass.DECIMAL_SUSPECT.value else "MEDIUM",
                    status=ExceptionStatus.OPEN.value,
                )
                exceptions.append(exc)

    # -------------------------------------------------------------
    # PASS 2: Same-Day Batch Aggregation
    # -------------------------------------------------------------
    batch_matches_count = 0
    # Group remaining unallocated lines by (date, material_item_id)
    unallocated_issue_lines_by_date_item: Dict[Tuple[date, int], List[MaterialIssueLineItem]] = {}
    for issue in issues:
        for il in issue.lines:
            if il.id not in allocated_issue_line_ids:
                key = (issue.issue_date, il.material_item_id)
                unallocated_issue_lines_by_date_item.setdefault(key, []).append(il)
    
    unallocated_charge_lines_by_date_item: Dict[Tuple[date, int], List[HeatChargeLine]] = {}
    for heat in heats:
        for cl in heat.charge_lines:
            if cl.id not in allocated_charge_line_ids and cl.material_item_id:
                key = (heat.heat_date, cl.material_item_id)
                unallocated_charge_lines_by_date_item.setdefault(key, []).append(cl)
    
    common_date_items = set(unallocated_issue_lines_by_date_item.keys()).intersection(
        set(unallocated_charge_lines_by_date_item.keys())
    )
    
    for (d, item_id) in common_date_items:
        i_lines = unallocated_issue_lines_by_date_item[(d, item_id)]
        c_lines = unallocated_charge_lines_by_date_item[(d, item_id)]
        
        issued_qty = sum((l.quantity for l in i_lines), Decimal("0.0000"))
        charged_qty = sum((l.charged_quantity for l in c_lines), Decimal("0.0000"))
        
        tol_limit, tol_basis = calculate_tolerance_limit(issued_qty)
        v_class, v_pct = classify_variance(issued_qty, charged_qty, tol_limit)
        
        i_line_ids = [l.id for l in i_lines]
        c_line_ids = [l.id for l in c_lines]
        issue_ids = list({l.issue_id for l in i_lines})
        heat_ids = list({l.heat_id for l in c_lines})
        
        allocated_issue_line_ids.update(i_line_ids)
        allocated_charge_line_ids.update(c_line_ids)
        
        variance = issued_qty - charged_qty
        res = ReconciliationResult(
            run_id=run.id,
            material_item_id=item_id,
            heat_id=heat_ids[0] if len(heat_ids) == 1 else None,
            match_method=MatchMethod.SAME_DAY_BATCH.value,
            issued_quantity=issued_qty,
            charged_quantity=charged_qty,
            variance_quantity=variance,
            variance_percentage=v_pct,
            applied_tolerance=tol_limit,
            tolerance_basis=f"Same-day aggregation ({d.isoformat()}): {tol_basis}",
            variance_class=v_class,
            contributing_issue_ids=json.dumps(issue_ids),
            contributing_issue_line_ids=json.dumps(i_line_ids),
            contributing_heat_ids=json.dumps(heat_ids),
            contributing_charge_line_ids=json.dumps(c_line_ids),
            notes=f"Aggregated {len(i_lines)} issue lines and {len(c_lines)} heat charge lines on {d.isoformat()}",
            status="RESOLVED" if v_class == VarianceClass.OK.value else "FLAGGED",
        )
        results.append(res)
        batch_matches_count += 1
        
        if v_class != VarianceClass.OK.value:
            exc = ReconciliationException(
                run_id=run.id,
                exception_type=v_class,
                source_reference=f"Date {d.isoformat()} / Item {item_id}",
                description=(
                    f"Same-day batch: Issued {issued_qty} vs Charged {charged_qty} "
                    f"(Variance {variance:+.4f}, Tolerance {tol_limit:.4f})"
                ),
                assigned_role="Foundry" if v_class == VarianceClass.SHORT_ISSUE.value else "Stores",
                priority="MEDIUM",
                status=ExceptionStatus.OPEN.value,
            )
            exceptions.append(exc)

    # -------------------------------------------------------------
    # PASS 3: Advisory Fuzzy Suggestions (Advisory Only)
    # -------------------------------------------------------------
    fuzzy_candidates_count = 0
    # Collect remaining unallocated issue lines and charge lines
    remaining_issue_lines = [
        il for issue in issues for il in issue.lines
        if il.id not in allocated_issue_line_ids
    ]
    remaining_charge_lines = [
        cl for heat in heats for cl in heat.charge_lines
        if cl.id not in allocated_charge_line_ids and cl.material_item_id
    ]

    for il in remaining_issue_lines:
        parent_issue = il.header
        for cl in remaining_charge_lines:
            parent_heat = cl.heat
            
            # Check 1: Must be the same material item
            if il.material_item_id != cl.material_item_id:
                continue
            
            # Check 2: Date difference <= 1 day (accommodates shift crossover)
            date_diff = abs((parent_issue.issue_date - parent_heat.heat_date).days)
            if date_diff > 1:
                continue
            
            # Check 3: Reference similarity or quantity proximity
            ref_sim = 0.0
            if parent_issue.heat_reference_number:
                ref_sim = compute_string_similarity(
                    parent_issue.heat_reference_number, parent_heat.heat_number
                )
            
            qty_diff = abs(il.quantity - cl.charged_quantity)
            qty_sim = Decimal("0.0")
            if il.quantity > Decimal("0"):
                qty_sim = max(Decimal("0.0"), Decimal("1.0") - (qty_diff / il.quantity))
            
            confidence = Decimal("0.0")
            reasons = []
            if ref_sim >= 0.7:
                confidence += Decimal(str(round(ref_sim * 50, 2)))
                reasons.append(f"Heat ref similarity {ref_sim*100:.1f}%")
            if date_diff <= 1:
                confidence += Decimal("30.0")
                reasons.append(f"Date delta {date_diff} day(s)")
            if qty_sim >= Decimal("0.90"):
                confidence += Decimal("20.0")
                reasons.append(f"Quantity match ({il.quantity} vs {cl.charged_quantity})")
            
            # Candidate threshold: confidence >= 60%
            if confidence >= Decimal("60.0"):
                candidate = ReconciliationCandidateMatch(
                    run_id=run.id,
                    issue_line_id=il.id,
                    heat_charge_line_id=cl.id,
                    confidence_score=min(Decimal("99.0"), confidence),
                    suggestion_reason="; ".join(reasons),
                    status=CandidateMatchStatus.SUGGESTED.value,
                )
                candidates.append(candidate)
                fuzzy_candidates_count += 1

    # -------------------------------------------------------------
    # Unmatched Queues & Unmapped Materials
    # -------------------------------------------------------------
    # Charge lines with unmapped alias
    for heat in heats:
        for cl in heat.charge_lines:
            if not cl.material_item_id:
                exc = ReconciliationException(
                    run_id=run.id,
                    exception_type=VarianceClass.UNMAPPED_MATERIAL.value,
                    source_reference=f"Heat {heat.heat_number} / Line {cl.line_number}",
                    description=f"Unmapped material description: '{cl.original_material_description}'",
                    assigned_role="Stores",
                    priority="HIGH",
                    status=ExceptionStatus.OPEN.value,
                )
                exceptions.append(exc)

    # Remaining unmatched issue lines
    for il in remaining_issue_lines:
        res = ReconciliationResult(
            run_id=run.id,
            material_item_id=il.material_item_id,
            heat_id=None,
            match_method=MatchMethod.UNMATCHED_SLIP.value,
            issued_quantity=il.quantity,
            charged_quantity=Decimal("0.0000"),
            variance_quantity=il.quantity,
            applied_tolerance=Decimal("0.0000"),
            tolerance_basis="No heat match found",
            variance_class=VarianceClass.UNMATCHED_SLIP.value,
            contributing_issue_ids=json.dumps([il.issue_id]),
            contributing_issue_line_ids=json.dumps([il.id]),
            notes="Unmatched issue slip line",
            status="FLAGGED",
        )
        results.append(res)

    # Remaining unmatched charge lines
    for cl in remaining_charge_lines:
        res = ReconciliationResult(
            run_id=run.id,
            material_item_id=cl.material_item_id,
            heat_id=cl.heat_id,
            match_method=MatchMethod.UNMATCHED_HEAT.value,
            issued_quantity=Decimal("0.0000"),
            charged_quantity=cl.charged_quantity,
            variance_quantity=-cl.charged_quantity,
            applied_tolerance=Decimal("0.0000"),
            tolerance_basis="No issue slip match found",
            variance_class=VarianceClass.UNMATCHED_HEAT.value,
            contributing_heat_ids=json.dumps([cl.heat_id]),
            contributing_charge_line_ids=json.dumps([cl.id]),
            notes="Unmatched heat charge line",
            status="FLAGGED",
        )
        results.append(res)

    # Update summary counts
    discrepancies_count = sum(1 for r in results if r.variance_class != VarianceClass.OK.value)
    run.total_evaluated_count = len(results)
    run.exact_matches_count = exact_matches_count
    run.batch_matches_count = batch_matches_count
    run.fuzzy_candidates_count = fuzzy_candidates_count
    run.discrepancies_count = discrepancies_count
    run.status = "COMPLETED"

    for r in results:
        db.add(r)
    for c in candidates:
        db.add(c)
    for e in exceptions:
        db.add(e)

    db.commit()
    db.refresh(run)
    return run


def confirm_candidate_match(
    db: Session,
    candidate_id: int,
    reviewer_id: str,
    comments: Optional[str] = None,
) -> ReconciliationCandidateMatch:
    """
    Explicit human confirmation of an advisory fuzzy match candidate.
    Creates a MANUAL_CONFIRMED ReconciliationResult and updates candidate status.
    NOTE: Never alters stock balances or ledger entries.
    """
    candidate = db.execute(
        select(ReconciliationCandidateMatch)
        .options(
            selectinload(ReconciliationCandidateMatch.issue_line),
            selectinload(ReconciliationCandidateMatch.charge_line),
        )
        .where(ReconciliationCandidateMatch.id == candidate_id)
    ).scalar_one_or_none()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate match ID {candidate_id} not found",
        )
    if candidate.status != CandidateMatchStatus.SUGGESTED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Candidate is already in state '{candidate.status}'",
        )

    candidate.status = CandidateMatchStatus.CONFIRMED.value
    candidate.reviewed_by = reviewer_id
    candidate.reviewed_at = datetime.now(timezone.utc)
    candidate.review_comments = comments or "Confirmed by supervisor"

    # Add ReconciliationResult representing manual confirmation
    il = candidate.issue_line
    cl = candidate.charge_line
    tol_limit, tol_basis = calculate_tolerance_limit(il.quantity)
    v_class, v_pct = classify_variance(il.quantity, cl.charged_quantity, tol_limit)
    variance = il.quantity - cl.charged_quantity

    res = ReconciliationResult(
        run_id=candidate.run_id,
        material_item_id=il.material_item_id,
        heat_id=cl.heat_id,
        match_method=MatchMethod.MANUAL_CONFIRMED.value,
        issued_quantity=il.quantity,
        charged_quantity=cl.charged_quantity,
        variance_quantity=variance,
        variance_percentage=v_pct,
        applied_tolerance=tol_limit,
        tolerance_basis=f"Manual confirmation: {tol_basis}",
        variance_class=v_class,
        contributing_issue_ids=json.dumps([il.issue_id]),
        contributing_issue_line_ids=json.dumps([il.id]),
        contributing_heat_ids=json.dumps([cl.heat_id]),
        contributing_charge_line_ids=json.dumps([cl.id]),
        notes=f"Human confirmed candidate #{candidate.id} ({reviewer_id}): {comments or ''}",
        status="RESOLVED" if v_class == VarianceClass.OK.value else "FLAGGED",
    )
    db.add(res)
    db.commit()
    db.refresh(candidate)
    return candidate


def reject_candidate_match(
    db: Session,
    candidate_id: int,
    reviewer_id: str,
    comments: str,
) -> ReconciliationCandidateMatch:
    """
    Rejects an advisory candidate match. Comments mandatory.
    """
    if not comments or not comments.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection comments are mandatory",
        )
    candidate = db.execute(
        select(ReconciliationCandidateMatch).where(ReconciliationCandidateMatch.id == candidate_id)
    ).scalar_one_or_none()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate match ID {candidate_id} not found",
        )
    
    candidate.status = CandidateMatchStatus.REJECTED.value
    candidate.reviewed_by = reviewer_id
    candidate.reviewed_at = datetime.now(timezone.utc)
    candidate.review_comments = comments.strip()
    db.commit()
    db.refresh(candidate)
    return candidate


def resolve_exception(
    db: Session,
    exception_id: int,
    resolver_id: str,
    action: str,
    comments: str,
) -> ReconciliationException:
    """
    Resolves an open reconciliation exception with audit trail.
    """
    if not comments or not comments.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resolution comments are mandatory",
        )
    exc = db.execute(
        select(ReconciliationException).where(ReconciliationException.id == exception_id)
    ).scalar_one_or_none()
    if not exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reconciliation exception ID {exception_id} not found",
        )
    
    from_status = exc.status
    to_status = (
        ExceptionStatus.RESOLVED.value if action == "RESOLVE" else ExceptionStatus.ACCEPTED_LOSS.value
    )
    exc.status = to_status
    exc.resolved_by = resolver_id
    exc.resolved_at = datetime.now(timezone.utc)
    exc.resolution_comments = comments.strip()

    audit = ReconciliationExceptionAuditLog(
        exception_id=exc.id,
        action=action,
        from_status=from_status,
        to_status=to_status,
        actor_id=resolver_id,
        comments=comments.strip(),
    )
    db.add(audit)
    db.commit()
    db.refresh(exc)
    return exc


def get_reconciliation_run_detail(db: Session, run_id: int) -> Optional[ReconciliationRun]:
    """Retrieves full reconciliation run with results, candidates, and exceptions."""
    return db.execute(
        select(ReconciliationRun)
        .options(
            selectinload(ReconciliationRun.results).selectinload(ReconciliationResult.material_item),
            selectinload(ReconciliationRun.results).selectinload(ReconciliationResult.heat),
            selectinload(ReconciliationRun.candidate_matches).selectinload(ReconciliationCandidateMatch.issue_line),
            selectinload(ReconciliationRun.candidate_matches).selectinload(ReconciliationCandidateMatch.charge_line),
            selectinload(ReconciliationRun.exceptions),
        )
        .where(ReconciliationRun.id == run_id)
    ).scalar_one_or_none()


def list_reconciliation_runs(
    db: Session,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[ReconciliationRun], int]:
    """Lists reconciliation runs with pagination."""
    stmt = select(ReconciliationRun)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.execute(
        stmt.order_by(ReconciliationRun.id.desc()).offset(offset).limit(limit)
    ).scalars().all()
    return items, total

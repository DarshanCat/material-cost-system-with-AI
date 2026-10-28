"""
Automated Test Suite for Sprint 3.2: Document-Number Robustness Remediation.

Test Coverage:
1. Normal sequential number generation across all 8 document types [SQLite].
2. Database-side aggregate (MAX) sequence recovery when records are deleted/gapped [SQLite].
3. Multi-line in-session allocation (db.new) monotonic increment [SQLite].
4. Bounded savepoint retry resolving collision on recalculation [SQLite].
5. Exhausted retries returning HTTP 409 Conflict [SQLite].
6. Savepoint rollback when callback raises non-IntegrityError exception [SQLite].
7. Outer transaction usability preserved after nested savepoint failure [SQLite].
8. Recalculation of fresh document number on each retry attempt [SQLite].
9. Unrelated unique constraints (e.g. item_code, composite ledger constraint) NOT retried [SQLite].
10. Exact PostgreSQL constraint-diagnostic matching (SQLSTATE 23505, diag.constraint_name) [Mocked Diagnostics].
11. Four-digit sequence boundary and overflow prevention [SQLite].
12. Six-digit ledger sequence boundary and overflow prevention [SQLite].
13. Long posting-group source identifiers retaining uniqueness suffix and length <= 50 [Unit].
14. High-frequency posting-group generation uniqueness [Unit].
15. Absence of partial records after failed document creation [SQLite].
16. End-to-end API workflows across all domain routes [SQLite].
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import types
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.costing import CostingRun
from app.models.department import Department
from app.models.grn import GRNHeader, GRNLineItem, GRNStatus, GRNSourceType
from app.models.issue import MaterialIssueHeader, MaterialIssueLineItem, IssueStatus
from app.models.item import MaterialItem
from app.models.item_request import ItemRequest, RequestStatus
from app.models.ledger import StockLedgerEntry, MovementType
from app.models.physical_audit import PhysicalAuditHeader, PhysicalAuditLine, AuditStatus
from app.models.reconciliation import ReconciliationRun
from app.models.uom import UOM
from app.models.vendor import Vendor
from app.models.waste import WasteDispositionHeader, WasteDispositionLineItem, WasteStatus, WasteType, DispositionType
from app.services.document_number_service import (
    DOCUMENT_CONFIGS,
    DocumentType,
    SequenceExhaustedError,
    execute_with_document_number_retry,
    generate_document_number,
    generate_posting_group_id,
    generate_reversal_posting_group_id,
    is_document_number_collision,
)
from app.services.grn_service import create_grn, generate_grn_number
from app.services.issue_service import create_material_issue, generate_issue_slip_number
from app.services.item_request_service import ItemRequestService
from app.services.ledger_service import generate_ledger_entry_number
from app.services.physical_audit_service import create_physical_audit, generate_audit_number
from app.services.reconciliation_service import run_reconciliation
from app.services.waste_service import create_waste_disposition, generate_waste_number


# ==============================================================================
# Helper fixtures
# ==============================================================================

def _create_test_material_item(db: Session, code: str = "RM-CI-001") -> MaterialItem:
    dept = db.execute(select(Department).where(Department.code == "FDY")).scalar_one()
    uom = db.execute(select(UOM).where(UOM.code == "KG")).scalar_one()
    item = MaterialItem(
        item_code=code,
        name=f"Test Material {code}",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom.id,
        is_active=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _create_test_vendor(db: Session, name: str = "Standard Metal Traders") -> Vendor:
    vendor = Vendor(
        name=name,
        normalized_name=name.strip().upper(),
        address="Belgaum, Karnataka",
        gstin="29ABCDE1234F1Z5",
        is_active=True,
    )
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


# ==============================================================================
# 1. Normal number generation for every document type [SQLite Tests]
# ==============================================================================

def test_document_number_generation_all_types(db_session: Session):
    """[SQLite Test] Verifies that all 8 document types generate compliant, date-prefixed document numbers."""
    target_date = date(2026, 10, 22)

    expected_prefixes = {
        DocumentType.GRN: "GRN-20261022-0001",
        DocumentType.ISSUE: "ISS-20261022-0001",
        DocumentType.WASTE: "WST-20261022-0001",
        DocumentType.AUDIT: "AUD-20261022-0001",
        DocumentType.LEDGER: "STK-20261022-0001",
        DocumentType.COSTING_RUN: "CRUN-20261022-0001",
        DocumentType.ITEM_REQUEST: "REQ-20261022-0001",
        DocumentType.RECONCILIATION_RUN: "REC-20261022-0001",
    }

    for doc_type, expected_doc_num in expected_prefixes.items():
        doc_num = generate_document_number(db_session, doc_type, target_date)
        assert doc_num == expected_doc_num, f"Mismatch for {doc_type}: got {doc_num}, expected {expected_doc_num}"


def test_date_prefix_behaviour(db_session: Session):
    """[SQLite Test] Verifies date formatting across past, present, and leap dates."""
    dates_to_test = [
        (date(2024, 2, 29), "20240229"),
        (date(2026, 1, 1), "20260101"),
        (date(2026, 12, 31), "20261231"),
    ]

    for d, d_str in dates_to_test:
        doc_num = generate_document_number(db_session, DocumentType.GRN, d)
        assert doc_num.startswith(f"GRN-{d_str}-")


def test_sequential_creation_without_duplicates(db_session: Session):
    """[SQLite Test] Verifies that sequentially persisted documents increment sequence numbers monotonically."""
    target_date = date(2026, 10, 22)

    for i in range(1, 4):
        num = generate_document_number(db_session, DocumentType.GRN, target_date)
        assert num == f"GRN-20261022-{i:04d}"
        header = GRNHeader(
            grn_number=num,
            receipt_date=target_date,
            source_type=GRNSourceType.INTERNAL_VSPL.value,
            status=GRNStatus.DRAFT.value,
            created_by="user_test",
        )
        db_session.add(header)
        db_session.commit()

    next_num = generate_document_number(db_session, DocumentType.GRN, target_date)
    assert next_num == "GRN-20261022-0004"


def test_sequence_recovers_from_deleted_or_gapped_records_via_max(db_session: Session):
    """
    [SQLite Test] Verifies that if row 0002 is deleted or lower numbers are missing,
    the generator takes database-side MAX + 1 rather than table count + 1, avoiding collisions.
    """
    target_date = date(2026, 10, 22)

    h1 = GRNHeader(
        grn_number="GRN-20261022-0001",
        receipt_date=target_date,
        source_type=GRNSourceType.INTERNAL_VSPL.value,
        status=GRNStatus.DRAFT.value,
        created_by="user_test",
    )
    h5 = GRNHeader(
        grn_number="GRN-20261022-0005",
        receipt_date=target_date,
        source_type=GRNSourceType.INTERNAL_VSPL.value,
        status=GRNStatus.DRAFT.value,
        created_by="user_test",
    )
    db_session.add_all([h1, h5])
    db_session.commit()

    # Even though count is 2, next sequence must be 6 (0006)
    next_num = generate_document_number(db_session, DocumentType.GRN, target_date)
    assert next_num == "GRN-20261022-0006"


def test_multi_line_ledger_allocation_sequential_within_one_session(db_session: Session):
    """
    [SQLite Test] Verifies that multiple uncommitted objects added to db.new before flush
    receive distinct, incrementing sequence numbers.
    """
    target_date = date(2026, 10, 22)

    n1 = generate_document_number(db_session, DocumentType.LEDGER, target_date)
    assert n1 == "STK-20261022-0001"
    e1 = StockLedgerEntry(
        entry_number=n1,
        posting_group_id="POST-TEST-1",
        material_item_id=1,
        uom_id=1,
        transaction_date=target_date,
        movement_type=MovementType.INWARD_RECEIPT.value,
        quantity_delta=Decimal("10.0000"),
        source_document_type="GRN",
        source_document_id=1,
        source_line_id=1,
        source_document_number="GRN-1",
        posted_by="user_test",
    )
    db_session.add(e1)

    n2 = generate_document_number(db_session, DocumentType.LEDGER, target_date)
    assert n2 == "STK-20261022-0002"
    e2 = StockLedgerEntry(
        entry_number=n2,
        posting_group_id="POST-TEST-1",
        material_item_id=1,
        uom_id=1,
        transaction_date=target_date,
        movement_type=MovementType.INWARD_RECEIPT.value,
        quantity_delta=Decimal("20.0000"),
        source_document_type="GRN",
        source_document_id=1,
        source_line_id=2,
        source_document_number="GRN-1",
        posted_by="user_test",
    )
    db_session.add(e2)

    n3 = generate_document_number(db_session, DocumentType.LEDGER, target_date)
    assert n3 == "STK-20261022-0003"


# ==============================================================================
# 2. Savepoint handling & Transaction Safety [SQLite Tests]
# ==============================================================================

def test_savepoint_rollback_on_non_integrity_error_exception(db_session: Session):
    """
    [SQLite Test] Verifies that when a callback raises a non-IntegrityError exception
    (e.g. ValueError or HTTPException), the nested savepoint is rolled back cleanly,
    leaving no dirty objects in session.
    """
    target_date = date(2026, 10, 22)

    def _failing_create(doc_num: str) -> GRNHeader:
        h = GRNHeader(
            grn_number=doc_num,
            receipt_date=target_date,
            source_type=GRNSourceType.INTERNAL_VSPL.value,
            status=GRNStatus.DRAFT.value,
            created_by="user_test",
        )
        db_session.add(h)
        raise ValueError("Simulated business logic validation error")

    with pytest.raises(ValueError, match="Simulated business logic validation error"):
        execute_with_document_number_retry(
            db=db_session,
            doc_type=DocumentType.GRN,
            create_fn=_failing_create,
            target_date=target_date,
        )

    # Assert no GRN record exists in database
    records = db_session.execute(select(GRNHeader)).scalars().all()
    assert len(records) == 0


def test_outer_transaction_remains_usable_after_failed_nested_attempt(db_session: Session):
    """
    [SQLite Test] Verifies that a failed nested attempt within execute_with_document_number_retry
    does not poison or roll back the caller's outer transaction.
    """
    # 1. Start work in outer transaction
    vendor = _create_test_vendor(db_session, "Active Outer Vendor")
    db_session.flush()

    # 2. Execute failing document creation
    def _fail_callback(_doc_num: str):
        raise RuntimeError("Non-integrity unexpected failure")

    with pytest.raises(RuntimeError):
        execute_with_document_number_retry(
            db=db_session,
            doc_type=DocumentType.GRN,
            create_fn=_fail_callback,
        )

    # 3. Outer transaction continues cleanly and commits
    item = _create_test_material_item(db_session, "OUTER-ITEM-01")
    db_session.commit()

    # 4. Both outer vendor and outer item were persisted successfully
    v_check = db_session.get(Vendor, vendor.id)
    i_check = db_session.get(MaterialItem, item.id)
    assert v_check is not None
    assert i_check is not None


def test_pre_savepoint_autoflush_failure_not_retried(db_session: Session):
    """
    [SQLite Test] Verifies that if caller's session already contains invalid pending objects
    before execute_with_document_number_retry is invoked, the pre-savepoint autoflush failure
    is immediately re-raised and NEVER treated as a document-number collision or retried.
    """
    # Pre-commit an item
    _create_test_material_item(db_session, code="EXISTING-CODE")

    # Add an uncommitted conflicting item to the session (will fail autoflush on begin_nested)
    dept = db_session.execute(select(Department).where(Department.code == "FDY")).scalar_one()
    uom = db_session.execute(select(UOM).where(UOM.code == "KG")).scalar_one()
    invalid_item = MaterialItem(
        item_code="EXISTING-CODE",
        name="Conflicting Pending Item",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom.id,
        is_active=True,
    )
    db_session.add(invalid_item)

    callback_attempts = 0

    def _should_not_be_called(doc_num: str):
        nonlocal callback_attempts
        callback_attempts += 1
        return GRNHeader(grn_number=doc_num, receipt_date=date.today(), created_by="test")

    with pytest.raises(IntegrityError):
        execute_with_document_number_retry(
            db=db_session,
            doc_type=DocumentType.GRN,
            create_fn=_should_not_be_called,
            max_retries=3,
        )

    # The callback must not have executed because begin_nested() failed during pre-savepoint autoflush
    assert callback_attempts == 0


def test_outer_transaction_clean_objects_preserved_on_nested_collision_retry(db_session: Session):
    """
    [SQLite Test] Verifies that valid dirty objects in the caller's outer transaction
    remain intact and committed when a nested document creation experiences a collision and retries.
    """
    target_date = date(2026, 10, 22)

    # Pre-commit 0001
    existing = GRNHeader(
        grn_number="GRN-20261022-0001",
        receipt_date=target_date,
        source_type=GRNSourceType.INTERNAL_VSPL.value,
        status=GRNStatus.DRAFT.value,
        created_by="worker_prev",
    )
    db_session.add(existing)
    db_session.commit()

    # Outer transaction adds a pending vendor without committing
    vendor = Vendor(
        name="Pending Outer Vendor",
        normalized_name="PENDING OUTER VENDOR",
        address="Bangalore, Karnataka",
        gstin="29PENDING1234F1Z1",
        is_active=True,
    )
    db_session.add(vendor)

    attempts = 0

    def _colliding_create(doc_num: str) -> GRNHeader:
        nonlocal attempts
        attempts += 1
        forced_num = "GRN-20261022-0001" if attempts == 1 else doc_num
        h = GRNHeader(
            grn_number=forced_num,
            receipt_date=target_date,
            source_type=GRNSourceType.INTERNAL_VSPL.value,
            status=GRNStatus.DRAFT.value,
            created_by="worker_new",
        )
        db_session.add(h)
        return h

    header = execute_with_document_number_retry(
        db=db_session,
        doc_type=DocumentType.GRN,
        create_fn=_colliding_create,
        target_date=target_date,
        max_retries=3,
    )
    db_session.commit()

    # Assert both the outer vendor AND the newly allocated GRN (0002) were persisted!
    assert attempts == 2
    assert header.grn_number == "GRN-20261022-0002"
    v_check = db_session.get(Vendor, vendor.id)
    assert v_check is not None
    assert v_check.name == "Pending Outer Vendor"


def test_retry_recalculates_fresh_number_after_genuine_collision(db_session: Session):
    """
    [SQLite Test] Verifies that when a collision occurs on attempt 1, the retry loop
    recalculates a fresh document number on attempt 2 rather than reusing the colliding one.
    """
    target_date = date(2026, 10, 22)

    # Worker A pre-commits 0001
    existing = GRNHeader(
        grn_number="GRN-20261022-0001",
        receipt_date=target_date,
        source_type=GRNSourceType.INTERNAL_VSPL.value,
        status=GRNStatus.DRAFT.value,
        created_by="worker_a",
    )
    db_session.add(existing)
    db_session.commit()

    allocated_numbers = []

    def _create(doc_num: str) -> GRNHeader:
        allocated_numbers.append(doc_num)
        # On first attempt, force a collision by using the pre-committed 0001
        forced_num = "GRN-20261022-0001" if len(allocated_numbers) == 1 else doc_num
        h = GRNHeader(
            grn_number=forced_num,
            receipt_date=target_date,
            source_type=GRNSourceType.INTERNAL_VSPL.value,
            status=GRNStatus.DRAFT.value,
            created_by="worker_b",
        )
        db_session.add(h)
        return h

    header = execute_with_document_number_retry(
        db=db_session,
        doc_type=DocumentType.GRN,
        create_fn=_create,
        target_date=target_date,
        max_retries=3,
    )
    db_session.commit()

    # Attempt 1 received 0002, collided with forced 0001.
    # Attempt 2 recalculated and successfully committed 0002.
    assert len(allocated_numbers) == 2
    assert header.grn_number == "GRN-20261022-0002"


def test_exhausted_retries_returns_controlled_409_conflict(db_session: Session):
    """[SQLite Test] Verifies that exhausted retries raise HTTP 409 Conflict with clear detail."""
    target_date = date(2026, 10, 22)

    existing = GRNHeader(
        grn_number="GRN-20261022-0001",
        receipt_date=target_date,
        source_type=GRNSourceType.INTERNAL_VSPL.value,
        status=GRNStatus.DRAFT.value,
        created_by="worker_background",
    )
    db_session.add(existing)
    db_session.commit()

    attempts = 0

    def _always_colliding_create(_doc_num: str) -> GRNHeader:
        nonlocal attempts
        attempts += 1
        h = GRNHeader(
            grn_number="GRN-20261022-0001",
            receipt_date=target_date,
            source_type=GRNSourceType.INTERNAL_VSPL.value,
            status=GRNStatus.DRAFT.value,
            created_by="worker_collision",
        )
        db_session.add(h)
        return h

    with pytest.raises(HTTPException) as exc_info:
        execute_with_document_number_retry(
            db=db_session,
            doc_type=DocumentType.GRN,
            create_fn=_always_colliding_create,
            target_date=target_date,
            max_retries=3,
        )

    assert exc_info.value.status_code == 409
    assert "Concurrent creation conflict for Goods Receipt Note after 3 attempts" in exc_info.value.detail
    assert attempts == 3


def test_unrelated_unique_violations_never_retried(db_session: Session):
    """
    [SQLite Test] Verifies that unrelated unique constraint violations
    (e.g. unique item_code or double-posting composite constraint) are NOT retried.
    """
    target_date = date(2026, 10, 22)
    attempts = 0

    _create_test_material_item(db_session, code="DUP-ITEM-CODE")

    def _unrelated_violating_create(doc_num: str) -> GRNHeader:
        nonlocal attempts
        attempts += 1
        dept = db_session.execute(select(Department).where(Department.code == "FDY")).scalar_one()
        uom = db_session.execute(select(UOM).where(UOM.code == "KG")).scalar_one()
        # Conflicts on material_items.item_code
        item = MaterialItem(
            item_code="DUP-ITEM-CODE",
            name="Conflicting Item",
            department_id=dept.id,
            category="RAW_MATERIALS",
            base_uom_id=uom.id,
            is_active=True,
        )
        db_session.add(item)
        db_session.flush()
        return GRNHeader(grn_number=doc_num, receipt_date=target_date, created_by="user")

    with pytest.raises(IntegrityError):
        execute_with_document_number_retry(
            db=db_session,
            doc_type=DocumentType.GRN,
            create_fn=_unrelated_violating_create,
            target_date=target_date,
            max_retries=4,
        )

    # Must fail on attempt 1 without entering retry loop
    assert attempts == 1


# ==============================================================================
# 3. PostgreSQL Driver Diagnostic Discrimination [Mocked Tests]
# ==============================================================================

def test_exact_postgresql_constraint_diagnostic_matching_mocked():
    """
    [Mocked Diagnostics Test] Verifies exact PostgreSQL driver diagnostics discrimination.
    Tests structured psycopg 3 / psycopg 2 attributes (sqlstate 23505, diag.constraint_name).
    """
    # 1. Intended document-number collision on PostgreSQL standard constraint name
    mock_orig_success = types.SimpleNamespace(
        sqlstate="23505",
        pgcode="23505",
        diag=types.SimpleNamespace(
            constraint_name="grn_headers_grn_number_key",
            column_name="grn_number",
            table_name="grn_headers",
            message_detail="Key (grn_number)=(GRN-20261022-0001) already exists.",
        ),
    )
    exc_success = IntegrityError(statement="INSERT ...", params={}, orig=mock_orig_success)
    assert is_document_number_collision(exc_success, "grn_number", "grn_headers") is True

    # 2. Intended document-number collision on PostgreSQL Alembic convention (uq_table_column)
    mock_orig_uq = types.SimpleNamespace(
        sqlstate="23505",
        diag=types.SimpleNamespace(
            constraint_name="uq_grn_headers_grn_number",
            column_name="grn_number",
            table_name="grn_headers",
            message_detail="Key (grn_number)=(GRN-20261022-0001) already exists.",
        ),
    )
    exc_uq = IntegrityError(statement="INSERT ...", params={}, orig=mock_orig_uq)
    assert is_document_number_collision(exc_uq, "grn_number", "grn_headers") is True

    # 3. Unrelated unique constraint (e.g. stock ledger double-posting constraint) MUST be False
    mock_orig_double_post = types.SimpleNamespace(
        sqlstate="23505",
        diag=types.SimpleNamespace(
            constraint_name="uq_source_doc_line_posting",
            message_detail="Key (source_document_type, source_line_id)=(GRN, 1) already exists.",
        ),
    )
    exc_double_post = IntegrityError(statement="INSERT ...", params={}, orig=mock_orig_double_post)
    assert is_document_number_collision(exc_double_post, "entry_number", "stock_ledger_entries") is False

    # 4. Unrelated unique constraint (e.g. item_code) MUST be False
    mock_orig_item = types.SimpleNamespace(
        sqlstate="23505",
        diag=types.SimpleNamespace(
            constraint_name="material_items_item_code_key",
            message_detail="Key (item_code)=(RM-001) already exists.",
        ),
    )
    exc_item = IntegrityError(statement="INSERT ...", params={}, orig=mock_orig_item)
    assert is_document_number_collision(exc_item, "grn_number", "grn_headers") is False

    # 5. Foreign Key violation (SQLSTATE 23503) MUST be False
    mock_orig_fk = types.SimpleNamespace(
        sqlstate="23503",
        diag=types.SimpleNamespace(
            constraint_name="fk_grn_headers_vendor_id",
            message_detail="Key (vendor_id)=(9999) is not present in table vendors.",
        ),
    )
    exc_fk = IntegrityError(statement="INSERT ...", params={}, orig=mock_orig_fk)
    assert is_document_number_collision(exc_fk, "grn_number", "grn_headers") is False

    # 6. Check constraint violation (SQLSTATE 23514) MUST be False
    mock_orig_check = types.SimpleNamespace(
        sqlstate="23514",
        diag=types.SimpleNamespace(
            constraint_name="chk_quantity_positive",
        ),
    )
    exc_check = IntegrityError(statement="INSERT ...", params={}, orig=mock_orig_check)
    assert is_document_number_collision(exc_check, "grn_number", "grn_headers") is False

    # 7. NOT NULL violation (SQLSTATE 23502) MUST be False
    mock_orig_null = types.SimpleNamespace(
        sqlstate="23502",
        diag=types.SimpleNamespace(
            column_name="receipt_date",
        ),
    )
    exc_null = IntegrityError(statement="INSERT ...", params={}, orig=mock_orig_null)
    assert is_document_number_collision(exc_null, "grn_number", "grn_headers") is False


# ==============================================================================
# 4. Sequence Width Boundaries and Overflow Behaviour [SQLite Tests]
# ==============================================================================

def test_four_digit_sequence_boundary_and_overflow(db_session: Session):
    """
    [SQLite Test] Verifies that a 4-digit sequence correctly permits 9999 as its upper
    boundary, and strictly raises SequenceExhaustedError when 10,000 is attempted.
    """
    target_date = date(2026, 10, 22)

    # Insert 9999 directly
    h9999 = GRNHeader(
        grn_number="GRN-20261022-9999",
        receipt_date=target_date,
        source_type=GRNSourceType.INTERNAL_VSPL.value,
        status=GRNStatus.DRAFT.value,
        created_by="boundary_test",
    )
    db_session.add(h9999)
    db_session.commit()

    # Attempting to allocate next document on 4-digit width must raise SequenceExhaustedError
    with pytest.raises(SequenceExhaustedError) as exc_info:
        generate_document_number(db_session, DocumentType.GRN, target_date, padding=4)

    assert exc_info.value.status_code == 409
    assert "Sequence capacity exhausted for GRN on 20261022" in exc_info.value.detail
    assert "9999" in exc_info.value.detail


def test_six_digit_ledger_sequence_boundary_and_overflow(db_session: Session):
    """
    [SQLite Test] Verifies that a 6-digit ledger sequence correctly permits 999999,
    and raises SequenceExhaustedError when 1,000,000 is reached.
    """
    target_date = date(2026, 10, 22)

    # Insert 999999 directly
    e999999 = StockLedgerEntry(
        entry_number="STK-20261022-999999",
        posting_group_id="POST-LIMIT",
        material_item_id=1,
        uom_id=1,
        transaction_date=target_date,
        movement_type=MovementType.INWARD_RECEIPT.value,
        quantity_delta=Decimal("1.0000"),
        source_document_type="GRN",
        source_document_id=1,
        source_line_id=1,
        source_document_number="GRN-1",
        posted_by="user_test",
    )
    db_session.add(e999999)
    db_session.commit()

    with pytest.raises(SequenceExhaustedError) as exc_info:
        generate_document_number(db_session, DocumentType.LEDGER, target_date, padding=6)

    assert exc_info.value.status_code == 409
    assert "Sequence capacity exhausted for LEDGER on 20261022" in exc_info.value.detail
    assert "999999" in exc_info.value.detail


# ==============================================================================
# 5. Posting-Group ID Robustness & Constraint Limits [Unit Tests]
# ==============================================================================

def test_long_posting_group_source_identifiers_retain_uniqueness_suffix():
    """
    [Unit Test] Verifies that even when an excessively long source identifier (e.g. 80 chars)
    is supplied, the ID remains strictly <= 50 chars AND the random uniqueness suffix
    (-YYYYMMDDHHMMSS-HEX8) is never truncated.
    """
    long_id = "EXTREMELY-LONG-SOURCE-IDENTIFIER-THAT-EXCEEDS-ANY-CONVENTIONAL-LIMIT"
    pg_id = generate_posting_group_id("SOURCE_DEPT", long_id)

    assert len(pg_id) <= 50, f"Length {len(pg_id)} exceeds 50!"
    assert pg_id.startswith("POST-SOURCE_DEPT-")

    # The last 24 characters must be -YYYYMMDDHHMMSS-HEX8
    suffix = pg_id[-24:]
    assert suffix.startswith("-")
    parts = suffix[1:].split("-")
    assert len(parts) == 2
    assert len(parts[0]) == 14  # Timestamp
    assert len(parts[1]) == 8   # Hex8 entropy


def test_long_reversal_posting_group_id_retains_uniqueness_suffix():
    """
    [Unit Test] Verifies that reversal posting group IDs preserve uniqueness suffix
    under excessively long entry numbers.
    """
    long_entry = "STK-20261022-VERY-LONG-CUSTOM-ENTRY-IDENTIFIER-OVERFLOW"
    rev_id = generate_reversal_posting_group_id(long_entry)

    assert len(rev_id) <= 50, f"Length {len(rev_id)} exceeds 50!"
    assert rev_id.startswith("REV-")

    suffix = rev_id[-24:]
    assert suffix.startswith("-")
    parts = suffix[1:].split("-")
    assert len(parts) == 2
    assert len(parts[0]) == 14
    assert len(parts[1]) == 8


def test_repeated_posting_group_generation_preserves_uniqueness():
    """
    [Unit Test] Generates 10,000 posting group IDs in rapid loop.
    Asserts 100% distinct set with zero collisions and all <= 50 chars.
    """
    ids = set()
    for i in range(10000):
        val = generate_posting_group_id("GEN", i)
        assert len(val) <= 50
        ids.add(val)

    assert len(ids) == 10000, "Collision detected in posting group IDs!"


# ==============================================================================
# 6. Absence of Partial Records on Creation Failure [SQLite Tests]
# ==============================================================================

def test_absence_of_partial_records_on_failed_grn_creation(db_session: Session):
    """
    [SQLite Test] Verifies that if line item validation or insertion fails, the savepoint rolls back
    and zero header or line records remain in the database.
    """
    from app.schemas.grn import GRNCreate, GRNLineItemCreate
    vendor = _create_test_vendor(db_session)
    item = _create_test_material_item(db_session)

    initial_header_count = db_session.execute(select(GRNHeader)).scalars().all()
    initial_line_count = db_session.execute(select(GRNLineItem)).scalars().all()

    # Create payload with invalid rate (missing rate for RAW_MATERIALS from EXTERNAL_VENDOR triggers 422)
    payload = GRNCreate(
        receipt_date=date.today(),
        source_type=GRNSourceType.EXTERNAL_VENDOR,
        vendor_id=vendor.id,
        lines=[
            GRNLineItemCreate(
                line_number=1,
                material_item_id=item.id,
                uom_id=item.base_uom_id,
                quantity=Decimal("15.0000"),
                rate_ex_gst=None,
                gst_percent=Decimal("18.00"),
            )
        ],
    )

    with pytest.raises(HTTPException) as exc_info:
        create_grn(db_session, payload, created_by="user_test")

    assert exc_info.value.status_code == 422

    # Assert no residual header or lines exist
    current_headers = db_session.execute(select(GRNHeader)).scalars().all()
    current_lines = db_session.execute(select(GRNLineItem)).scalars().all()
    assert len(current_headers) == len(initial_header_count)
    assert len(current_lines) == len(initial_line_count)


# ==============================================================================
# 7. End-to-end API creation regression checks [SQLite Tests]
# ==============================================================================

def test_grn_api_creation_flow(client, stores_headers, db_session: Session):
    """[SQLite Test] Verifies end-to-end GRN creation through FastAPI endpoint."""
    vendor = _create_test_vendor(db_session)
    item = _create_test_material_item(db_session)

    payload = {
        "receipt_date": "2026-10-22",
        "source_type": "EXTERNAL_VENDOR",
        "vendor_id": vendor.id,
        "vendor_invoice_no": "INV-TEST-001",
        "invoice_date": "2026-10-22",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": item.base_uom_id,
                "quantity": "50.0000",
                "rate_ex_gst": "120.0000",
                "gst_percent": "18.00",
            }
        ],
    }

    resp = client.post("/api/v1/grn/", json=payload, headers=stores_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["grn_number"].startswith("GRN-20261022-")


def test_issue_api_creation_flow(client, stores_headers, db_session: Session):
    """[SQLite Test] Verifies end-to-end Material Issue creation through FastAPI endpoint."""
    fdy_dept = db_session.execute(select(Department).where(Department.code == "FDY")).scalar_one()
    item = _create_test_material_item(db_session)

    payload = {
        "issue_date": "2026-10-22",
        "issuing_department_id": fdy_dept.id,
        "receiving_department_id": fdy_dept.id,
        "heat_reference_number": "HEAT-TEST-01",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": item.base_uom_id,
                "quantity": "25.0000",
            }
        ],
    }

    resp = client.post("/api/v1/issues/", json=payload, headers=stores_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["issue_slip_number"].startswith("ISS-20261022-")


def test_waste_api_creation_flow(client, stores_headers, db_session: Session):
    """[SQLite Test] Verifies end-to-end Waste Disposition creation through FastAPI endpoint."""
    fdy_dept = db_session.execute(select(Department).where(Department.code == "FDY")).scalar_one()
    item = _create_test_material_item(db_session)

    payload = {
        "disposition_date": "2026-10-22",
        "waste_type": "SLAG",
        "disposition_type": "SCRAP_OUTWARD",
        "source_department_id": fdy_dept.id,
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": item.base_uom_id,
                "quantity": "5.0000",
                "reason": "Furnace slag separation",
            }
        ],
    }

    resp = client.post("/api/v1/waste/", json=payload, headers=stores_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["waste_number"].startswith("WST-20261022-")


def test_physical_audit_api_creation_flow(client, stores_headers, db_session: Session):
    """[SQLite Test] Verifies end-to-end Physical Audit creation through FastAPI endpoint."""
    fdy_dept = db_session.execute(select(Department).where(Department.code == "FDY")).scalar_one()
    item = _create_test_material_item(db_session)

    payload = {
        "audit_date": "2026-10-22",
        "department_id": fdy_dept.id,
        "notes": "Annual physical count",
        "lines": [
            {
                "material_item_id": item.id,
                "uom_id": item.base_uom_id,
                "physical_quantity": "100.0000",
                "reason": "Floor count verified",
            }
        ],
    }

    resp = client.post("/api/v1/physical-audits/", json=payload, headers=stores_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["audit_number"].startswith("AUD-20261022-")


def test_item_request_api_creation_flow(client, stores_headers, db_session: Session):
    """[SQLite Test] Verifies end-to-end Item Request creation through FastAPI endpoint."""
    fdy_dept = db_session.execute(select(Department).where(Department.code == "FDY")).scalar_one()
    uom = db_session.execute(select(UOM).where(UOM.code == "KG")).scalar_one()

    payload = {
        "requested_name": "Inoculant FeSi 75 Special",
        "proposed_department_id": fdy_dept.id,
        "proposed_category": "RM",  # Nomenclature Standard v1.0 category (Raw Material)
        "proposed_subcategory": "INOCULANT",
        "proposed_uom_id": uom.id,
        "justification": "Required for ladle inoculation",
    }

    resp = client.post("/api/v1/item-requests/", json=payload, headers=stores_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["request_number"].startswith("REQ-")


def test_reconciliation_run_number_sequential_not_repeating(db_session: Session):
    """
    [SQLite Test] Verifies that reconciliation run numbers follow sequential numbering: REC-YYYYMMDD-XXXX
    and do not repeat even when executed within the exact same second/timestamp.
    """
    target_date = date(2026, 10, 22)

    runs = []
    for _ in range(1, 4):
        def _create(num: str) -> ReconciliationRun:
            r = ReconciliationRun(
                run_number=num,
                algorithm_version="v1.0-test",
                status="COMPLETED",
                created_by="user_recon",
            )
            db_session.add(r)
            return r

        run = execute_with_document_number_retry(
            db=db_session,
            doc_type=DocumentType.RECONCILIATION_RUN,
            create_fn=_create,
            target_date=target_date,
        )
        db_session.commit()
        runs.append(run.run_number)

    assert runs == ["REC-20261022-0001", "REC-20261022-0002", "REC-20261022-0003"]
    assert len(set(runs)) == 3


# ==============================================================================
# 8. Sprint 3.3: Model Table-Name Alignment, ix_* Index Diagnostics & Live PG Concurrency
# ==============================================================================

def test_document_configs_match_model_tablenames_and_pg_index_names():
    """
    [Unit / Model Alignment Test] Verifies that every DocumentConfig.table_name matches
    its SQLAlchemy model's actual __tablename__ and includes the ix_{table}_{column}
    unique index name created by Alembic migrations 001-005.
    """
    expected_tables = {
        DocumentType.GRN: ("grn_headers", "grn_number"),
        DocumentType.ISSUE: ("material_issue_headers", "issue_slip_number"),
        DocumentType.WASTE: ("waste_disposition_headers", "waste_number"),
        DocumentType.AUDIT: ("physical_audit_headers", "audit_number"),
        DocumentType.LEDGER: ("stock_ledger_entries", "entry_number"),
        DocumentType.COSTING_RUN: ("costing_runs", "run_number"),
        DocumentType.ITEM_REQUEST: ("item_requests", "request_number"),
        DocumentType.RECONCILIATION_RUN: ("reconciliation_runs", "run_number"),
    }

    for doc_type, (expected_table, expected_col) in expected_tables.items():
        cfg = DOCUMENT_CONFIGS[doc_type]
        assert cfg.table_name == expected_table
        assert cfg.model_class.__tablename__ == expected_table
        assert cfg.column_name == expected_col
        assert f"ix_{expected_table}_{expected_col}" in cfg.pg_constraint_names
        assert f"uq_{expected_table}_{expected_col}" in cfg.pg_constraint_names
        assert f"{expected_table}_{expected_col}_key" in cfg.pg_constraint_names


def test_postgresql_ix_unique_index_diagnostic_matching_all_corrected_types():
    """
    [Mocked Diagnostics Test] Verifies that is_document_number_collision recognizes
    the exact ix_{table}_{column} unique index names from migrations 001-005 and rejects
    stale table names or unrelated unique constraints on the same tables.
    """
    for doc_type, cfg in DOCUMENT_CONFIGS.items():
        ix_name = f"ix_{cfg.table_name}_{cfg.column_name}"
        mock_orig = types.SimpleNamespace(
            sqlstate="23505",
            pgcode="23505",
            diag=types.SimpleNamespace(
                constraint_name=ix_name,
                table_name=cfg.table_name,
            ),
        )
        exc = IntegrityError(statement="INSERT ...", params={}, orig=mock_orig)
        assert is_document_number_collision(exc, cfg.column_name, cfg.table_name) is True, (
            f"Failed to match intended unique index {ix_name} for {doc_type}"
        )

    # Stale/wrong table names must NOT match the corrected config table names
    stale_cases = [
        ("ix_material_issues_issue_slip_number", "issue_slip_number", "material_issue_headers"),
        ("ix_waste_dispositions_waste_number", "waste_number", "waste_disposition_headers"),
        ("ix_physical_audits_audit_number", "audit_number", "physical_audit_headers"),
        ("uq_source_doc_line_posting", "entry_number", "stock_ledger_entries"),
        ("ix_material_items_item_code", "issue_slip_number", "material_issue_headers"),
    ]
    for bad_constraint, col_name, tbl_name in stale_cases:
        mock_bad = types.SimpleNamespace(
            sqlstate="23505",
            diag=types.SimpleNamespace(constraint_name=bad_constraint),
        )
        exc_bad = IntegrityError(statement="INSERT ...", params={}, orig=mock_bad)
        assert is_document_number_collision(exc_bad, col_name, tbl_name) is False


def test_postgres_live_concurrent_document_number_collision_and_retry(pg_session_factory):
    """
    [Real PostgreSQL Concurrency Test] Uses 4 independent PostgreSQL sessions/threads
    synchronized via threading.Barrier so all 4 sessions read the same initial MAX()
    sequence before any commits, forcing genuine PostgreSQL 23505 unique-index collisions
    on ix_material_issue_headers_issue_slip_number, ix_waste_disposition_headers_waste_number,
    ix_physical_audit_headers_audit_number, and ix_grn_headers_grn_number, and verifying
    savepoint rollback + sequence retry recovery.
    """
    import threading
    from sqlalchemy import delete

    num_workers = 4
    target_dates = {
        DocumentType.ISSUE: date(2099, 3, 1),
        DocumentType.WASTE: date(2099, 3, 2),
        DocumentType.AUDIT: date(2099, 3, 3),
        DocumentType.GRN: date(2099, 3, 4),
    }

    with pg_session_factory() as prep_db:
        fdy_dept_id = prep_db.execute(select(Department.id).where(Department.code == "FDY")).scalar_one()
        prep_db.execute(delete(MaterialIssueHeader).where(MaterialIssueHeader.issue_date == target_dates[DocumentType.ISSUE]))
        prep_db.execute(delete(WasteDispositionHeader).where(WasteDispositionHeader.disposition_date == target_dates[DocumentType.WASTE]))
        prep_db.execute(delete(PhysicalAuditHeader).where(PhysicalAuditHeader.audit_date == target_dates[DocumentType.AUDIT]))
        prep_db.execute(delete(GRNHeader).where(GRNHeader.receipt_date == target_dates[DocumentType.GRN]))
        prep_db.commit()

    def _run_concurrent_batch(doc_type: DocumentType, tx_date: date, builder_fn):
        barrier = threading.Barrier(num_workers)
        results = [None] * num_workers
        errors = [None] * num_workers
        first_attempt_numbers = [[] for _ in range(num_workers)]

        def _worker(idx: int):
            try:
                with pg_session_factory() as worker_db:
                    attempt_counter = 0

                    def _create(doc_num: str):
                        nonlocal attempt_counter
                        attempt_counter += 1
                        first_attempt_numbers[idx].append(doc_num)
                        if attempt_counter == 1:
                            # All 4 threads read MAX() before any thread flushes/commits
                            barrier.wait(timeout=10)
                        obj = builder_fn(doc_num, idx)
                        worker_db.add(obj)
                        return obj

                    created = execute_with_document_number_retry(
                        db=worker_db,
                        doc_type=doc_type,
                        create_fn=_create,
                        target_date=tx_date,
                        max_retries=8,
                    )
                    worker_db.commit()
                    results[idx] = getattr(created, DOCUMENT_CONFIGS[doc_type].column_name)
            except Exception as e:
                errors[idx] = e

        threads = [threading.Thread(target=_worker, args=(i,)) for i in range(num_workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)

        assert all(err is None for err in errors), f"Errors in {doc_type}: {errors}"
        # Prove contention occurred: every worker initially generated -0001 on attempt 1
        for idx in range(num_workers):
            assert first_attempt_numbers[idx][0].endswith("-0001"), (
                f"Worker {idx} did not contend on -0001: {first_attempt_numbers[idx]}"
            )
        # At least num_workers - 1 workers had to retry (>1 attempt)
        total_retries = sum(len(attempts) - 1 for attempts in first_attempt_numbers)
        assert total_retries >= num_workers - 1
        return sorted(results)

    issue_nums = _run_concurrent_batch(
        DocumentType.ISSUE,
        target_dates[DocumentType.ISSUE],
        lambda num, idx: MaterialIssueHeader(
            issue_slip_number=num,
            issue_date=target_dates[DocumentType.ISSUE],
            issuing_department_id=fdy_dept_id,
            receiving_department_id=fdy_dept_id,
            status=IssueStatus.DRAFT.value,
            created_by=f"pg_worker_{idx}",
        ),
    )
    assert issue_nums == [f"ISS-20990301-000{i}" for i in range(1, 5)]

    waste_nums = _run_concurrent_batch(
        DocumentType.WASTE,
        target_dates[DocumentType.WASTE],
        lambda num, idx: WasteDispositionHeader(
            waste_number=num,
            disposition_date=target_dates[DocumentType.WASTE],
            waste_type=WasteType.SLAG.value,
            disposition_type=DispositionType.SCRAP_OUTWARD.value,
            source_department_id=fdy_dept_id,
            status=WasteStatus.DRAFT.value,
            created_by=f"pg_worker_{idx}",
        ),
    )
    assert waste_nums == [f"WST-20990302-000{i}" for i in range(1, 5)]

    audit_nums = _run_concurrent_batch(
        DocumentType.AUDIT,
        target_dates[DocumentType.AUDIT],
        lambda num, idx: PhysicalAuditHeader(
            audit_number=num,
            audit_date=target_dates[DocumentType.AUDIT],
            department_id=fdy_dept_id,
            status=AuditStatus.DRAFT.value,
            created_by=f"pg_worker_{idx}",
        ),
    )
    assert audit_nums == [f"AUD-20990303-000{i}" for i in range(1, 5)]

    grn_nums = _run_concurrent_batch(
        DocumentType.GRN,
        target_dates[DocumentType.GRN],
        lambda num, idx: GRNHeader(
            grn_number=num,
            receipt_date=target_dates[DocumentType.GRN],
            source_type=GRNSourceType.INTERNAL_VSPL.value,
            status=GRNStatus.DRAFT.value,
            created_by=f"pg_worker_{idx}",
        ),
    )
    assert grn_nums == [f"GRN-20990304-000{i}" for i in range(1, 5)]

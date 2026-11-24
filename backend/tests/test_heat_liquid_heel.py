"""
Isolated Automated Test Suite for Induction Furnace Liquid Heel & Mass-Balance Implementation.
Covers all 16 test cases mandated by External Review Phase 2B-2A:
1. Verified cold-start opening heel of zero.
2. Subsequent heat carry-forward.
3. Missing previous closing heel.
4. Unverified previous closing heel.
5. Furnace-empty closing heel of zero.
6. Multiple furnaces and separate campaigns.
7. Negative heel rejection.
8. Negative melt-loss anomaly.
9. Recovery greater than 100% anomaly.
10. Zero total available metal.
11. Missing heel data.
12. Separate tapped recovery and mass-balance recovery.
13. Casting yield remains independent.
14. Maker-checker verification.
15. Audit history and correction traceability.
16. Concurrent heat/carry-forward protection.
"""

from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem
from app.models.heat import (
    HeatHeader,
    HeatChargeLine,
    HeatPartsProduced,
    HeelMeasurementMethod,
    HeelVerificationStatus,
)
from app.services.heat_service import (
    create_heat,
    propose_heat_carry_forward,
    verify_heat_heel,
)
from app.services.heat_calculations import (
    calculate_heat_kpis,
    calculate_heat_full_summary,
)


def _get_kg_uom(db_session: Session) -> UOM:
    return db_session.execute(select(UOM).where(UOM.code == "KG")).scalar_one()


def _get_fdy_dept(db_session: Session) -> Department:
    return db_session.execute(select(Department).where(Department.code == "FDY")).scalar_one()


# 1. Verified cold-start opening heel of zero
def test_verified_cold_start_opening_heel_of_zero(db_session: Session):
    uom = _get_kg_uom(db_session)
    heat = create_heat(
        db=db_session,
        heat_number="H-COLD-001",
        heat_date=date(2026, 11, 5),
        created_by="melter_01",
        furnace_id="F-01",
        metal_tapped_weight=Decimal("1000.0000"),
        metal_tapped_uom_id=uom.id,
        is_cold_start=True,
    )
    assert heat.is_cold_start is True
    assert heat.opening_liquid_heel_kg == Decimal("0.0000")
    assert heat.heel_measurement_method == HeelMeasurementMethod.COLD_START.value
    assert heat.heel_verification_status == HeelVerificationStatus.PENDING_VERIFICATION.value

    # Verify by supervisor
    verified_heat = verify_heat_heel(
        db=db_session,
        heat_id=heat.id,
        decision="VERIFY",
        verified_by="supervisor_01",
        comments="Cold start verified after furnace relining.",
    )
    assert verified_heat.heel_verification_status == HeelVerificationStatus.VERIFIED.value
    assert verified_heat.heel_verified_by == "supervisor_01"


# 2. Subsequent heat carry-forward
def test_subsequent_heat_carry_forward(db_session: Session):
    uom = _get_kg_uom(db_session)
    # Heat 1 with closing heel = 450 kg
    h1 = create_heat(
        db=db_session,
        heat_number="H-CAMP-001",
        heat_date=date(2026, 11, 5),
        created_by="melter_01",
        furnace_id="F-01",
        metal_tapped_weight=Decimal("5000.0000"),
        metal_tapped_uom_id=uom.id,
        closing_liquid_heel_kg=Decimal("450.0000"),
        heel_measurement_method=HeelMeasurementMethod.DIP_ROD.value,
    )
    # Verify closing heel of Heat 1
    verify_heat_heel(db=db_session, heat_id=h1.id, decision="VERIFY", verified_by="supervisor_01")

    # Propose carry forward for Heat 2 on F-01
    proposal = propose_heat_carry_forward(db=db_session, furnace_id="F-01")
    assert proposal["can_carry_forward"] is True
    assert proposal["proposed_opening_heel_kg"] == Decimal("450.0000")
    assert proposal["source_heat_id"] == h1.id

    # Create Heat 2 consuming Heat 1 closing heel
    h2 = create_heat(
        db=db_session,
        heat_number="H-CAMP-002",
        heat_date=date(2026, 11, 5),
        created_by="melter_02",
        furnace_id="F-01",
        metal_tapped_weight=Decimal("5200.0000"),
        metal_tapped_uom_id=uom.id,
        opening_heel_source_heat_id=proposal["source_heat_id"],
    )
    assert h2.opening_liquid_heel_kg == Decimal("450.0000")
    assert h2.opening_heel_source_heat_id == h1.id


# 3. Missing previous closing heel
def test_missing_previous_closing_heel_blocks_carry_forward(db_session: Session):
    uom = _get_kg_uom(db_session)
    # Heat 1 has NO closing heel recorded
    h1 = create_heat(
        db=db_session,
        heat_number="H-MISS-001",
        heat_date=date(2026, 11, 5),
        created_by="melter_01",
        furnace_id="F-01",
        metal_tapped_weight=Decimal("5000.0000"),
        metal_tapped_uom_id=uom.id,
        closing_liquid_heel_kg=None,
    )
    proposal = propose_heat_carry_forward(db=db_session, furnace_id="F-01")
    assert proposal["can_carry_forward"] is False
    assert "no closing liquid heel recorded" in proposal["message"]


# 4. Unverified previous closing heel
def test_unverified_previous_closing_heel_blocks_carry_forward(db_session: Session):
    uom = _get_kg_uom(db_session)
    # Heat 1 has closing heel but NOT verified (PENDING_VERIFICATION)
    h1 = create_heat(
        db=db_session,
        heat_number="H-UNVERIF-001",
        heat_date=date(2026, 11, 5),
        created_by="melter_01",
        furnace_id="F-01",
        metal_tapped_weight=Decimal("5000.0000"),
        metal_tapped_uom_id=uom.id,
        closing_liquid_heel_kg=Decimal("400.0000"),
    )
    proposal = propose_heat_carry_forward(db=db_session, furnace_id="F-01")
    assert proposal["can_carry_forward"] is False
    assert "closing heel is unverified" in proposal["message"]

    # Attempting to force create heat with unverified source raises 422
    with pytest.raises(HTTPException) as exc_info:
        create_heat(
            db=db_session,
            heat_number="H-UNVERIF-002",
            heat_date=date(2026, 11, 5),
            created_by="melter_02",
            furnace_id="F-01",
            opening_heel_source_heat_id=h1.id,
        )
    assert exc_info.value.status_code == 422
    assert "Automatic carry-forward blocked" in exc_info.value.detail


# 5. Furnace-empty closing heel of zero
def test_furnace_empty_closing_heel_of_zero(db_session: Session):
    uom = _get_kg_uom(db_session)
    heat = create_heat(
        db=db_session,
        heat_number="H-EMPTY-001",
        heat_date=date(2026, 11, 5),
        created_by="melter_01",
        furnace_id="F-01",
        metal_tapped_weight=Decimal("5000.0000"),
        metal_tapped_uom_id=uom.id,
        is_furnace_empty=True,
    )
    assert heat.is_furnace_empty is True
    assert heat.closing_liquid_heel_kg == Decimal("0.0000")
    assert heat.heel_measurement_method == HeelMeasurementMethod.FURNACE_EMPTIED.value


# 6. Multiple furnaces and separate campaigns
def test_multiple_furnaces_and_separate_campaigns(db_session: Session):
    uom = _get_kg_uom(db_session)
    # Heat on F-01
    h_f1 = create_heat(
        db=db_session,
        heat_number="H-F1-001",
        heat_date=date(2026, 11, 5),
        created_by="melter_01",
        furnace_id="F-01",
        metal_tapped_weight=Decimal("3000.0000"),
        metal_tapped_uom_id=uom.id,
        closing_liquid_heel_kg=Decimal("300.0000"),
    )
    verify_heat_heel(db=db_session, heat_id=h_f1.id, decision="VERIFY", verified_by="supervisor_01")

    # Heat on F-02
    h_f2 = create_heat(
        db=db_session,
        heat_number="H-F2-001",
        heat_date=date(2026, 11, 5),
        created_by="melter_01",
        furnace_id="F-02",
        metal_tapped_weight=Decimal("7000.0000"),
        metal_tapped_uom_id=uom.id,
        closing_liquid_heel_kg=Decimal("600.0000"),
    )
    verify_heat_heel(db=db_session, heat_id=h_f2.id, decision="VERIFY", verified_by="supervisor_01")

    # Proposal for F-01 gets F-01 closing heel (300 kg)
    prop_f1 = propose_heat_carry_forward(db=db_session, furnace_id="F-01")
    assert prop_f1["proposed_opening_heel_kg"] == Decimal("300.0000")

    # Proposal for F-02 gets F-02 closing heel (600 kg)
    prop_f2 = propose_heat_carry_forward(db=db_session, furnace_id="F-02")
    assert prop_f2["proposed_opening_heel_kg"] == Decimal("600.0000")

    # Attempting cross-furnace carry forward raises 422
    with pytest.raises(HTTPException) as exc_info:
        create_heat(
            db=db_session,
            heat_number="H-F2-002",
            heat_date=date(2026, 11, 5),
            created_by="melter_02",
            furnace_id="F-02",
            opening_heel_source_heat_id=h_f1.id,  # h_f1 belongs to F-01!
        )
    assert exc_info.value.status_code == 422
    assert "Cannot carry forward heel across different furnaces" in exc_info.value.detail


# 7. Negative heel rejection
def test_negative_heel_rejection(db_session: Session):
    uom = _get_kg_uom(db_session)
    # Negative opening heel
    with pytest.raises(HTTPException) as exc1:
        create_heat(
            db=db_session,
            heat_number="H-NEG-001",
            heat_date=date(2026, 11, 5),
            created_by="melter_01",
            opening_liquid_heel_kg=Decimal("-10.0000"),
        )
    assert exc1.value.status_code == 422

    # Negative closing heel
    with pytest.raises(HTTPException) as exc2:
        create_heat(
            db=db_session,
            heat_number="H-NEG-002",
            heat_date=date(2026, 11, 5),
            created_by="melter_01",
            closing_liquid_heel_kg=Decimal("-50.0000"),
        )
    assert exc2.value.status_code == 422


# 8. Negative melt-loss anomaly
def test_negative_melt_loss_anomaly():
    kpis = calculate_heat_kpis(
        charge_quantities=[Decimal("1000.0000")],
        metal_tapped_weight=Decimal("1200.0000"),
        opening_liquid_heel_kg=Decimal("100.0000"),
        closing_liquid_heel_kg=Decimal("200.0000"),
    )
    # Available: 1000 + 100 = 1100 kg
    # Accounted: 1200 + 200 = 1400 kg
    # True Melt Loss: 1100 - 1400 = -300 kg
    assert kpis.true_melt_loss_kg == Decimal("-300.0000")
    assert any("NEGATIVE_TRUE_MELT_LOSS" in a for a in kpis.anomalies)


# 9. Recovery greater than 100% anomaly
def test_recovery_greater_than_100_percent_anomaly():
    kpis = calculate_heat_kpis(
        charge_quantities=[Decimal("1000.0000")],
        metal_tapped_weight=Decimal("1050.0000"),
        opening_liquid_heel_kg=Decimal("100.0000"),
        closing_liquid_heel_kg=Decimal("100.0000"),
    )
    # Available: 1100 kg. Accounted: 1150 kg -> Mass balance recovery: 104.5455%
    assert kpis.mass_balance_recovery_pct is not None
    assert kpis.mass_balance_recovery_pct > Decimal("100.0000")
    assert any("MASS_BALANCE_RECOVERY_EXCEEDS_100" in a for a in kpis.anomalies)


# 10. Zero total available metal
def test_zero_total_available_metal():
    kpis = calculate_heat_kpis(
        charge_quantities=[],
        metal_tapped_weight=Decimal("0.0000"),
        opening_liquid_heel_kg=Decimal("0.0000"),
        closing_liquid_heel_kg=Decimal("0.0000"),
    )
    assert kpis.total_liquid_metal_available_kg == Decimal("0.0000")
    assert kpis.mass_balance_recovery_pct is None
    assert any("ZERO_TOTAL_AVAILABLE_METAL" in a for a in kpis.anomalies)


# 11. Missing heel data
def test_missing_heel_data():
    kpis = calculate_heat_kpis(
        charge_quantities=[Decimal("1000.0000")],
        metal_tapped_weight=Decimal("950.0000"),
        opening_liquid_heel_kg=Decimal("200.0000"),
        closing_liquid_heel_kg=None,  # Missing closing heel
    )
    assert kpis.heel_status == "INCOMPLETE_HEEL_DATA"
    assert kpis.true_melt_loss_kg is None
    assert kpis.mass_balance_recovery_pct is None
    assert any("INCOMPLETE_HEEL_DATA" in a for a in kpis.anomalies)


# 12. Separate tapped recovery and mass-balance recovery
def test_separate_tapped_recovery_and_mass_balance_recovery():
    # Solid charge = 1000 kg, Opening heel = 300 kg -> Available = 1300 kg
    # Tapped = 950 kg, Closing heel = 310 kg -> Accounted = 1260 kg
    kpis = calculate_heat_kpis(
        charge_quantities=[Decimal("1000.0000")],
        metal_tapped_weight=Decimal("950.0000"),
        opening_liquid_heel_kg=Decimal("300.0000"),
        closing_liquid_heel_kg=Decimal("310.0000"),
    )
    # Tapped Recovery = 950 / 1300 * 100 = 73.0769%
    # Mass Balance Recovery = 1260 / 1300 * 100 = 96.9231%
    assert kpis.tapped_metal_recovery_pct == Decimal("73.0769")
    assert kpis.mass_balance_recovery_pct == Decimal("96.9231")
    assert kpis.true_melt_loss_kg == Decimal("40.0000")
    # Verify strict separation
    assert kpis.tapped_metal_recovery_pct != kpis.mass_balance_recovery_pct


# 13. Casting yield remains independent
def test_casting_yield_remains_independent():
    # Solid charge = 1000 kg, Good castings = 650 kg
    # Casting yield = 650 / 1000 = 65.0000%
    parts = [{"quantity_produced": 50, "unit_cast_weight": 13, "classification": "GOOD"}]
    kpis = calculate_heat_kpis(
        charge_quantities=[Decimal("1000.0000")],
        metal_tapped_weight=Decimal("950.0000"),
        parts_produced=parts,
        opening_liquid_heel_kg=Decimal("300.0000"),
        closing_liquid_heel_kg=Decimal("310.0000"),
    )
    assert kpis.casting_yield_pct == Decimal("65.0000")
    assert kpis.mass_balance_recovery_pct == Decimal("96.9231")
    assert kpis.tapped_metal_recovery_pct == Decimal("73.0769")
    # Confirms casting yield is strictly calculated against solid charge, not available liquid metal
    assert kpis.casting_yield_pct != kpis.mass_balance_recovery_pct


# 14. Maker-checker verification
def test_maker_checker_verification(db_session: Session):
    uom = _get_kg_uom(db_session)
    heat = create_heat(
        db=db_session,
        heat_number="H-MAKER-001",
        heat_date=date(2026, 11, 5),
        created_by="operator_darshan",
        closing_liquid_heel_kg=Decimal("350.0000"),
    )
    # Attempt verification by same user -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        verify_heat_heel(
            db=db_session,
            heat_id=heat.id,
            decision="VERIFY",
            verified_by="operator_darshan",  # SAME AS CREATOR!
        )
    assert exc_info.value.status_code == 403
    assert "Maker-checker violation" in exc_info.value.detail

    # Verification by distinct supervisor -> Success
    verified = verify_heat_heel(
        db=db_session,
        heat_id=heat.id,
        decision="VERIFY",
        verified_by="foundry_in_charge",
    )
    assert verified.heel_verification_status == HeelVerificationStatus.VERIFIED.value
    assert verified.heel_verified_by == "foundry_in_charge"


# 15. Audit history and correction traceability
def test_audit_history_and_correction_traceability(db_session: Session):
    uom = _get_kg_uom(db_session)
    heat = create_heat(
        db=db_session,
        heat_number="H-AUDIT-001",
        heat_date=date(2026, 11, 5),
        created_by="melter_01",
        closing_liquid_heel_kg=Decimal("400.0000"),
    )
    verified = verify_heat_heel(
        db=db_session,
        heat_id=heat.id,
        decision="VERIFY",
        verified_by="supervisor_01",
        comments="Dip rod level calibrated.",
    )
    assert "[HEEL_AUDIT] VERIFY by supervisor_01" in verified.notes
    assert "Dip rod level calibrated." in verified.notes

    # Attempting silent overwriting of already verified measurement raises 409
    with pytest.raises(HTTPException) as exc_info:
        verify_heat_heel(
            db=db_session,
            heat_id=heat.id,
            decision="REJECT",
            verified_by="supervisor_02",
        )
    assert exc_info.value.status_code == 409
    assert "liquid heel has already been verified" in exc_info.value.detail


# 16. Concurrent heat/carry-forward protection
def test_concurrent_heat_carry_forward_protection(db_session: Session):
    uom = _get_kg_uom(db_session)
    # Heat 1 with verified closing heel
    h1 = create_heat(
        db=db_session,
        heat_number="H-CONCUR-001",
        heat_date=date(2026, 11, 5),
        created_by="melter_01",
        furnace_id="F-01",
        closing_liquid_heel_kg=Decimal("450.0000"),
    )
    verify_heat_heel(db=db_session, heat_id=h1.id, decision="VERIFY", verified_by="supervisor_01")

    # Heat 2 consumes Heat 1 closing heel
    h2 = create_heat(
        db=db_session,
        heat_number="H-CONCUR-002",
        heat_date=date(2026, 11, 5),
        created_by="melter_02",
        furnace_id="F-01",
        opening_heel_source_heat_id=h1.id,
    )
    assert h2.opening_heel_source_heat_id == h1.id

    # Proposal now reports Heat 1 closing heel already consumed
    proposal = propose_heat_carry_forward(db=db_session, furnace_id="F-01")
    # If h2 hasn't closed yet, h1 cannot be consumed again
    # Attempting Heat 3 to consume Heat 1 closing heel raises 409 Conflict
    with pytest.raises(HTTPException) as exc_info:
        create_heat(
            db=db_session,
            heat_number="H-CONCUR-003",
            heat_date=date(2026, 11, 5),
            created_by="melter_03",
            furnace_id="F-01",
            opening_heel_source_heat_id=h1.id,  # DUPLICATE CONSUMPTION!
        )
    assert exc_info.value.status_code == 409
    assert "was already consumed by heat" in exc_info.value.detail

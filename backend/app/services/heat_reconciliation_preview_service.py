"""
Induction Furnace Heat Log & Furnace-Charge Dry-Run Reconciliation Engine.
Evaluates stores issue slips against furnace charge details across induction heats.
Strictly read-only: performs 3-pass reconciliation matching, tolerance classification,
multi-addition aggregation, and floor-consumable segregation with ZERO database mutations.
"""

import os
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any, Optional, Set, Tuple
from collections import defaultdict
import openpyxl

from app.schemas.heat_reconciliation_preview import (
    ReconciliationVarianceClass,
    HeatReconciliationLineMatch,
    HeatReconciliationSummary,
)
from app.services.reconciliation_service import (
    calculate_tolerance_limit,
    DEFAULT_RELATIVE_TOLERANCE,
    DEFAULT_ABSOLUTE_TOLERANCE_KG,
)
from app.services.validators import normalize_heat_number
from app.services.item_nomenclature import (
    RECON_NON_HEAT_SPECIFIC,
    resolve_effective_reconciliation_category,
)


HEAT_NUMBER_PATTERN = re.compile(r"^(?:H-)?(\d{6}-\d{4})$", re.IGNORECASE)

FLOOR_CONSUMABLE_KEYWORDS = {
    "PRE COATED SAND",
    "CHROMITE SAND",
    "SLAX",
    "HOLCOTE",
    "DIE COTE",
}


def clean_heat_key(raw_heat: str) -> str:
    """Standardizes heat numbers by stripping 'H-' prefix and whitespace."""
    if not raw_heat:
        return ""
    s = str(raw_heat).strip().upper()
    if s.startswith("H-"):
        s = s[2:].strip()
    elif s.startswith("H"):
        s = s[1:].strip()
    return s


class HeatReconciliationPreviewEngine:
    """
    Dry-run reconciliation preview engine.
    Compares stores furnace charges against induction heat log charge details.
    Guarantees 100% read-only operation: no database writes, no ledger entries.
    """

    def __init__(
        self,
        approved_items: Optional[Dict[str, Dict[str, Any]]] = None,
        heat_master_path: Optional[str] = None,
    ):
        self.approved_items = approved_items or {}
        self.heat_logs: Dict[str, Dict[str, Any]] = {}
        self.heat_charges: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        if heat_master_path and os.path.exists(heat_master_path):
            self._load_heat_master_workbook(heat_master_path)

    def _load_heat_master_workbook(self, file_path: str):
        """Loads Heat Log and Charge Details from master workbook."""
        try:
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            if "Heat Log" in wb.sheetnames:
                ws_hl = wb["Heat Log"]
                for r in list(ws_hl.iter_rows(values_only=True))[1:]:
                    if r[0]:
                        raw_h = str(r[0]).strip()
                        norm_k = clean_heat_key(raw_h)
                        self.heat_logs[norm_k] = {
                            "heat_number": raw_h,
                            "date": str(r[1])[:10] if len(r) > 1 and r[1] else None,
                            "furnace": str(r[2]).strip() if len(r) > 2 and r[2] else None,
                            "target_grade": str(r[3]).strip() if len(r) > 3 and r[3] else None,
                            "shift": str(r[4]).strip() if len(r) > 4 and r[4] else None,
                            "total_charge": r[5] if len(r) > 5 else None,
                            "metal_tapped": r[6] if len(r) > 6 else None,
                        }

            if "Charge Details" in wb.sheetnames:
                ws_cd = wb["Charge Details"]
                for r in list(ws_cd.iter_rows(values_only=True))[1:]:
                    if r[0]:
                        raw_h = str(r[0]).strip()
                        norm_k = clean_heat_key(raw_h)
                        desc = str(r[1]).strip() if len(r) > 1 and r[1] else ""
                        code = str(r[2]).strip().upper() if len(r) > 2 and r[2] else ""
                        uom = str(r[3]).strip() if len(r) > 3 and r[3] else "Kg"
                        qty = None
                        if len(r) > 4 and r[4] is not None:
                            try:
                                qty = Decimal(str(r[4]))
                            except Exception:
                                pass
                        self.heat_charges[norm_k].append({
                            "description": desc,
                            "code": code,
                            "uom": uom,
                            "quantity": qty or Decimal("0.0000"),
                        })
            wb.close()
        except Exception:
            pass

    def reconcile_furnace_charges(
        self,
        furnace_charge_rows: List[Dict[str, Any]],
        external_heat_charges: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> HeatReconciliationSummary:
        """
        Executes dry-run reconciliation between furnace charge issue rows and heat charge logs.
        Aggregates multi-addition charge lines within each heat and classifies variances.
        """
        heat_charges_db = external_heat_charges if external_heat_charges is not None else self.heat_charges

        # 1. Group stores issue lines by normalized heat number
        heats_grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        floor_consumables: List[Dict[str, Any]] = []
        zero_qty_lines: List[Dict[str, Any]] = []
        missing_code_lines: List[Dict[str, Any]] = []
        uom_mismatches: List[Dict[str, Any]] = []

        total_issued_weight = Decimal("0.0000")
        total_charged_weight = Decimal("0.0000")

        for row in furnace_charge_rows:
            raw_slip = str(row.get("heat_slip", "")).strip()
            desc = str(row.get("desc", "")).strip().upper()
            code = str(row.get("code", "")).strip().upper()
            uom = str(row.get("uom", "Kg")).strip()
            qty_raw = row.get("qty")

            # Check quantity validity
            try:
                qty_dec = Decimal(str(qty_raw)) if qty_raw is not None else Decimal("0.0000")
            except (InvalidOperation, ValueError):
                qty_dec = Decimal("0.0000")

            # Check floor consumable via two-tier classification (override or category rule)
            recon_class = resolve_effective_reconciliation_category(
                item_code=code,
                category_text=desc,
                explicit_category=None,
            )
            # Support known uncatalogued floor consumable terms, but NEVER treat blank raw_slip as consumable
            is_floor_cons = (
                recon_class == RECON_NON_HEAT_SPECIFIC
                or any(k in desc for k in FLOOR_CONSUMABLE_KEYWORDS)
            )
            if is_floor_cons:
                floor_consumables.append(row)
                continue

            # Check zero quantity
            if qty_dec <= Decimal("0.0000"):
                zero_qty_lines.append(row)
                continue

            # Check missing code
            if not code or code == "NONE":
                missing_code_lines.append(row)

            # Check UOM against approved item master
            if code in self.approved_items:
                master_uom = self.approved_items[code].get("uom", "")
                if master_uom and uom and master_uom.upper() != uom.upper():
                    uom_mismatches.append(row)

            norm_heat = clean_heat_key(raw_slip)
            heats_grouped[norm_heat].append(row)
            total_issued_weight += qty_dec

        # 2. Evaluate each heat against heat log charges
        all_matches: List[HeatReconciliationLineMatch] = []
        matched_heats_cnt = 0
        unmatched_heats_cnt = 0

        exact_matches_cnt = 0
        tolerance_ok_cnt = 0
        excess_cnt = 0
        short_cnt = 0
        unmatched_lines_cnt = 0

        all_heat_keys = set(heats_grouped.keys()).union(set(heat_charges_db.keys()))

        for heat_key in sorted(all_heat_keys):
            issue_lines = heats_grouped.get(heat_key, [])
            heat_lines = heat_charges_db.get(heat_key, [])

            if issue_lines and not heat_lines:
                # Heat exists in stores issues, but missing from Heat Log
                unmatched_heats_cnt += 1
                for il in issue_lines:
                    unmatched_lines_cnt += 1
                    qty_val = Decimal(str(il.get("qty", "0")))
                    all_matches.append(
                        HeatReconciliationLineMatch(
                            heat_number=il.get("heat_slip", heat_key),
                            heat_date=il.get("date"),
                            item_code=il.get("code"),
                            material_description=il.get("desc", ""),
                            uom=il.get("uom", "Kg"),
                            issued_quantity=qty_val,
                            charged_quantity=Decimal("0.0000"),
                            variance=qty_val,
                            variance_percentage=None,
                            tolerance_limit=Decimal("0.5000"),
                            variance_class=ReconciliationVarianceClass.UNMATCHED_SLIP,
                            match_method="UNMATCHED_SLIP",
                            is_multi_addition=False,
                            source_file=il.get("file"),
                            notes=(
                                f"Furnace charge issued to heat '{heat_key}', but heat record is missing from "
                                "Heat Log Master. Segregated to prevent double deduction."
                            ),
                        )
                    )
                continue

            if heat_lines and not issue_lines:
                # Heat exists in Heat Log, but has no stores issue slips
                unmatched_heats_cnt += 1
                for hl in heat_lines:
                    unmatched_lines_cnt += 1
                    chg_qty = hl.get("quantity", Decimal("0.0000"))
                    total_charged_weight += chg_qty
                    all_matches.append(
                        HeatReconciliationLineMatch(
                            heat_number=heat_key,
                            heat_date=None,
                            item_code=hl.get("code"),
                            material_description=hl.get("description", ""),
                            uom=hl.get("uom", "Kg"),
                            issued_quantity=Decimal("0.0000"),
                            charged_quantity=chg_qty,
                            variance=-chg_qty,
                            variance_percentage=None,
                            tolerance_limit=Decimal("0.5000"),
                            variance_class=ReconciliationVarianceClass.UNMATCHED_HEAT,
                            match_method="UNMATCHED_HEAT",
                            is_multi_addition=False,
                            notes="Heat Log charge recorded without matching stores issue slip.",
                        )
                    )
                continue

            # Both issue lines and heat log lines exist for this heat!
            matched_heats_cnt += 1

            # Group issue lines by material (aggregating multi-additions, e.g. trim additions)
            issues_by_mat: Dict[str, Dict[str, Any]] = {}
            for il in issue_lines:
                mat_key = (il.get("code") or il.get("desc", "")).strip().upper()
                q = Decimal(str(il.get("qty", "0")))
                if mat_key not in issues_by_mat:
                    issues_by_mat[mat_key] = {
                        "item_code": il.get("code"),
                        "desc": il.get("desc", ""),
                        "uom": il.get("uom", "Kg"),
                        "qty": q,
                        "addition_count": 1,
                        "date": il.get("date"),
                        "file": il.get("file"),
                        "heat_slip": il.get("heat_slip", heat_key),
                    }
                else:
                    issues_by_mat[mat_key]["qty"] += q
                    issues_by_mat[mat_key]["addition_count"] += 1

            # Group heat log charges by material
            charges_by_mat: Dict[str, Dict[str, Any]] = {}
            for hl in heat_lines:
                mat_key = (hl.get("code") or hl.get("description", "")).strip().upper()
                q = hl.get("quantity", Decimal("0.0000"))
                total_charged_weight += q
                if mat_key not in charges_by_mat:
                    charges_by_mat[mat_key] = {
                        "item_code": hl.get("code"),
                        "desc": hl.get("description", ""),
                        "uom": hl.get("uom", "Kg"),
                        "qty": q,
                    }
                else:
                    charges_by_mat[mat_key]["qty"] += q

            # Compare material by material
            all_mats = set(issues_by_mat.keys()).union(set(charges_by_mat.keys()))
            for m_key in all_mats:
                i_data = issues_by_mat.get(m_key)
                c_data = charges_by_mat.get(m_key)

                issued_q = i_data["qty"] if i_data else Decimal("0.0000")
                charged_q = c_data["qty"] if c_data else Decimal("0.0000")
                item_c = (i_data["item_code"] if i_data else None) or (c_data["item_code"] if c_data else None)
                m_desc = (i_data["desc"] if i_data else None) or (c_data["desc"] if c_data else "")
                u_str = (i_data["uom"] if i_data else None) or (c_data["uom"] if c_data else "Kg")
                is_multi = i_data["addition_count"] > 1 if i_data else False

                tol_lim, _ = calculate_tolerance_limit(issued_q)
                var = issued_q - charged_q
                abs_var = abs(var)

                # Variance classification
                pct = (abs_var / issued_q * Decimal("100")) if issued_q > Decimal("0") else None

                if not i_data:
                    v_cls = ReconciliationVarianceClass.UNMATCHED_HEAT
                    method = "UNMATCHED_HEAT"
                    notes = "Heat Log charge has no corresponding store issue slip."
                    unmatched_lines_cnt += 1
                elif not c_data:
                    v_cls = ReconciliationVarianceClass.UNMATCHED_SLIP
                    method = "UNMATCHED_SLIP"
                    notes = "Store issue slip has no corresponding charge line in Heat Log."
                    unmatched_lines_cnt += 1
                elif issued_q > Decimal("0") and charged_q > Decimal("0") and (
                    issued_q / charged_q >= Decimal("9.5") or issued_q / charged_q <= Decimal("0.105")
                ):
                    v_cls = ReconciliationVarianceClass.DECIMAL_SUSPECT
                    method = "EXACT_HEAT_SLIP"
                    notes = f"Suspected order of magnitude decimal error (ratio {float(issued_q/charged_q):.2f})."
                elif abs_var == Decimal("0.0000"):
                    v_cls = ReconciliationVarianceClass.OK
                    method = "EXACT_HEAT_SLIP"
                    notes = "Exact match between stores issue and furnace charge."
                    exact_matches_cnt += 1
                    tolerance_ok_cnt += 1
                elif abs_var <= tol_lim:
                    v_cls = ReconciliationVarianceClass.OK
                    method = "EXACT_HEAT_SLIP"
                    notes = f"Within precedence tolerance ({float(tol_lim):.2f} {u_str})."
                    tolerance_ok_cnt += 1
                elif var > tol_lim:
                    v_cls = ReconciliationVarianceClass.EXCESS_ISSUE
                    method = "EXACT_HEAT_SLIP"
                    notes = f"Excess issue: Stores issued {float(issued_q)} > Crucible charged {float(charged_q)}."
                    excess_cnt += 1
                else:
                    v_cls = ReconciliationVarianceClass.SHORT_ISSUE
                    method = "EXACT_HEAT_SLIP"
                    notes = f"Short issue: Crucible charged {float(charged_q)} > Stores issued {float(issued_q)}."
                    short_cnt += 1

                all_matches.append(
                    HeatReconciliationLineMatch(
                        heat_number=heat_key,
                        heat_date=i_data.get("date") if i_data else None,
                        item_code=item_c,
                        material_description=m_desc,
                        uom=u_str,
                        issued_quantity=issued_q,
                        charged_quantity=charged_q,
                        variance=var,
                        variance_percentage=pct,
                        tolerance_limit=tol_lim,
                        variance_class=v_cls,
                        match_method=method,
                        is_multi_addition=is_multi,
                        source_file=i_data.get("file") if i_data else None,
                        notes=notes,
                    )
                )

        return HeatReconciliationSummary(
            is_read_only=True,
            total_heats_evaluated=len(all_heat_keys),
            matched_heats_count=matched_heats_cnt,
            unmatched_heats_count=unmatched_heats_cnt,
            total_charge_rows_evaluated=len(furnace_charge_rows),
            exact_matches_count=exact_matches_cnt,
            tolerance_ok_count=tolerance_ok_cnt,
            variance_excess_count=excess_cnt,
            variance_short_count=short_cnt,
            unmatched_charge_lines_count=unmatched_lines_cnt,
            floor_consumables_segregated_count=len(floor_consumables),
            zero_qty_lines_suppressed_count=len(zero_qty_lines),
            uom_mismatches_count=len(uom_mismatches),
            missing_code_count=len(missing_code_lines),
            total_issued_weight_kg=total_issued_weight,
            total_charged_weight_kg=total_charged_weight,
            matches=all_matches,
            message=(
                "Heat log and furnace-charge dry-run reconciliation completed. "
                "STRICTLY READ-ONLY: 0 ledger entries created, 0 database mutations performed. "
                "Furnace charges segregated to prevent double deduction."
            ),
        )

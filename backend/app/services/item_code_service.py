"""
Item Code Generator Service (Nomenclature Standard v1.0).

Responsibilities:
- Strict validation of NEW item proposals against v1.0 (department, category ownership, UOM, description).
- Duplicate search over normalised descriptions of all items (active and inactive, every department),
  approved material aliases, and open item requests.
- Non-reserving code preview.
- Concurrency-safe allocation at approval time: the (department, category) sequence row is locked with
  SELECT ... FOR UPDATE, and the next serial is the highest serial ever issued plus one — never a gap.
- Permanent registry of issued codes and item master audit history.
- Read-only compliance report for grandfathered legacy codes (never modifies them).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import DevUserContext
from app.models.department import Department
from app.models.item import MaterialItem
from app.models.item_code import ItemCodeRegistry, ItemCodeSequence, ItemMasterAction, ItemMasterAuditLog
from app.models.item_request import ItemRequest, RequestStatus
from app.models.material_alias import AliasApprovalStatus, MaterialAlias
from app.models.uom import UOM
from app.services import item_nomenclature as std

REGISTRY_TABLES = ("item_code_sequences", "item_code_registry", "item_master_audit_logs")
OPEN_REQUEST_STATUSES = (RequestStatus.DRAFT.value, RequestStatus.SUBMITTED.value)


@dataclass
class DuplicateMatch:
    source: str  # ITEM | ALIAS | REQUEST
    match_type: str  # EXACT (same normalised words) | COMPACT (same once spaces are removed)
    name: str
    item_id: Optional[int] = None
    item_code: Optional[str] = None
    is_active: Optional[bool] = None
    department_code: Optional[str] = None
    request_id: Optional[int] = None
    request_number: Optional[str] = None
    request_status: Optional[str] = None

    @property
    def blocking(self) -> bool:
        """Existing items and approved aliases always block; a request blocks only once submitted."""
        if self.source in ("ITEM", "ALIAS"):
            return True
        return self.request_status == RequestStatus.SUBMITTED.value

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "match_type": self.match_type,
            "name": self.name,
            "item_id": self.item_id,
            "item_code": self.item_code,
            "is_active": self.is_active,
            "department_code": self.department_code,
            "request_id": self.request_id,
            "request_number": self.request_number,
            "request_status": self.request_status,
            "blocking": self.blocking,
        }


@dataclass
class ProposalCheck:
    errors: list[std.Issue] = field(default_factory=list)
    warnings: list[std.Issue] = field(default_factory=list)
    department: Optional[Department] = None
    category: Optional[std.CategoryRule] = None
    uom: Optional[UOM] = None

    @property
    def valid(self) -> bool:
        return not self.errors


def _issues(issues: list[std.Issue]) -> list[dict]:
    return [i.as_dict() for i in issues]


def validation_exception(message: str, errors: list[std.Issue], status_code: int = 422) -> HTTPException:
    """Structured error: detail = {message, errors: [{field, code, message}]}."""
    return HTTPException(status_code=status_code, detail={"message": message, "errors": _issues(errors)})


class ItemCodeService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------------------------------
    # Schema dependency (revision 008)
    # ------------------------------------------------------------------------------------------

    def registry_installed(self) -> bool:
        inspector = inspect(self.db.get_bind())
        return all(inspector.has_table(name) for name in REGISTRY_TABLES)

    def require_registry(self) -> None:
        if not self.registry_installed():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Item code registry is not installed (Alembic revision 008_item_code_registry has not been "
                    "applied). Item codes cannot be allocated safely until it is."
                ),
            )

    # ------------------------------------------------------------------------------------------
    # Strict v1.0 validation for NEW items
    # ------------------------------------------------------------------------------------------

    def validate_proposal(
        self,
        department_id: Optional[int],
        category: Optional[str],
        description: Optional[str],
        uom_id: Optional[int],
    ) -> ProposalCheck:
        check = ProposalCheck()

        dept = self.db.get(Department, department_id) if department_id else None
        if dept is None:
            check.errors.append(std.Issue("department", "required", "Select the owning department."))
        elif not dept.is_active:
            check.errors.append(std.Issue("department", "inactive", f"Department '{dept.code}' is inactive."))
        elif dept.code not in std.DEPARTMENTS:
            allowed = ", ".join(std.DEPARTMENTS)
            check.errors.append(
                std.Issue(
                    "department",
                    "not_in_standard",
                    f"Department code '{dept.code}' ({dept.name}) is not a v{std.STANDARD_VERSION} standard department. "
                    f"New items must use one of: {allowed}.",
                )
            )
        else:
            check.department = dept

        rule = std.resolve_category(category)
        if not category or not category.strip():
            check.errors.append(std.Issue("category", "required", "Select the item category."))
        elif rule is None:
            check.errors.append(
                std.Issue(
                    "category",
                    "not_in_standard",
                    f"Category '{category}' is not a v{std.STANDARD_VERSION} category. New categories need an approved "
                    "update to the Nomenclature Standard before use.",
                )
            )
        else:
            check.category = rule
            if dept is not None and dept.code in std.DEPARTMENTS and rule.department_code != dept.code:
                check.errors.append(
                    std.Issue(
                        "category",
                        "department_mismatch",
                        f"Category {rule.code} ({rule.name}) belongs to department {rule.department_code} "
                        f"({std.DEPARTMENTS[rule.department_code]}), not {dept.code}.",
                    )
                )

        desc = std.validate_description(description, rule.code if rule else None)
        check.errors.extend(desc.errors)
        check.warnings.extend(desc.warnings)

        uom = self.db.get(UOM, uom_id) if uom_id else None
        if uom is None:
            check.errors.append(std.Issue("uom", "required", "Select the unit of measure."))
        elif not uom.is_active:
            check.errors.append(std.Issue("uom", "inactive", f"UOM '{uom.code}' is inactive."))
        elif uom.code.upper() not in std.APPROVED_UOMS:
            allowed = ", ".join(std.APPROVED_UOMS.values())
            check.errors.append(
                std.Issue("uom", "not_in_standard", f"UOM '{uom.code}' is not approved for new items. Use one of: {allowed}.")
            )
        else:
            check.uom = uom

        return check

    # ------------------------------------------------------------------------------------------
    # Duplicate search
    # ------------------------------------------------------------------------------------------

    def find_duplicates(self, description: Optional[str], exclude_request_id: Optional[int] = None) -> list[DuplicateMatch]:
        key = std.description_key(description or "")
        compact = key.replace(" ", "")
        if not compact:
            return []

        def match_type(text: str) -> Optional[str]:
            other = std.description_key(text)
            if other == key:
                return "EXACT"
            if other.replace(" ", "") == compact:
                return "COMPACT"
            return None

        matches: list[DuplicateMatch] = []
        rows = self.db.execute(
            select(MaterialItem.id, MaterialItem.item_code, MaterialItem.name, MaterialItem.is_active, Department.code)
            .join(Department, Department.id == MaterialItem.department_id)
        ).all()
        for item_id, code, name, is_active, dept_code in rows:
            kind = match_type(name)
            if kind:
                matches.append(
                    DuplicateMatch("ITEM", kind, name, item_id=item_id, item_code=code, is_active=is_active, department_code=dept_code)
                )

        alias_rows = self.db.execute(
            select(MaterialAlias.alias_text, MaterialItem.id, MaterialItem.item_code, MaterialItem.is_active)
            .join(MaterialItem, MaterialItem.id == MaterialAlias.material_item_id)
            .where(MaterialAlias.is_active.is_(True), MaterialAlias.status == AliasApprovalStatus.APPROVED.value)
        ).all()
        for alias_text, item_id, code, is_active in alias_rows:
            kind = match_type(alias_text)
            if kind:
                matches.append(DuplicateMatch("ALIAS", kind, alias_text, item_id=item_id, item_code=code, is_active=is_active))

        req_stmt = select(ItemRequest).where(ItemRequest.status.in_(OPEN_REQUEST_STATUSES))
        if exclude_request_id is not None:
            req_stmt = req_stmt.where(ItemRequest.id != exclude_request_id)
        for req in self.db.scalars(req_stmt).all():
            kind = match_type(req.requested_name)
            if kind:
                matches.append(
                    DuplicateMatch(
                        "REQUEST",
                        kind,
                        req.requested_name,
                        request_id=req.id,
                        request_number=req.request_number,
                        request_status=req.status,
                    )
                )
        return matches

    @staticmethod
    def duplicate_exception(matches: list[DuplicateMatch], action: str) -> Optional[HTTPException]:
        blocking = [m for m in matches if m.blocking]
        if not blocking:
            return None
        first = blocking[0]
        if first.source == "REQUEST":
            message = (
                f"{action} blocked: request {first.request_number} for '{first.name}' is already submitted. "
                "Never create a duplicate item."
            )
        else:
            state = "active" if first.is_active else "inactive (retired)"
            message = (
                f"{action} blocked: '{first.name}' already exists as {state} item {first.item_code}"
                f"{' (via alternate name)' if first.source == 'ALIAS' else ''}. Use the existing code; never create a duplicate."
            )
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": message, "duplicates": [m.as_dict() for m in blocking]},
        )

    # ------------------------------------------------------------------------------------------
    # Serials
    # ------------------------------------------------------------------------------------------

    def highest_issued_serial(self, department_code: str, category_code: str, include_registry: bool = True) -> int:
        """Highest serial ever issued for the pair, from existing items, the registry and the sequence."""
        prefix = std.code_prefix(department_code, category_code)
        highest = 0
        for code in self.db.scalars(select(MaterialItem.item_code).where(MaterialItem.item_code.like(f"{prefix}%"))).all():
            serial = std.serial_from_code(code, prefix)
            if serial is not None:
                highest = max(highest, serial)
        if include_registry:
            registry_max = self.db.scalar(
                select(func.max(ItemCodeRegistry.serial)).where(
                    ItemCodeRegistry.department_code == department_code,
                    ItemCodeRegistry.category_code == category_code,
                )
            )
            sequence_max = self.db.scalar(
                select(ItemCodeSequence.last_serial).where(
                    ItemCodeSequence.department_code == department_code,
                    ItemCodeSequence.category_code == category_code,
                )
            )
            highest = max(highest, registry_max or 0, sequence_max or 0)
        return highest

    def _lock_sequence(self, department_code: str, category_code: str) -> ItemCodeSequence:
        stmt = (
            select(ItemCodeSequence)
            .where(ItemCodeSequence.department_code == department_code, ItemCodeSequence.category_code == category_code)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        seq = self.db.scalar(stmt)
        if seq is not None:
            return seq
        try:
            with self.db.begin_nested():
                self.db.add(ItemCodeSequence(department_code=department_code, category_code=category_code, last_serial=0))
        except IntegrityError:
            pass  # Created concurrently by another transaction; lock the existing row below.
        seq = self.db.scalar(stmt)
        if seq is None:  # pragma: no cover - defensive
            raise HTTPException(status_code=503, detail="Could not lock the item code sequence; retry the approval.")
        return seq

    def allocate_code(self, department_code: str, category_code: str) -> tuple[str, int]:
        """
        Allocates the next code for the pair inside the caller's transaction. The sequence row stays locked
        until the caller commits or rolls back, so concurrent approvals for the same pair serialise.
        """
        self.require_registry()
        seq = self._lock_sequence(department_code, category_code)
        next_serial = self.highest_issued_serial(department_code, category_code) + 1
        if next_serial > std.MAX_SERIAL:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Serial range exhausted for {department_code}-{category_code}: {std.MAX_SERIAL:03d} has been issued. "
                    "The standard does not allow four-digit serials; raise a change to the Nomenclature Standard."
                ),
            )
        code = std.format_item_code(department_code, category_code, next_serial)
        if self.db.scalar(select(MaterialItem.id).where(MaterialItem.item_code == code)) is not None or self.db.scalar(
            select(ItemCodeRegistry.id).where(ItemCodeRegistry.item_code == code)
        ) is not None:  # pragma: no cover - guarded by highest_issued_serial
            raise HTTPException(status_code=409, detail=f"Item code {code} already exists; allocation aborted.")
        seq.last_serial = next_serial
        return code, next_serial

    # ------------------------------------------------------------------------------------------
    # Preview (non-reserving)
    # ------------------------------------------------------------------------------------------

    def preview(
        self,
        department_id: Optional[int],
        category: Optional[str],
        description: Optional[str],
        uom_id: Optional[int],
        exclude_request_id: Optional[int] = None,
    ) -> dict:
        check = self.validate_proposal(department_id, category, description, uom_id)
        duplicates = self.find_duplicates(description, exclude_request_id=exclude_request_id)
        registry = self.registry_installed()
        warnings = list(check.warnings)
        errors = list(check.errors)
        if not registry:
            warnings.append(
                std.Issue(
                    "item_code",
                    "registry_not_installed",
                    "Code registry (migration 008) is not installed: the preview uses existing items only, and approval "
                    "will be refused until the registry is installed.",
                )
            )
        for m in duplicates:
            target = m.item_code or m.request_number
            if m.blocking:
                errors.append(std.Issue("description", "duplicate", f"Duplicate of {m.source.lower()} {target}: '{m.name}'."))
            else:
                warnings.append(std.Issue("description", "possible_duplicate", f"Similar open draft request {target}: '{m.name}'."))

        proposed_code = None
        next_serial = None
        remaining = None
        if check.department is not None and check.category is not None and check.category.department_code == check.department.code:
            highest = self.highest_issued_serial(check.department.code, check.category.code, include_registry=registry)
            next_serial = highest + 1
            remaining = max(std.MAX_SERIAL - highest, 0)
            if next_serial > std.MAX_SERIAL:
                errors.append(
                    std.Issue(
                        "item_code",
                        "serial_exhausted",
                        f"Serial range for {check.department.code}-{check.category.code} is exhausted ({std.MAX_SERIAL:03d} issued).",
                    )
                )
                next_serial = None
            else:
                proposed_code = std.format_item_code(check.department.code, check.category.code, next_serial)

        return {
            "valid": not errors,
            "provisional": True,
            "proposed_code": proposed_code,
            "next_serial": next_serial,
            "serials_remaining": remaining,
            "department_code": check.department.code if check.department else None,
            "category_code": check.category.code if check.category else None,
            "category_name": check.category.name if check.category else None,
            "cost_head": check.category.cost_head if check.category else None,
            "uom_code": check.uom.code if check.uom else None,
            "errors": _issues(errors),
            "warnings": _issues(warnings),
            "duplicates": [m.as_dict() for m in duplicates],
            "registry_installed": registry,
            "standard_version": std.STANDARD_VERSION,
            "note": "Provisional: the final code is allocated only when the request is approved and may differ.",
        }

    # ------------------------------------------------------------------------------------------
    # Rules (static standard + database references)
    # ------------------------------------------------------------------------------------------

    def rules(self) -> dict:
        payload = std.rules_payload()
        depts = {d.code: d for d in self.db.scalars(select(Department)).all()}
        for entry in payload["departments"]:
            d = depts.get(entry["code"])
            entry["department_id"] = d.id if d and d.is_active else None
            entry["provisioned"] = bool(d and d.is_active)
        uoms = {u.code.upper(): u for u in self.db.scalars(select(UOM)).all()}
        for entry in payload["uoms"]:
            u = uoms.get(entry["code"])
            entry["uom_id"] = u.id if u and u.is_active else None
            entry["provisioned"] = bool(u and u.is_active)
        payload["registry_installed"] = self.registry_installed()
        payload["unprovisioned_departments"] = [e["code"] for e in payload["departments"] if not e["provisioned"]]
        payload["unprovisioned_uoms"] = [e["label"] for e in payload["uoms"] if not e["provisioned"]]
        return payload

    # ------------------------------------------------------------------------------------------
    # Registration (called by the approval workflow inside its transaction)
    # ------------------------------------------------------------------------------------------

    def register_item(self, req: ItemRequest, check: ProposalCheck, actor: DevUserContext) -> MaterialItem:
        assert check.department is not None and check.category is not None and check.uom is not None
        code, serial = self.allocate_code(check.department.code, check.category.code)
        now = datetime.now(timezone.utc)
        item = MaterialItem(
            item_code=code,
            name=req.requested_name,
            department_id=check.department.id,
            # Stored as the standard category name, matching the approved Item Master workbook convention.
            category=check.category.name,
            subcategory=req.proposed_subcategory,
            base_uom_id=check.uom.id,
            description=req.justification,
            is_active=True,
        )
        self.db.add(item)
        self.db.flush()
        self.db.add(
            ItemCodeRegistry(
                item_code=code,
                department_code=check.department.code,
                category_code=check.category.code,
                serial=serial,
                material_item_id=item.id,
                item_request_id=req.id,
                standard_version=std.STANDARD_VERSION,
                issued_by=actor.user_id,
                issued_at=now,
            )
        )
        self.db.add(
            ItemMasterAuditLog(
                material_item_id=item.id,
                item_code=code,
                action=ItemMasterAction.REGISTERED,
                new_value=f"{code} | {item.name} | {check.category.name} | {check.uom.code}",
                reason=f"Approved item request {req.request_number}.",
                item_request_id=req.id,
                actor_id=actor.user_id,
                actor_role=actor.role.value,
                timestamp=now,
            )
        )
        self.db.flush()
        return item

    # ------------------------------------------------------------------------------------------
    # Legacy compliance (read-only)
    # ------------------------------------------------------------------------------------------

    def compliance_report(self) -> dict:
        rows = self.db.execute(
            select(MaterialItem.id, MaterialItem.item_code, MaterialItem.name, MaterialItem.category, MaterialItem.is_active, Department.code, Department.name)
            .join(Department, Department.id == MaterialItem.department_id)
            .order_by(MaterialItem.item_code)
        ).all()
        findings = []
        for item_id, code, name, category, is_active, dept_code, dept_name in rows:
            reasons = std.classify_existing_item(code, dept_code, category)
            if dept_code not in std.DEPARTMENTS and not code.startswith(f"{dept_code}-"):
                reasons.append(f"Item department code '{dept_code}' is not a v{std.STANDARD_VERSION} department.")
            if reasons:
                findings.append(
                    {
                        "item_id": item_id,
                        "item_code": code,
                        "name": name,
                        "department_code": dept_code,
                        "department_name": dept_name,
                        "category": category,
                        "is_active": is_active,
                        "reasons": reasons,
                    }
                )
        return {
            "standard_version": std.STANDARD_VERSION,
            "items_checked": len(rows),
            "non_standard_count": len(findings),
            "policy": "Grandfathered: reported only. These records are not rejected, renamed, deactivated or migrated.",
            "items": findings,
        }

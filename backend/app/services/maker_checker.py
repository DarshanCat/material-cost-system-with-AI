"""
Maker-checker (separation of duties) enforcement for document approvals.

Established company rule: only Rule M2 (item requests: a requester may not approve their own request)
is written in docs/BUSINESS_RULES.md. Rule T5 defines DRAFT -> SUBMITTED ("verification") -> APPROVED
for GRN / issue / waste, and Rule L8 defines physical-audit approval, but none of them names who may
verify, and none states whether one person may create AND approve.

Provisional control (needs Plant Head / Management sign-off, see docs/security/SPRINT2_TRANSACTION_INTEGRITY.md):
approval of documents that post to the stock ledger is refused when the approver is the document's
creator. The set of document types is configurable (settings.MAKER_CHECKER_DOCUMENTS) so management can
tighten or relax it without a code change. No new role assignments are introduced here.

The check runs in the domain service against the authenticated actor established in Sprint 1; it cannot
be influenced by request-body or query-string user ids.
"""

from fastapi import HTTPException, status

from app.core.config import settings

GRN = "GRN"
ISSUE = "ISSUE"
WASTE = "WASTE"
PHYSICAL_AUDIT = "PHYSICAL_AUDIT"
ALIAS = "ALIAS"

SUPPORTED_DOCUMENT_TYPES = {GRN, ISSUE, WASTE, PHYSICAL_AUDIT, ALIAS}


def enforced_document_types() -> set[str]:
    raw = settings.MAKER_CHECKER_DOCUMENTS or ""
    return {part.strip().upper() for part in raw.split(",") if part.strip()}


def _same_person(a: str, b: str) -> bool:
    return (a or "").strip().casefold() == (b or "").strip().casefold()


def enforce_maker_checker(document_type: str, created_by: str, approver_id: str, label: str) -> None:
    """Raise HTTP 403 when `approver_id` created the document and maker-checker applies to its type."""
    if document_type not in enforced_document_types():
        return
    if _same_person(created_by, approver_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Maker-checker violation: the creator of {label} cannot approve it. A different authorized approver is required.",
        )

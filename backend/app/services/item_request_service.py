"""
Item Request and Approval Workflow Service.
Enforces state machine transitions, separation of duties (no self-approval),
strict Nomenclature Standard v1.0 validation for new items, duplicate detection,
concurrency-safe item code allocation at approval, and immutable audit logs.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.item_request import ItemRequest, ItemRequestAuditLog, RequestStatus
from app.core.security import DevUserContext
from app.services.item_code_service import ItemCodeService, ProposalCheck, validation_exception
from app.services.document_number_service import (
    DocumentType,
    generate_document_number,
    execute_with_document_number_retry,
)


class ItemRequestService:
    def __init__(self, db: Session):
        self.db = db

    def generate_request_number(self) -> str:
        """Generates next request number: REQ-YYYYMMDD-XXXX."""
        return generate_document_number(self.db, DocumentType.ITEM_REQUEST)

    def _get_for_update(self, request_id: int) -> ItemRequest:
        """Loads and row-locks a request so concurrent decisions on it serialise (no-op lock on SQLite)."""
        req = self.db.scalar(
            select(ItemRequest)
            .where(ItemRequest.id == request_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not req:
            raise HTTPException(status_code=404, detail="Item request not found.")
        return req

    def _check_proposal(
        self,
        requested_name: str,
        proposed_department_id: int,
        proposed_category: str,
        proposed_uom_id: int,
        action: str,
        exclude_request_id: Optional[int] = None,
    ) -> ProposalCheck:
        """
        Strict v1.0 validation for a NEW item plus duplicate search. Raises 422 for rule violations and
        409 for duplicates of existing items, approved aliases or submitted requests.
        """
        codes = ItemCodeService(self.db)
        check = codes.validate_proposal(proposed_department_id, proposed_category, requested_name, proposed_uom_id)
        if not check.valid:
            raise validation_exception(
                f"{action} rejected: the item does not meet the Item Nomenclature Standard.", check.errors
            )
        duplicate = codes.duplicate_exception(codes.find_duplicates(requested_name, exclude_request_id), action)
        if duplicate:
            raise duplicate
        return check

    def create_draft(
        self,
        requested_name: str,
        proposed_department_id: int,
        proposed_category: str,
        proposed_subcategory: Optional[str],
        proposed_uom_id: int,
        justification: str,
        actor: DevUserContext,
    ) -> ItemRequest:
        """Creates a new request in DRAFT status after strict v1.0 validation and duplicate search."""
        check = self._check_proposal(
            requested_name, proposed_department_id, proposed_category, proposed_uom_id, "Item request"
        )

        def _create(req_number: str) -> ItemRequest:
            req = ItemRequest(
                request_number=req_number,
                requested_name=requested_name,
                proposed_department_id=proposed_department_id,
                proposed_category=check.category.code,
                proposed_subcategory=proposed_subcategory.strip().upper() if proposed_subcategory else None,
                proposed_uom_id=proposed_uom_id,
                justification=justification.strip(),
                requester_id=actor.user_id,
                requester_role=actor.role.value,
                requester_department=actor.department,
                status=RequestStatus.DRAFT.value,
            )
            self.db.add(req)
            self.db.flush()

            # Audit Log
            audit = ItemRequestAuditLog(
                request_id=req.id,
                action="CREATED",
                from_status=None,
                to_status=RequestStatus.DRAFT.value,
                actor_id=actor.user_id,
                actor_role=actor.role.value,
                comments="Draft item request initiated.",
                timestamp=datetime.now(timezone.utc),
            )
            self.db.add(audit)
            return req

        req = execute_with_document_number_retry(
            db=self.db,
            doc_type=DocumentType.ITEM_REQUEST,
            create_fn=_create,
        )
        self.db.commit()
        self.db.refresh(req)
        return req

    def update_draft(
        self,
        request_id: int,
        requested_name: str,
        proposed_department_id: int,
        proposed_category: str,
        proposed_subcategory: Optional[str],
        proposed_uom_id: int,
        justification: str,
        actor: DevUserContext,
    ) -> ItemRequest:
        """Updates draft request details (strict v1.0 validation and duplicate search)."""
        req = self._get_for_update(request_id)

        if req.status != RequestStatus.DRAFT.value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot edit request in '{req.status}' state. Only DRAFT requests can be modified directly."
            )

        check = self._check_proposal(
            requested_name, proposed_department_id, proposed_category, proposed_uom_id,
            "Draft update", exclude_request_id=req.id,
        )

        req.requested_name = requested_name
        req.proposed_department_id = proposed_department_id
        req.proposed_category = check.category.code
        req.proposed_subcategory = proposed_subcategory.strip().upper() if proposed_subcategory else None
        req.proposed_uom_id = proposed_uom_id
        req.justification = justification.strip()

        audit = ItemRequestAuditLog(
            request_id=req.id,
            action="UPDATED",
            from_status=RequestStatus.DRAFT.value,
            to_status=RequestStatus.DRAFT.value,
            actor_id=actor.user_id,
            actor_role=actor.role.value,
            comments="Draft details updated.",
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(req)
        return req

    def submit_request(self, request_id: int, actor: DevUserContext) -> ItemRequest:
        """Transitions request from DRAFT to SUBMITTED after re-validating against v1.0."""
        req = self._get_for_update(request_id)

        if req.status != RequestStatus.DRAFT.value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot submit request in '{req.status}' status. Only DRAFT requests can be submitted."
            )

        # Drafts created before v1.0 enforcement must be corrected (update the draft) before submission.
        self._check_proposal(
            req.requested_name, req.proposed_department_id, req.proposed_category, req.proposed_uom_id,
            "Submission", exclude_request_id=req.id,
        )

        req.status = RequestStatus.SUBMITTED.value
        req.submitted_at = datetime.now(timezone.utc)

        audit = ItemRequestAuditLog(
            request_id=req.id,
            action="SUBMITTED",
            from_status=RequestStatus.DRAFT.value,
            to_status=RequestStatus.SUBMITTED.value,
            actor_id=actor.user_id,
            actor_role=actor.role.value,
            comments="Submitted for management review and approval.",
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(req)
        return req

    def cancel_request(self, request_id: int, actor: DevUserContext, comments: Optional[str] = None) -> ItemRequest:
        """Cancels a DRAFT or SUBMITTED request."""
        req = self._get_for_update(request_id)

        if req.status in (RequestStatus.APPROVED.value, RequestStatus.REJECTED.value, RequestStatus.CANCELLED.value):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel request in terminal '{req.status}' status."
            )

        prev_status = req.status
        req.status = RequestStatus.CANCELLED.value

        audit = ItemRequestAuditLog(
            request_id=req.id,
            action="CANCELLED",
            from_status=prev_status,
            to_status=RequestStatus.CANCELLED.value,
            actor_id=actor.user_id,
            actor_role=actor.role.value,
            comments=comments or "Request cancelled by user.",
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(req)
        return req

    def approve_request(self, request_id: int, actor: DevUserContext, comments: Optional[str] = None) -> ItemRequest:
        """
        Approves a SUBMITTED request, creates exactly one MaterialItem in an atomic transaction,
        and links it to the request. Prevents self-approval and duplicate approvals.

        The request row is locked for the decision, the request is re-validated strictly against v1.0, and the
        item code is allocated here (never earlier) from the locked (department, category) sequence.
        """
        req = self._get_for_update(request_id)

        if req.status != RequestStatus.SUBMITTED.value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot approve request in '{req.status}' state. Only SUBMITTED requests can be approved."
            )

        # Non-negotiable security rule: No self-approval
        if req.requester_id == actor.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Self-approval violation: Requester cannot approve their own item request."
            )

        # Strict v1.0 re-validation (requests submitted before enforcement fail here and must be rejected)
        # and duplicate search across items (active and retired), approved aliases and other submitted requests.
        check = self._check_proposal(
            req.requested_name, req.proposed_department_id, req.proposed_category, req.proposed_uom_id,
            "Approval", exclude_request_id=req.id,
        )

        # Atomic transaction: allocate code, create MaterialItem, registry entry and item history, update request
        try:
            item = ItemCodeService(self.db).register_item(req, check, actor)
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Item code allocation collided with a concurrent change. Nothing was created; retry the approval.",
            )
        item_code = item.item_code

        now = datetime.now(timezone.utc)
        req.status = RequestStatus.APPROVED.value
        req.reviewer_id = actor.user_id
        req.decision_at = now
        req.decision_comments = comments or "Approved for procurement and inventory catalog."
        req.linked_item_id = item.id

        audit = ItemRequestAuditLog(
            request_id=req.id,
            action="APPROVED",
            from_status=RequestStatus.SUBMITTED.value,
            to_status=RequestStatus.APPROVED.value,
            actor_id=actor.user_id,
            actor_role=actor.role.value,
            comments=f"Approved. Material item created with code '{item_code}'. {comments or ''}".strip(),
            timestamp=now,
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(req)
        return req

    def reject_request(self, request_id: int, actor: DevUserContext, comments: str) -> ItemRequest:
        """
        Rejects a SUBMITTED request with mandatory explanation.
        Prevents self-decision and does NOT create a material item.
        """
        if not comments or not comments.strip():
            raise HTTPException(
                status_code=400,
                detail="Rejection requires an explicit explanation/reason in decision comments."
            )

        req = self._get_for_update(request_id)

        if req.status != RequestStatus.SUBMITTED.value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reject request in '{req.status}' state. Only SUBMITTED requests can be rejected."
            )

        # Non-negotiable security rule: No self-rejection
        if req.requester_id == actor.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Self-decision violation: Requester cannot reject their own item request."
            )

        now = datetime.now(timezone.utc)
        req.status = RequestStatus.REJECTED.value
        req.reviewer_id = actor.user_id
        req.decision_at = now
        req.decision_comments = comments.strip()

        audit = ItemRequestAuditLog(
            request_id=req.id,
            action="REJECTED",
            from_status=RequestStatus.SUBMITTED.value,
            to_status=RequestStatus.REJECTED.value,
            actor_id=actor.user_id,
            actor_role=actor.role.value,
            comments=f"Rejected: {comments.strip()}",
            timestamp=now,
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(req)
        return req

"""
Item Request and Approval Workflow Service.
Enforces state machine transitions, separation of duties (no self-approval),
conflict detection, atomic material item generation, and immutable audit logs.
"""

from datetime import datetime, timezone
import re
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem
from app.models.item_request import ItemRequest, ItemRequestAuditLog, RequestStatus
from app.core.security import DevUserContext
from app.services.validators import get_category_code


class ItemRequestService:
    def __init__(self, db: Session):
        self.db = db

    def generate_request_number(self) -> str:
        """Generates next request number: REQ-YYYYMMDD-XXXX."""
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        count = self.db.scalar(
            select(func.count(ItemRequest.id)).where(ItemRequest.request_number.like(f"REQ-{today_str}-%"))
        ) or 0
        return f"REQ-{today_str}-{count + 1:04d}"

    def generate_next_item_code(self, department_id: int, category: str) -> str:
        """
        Generates unique item code following the convention: DEPT-CATEGORY-SERIAL (e.g. FDY-RM-016).
        """
        dept = self.db.get(Department, department_id)
        if not dept:
            raise HTTPException(status_code=400, detail="Invalid department ID")

        dept_code = dept.code.upper()
        cat_code = get_category_code(category)
        prefix = f"{dept_code}-{cat_code}-"

        # Query all existing item codes with this prefix
        existing_codes = self.db.scalars(
            select(MaterialItem.item_code).where(MaterialItem.item_code.like(f"{prefix}%"))
        ).all()

        max_serial = 0
        for code in existing_codes:
            suffix = code[len(prefix):]
            if suffix.isdigit():
                max_serial = max(max_serial, int(suffix))

        next_serial = max_serial + 1
        return f"{prefix}{next_serial:03d}"

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
        """Creates a new request in DRAFT status."""
        # Validate department
        dept = self.db.get(Department, proposed_department_id)
        if not dept or not dept.is_active:
            raise HTTPException(status_code=400, detail="Invalid or inactive department specified.")

        # Validate UOM
        uom = self.db.get(UOM, proposed_uom_id)
        if not uom or not uom.is_active:
            raise HTTPException(status_code=400, detail="Invalid or inactive UOM specified.")

        request_number = self.generate_request_number()
        req = ItemRequest(
            request_number=request_number,
            requested_name=requested_name.strip(),
            proposed_department_id=proposed_department_id,
            proposed_category=proposed_category.strip().upper(),
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
        """Updates draft request details."""
        req = self.db.get(ItemRequest, request_id)
        if not req:
            raise HTTPException(status_code=404, detail="Item request not found.")

        if req.status != RequestStatus.DRAFT.value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot edit request in '{req.status}' state. Only DRAFT requests can be modified directly."
            )

        # Validate department & UOM
        dept = self.db.get(Department, proposed_department_id)
        if not dept or not dept.is_active:
            raise HTTPException(status_code=400, detail="Invalid or inactive department specified.")
        uom = self.db.get(UOM, proposed_uom_id)
        if not uom or not uom.is_active:
            raise HTTPException(status_code=400, detail="Invalid or inactive UOM specified.")

        req.requested_name = requested_name.strip()
        req.proposed_department_id = proposed_department_id
        req.proposed_category = proposed_category.strip().upper()
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
        """Transitions request from DRAFT to SUBMITTED."""
        req = self.db.get(ItemRequest, request_id)
        if not req:
            raise HTTPException(status_code=404, detail="Item request not found.")

        if req.status != RequestStatus.DRAFT.value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot submit request in '{req.status}' status. Only DRAFT requests can be submitted."
            )

        # Pre-check for duplicate active item with same name in department
        conflict = self.db.scalar(
            select(MaterialItem).where(
                MaterialItem.department_id == req.proposed_department_id,
                func.lower(MaterialItem.name) == func.lower(req.requested_name),
                MaterialItem.is_active == True,
            )
        )
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"Conflict detected: Item '{conflict.name}' already exists in this department with code '{conflict.item_code}'."
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
        req = self.db.get(ItemRequest, request_id)
        if not req:
            raise HTTPException(status_code=404, detail="Item request not found.")

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
        """
        req = self.db.get(ItemRequest, request_id)
        if not req:
            raise HTTPException(status_code=404, detail="Item request not found.")

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

        # Conflict check: ensure no active item with same name in same department
        conflict = self.db.scalar(
            select(MaterialItem).where(
                MaterialItem.department_id == req.proposed_department_id,
                func.lower(MaterialItem.name) == func.lower(req.requested_name),
                MaterialItem.is_active == True,
            )
        )
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"Approval blocked: Item '{conflict.name}' already exists in this department with code '{conflict.item_code}'."
            )

        # Generate unique item code
        item_code = self.generate_next_item_code(req.proposed_department_id, req.proposed_category)

        # Atomic transaction: Create MaterialItem & Update Request
        item = MaterialItem(
            item_code=item_code,
            name=req.requested_name,
            department_id=req.proposed_department_id,
            category=req.proposed_category,
            subcategory=req.proposed_subcategory,
            base_uom_id=req.proposed_uom_id,
            description=req.justification,
            is_active=True,
        )
        self.db.add(item)
        self.db.flush()  # Populates item.id

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

        req = self.db.get(ItemRequest, request_id)
        if not req:
            raise HTTPException(status_code=404, detail="Item request not found.")

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

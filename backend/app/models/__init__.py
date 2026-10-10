"""
VSPL Database Models Registry.
"""

from app.db.base import Base
from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem
from app.models.vendor import Vendor
from app.models.item_request import ItemRequest, ItemRequestAuditLog, RequestStatus
from app.models.grn import GRNHeader, GRNLineItem, GRNAuditLog, GRNSourceType, GRNStatus
from app.models.issue import MaterialIssueHeader, MaterialIssueLineItem, IssueAuditLog, IssueStatus
from app.models.waste import (
    WasteDispositionHeader,
    WasteDispositionLineItem,
    WasteAuditLog,
    WasteType,
    DispositionType,
    WasteStatus,
)
from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
from app.models.physical_audit import (
    PhysicalAuditHeader,
    PhysicalAuditLine,
    PhysicalAuditAuditLog,
    AuditStatus,
)

__all__ = [
    "Base",
    "Department",
    "UOM",
    "MaterialItem",
    "Vendor",
    "ItemRequest",
    "ItemRequestAuditLog",
    "RequestStatus",
    "GRNHeader",
    "GRNLineItem",
    "GRNAuditLog",
    "GRNSourceType",
    "GRNStatus",
    "MaterialIssueHeader",
    "MaterialIssueLineItem",
    "IssueAuditLog",
    "IssueStatus",
    "WasteDispositionHeader",
    "WasteDispositionLineItem",
    "WasteAuditLog",
    "WasteType",
    "DispositionType",
    "WasteStatus",
    "StockLedgerEntry",
    "MovementType",
    "SourceDocumentType",
    "PhysicalAuditHeader",
    "PhysicalAuditLine",
    "PhysicalAuditAuditLog",
    "AuditStatus",
]

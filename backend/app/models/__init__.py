"""
VSPL Database Models Registry.
"""

from app.db.base import Base
from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem
from app.models.vendor import Vendor
from app.models.item_request import ItemRequest, ItemRequestAuditLog, RequestStatus
from app.models.item_code import ItemCodeSequence, ItemCodeRegistry, ItemMasterAuditLog
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
from app.models.heat import (
    HeatHeader,
    HeatChargeLine,
    HeatPartsProduced,
    ProductionStatus,
    HeatChargeValidationStatus,
    CastingClassification,
)
from app.models.material_alias import (
    MaterialAlias,
    MaterialAliasAuditLog,
    AliasApprovalStatus,
)
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

from app.models.costing import (
    CostingRun,
    ItemCostSnapshot,
    ItemCostJournalEntry,
    HeatCostRecord,
    HeatCostLine,
    PartCostRecord,
    ItemOpeningValuation,
    ItemOpeningValuationAuditLog,
    OpeningValuationStatus,
    DenominatorPolicy,
    CostScope,
    ValuationStatus,
    HeatCostStatus,
    PartCostStatus,
    CostingRunStatus,
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
    "ItemCodeSequence",
    "ItemCodeRegistry",
    "ItemMasterAuditLog",
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
    "HeatHeader",
    "HeatChargeLine",
    "HeatPartsProduced",
    "ProductionStatus",
    "HeatChargeValidationStatus",
    "CastingClassification",
    "MaterialAlias",
    "MaterialAliasAuditLog",
    "AliasApprovalStatus",
    "ReconciliationRun",
    "ReconciliationResult",
    "ReconciliationCandidateMatch",
    "ReconciliationException",
    "ReconciliationExceptionAuditLog",
    "VarianceClass",
    "MatchMethod",
    "CandidateMatchStatus",
    "ExceptionStatus",
    "CostingRun",
    "ItemCostSnapshot",
    "ItemCostJournalEntry",
    "HeatCostRecord",
    "HeatCostLine",
    "PartCostRecord",
    "ItemOpeningValuation",
    "ItemOpeningValuationAuditLog",
    "OpeningValuationStatus",
    "DenominatorPolicy",
    "CostScope",
    "ValuationStatus",
    "HeatCostStatus",
    "PartCostStatus",
    "CostingRunStatus",
]

# Append-only protection for the stock ledger (ORM guard + SQLite triggers); see app/db/ledger_guard.py
from app.db.ledger_guard import install_ledger_guard  # noqa: E402

install_ledger_guard()

# Append-only protection for issued item codes and item master history; see app/db/item_code_guard.py
from app.db.item_code_guard import install_item_code_guard  # noqa: E402

install_item_code_guard()

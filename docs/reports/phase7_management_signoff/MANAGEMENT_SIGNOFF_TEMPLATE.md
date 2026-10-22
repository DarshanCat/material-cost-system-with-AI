# VSPL Material Management & Costing System — Phase 7 Management Sign-off Template

**Document ID:** `DOC-P7-MGMT-SIGNOFF-TEMPLATE`  
**System:** VSPL Material Management & Costing System  
**Company:** Vijay Spheroidals Pvt. Ltd. (SG Iron Foundry & Machine Shop, Peenya, Bangalore)  
**Governance Scope:** Practical Decision Sign-off Forms for Corporate & Operational Leaders  
**Date:** 2026-10-13  
**Status:** **OFFICIAL SIGN-OFF FORM — AWAITING AUTHORIZED SIGNATURES**  

---

## Instructions for Use

1. This template must be printed or signed electronically by the designated corporate authority for each decision item.
2. In accordance with governance constraints, all approval fields below are **initially blank**.
3. Once completed and signed, this form must be filed in the corporate project archive and logged into `MANAGEMENT_DECISION_REGISTER.csv`.
4. **Safety Rule:** Business sign-off on this form authorizes policy selection only. Live technical database execution requires separate Layer 2 operational authorization.

---

```
====================================================================================================
                        VSPL FORMAL MANAGEMENT DECISION SIGN-OFF FORM
====================================================================================================

DEC-001: MISSING HISTORICAL COMMERCIAL PURCHASE RATES (GRN ROWS 2–5)
----------------------------------------------------------------------------------------------------
Selected Resolution Option:
[  ] OPTION 1: Audit Vendor Invoices & Enter ex-GST Rates into Staging
[  ] OPTION 2: Quarantine Records as Unvalued Physical Audit Archive (No Live Valuation)
[  ] OPTION 3: Certified Benchmark Valuation Appraisal (Finance Head Justification Required)

Supporting Commercial Evidence References:
Invoice / PO Numbers Verified: ____________________________________________________________________
Exceptions & Specific Conditions: _________________________________________________________________

Authorized Approver:
Name: _____________________________________   Title: [  ] Finance Head   [  ] Purchase Head
Signature: ________________________________   Date:  ____________________
Implementation Authorization Status: [  ] APPROVED FOR STAGING   [  ] HELD PENDING EVIDENCE


DEC-002: HISTORICAL CUTOFF POLICY & OPENING STOCK BASELINE (12-OCT-2026)
----------------------------------------------------------------------------------------------------
Selected Cutoff Policy Scenario:
[  ] SCENARIO A: Historical Audit Archive (Live Ledger starts 12-Oct-2026 on Physical Stocktake)
[  ] SCENARIO B: Reconstructed Opening Position (Roll-forward intervening movements)
[  ] SCENARIO C: Two-Phase Transition (Simulate July in Sandbox, post 12-Oct variance adjustment)

Authorized Physical Stocktake Effective Date: ____________________
Authorized Opening Valuation Principles: ___________________________________________________________

Executive Approvals:
Managing Director Signature: ______________________________   Date: ____________________
Plant Head Signature:        ______________________________   Date: ____________________
Finance Head Signature:      ______________________________   Date: ____________________
Implementation Authorization Status: [  ] APPROVED FOR STAGING   [  ] HELD PENDING EVIDENCE


DEC-003: UNMAPPED GRN ITEMS & SCRAP METALLURGICAL CLASSIFICATION
----------------------------------------------------------------------------------------------------
Master Data Item Creation Approvals:
[  ] Approve creation of MNT-CN-001 (3306PMKT-Generator, Maintenance, Set)
[  ] Approve creation of MCS-CN-002 (Tool Post, Machine Shop, Nos)

crca scrap (15,200 kg) Metallurgical Classification:
[  ] Classify as FDY-RM-007 (CRC Scrap-Low High MN)
[  ] Classify as FDY-RM-008 (CRC Scrap-Low MN)
Supporting Chemical Spec / Mill Test Cert Reference: ______________________________________________

Authorized Approvers:
Plant Head Signature (Item Master): _______________________   Date: ____________________
Metallurgist Signature (Scrap Grade): _____________________   Date: ____________________
Implementation Authorization Status: [  ] APPROVED FOR STAGING   [  ] HELD PENDING EVIDENCE


DEC-004: ISSUE DATE TYPO NORMALIZATION (7-16-20236 ACROSS ROWS 537–548)
----------------------------------------------------------------------------------------------------
Selected Resolution Option:
[  ] OPTION 1: Normalize date string '7-16-20236' to '2026-07-16' in Staging (Retain original in audit log)
[  ] OPTION 2: Quarantine rows 537–548 from operational staging

Stores Issue Slip Books Verified: Slips 325, 326, 327, 910, 1148, 1149, 2725
Stores Manager Confirmation:
"I have inspected the physical stores issue voucher books for 16-Jul-2026 and confirm that
 the literal date string '7-16-20236' represents issue transactions executed on 16-Jul-2026."

Stores Manager Signature: _________________________________   Date: ____________________
Implementation Authorization Status: [  ] APPROVED FOR STAGING   [  ] HELD PENDING EVIDENCE


DEC-005: RESOLUTION OF SEVEN NEGATIVE STOCK BALANCES & OMITTED ISSUES
----------------------------------------------------------------------------------------------------
Authorized Action:
[  ] Mandate Plant-Wide Physical Stocktake as of Cutoff Date to establish Opening Stock Balances
     (Enforce Rule H1: segregate furnace charges from store issues; do not post artificial journals)

Physical Stocktake Completion Reference: ___________________________________________________________
Opening Stock Valuation Certificate Reference: ____________________________________________________

Authorized Approvers:
Plant Head Signature:        ______________________________   Date: ____________________
Inventory Auditor Signature: ______________________________   Date: ____________________
Finance Head Signature:      ______________________________   Date: ____________________
Implementation Authorization Status: [  ] APPROVED FOR STAGING   [  ] HELD PENDING EVIDENCE


DEC-006: SAMPLE TEMPLATE DUMMY ROWS IN MATERIAL ENTRY (ROW 2 PURGE)
----------------------------------------------------------------------------------------------------
Selected Resolution Option:
[  ] OPTION 1: Purge Row 2 across GRN, Issue, and Waste sheets from Operational Staging Manifest
[  ] OPTION 2: Retain Row 2 records (Stores Manager must provide verified physical delivery vouchers)

Authorized Approvers:
Stores Manager Signature:    ______________________________   Date: ____________________
Systems Architect Signature: ______________________________   Date: ____________________
Implementation Authorization Status: [  ] APPROVED FOR STAGING   [  ] HELD PENDING EVIDENCE


DEC-007: FURNACE HEAT PRODUCTION LOG STAGING QUARANTINE
----------------------------------------------------------------------------------------------------
Selected Resolution Option:
[  ] OPTION 1: Controlled Quarantine of 19 heats and 10 charges in Staging Preview (Do not post to live tables)
[  ] OPTION 2: Audit and supply complete physical furnace charge sheets for 22-Jul-2026 before staging

Authorized Approver:
Foundry Head Signature:      ______________________________   Date: ____________________
Metallurgist Signature:      ______________________________   Date: ____________________
Implementation Authorization Status: [  ] APPROVED FOR STAGING   [  ] HELD PENDING EVIDENCE


DEC-008: RETIREMENT OF LEGACY STORE INVENTORY SPREADSHEETS
----------------------------------------------------------------------------------------------------
Selected Resolution Option:
[  ] OPTION 1: Permanently exclude 'Store Inventory.xlsx' from operational data migration
                (Preserve file strictly as immutable read-only historical audit archive)
[  ] OPTION 2: Authorize selective manual extraction of physical stock lines (Magnesium, Manganese)

Authorized Approver:
IT Head Signature:           ______________________________   Date: ____________________
Plant Head Signature:        ______________________________   Date: ____________________
Implementation Authorization Status: [  ] APPROVED FOR STAGING   [  ] HELD PENDING EVIDENCE

====================================================================================================
```

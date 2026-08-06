# POC Scope — AI-Assisted Key Control Testing (KCT)

Source: [`POC - OG 06072026.pptx`](./POC%20Scope%20-%20Case%201%20and%20Case%202.pptx) ("POC - Case 1 / Case 2", dated 06/07/2026).

This POC assesses whether AI can assist Internal Audit / Compliance in identifying
control breaches and exceptions during two existing manual Key Control Testing (KCT)
procedures. Both cases follow the same as-is process (KCT Review → Sampling → Testing →
Conclusion) and the same target: **demonstrate the feasibility of using AI to strengthen
review controls and support KCT testing activities**, not to replace the Maker-Checker
control itself.

---

## Case 1 — Credit Facilities (Letter of Offer vs. Credit Paper)

### Purpose
The Letter of Offer (LO) is a critical customer-facing document that formalizes approved
credit facilities and terms. Recent testing identified several discrepancies between the
approved Credit Paper and the issued LO, together with weaknesses in the Maker-Checker
review process. The POC assesses whether AI can assist in identifying control breaches
and exceptions during LO preparation and review.

### Scope of review — fields to compare (LO vs. approved Credit Paper)
- Facility Amount
- Facility Purpose
- Pricing / Profit Rate
- Facility Tenure
- Special Conditions (all special conditions in the Credit Paper must be reflected in the LO)
- Customer Information: Customer name, Customer IC, Customer Address, Contact Details
- Letterhead Accuracy (Conventional vs. Islamic)
- LO Issuance Date

### As-is process
1. **KCT Review** — open the KCT working paper (Excel), understand objective/control
   requirements/testing steps, identify testing frequency (Annual / Semi-Annual /
   Quarterly), select sample size (Annual: 2–3, Semi-Annual: 5, Quarterly: 10).
2. **Sampling** — prepare sample request list + supporting docs, email the Business Unit
   (BU), follow up on outstanding requests.
3. **Testing** — perform testing per the KCT procedure, record results/evidence in the
   KCT working paper (Excel), investigate and discuss exceptions.
4. **Conclusion** — re-validate exceptions, conclude Pass/Fail, update working paper,
   submit for review and approval.

### Common exceptions & exception mapping
| No. | Exception Identified |
|---|---|
| 1 | Facility amount in LO differs from approved amount |
| 2 | Facility purpose differs from approved purpose |
| 3 | Pricing/Profit rate differs from approved rate |
| 4 | Tenure differs from approved tenure |
| 5 | Approved special conditions omitted from LO |
| 6 | LO issued before Maker-Checker approval completed |
| 7 | No evidence of Maker-Checker review and approval |
| 8 | Incorrect customer details in LO |
| 9 | Wrong letterhead used (Conventional/Islamic) |

### Root causes (hypothesis)
- Manual data entry errors during LO preparation
- Insufficient review prior to issuance
- Inconsistent adherence to established procedures
- Incomplete Maker-Checker verification

### Target outcome
Demonstrate the feasibility of using AI to strengthen LO review controls and support KCT
testing activities.

### KCTs in scope
| KCT | Control |
|---|---|
| KCT-00001 | Data Accuracy — Incorrect Facility Amount |
| KCT-00002 | Data Accuracy — Incorrect Facility Purpose |
| KCT-00003 | Data Accuracy — Incorrect Pricing/Profit Rate |
| KCT-00004 | Data Accuracy — Incorrect Facility Tenure |
| KCT-00005 | Completeness — Missing Special Conditions |
| KCT-00006 | Approval Control — LO Issued Prior to Approval |
| KCT-00007 | Maker-Checker Control — No Evidence of Dual Control Approval |

### Proposed AI use case (capabilities to build)
- LO vs. Credit Paper comparison
- Facility amount verification
- Purpose matching
- Pricing validation
- Tenure validation
- Special conditions validation
- Customer details check
- Approval evidence identification
- Exception summary generation

### Sample data provided
`samples/case-1-credit-facilities/hadyan-sdn-bhd/` — Credit Paper (Annual Review 2025)
and a Letter of Offer (Revise Purpose supplemental letter) for **Hadyan Sdn Bhd**, a Bank
Guarantee facility of RM2.5 million. See that folder's `notes.md` for extracted fields
and an initial LO-vs-Credit-Paper comparison against the KCTs above.

---

## Case 2 — Account Opening (Customer Information File / CIF)

### Purpose
CIF creation is a critical onboarding process that establishes a corporate customer's
profile in the Bank's systems, supporting subsequent account opening, credit assessment
and regulatory reporting. Recent reviews found inaccuracies, omissions and
inconsistencies between customer information entered in the Customer Lifecycle System
(CLS) and Central Credit Reference Information System (CCRIS) versus the supporting
documents provided by the Relationship Manager (RM). The POC assesses whether AI can
help verify the accuracy, completeness and consistency of customer information captured
in CLS/CCRIS, and identify control gaps or exceptions during CIF creation.

### Scope of review — fields to compare (CLS/CCRIS vs. supporting documents)
- **Corporate Customer Information**: Customer Name, Registration Number, Business
  Registration Type, Date of Incorporation, Registered Address, Business Nature /
  Industry Code, Contact Details
- **Authorized Signatory Information**: Name, Identification Number, Designation
- **Guarantor Information** (if applicable): Name, Identification Number, Address,
  Contact Details
- **CCRIS Information**: Customer Details, Guarantor Details, Consent and Declaration
  Information

### As-is process
1. **KCT Review** — open the KCT working paper, understand control objective/requirements
   /testing procedures, identify testing frequency, determine sample size per approved
   KCT methodology.
2. **Sampling** — prepare sample request list for selected CIF creation cases; obtain
   supporting documents from the BU/RM: Application Form, CCRIS Form, Guarantor Form (if
   applicable), SSM Documents, Email Request; follow up on outstanding documents.
3. **Testing** — compare CLS data and CCRIS data (customer + guarantor) against
   supporting documents, verify completeness/accuracy of mandatory fields, record
   results/evidence in the KCT working paper, investigate discrepancies.
4. **Conclusion** — re-validate exceptions, conclude Pass (complete/accurate/supported)
   or Fail (material discrepancies/missing/unsupported data), update working paper,
   submit for review and approval.

### Common exceptions & exception mapping
| No. | Exception Identified |
|---|---|
| 1 | Customer name in CLS differs from Application Form / SSM |
| 2 | Company registration number incorrectly keyed in CLS |
| 3 | Registered address differs from SSM records |
| 4 | Business nature / industry information incorrectly captured |
| 5 | Director information differs from Application Form or SSM |
| 6 | Guarantor information differs from Guarantor Form |
| 7 | CCRIS information does not match CCRIS Form |
| 8 | Mandatory CIF supporting documents are missing |
| 9 | CIF approved without sufficient Maker-Checker verification evidence |

### Root causes (hypothesis)
- Manual data entry errors during CIF creation in CLS and CCRIS
- Insufficient review and validation by Checker prior to CIF approval
- Incomplete verification of customer, director, shareholder and guarantor information
  against source documents
- Inconsistent adherence to CIF creation procedures and documentation requirements

### Target outcome
Demonstrate the feasibility of using AI to strengthen CIF creation review controls by
validating information entered into CLS and CCRIS against supporting documents,
identifying data inaccuracies, highlighting control exceptions, and supporting KCT
testing activities.

### KCTs in scope
| KCT | Control |
|---|---|
| KCT-00001 | Data Accuracy — Incorrect Customer Name |
| KCT-00002 | Data Accuracy — Incorrect Registration Number |
| KCT-00003 | Data Accuracy — Incorrect Registered Address |
| KCT-00004 | Data Accuracy — Incorrect Business Information |
| KCT-00005 | Completeness — Incorrect Director Information |
| KCT-00006 | Data Accuracy — Incorrect Guarantor Information |
| KCT-00007 | Data Accuracy — Incorrect CCRIS Information |

### Proposed AI use case (capabilities to build)
- Application Form vs. CLS comparison
- SSM verification
- Guarantor information validation
- CCRIS Form matching
- Mandatory document completeness check
- Exception identification
- Exception summary generation

### Sample data provided
`samples/case-2-account-opening/xyz-sdn-bhd/` — a full CIF creation document set for
**"XYZ Sdn Bhd"** (see confidentiality note in the root `README.md` — the underlying
customer is not actually anonymized in every file): CLS extract, CCRIS screen extract,
CCRIS Application Form, Guarantor Application Form, SSM company search, and the internal
email thread requesting CCRIS creation. See that folder's `notes.md` for extracted
fields and an initial cross-document comparison against the KCTs above.

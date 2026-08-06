# Case 1 sample — Hadyan Sdn Bhd (Bank Guarantee facility)

Maps to `docs/poc-scope.md` → Case 1 (Letter of Offer vs. Credit Paper).

> This is now a manual first read. The automated version — `src/case1_credit_facilities/`
> extracting fields from both documents and running the KCT checks — lives in
> [`generated/exception-report.md`](generated/exception-report.md); see
> [`src/README.md`](../../../src/README.md) for how it works and how to rerun it.

> **Confidentiality**: unlike the Case 2 "XYZ Sdn Bhd" set, these two files are **not**
> anonymized at all — real customer name, registration number, guarantor NRIC, and
> AmBank staff names/signatures appear throughout. See the root `README.md` for the
> handling recommendation before this repo is pushed anywhere.

## Files
| File | What it is |
|---|---|
| `Credit Paper - AR2025 - Hadyan Sdn Bhd.docx` | Annual Review 2025 Credit Paper (the **approved** facility terms) |
| `Letter of Offer - Revise Purpose - Hadyan Sdn Bhd.doc` | Supplemental Letter of Offer, dated 12 Feb 2026, revising the BG purpose clause (the **issued** LO to test against the Credit Paper) |

## Extracted fields — Credit Paper (approved)
- Customer: Hadyan Sdn. Bhd. — Reg. No. 200101007110 (542866-W)
- Facility: BG (Bank Guarantee), Limit RM2,500,000 (fully secured)
- Pricing: 1.25% p.a.
- Security: 1-to-1 Fixed Deposit placed prior to issuance (P+I), Memorandum of Deposit +
  Letter of Set-Off
- Support: Personal Guarantee of **Datin Sri Sharifah**, NRIC 940202-07-5149
- Existing/current facility purpose (pre-revision, as stated in the CP purpose field):
  *"As performance bonds, tender deposits and security deposits in favour of Gas
  District Cooling (KLIA) Sdn Bhd for operation and maintenance agreement for the KLIA
  co-generation and district cooling storage plant ('KLIA Project') and in relation to
  the operation of electrical system for Petronas Twin Towers, Masjid Asy-Syakirin,
  common estate, common facilities and Menara ExxonMobil."*
- Purpose of submission (item 5) explicitly requests: annual review, **and** "to revise
  the BG purpose as per table below", **and** an exception request not to classify the
  account as UA despite an SICR trigger (Risk Grade deteriorated 3 notches, 12→15).
- Rationale explains the bank proposes to "open-up the BG utilization" (move from a
  single named beneficiary to general use) to support the customer's tendering pipeline.
- Prepared by Raymond Lim Giin Hoong (VP), Reviewed by Tay Bee Leng (VP), Recommended by
  Tan Bee Yan (SVP), Approved (CAD Level 1) by Patrick Chin Hau Yui.
- Tenure/review: existing review date 30 Sep 2025, next review date 30 Sep 2026.

## Extracted fields — Letter of Offer (issued, "Revise Purpose")
- Addressed to Hadyan Sdn Bhd, Attn: Datuk Sivabalan, Ref CB2/MKS/18/02/2026, dated
  12 February 2026.
- Confirms: (i) renew and continue the RM2,500,000 BG Facility, (ii) revise the purpose
  clause.
- **Revised purpose text in the LO**: *"As performance bonds, design bonds, maintenance
  bonds, tender deposits, advance payment, payment of excise duty, sales tax, utility
  and earnest money for tender / security deposits in favour of government statutory
  bodies and / or other parties acceptable to the Bank."*
- Signed for the Bank by **Tan Bee Yan** (SVP, Commercial Banking) and **Tay Bee Leng**
  (VP, Commercial Banking) — matches the Credit Paper's Recommended By / Reviewed By
  names.
- Guarantor acknowledgment block: **Datin Sri Sharifah**, MyKad No. 940202-07-5149 —
  matches the Credit Paper's guarantor exactly.
- Borrower acknowledgment block (name/designation/MyKad/date) is left blank in this copy
  — no signature/acceptance evidence captured in this sample.

## Preliminary read against the KCT checklist
This is only a manual, first-pass read — it is **not** the automated comparison the POC
is meant to build. Treat it as a starting reference, not a finding.

| KCT | Observation |
|---|---|
| KCT-00001 Facility Amount | RM2,500,000 in both CP and LO — consistent. |
| KCT-00002 Facility Purpose | CP records the *pre-revision* purpose (Gas District Cooling-specific) and separately states intent to broaden it; the LO's new purpose text is generic/government-statutory-bodies-facing. Wording differs materially between the two documents — **this is exactly the kind of comparison KCT-00002 is meant to catch, but confirming whether it's a true exception requires the CP's actual "revised purpose" table/approval text, which was not clearly captured in this extraction.** Worth using as the first test case for the purpose-matching AI capability. |
| KCT-00003 Pricing | Pricing (1.25% p.a.) is only in the CP; the LO (being a purpose-only supplemental letter) does not restate pricing — expected for a supplemental/variation letter, not necessarily an exception. |
| KCT-00004 Tenure | Not directly comparable — this LO is a purpose-revision supplement, not the full facility LO with tenure. |
| KCT-00005 Special Conditions | CP special condition: dividend payments capped at 50% of NPAT. Not repeated in this supplemental LO — check whether that's expected (supplemental letters may rely on the original LO for conditions not being varied). |
| KCT-00006 / 00007 Maker-Checker / Approval evidence | CP shows Prepared/Reviewed/Recommended/Approved-by names but no dated signatures captured in this extraction; LO borrower acceptance block is unsigned in this copy. |
| Customer details | Registration No. 200101007110 (542866-W) and guarantor NRIC 940202-07-5149 match exactly between CP and LO. |

## Why this pair is a good POC test case
It is a **supplemental/variation LO**, not a first-issue LO — a realistic edge case for
the AI comparison logic to handle (matching a revision letter against the base Credit
Paper's terms, rather than a 1:1 field match against a brand-new facility).

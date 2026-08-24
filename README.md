# AmBank POC — AI-Assisted Key Control Testing (KCT)

This repo holds the scope and sample data for a proof of concept assessing whether AI
can assist Internal Audit / Compliance in detecting control breaches and exceptions in
two existing manual KCT procedures:

- **Case 1 — Credit Facilities**: compare an issued Letter of Offer (LO) against the
  approved Credit Paper.
- **Case 2 — Account Opening**: for an individual investor, compare their Account
  Opening Form against their Identity Document, FATCA/CRS Declaration, Vulnerable Client
  Assessment and AML/NetReveal screening result; for a PRS (retirement scheme) account,
  reconcile the scanned evidence bundle against the internal TOMS system record instead.

Full scope, hypotheses, KCTs, exception catalogues and proposed AI capabilities for both
cases are written up in [`docs/poc-scope.md`](docs/poc-scope.md), extracted from the
source deck [`docs/POC Scope - Case 1 and Case 2.pptx`](<docs/POC Scope - Case 1 and Case 2.pptx>).

## ⚠️ Sample data is not anonymized

- The Case 1 set (`samples/case-1-credit-facilities/hadyan-sdn-bhd/`) is **not
  anonymized at all** — it's a real, "PRIVATE & CONFIDENTIAL" Credit Paper and Letter of
  Offer for a real customer (Hadyan Sdn Bhd), including a guarantor's full NRIC number
  and multiple AmBank officers' names and signatures.
- The Guarantor Application Form also contains a second individual guarantor's full
  NRIC/DOB and financials.
- The Case 2 sets (`samples/case-2-account-opening/` and
  `samples/case-2-account-opening-prs/`) contain real individual customers' Account
  Opening Forms, MyKad scans, FATCA/VCA declarations, AML screening results and internal
  TOMS system screenshots, including full names, NRIC numbers and residential addresses
  — not anonymized.

This repo has a live GitHub remote (`origin` →
`https://github.com/Dhruva-png/AmBankPoC.git`). Confirmed with the repo owner: commit
as-is, on the understanding that the GitHub repo is private and this is acceptable for
internal POC development use.

## Repo layout

```
docs/
  poc-scope.md                        Full POC scope for both cases (source: the pptx below)
  POC Scope - Case 1 and Case 2.pptx  Original scope deck
src/                                  Extraction + comparison pipeline -- see src/README.md
  common/extract_text.py              Generic .docx / .doc / .pdf -> plain text
  case1_credit_facilities/
    extract_fields.py                 Credit Paper + LO -> structured fields
    compare.py                        LO vs. Credit Paper -> KCT exception report
samples/
  case-1-credit-facilities/
    hadyan-sdn-bhd/
      Credit Paper - AR2025 - Hadyan Sdn Bhd.docx
      Letter of Offer - Revise Purpose - Hadyan Sdn Bhd.doc
      notes.md                       Extracted fields + preliminary KCT read
      generated/exception-report.md  Output of src/case1_credit_facilities/compare.py
      generated/exception-report.json
  case-2-account-opening/
    deepan-raj-al-gunalan/
    mohd-syafiq-bin-zukila/
    norazliana-binti-mohd-azmi/
      Account Opening Form.pdf
      Identity Document.pdf
      FATCA-CRS Declaration.pdf
      Vulnerable Client Assessment.pdf
      AML Screening (NetReveal).pdf
  case-2-account-opening-prs/
    aizan-farizal-shafiq/
    jimmy-lin-chee-vui/
    zul-fikri-in-yacob/
    yeoh-soon-khim/
      <customer> - Checked & Verified.pdf   PRS evidence bundle (AOF + FATCA + VCA + ID)
      <customer>1.pdf .. <customer>5.pdf    TOMS system-verification screenshots
requirements.txt
```

Original filenames were cleaned up (spaces/duplicate " 1" download artifacts removed)
but content is untouched from what was provided.

## What's already done
- Both sample sets read and cross-checked field-by-field against the scope's KCT/
  exception catalogue — see each folder's `notes.md`.
- **Case 1 is implemented end-to-end**: `src/case1_credit_facilities/` extracts
  structured fields from the Credit Paper (docx tables) and the Letter of Offer (regex
  over extracted prose), then runs the Case 1 KCT/exception checks and writes a
  Pass/Fail/Review exception report. Run it and read how it works in
  [`src/README.md`](src/README.md); the result on the Hadyan Sdn Bhd sample is committed
  at `samples/case-1-credit-facilities/hadyan-sdn-bhd/generated/exception-report.md` —
  it correctly matched the LO to the right facility (of two books on the same customer),
  passed 4 checks, flagged the purpose-wording difference and the un-repeated dividend
  covenant as `REVIEW` rather than guessing, and was honest that Maker-Checker timing
  (KCT-00006/07) isn't verifiable from this document pair (the Credit Paper's approval
  signatures are a scanned image, not text).
- **Case 2 is implemented end-to-end, with two flows**: `src/case2_account_opening/`
  classifies and extracts fields for individual-investor accounts (5 fixed documents,
  vision-based) and, separately, for PRS/retirement-scheme accounts (a variable-length
  scanned evidence bundle reconciled against internal TOMS system screenshots, using a
  hybrid text-layer/vision extraction). The Case 2 upload page in the app lets an
  auditor pick which flow applies. Verified live against all three individual-investor
  samples (correctly matched every field, and caught a genuine address mismatch between
  Norazliana's AOF and ID) and all four PRS samples (correctly matched three customers
  cleanly, flagged a genuine address discrepancy for the fourth, and surfaced a real
  AML/NetReveal match requiring manual clearance).

## Suggested next steps (for development)
1. Case 1's purpose-matching (KCT-00002) is currently a text diff, not a semantic
   comparison — the natural next iteration is routing genuinely-differing purpose text
   to an LLM call for a real Pass/Fail judgement instead of always returning `REVIEW`.
2. Expand sample coverage further — Case 2 now has seven customer samples across its two
   flows (Case 1 still has one); the KCT methodology calls for 2–10 samples depending on
   testing frequency.
3. Two PRS samples' FATCA signatory names come back slightly misread from a handwritten
   signature buried in a large scanned bundle, correctly flagged FAIL for manual
   confirmation rather than silently passed — see `src/README.md` for detail; worth
   revisiting if handwritten-signature accuracy on scanned bundles becomes a priority.

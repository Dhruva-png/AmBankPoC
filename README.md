# AmBank POC — AI-Assisted Key Control Testing (KCT)

This repo holds the scope and sample data for a proof of concept assessing whether AI
can assist Internal Audit / Compliance in detecting control breaches and exceptions in
two existing manual KCT procedures:

- **Case 1 — Credit Facilities**: compare an issued Letter of Offer (LO) against the
  approved Credit Paper.
- **Case 2 — Account Opening (CIF)**: compare CLS/CCRIS system data against the
  supporting documents used to create a corporate Customer Information File.

Full scope, hypotheses, KCTs, exception catalogues and proposed AI capabilities for both
cases are written up in [`docs/poc-scope.md`](docs/poc-scope.md), extracted from the
source deck [`docs/POC Scope - Case 1 and Case 2.pptx`](<docs/POC Scope - Case 1 and Case 2.pptx>).

## ⚠️ Sample data is not fully anonymized

The sample documents were clearly *intended* to be anonymized — files are named "XYZ Sdn
Bhd" and some pages carry an "XYZ SDN BHD" placeholder stamp — but the redaction is
**incomplete**:

- `samples/case-2-account-opening/xyz-sdn-bhd/XYZ Sdn Bhd - CLS Extract.pdf` is a raw,
  unredacted core-banking text export. It shows the real customer name
  (**Airoceanic Express Sdn Bhd**), real CIF/application numbers, real guarantor names,
  and real relationship-manager names throughout — no placeholder was applied.
- `XYZ Sdn Bhd - Email Request.pdf` leaks the real customer name in one un-redacted
  subject line, plus real AmBank staff names and `@ambankgroup.com` email addresses.
- The Case 1 set (`samples/case-1-credit-facilities/hadyan-sdn-bhd/`) is **not
  anonymized at all** — it's a real, "PRIVATE & CONFIDENTIAL" Credit Paper and Letter of
  Offer for a real customer (Hadyan Sdn Bhd), including a guarantor's full NRIC number
  and multiple AmBank officers' names and signatures.
- The Guarantor Application Form also contains a second individual guarantor's full
  NRIC/DOB and financials.

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
    xyz-sdn-bhd/
      XYZ Sdn Bhd - Email Request.pdf
      XYZ Sdn Bhd - CCRIS Application Form.pdf
      XYZ Sdn Bhd - Guarantor Application Form.pdf
      XYZ Sdn Bhd - SSM Search.pdf
      XYZ Sdn Bhd - CLS Extract.pdf
      XYZ Sdn Bhd - CCRIS Screen Extract.pdf
      notes.md                       Extracted fields + preliminary KCT read
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
- Note: `XYZ Sdn Bhd - CCRIS Application Form.pdf`, `Guarantor Application Form.pdf` and
  `SSM Search.pdf` are scanned/flattened images with no text layer — an OCR step (e.g.
  Tesseract, or a vision-capable model) will be needed before they can be parsed
  programmatically. `CLS Extract.pdf` and `Email Request.pdf` are text-based PDFs and
  parsed directly.

## Suggested next steps (for development)
1. **Case 2** — same "extract, then compare" pattern, next: adapt
   `src/common/extract_text.py`/a new `src/case2_account_opening/` package to the CLS/
   CCRIS/Application/Guarantor/SSM document set, with an OCR or vision-model step for
   the three scanned/image PDFs (see `src/README.md` for what's already scoped out).
2. Case 1's purpose-matching (KCT-00002) is currently a text diff, not a semantic
   comparison — the natural next iteration is routing genuinely-differing purpose text
   to an LLM call for a real Pass/Fail judgement instead of always returning `REVIEW`.
3. Expand sample coverage — each case currently has exactly one customer sample; the
   KCT methodology calls for 2–10 samples depending on testing frequency, so more
   samples (ideally with some genuinely clean and some genuinely exception-bearing) will
   be needed to validate the AI approach before a pilot.

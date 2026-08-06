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

## ⚠️ Before this goes any further: sample data is not fully anonymized

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

**This matters because this repo has a live GitHub remote**
(`origin` → `https://github.com/Dhruva-png/AmBankPoC.git`). Nothing in this working tree
has been committed or pushed as part of this session — everything above is currently
local, uncommitted changes only. Before committing/pushing, please confirm:

1. Is that GitHub repo **private**? Real customer PII (NRIC numbers, signatures, account
   numbers) should not land in a public repo.
2. Do you want these raw documents committed as-is (useful for realistic testing), or
   should they be redacted/replaced with synthetic equivalents first, or kept
   local-only (e.g. `.gitignore`'d) even if the write-ups in `docs/` and the `notes.md`
   summaries get committed?

## Repo layout

```
docs/
  poc-scope.md                        Full POC scope for both cases (source: the pptx below)
  POC Scope - Case 1 and Case 2.pptx  Original scope deck
samples/
  case-1-credit-facilities/
    hadyan-sdn-bhd/
      Credit Paper - AR2025 - Hadyan Sdn Bhd.docx
      Letter of Offer - Revise Purpose - Hadyan Sdn Bhd.doc
      notes.md                       Extracted fields + preliminary KCT read
  case-2-account-opening/
    xyz-sdn-bhd/
      XYZ Sdn Bhd - Email Request.pdf
      XYZ Sdn Bhd - CCRIS Application Form.pdf
      XYZ Sdn Bhd - Guarantor Application Form.pdf
      XYZ Sdn Bhd - SSM Search.pdf
      XYZ Sdn Bhd - CLS Extract.pdf
      XYZ Sdn Bhd - CCRIS Screen Extract.pdf
      notes.md                       Extracted fields + preliminary KCT read
```

Original filenames were cleaned up (spaces/duplicate " 1" download artifacts removed)
but content is untouched from what was provided.

## What's already done
- Both sample sets read and cross-checked field-by-field against the scope's KCT/
  exception catalogue — see each folder's `notes.md`.
- Two candidate "worked examples" identified for early development/testing:
  - **Case 1**: the LO's revised facility-purpose wording differs materially from the
    Credit Paper's on-file purpose text — a natural first test of the purpose-matching
    capability (see `hadyan-sdn-bhd/notes.md`).
  - **Case 2**: the Guarantor Application Form names ("MNO Sdn Bhd" / "MUTHU") don't
    match the guarantor names on the CLS facility-relationship screen ("Safeguards
    Corporati[on]" / "Darmendran A/L Kuna") — a natural first test of the guarantor
    matching capability (see `xyz-sdn-bhd/notes.md`).
- Note: `XYZ Sdn Bhd - CCRIS Application Form.pdf`, `Guarantor Application Form.pdf` and
  `SSM Search.pdf` are scanned/flattened images with no text layer — an OCR step (e.g.
  Tesseract, or a vision-capable model) will be needed before they can be parsed
  programmatically. `CLS Extract.pdf` and `Email Request.pdf` are text-based PDFs and
  parsed directly.

## Suggested next steps (for development)
1. Resolve the confidentiality question above before committing/pushing anything.
2. Decide the extraction approach for the scanned forms (OCR vs. vision-model parsing)
   given no OCR engine (Tesseract) or LibreOffice is installed in this environment —
   only `pypdf`/`pdfplumber`/`pypdfium2` (Python) and Microsoft Word COM automation
   (used here to read the legacy `.doc`) were available.
3. Design the comparison engine per case: a field-extraction step per document type,
   then a rules/LLM-based matcher producing the same Pass/Fail + exception-code output
   the manual KCT working paper currently records, so results can slot into the
   existing testing/conclusion workflow without changing it.
4. Expand sample coverage — each case currently has exactly one customer sample; the
   KCT methodology calls for 2–10 samples depending on testing frequency, so more
   samples (ideally with some genuinely clean and some genuinely exception-bearing) will
   be needed to validate the AI approach before a pilot.

# Pipeline: extract, then compare

Two-step pattern, used the same way both cases will need it (per `docs/poc-scope.md`):
**extract text/fields out of each source document, then compare the extracted fields
against the KCT/exception catalogue for that case.**

```
src/
  common/
    extract_text.py          Generic .docx / .doc / .pdf -> plain text
  case1_credit_facilities/
    extract_fields.py        Credit Paper (docx tables) + LO (regex over prose) -> structured fields
    compare.py                LO vs. Credit Paper -> KCT exception report (JSON + Markdown)
```

## Case 1 — Credit Facilities (implemented)

```bash
pip install -r requirements.txt

python src/case1_credit_facilities/compare.py \
  "samples/case-1-credit-facilities/hadyan-sdn-bhd/Credit Paper - AR2025 - Hadyan Sdn Bhd.docx" \
  "samples/case-1-credit-facilities/hadyan-sdn-bhd/Letter of Offer - Revise Purpose - Hadyan Sdn Bhd.doc" \
  "samples/case-1-credit-facilities/hadyan-sdn-bhd/generated"
```

Writes `exception-report.json` and `exception-report.md` into the given output
directory. See the committed
[`samples/case-1-credit-facilities/hadyan-sdn-bhd/generated/exception-report.md`](../samples/case-1-credit-facilities/hadyan-sdn-bhd/generated/exception-report.md)
for the result on the Hadyan Sdn Bhd sample.

**What it does:**
1. `extract_fields.extract_credit_paper_fields` reads the Credit Paper's "Principal
   Terms and Conditions" table (found by locating the row shaped
   `['Customer', ':', '<value>']`, not by a hardcoded table index) plus its per-book
   facility limit tables (found by header row `['Customer', 'Facility', ..., 'Pricing',
   'Security Details']`), and returns amount/purpose/pricing/tenure/special
   conditions/guarantor as structured fields.
2. `extract_fields.extract_lo_fields` reads the LO (`.doc`/`.docx`/`.pdf`) as plain text
   and pulls the same fields out via regex, since an LO is a prose letter rather than a
   form (facility amount, addressee + registration no., issuing entity/letterhead,
   purpose clause, guarantor acknowledgment block, signatories, date, reference).
3. `compare.compare` runs the checks from `docs/poc-scope.md`'s Case 1 exception
   catalogue and returns Pass / Fail / Review / N-A per check, matching the LO to the
   correct facility by amount when a customer has more than one book (e.g. AmBank
   conventional vs. AmIslamic), since Credit Papers commonly cover several.

**Known limitations (by design, not yet handled):**
- Purpose matching (KCT-00002) is text-comparison only, not semantic -- any wording
  difference comes back as `REVIEW`, not an automatic Pass/Fail. Judging whether a
  differently-worded purpose is a real exception or an approved revision is exactly the
  kind of judgement call the POC's proposed AI use case ("Purpose Matching") is meant to
  eventually make with an LLM; this rule-based pass surfaces the diff for a human (or a
  follow-up LLM call) rather than guessing.
- KCT-00006 (LO issued before approval) and KCT-00007 (Maker-Checker evidence) can't be
  verified from this sample pair -- the Credit Paper's approval date/signatures are in a
  scanned signature image, not extractable text. The report says so explicitly rather
  than silently passing.
- LO field extraction is regex-based against one bank's LO letter format (as seen in the
  Hadyan sample) -- expect to extend the regexes, not the architecture, as more LO
  formats/styles show up in additional samples.
- Only one Credit Paper + LO pair exists as a sample; the KCT methodology calls for
  2–10 samples depending on testing frequency, so this hasn't been validated against a
  clean case (all-Pass) or a genuinely-Fail case yet.

## Case 2 — Account Opening (implemented)

```bash
python src/case2_account_opening/compare.py \
  "samples/case-2-account-opening/deepan-raj-al-gunalan/Account Opening Form.pdf" \
  "samples/case-2-account-opening/deepan-raj-al-gunalan/Identity Document.pdf" \
  "samples/case-2-account-opening/deepan-raj-al-gunalan/FATCA-CRS Declaration.pdf" \
  "samples/case-2-account-opening/deepan-raj-al-gunalan/Vulnerable Client Assessment.pdf" \
  "samples/case-2-account-opening/deepan-raj-al-gunalan/AML Screening (NetReveal).pdf" \
  "samples/case-2-account-opening/deepan-raj-al-gunalan/generated"
```

Source documents are an individual investor's Account Opening Form (AOF), MyKad Identity
Document, FATCA/CRS Self-Certification, Vulnerable Client Assessment (VCA) and an
AML/NetReveal screening printout -- all scanned images with no text layer, so
`src/case2_account_opening/extract_fields.py` is vision-model-based throughout (unlike
Case 1, where every source document had a text layer). The AOF's principal-applicant
fields are written one character per box, so the extraction prompt explicitly instructs
reading every box left to right rather than stopping early.

**What it does:**
1. `classify_document` vision-classifies each uploaded file into one of the five document
   types so they can be uploaded in any order.
2. `extract_aof_fields` / `extract_id_fields` / `extract_fatca_fields` /
   `extract_vca_fields` / `extract_netreveal_fields` each vision-extract that document's
   fields; the AOF's signature block position varies by scan, so extraction searches
   backward through the last few pages rather than assuming a fixed page number.
3. `compare.compare` runs 7 KCTs + 1 exception: applicant name/NRIC/address cross-checked
   between the AOF and ID (NRIC via deterministic digit comparison, name/address via an
   AI semantic match), FATCA and VCA signed-by-applicant checks, NetReveal screening
   subject-matches-applicant (with an NRIC-mismatch override even if the name AI-matches)
   and screening-is-clear, and a mandatory-documents-present exception.

Verified live against all three real customer samples in
`samples/case-2-account-opening/` -- correctly matched every field for Deepan Raj and
Mohd Syafiq, and correctly flagged a genuine AOF-vs-ID address mismatch for Norazliana
rather than a false pass.

**Known limitations (by design, not yet handled):**
- Only three customer samples exist; the KCT methodology calls for 2-10 samples
  depending on testing frequency.

## Case 2 — Account Opening (PRS / Retirement Scheme sub-flow, implemented)

The original sample set also included four customer folders (Aizan, Jimmy, Zul Fikri,
Yeoh) following a structurally different pattern: a PRS (Private Retirement Scheme)
account isn't verified by cross-checking two paper documents -- it's verified by an
internal bank system (TOMS), whose "Account Inquiry" screens carry blue checkmarks
against each field once a staff member has confirmed it matches the source paperwork.
`case_detail.py` exposes this as a second flow ("PRS / Retirement Scheme") behind an
account-type toggle, since the upload/comparison shape is different from the i-Invest set:

```bash
python src/case2_account_opening/compare_prs.py \
  "samples/case-2-account-opening-prs/jimmy-lin-chee-vui/JIMMY LIN CHEE VUI - Checked & Verified.pdf" -- \
  samples/case-2-account-opening-prs/jimmy-lin-chee-vui/jimmy1.pdf \
  samples/case-2-account-opening-prs/jimmy-lin-chee-vui/jimmy2.pdf \
  samples/case-2-account-opening-prs/jimmy-lin-chee-vui/jimmy3.pdf \
  samples/case-2-account-opening-prs/jimmy-lin-chee-vui/jimmy4.pdf \
  samples/case-2-account-opening-prs/jimmy-lin-chee-vui/jimmy5.pdf \
  samples/case-2-account-opening-prs/jimmy-lin-chee-vui/generated
```

**What it does:**
1. `classify_document(..., categories=PRS_CATEGORIES)` sorts uploads into `toms_screen`
   (any TOMS "Account Inquiry" screenshot) or `prs_bundle` (everything else -- a
   customer's KYC evidence isn't split one-file-per-document-type like the i-Invest set;
   it may be one combined multi-page scan or spread across a few files).
2. `extract_toms_fields` merges the applicant's name/NRIC/DOB/address/account number
   across however many TOMS screens are uploaded (usually 5, each showing different
   fields). `extract_prs_bundle_fields` scans every page of every bundle file for the
   same fields plus FATCA/VCA/NetReveal content, wherever it happens to land.
3. Both extractors are **hybrid text/vision**: the TOMS screens and some bundle pages are
   computer-generated print-to-PDFs with a real embedded text layer -- reading that text
   directly is far more reliable than vision/OCR for names, so it's used whenever a page
   has one (`pdfplumber` extract_text, checked per-page since a bundle mixes typed pages
   with scanned paper/signature pages that have no text layer at all). Vision is only used
   as a fallback for pages without a usable text layer.
4. Even reading real text, the low-thinking-budget model occasionally garbled a name (e.g.
   read a clean "JIMMY LIN CHEE VUI" back as "SIMMY LIN CHWEE YUN") -- `_text_extract_verified`
   checks the extracted name is a literal substring of the source text and retries once if
   not, which fixed this for every TOMS read tested.
5. `compare_prs.compare` runs the same shape of checks as the i-Invest flow (name/NRIC/
   address cross-check, FATCA/VCA signed-by-applicant, NetReveal subject-match and
   screening-is-clear, mandatory-evidence-present exception) but reconciling the evidence
   bundle against the TOMS system record instead of two paper documents.

Verified live against all four real customer samples in `samples/case-2-account-opening-prs/`.
Three (Aizan, Zul Fikri, Yeoh) matched cleanly on name/NRIC/address; Jimmy's case
correctly flagged a genuine address discrepancy (a different unit/phase number between
the evidence bundle and the TOMS record) instead of a false pass. Yeoh's case correctly
surfaced a real AML/NetReveal match requiring manual clearance. Two customers' FATCA
signatory names (Jimmy's, Yeoh's) come back slightly misread from a handwritten signature
inside a large scanned bundle and are flagged FAIL for a human to confirm against the
actual page -- an honest "I'm not confident this matches" rather than a silent pass,
consistent with this project's no-fabricated-data standard, but worth noting as a real
OCR-difficulty limitation rather than a fixed one.

**Known limitations:**
- Aizan's evidence bundle has no page with a dedicated FATCA signature block (FATCA is
  answered inline on the Account Opening Form with no separate signature of its own) --
  correctly reported as REVIEW rather than guessing.
- Jimmy's and Zul Fikri's bundles have no NetReveal screening page at all in the sample
  provided -- correctly reported as REVIEW, not fabricated as clear.
- Only four PRS-pattern customer samples exist.

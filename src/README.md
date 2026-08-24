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
- The original sample set also included four customer folders following a different,
  "PRS"/internal-verification pattern (numbered system screenshots, "Checked & Verified"
  cover sheets) rather than the document-reconciliation model this pipeline assumes --
  deliberately excluded from this build rather than forced into a bad fit.

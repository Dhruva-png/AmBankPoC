# Case 2 sample — "XYZ Sdn Bhd" (CIF creation set)

Maps to `docs/poc-scope.md` → Case 2 (CLS/CCRIS vs. supporting documents).

> **Confidentiality note**: the filenames use the placeholder "XYZ Sdn Bhd", and the
> `SSM Search.pdf` and `Guarantor Application Form.pdf` are consistently overlaid with
> that placeholder. However, the anonymization is **incomplete**: the CLS extract is a
> raw, unredacted core-banking text dump that shows the real customer name throughout
> (**AIROCEANIC EXPRESS SDN. BHD.**), and the `Email Request.pdf` thread leaks the real
> name in one un-redacted subject line and shows real AmBank staff names/emails
> (@ambankgroup.com). See the root `README.md` before this repo is pushed anywhere.

## Files (renamed from the originals for clarity)
| File | What it is |
|---|---|
| `XYZ Sdn Bhd - Email Request.pdf` | Internal email thread requesting CCRIS/CIF creation (the Case 2 "Email Request" sampling document) |
| `XYZ Sdn Bhd - CCRIS Application Form.pdf` | Handwritten/typed New CCRIS Enhancement 2023 application form (facility-level detail) |
| `XYZ Sdn Bhd - Guarantor Application Form.pdf` | Guarantor 1 & Guarantor 2 input forms |
| `XYZ Sdn Bhd - SSM Search.pdf` | SSM (Companies Commission of Malaysia) company search extract — corporate info, share capital, directors/officers |
| `XYZ Sdn Bhd - CLS Extract.pdf` | Customer Lifecycle System screen extract (Application/Facility/Customer Information Inquiry screens) — **text-based, not image**, and not anonymized |
| `XYZ Sdn Bhd - CCRIS Screen Extract.pdf` | Single-page STARWORKS CIF application screen capture |

Note on format: the CCRIS Application, Guarantor Application and SSM Search PDFs are
**scanned/flattened images** (no extractable text layer) — OCR is required if you need
to machine-read them. The CLS extract and the email thread are text-based PDFs.

## Extracted fields — SSM Search (Corporate Information)
- Name: XYZ Sdn Bhd (placeholder — see confidentiality note above)
- Registration No.: 199001016623 (208292-V)
- Incorporation Date: 22-11-1990
- Type: Limited by Shares, Private Limited — Status: Existing
- Registered Address: 910 (ST 1) Blok B Phileo DMSR 2, No 15 Jalan 16/11, Off Jalan DMSR,
  PJ, Selangor, 46350 Petaling Jaya, Selangor
- Business Address: PT 64823, Jalan Tun Perak 3, Taman Perdana Industrial Park, KU16,
  Pelabuhan Klang, Selangor, 42000
- Nature of Business: Engaged as freight forwarder and transportation agents
- Total Issued Share Capital: RM2,000,000 (Ordinary: RM80,002 cash / RM1,919,998
  otherwise than cash)
- Directors/Officers: ABU (Secretary, appt. 07-02-2005), ALI (Director, appt.
  17-01-2005, IC 330303-03-0303), MUTHU (Director, appt. 10-06-2020, IC 610826-05-5555),
  AH CHONG (Director, appt. 05-02-2026, IC 770707-07-0707)

## Extracted fields — CLS Extract (Customer Lifecycle System)
- CIF Number: 1100006972 — Application No.: 1100006972104
- Customer name (system of record): **AIROCEANIC EXPRESS SDN. BHD.**
- ID No./Type: 208292V / CCT — matches SSM registration number 208292-V
- SSM/Reg. No. 2: 199001016623 — matches SSM search exactly
- Business type: Other transportation support activities (industry group 52290/52299)
- CIF branch: 808 HQ – Wholesale Banking; Business unit: 10104 AmB – Business Banking
- CIF created: 30/04/2020; date of birth/registration: 22/11/1990 (matches SSM
  incorporation date)
- Registered address (addr seq 2): 910 (ST 1) Block B Phileo Damansara 2, No 15 Jalan
  16/11, Off Jalan Damansara, 46350 Petaling Jaya, Selangor — matches SSM registered
  address
- Correspondence address (addr seq 1): PT 64823 Jalan Tun Perak 3, Taman Perdana
  Industrial Park, KU16, 42000 Pelabuhan Klang, Selangor — matches SSM business address
- Facility: ACF 00808/2020/0000909 (TBX/BNM, approved 30/04/20, RM1,000,000) and ACF
  00808/2026/0000862 (Term Loan FL, applied 12/05/26, RM1,000,000, Interest rate
  6.45%, purpose code 71)
- Guarantors on file: DARMENDRAN A/L KUNA (individual) and SAFEGUARDS CORPORATI[ON]
  (corporate) — **note: neither name matches "MUTHU" or "MNO Sdn Bhd", the guarantors
  named in the Guarantor Application Form (see below) — worth checking as a real
  KCT-00006 (Guarantor Information) exception candidate once the two guarantor forms in
  this set are fully reconciled against CLS.**
- Officer: BQQ06B - 2QQ06 YEP LEE XIN (RM); Manager: BQQ07 - 2QQ07 SHERINE SOO SOOK YEE
- Turnover: RM16,571,691 (FYE31/12/23, 51 staff) and RM16,184,620 (FYE31/12/24, 50 staff)

## Extracted fields — CCRIS Application Form (New CCRIS Enhancement 2023)
- Facility 1: Amount Applied RM1,000,000, Facility Code TMF, Purpose Code 71 / Sub-code 71
- Location of utilization: PT 64823, Jalan Tun Perak 3, Taman Perdana Industrial Park,
  KU16, 42000 Pelabuhan Klang, Selangor — matches SSM/CLS business address
- Prepared by: Yep Lee Xin — Checked by: Teng Hui Jin (digitally signed, 23 Apr 2026)

## Extracted fields — Guarantor Application Form
- **Guarantor 1**: MNO Sdn Bhd (placeholder name), Bus. Reg. No. 14914D, SME classified
  as Non-SME (large: 4,000 employees, RM502.5m / RM494.0m turnover for Year 1/Year 2)
- **Guarantor 2**: MUTHU, NRIC 610826-05-5555 (DOB 26/08/1961), Malaysian, guarantor
  relationship code "SH" (shareholder), employer/job "AS PER CIF"
- Both prepared by Yep Lee Xin, checked by Teng Hui Jin (23 Apr 2026)
- **Cross-check flag**: the CLS facility relationship screen lists the guarantors as
  "DARMENDRAN A/L KUNA" and "SAFEGUARDS CORPORATI[ON]" — different names from "MUTHU"
  and "MNO Sdn Bhd" on this form. This is exactly the class of discrepancy KCT-00006
  ("Data Accuracy — Incorrect Guarantor Information") is designed to catch; needs
  confirming against BNM/CCRIS whether these are the same underlying guarantor(s) with
  legal-entity vs. trading names, or a genuine mismatch.

## Extracted fields — Email Request thread (CCRIS Creation)
Chain from 21 Apr 2026 to 12 May 2026 between Yep Lee Xin (RM) and Mahdalina Mohd Rawi
(Corporate Loan – Facility Creation team), cc Sherine Soo Sook Yee:
1. 21 Apr: Lee Xin requests CCRIS creation for "Airoceanic Express Sdn Bhd", CCRIS form
   attached.
2. 22 Apr: **Rejected** — "Please sign the forms and provide in PDF format."
3. 23 Apr: Lee Xin resends signed CCRIS forms.
4. 24 Apr: Mahdalina asks for SSM instead of CTOS plus completed info.
5. 29 Apr: Lee Xin sends amended forms.
6. 5 May: Mahdalina asks Lee Xin to reconfirm officer code (shows CIF 1100006972 /
   Application 1100006972104 / ACF 00808/2020/0000909, RM1,000,000 approved) — matches
   CLS extract exactly.
7. 11 May: Lee Xin confirms office code correct.
8. 12 May: Mahdalina confirms "Application has been created accordingly", 6 attachments
   (filenames redacted in this copy).
- This thread is the **evidence trail** for KCT-00009 ("CIF approved without sufficient
  Maker-Checker verification evidence") — it shows the maker (Lee Xin) → checker
  (Mahdalina) round-trip, including one rejection cycle, which is a positive control
  example (Maker-Checker did catch and reject an incomplete submission).

## Preliminary read against the KCT checklist
Manual first pass only — not a substitute for the automated comparison the POC is meant
to build.

| KCT | Observation |
|---|---|
| KCT-00001 Customer Name | CLS records "AIROCEANIC EXPRESS SDN. BHD." consistently; SSM search shows "XYZ Sdn Bhd" (placeholder overlay) at the same registration number — can't verify true name match without an un-overlaid SSM extract, but registration numbers tie out. |
| KCT-00002 Registration Number | SSM 199001016623 (208292-V) = CLS "ID(BIZ REG) No 1" 208292V and "ID(BIZ REG) No 2" 199001016623 — **consistent**. |
| KCT-00003 Registered Address | SSM registered address = CLS address sequence 2 — **consistent**. SSM business address = CLS address sequence 1 (correspondence) — **consistent**. |
| KCT-00004 Business Information | SSM "freight forwarder and transportation agents" vs. CLS "Other transportation support activities" (industry code 52290/52299) — related but not verbatim; worth a fuzzy/semantic match rather than exact string match. |
| KCT-00005 Director Information | SSM lists 4 directors/officers (ABU, ALI, MUTHU, AH CHONG) with IC numbers; not yet cross-checked against an authorized-signatory field (not present in this extraction) — flag as incomplete sample for this specific KCT. |
| KCT-00006 Guarantor Information | **Likely exception candidate** — Guarantor Form names (MNO Sdn Bhd / MUTHU) don't match CLS facility-relationship guarantor names (SAFEGUARDS CORPORATI[ON] / DARMENDRAN A/L KUNA). See flag above. |
| KCT-00007 CCRIS Information | CCRIS Application Form facility amount (RM1,000,000, purpose code 71) matches the CLS ACF 00808/2020/0000909 exactly. |
| KCT-00008 Missing mandatory documents | Full document set appears present (Application/CCRIS/Guarantor/SSM/Email) for this sample. |
| KCT-00009 Maker-Checker evidence | Email thread documents a full maker→checker cycle including one rejection — evidence present. |

## Why this set is a good POC test case
It includes a **built-in rejection/resubmission cycle** in the email trail (a realistic
"Fail then Pass" Maker-Checker example) and a **plausible guarantor-name mismatch**
between the Guarantor Form and the CLS system record — both good seed cases for testing
the AI's exception-detection logic before it needs to run on a full sample population.

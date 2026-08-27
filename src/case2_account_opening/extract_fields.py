from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from extract_text import render_pdf_first_page, render_pdf_pages_to_images  # noqa: E402
from classify import classify_image  # noqa: E402
import ai_client  # noqa: E402

MIN_TEXT_LAYER_CHARS = 40


def _page_texts(path: str) -> list[str]:
    """Per-page extracted text, "" for a page with no usable text layer (e.g. a scanned
    image page). PRS evidence bundles mix computer-generated pages (real text layer,
    reading it directly is both more accurate and cheaper than vision) with scanned paper
    pages (image only, vision is the only option) within the same file."""
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        return [(page.extract_text() or "").strip() for page in pdf.pages]

VISION_SCALE = 1.3
# TOMS screenshots and PRS bundle scans are lower-quality/lower-DPI sources than the
# i-Invest scanned forms -- rendered at the same 1.3 scale, names get misread (e.g. a
# clean "JIMMY" read back as "SIMMY"). A higher render scale gives the vision model more
# pixels per character to work with.
PRS_VISION_SCALE = 2.2

CATEGORIES = {
    "aof": (
        "i-Invest Account Opening Form for an individual -- an AmInvest/AmFunds form with "
        "sections for Particulars of Principal Applicant (name, NRIC, address, employer), "
        "investment details, and signing declarations. Fields are often written one character "
        "per box."
    ),
    "id": (
        "Scanned Malaysian identity card (MyKad) -- shows a photo, the holder's name, NRIC "
        "number, address, and 'WARGANEGARA' nationality marker, usually front and back."
    ),
    "fatca": (
        "Foreign Account Tax Compliance Act (FATCA) and Common Reporting Standard (CRS) "
        "Self-Certification form -- a Yes/No questionnaire about U.S. person and tax residency "
        "status, ending in a signature and date."
    ),
    "vca": (
        "Vulnerable Client Assessment form -- assesses whether the applicant is a 'vulnerable "
        "client' (age, financial hardship, capability), with a Yes/No outcome, signature and date."
    ),
    "netreveal": (
        "AmBank NetReveal AML/sanctions screening printout -- a web tool screenshot showing "
        "'subject_name', 'subject_identification_number' fields and a results table of check "
        "names (TerroristAndSanctions, PEP, BNMEnforcement, etc.) with Content/Matches columns."
    ),
}

PRS_CATEGORIES = {
    "toms_screen": (
        "Screenshot of an internal bank system (TOMS) titled 'Account Inquiry' or similar, "
        "showing PRS account fields (Master Account Details, Personal Details, Addresses, "
        "Edit CIF Critical Details, Opening New Account) with blue checkmarks next to "
        "verified fields."
    ),
    "prs_bundle": (
        "Any other scanned document related to opening a PRS (Private Retirement Scheme) "
        "account that is NOT a TOMS system screenshot -- e.g. a PPA/PRS transfer form, "
        "PRS Account Opening Form, MyKad/IC copy, FATCA/CRS Self-Certification, Vulnerable "
        "Client Assessment, terms and conditions, or a checklist/cover sheet. This is the "
        "default category for anything that isn't clearly a TOMS screenshot."
    ),
}

CORP_CATEGORIES = {
    "toms_screen": (
        "Screenshot of an internal bank system (TOMS) titled 'Account Inquiry' or similar, "
        "showing a CORPORATE account (Category: CORPORATE) with a company name in the Name "
        "field and blue checkmarks next to verified fields."
    ),
    "corp_bundle": (
        "Any other scanned document related to opening a corporate account -- e.g. a "
        "corporate Account Opening Form, a New Corporate Onboarding Checklist (AmInvest "
        "FMD_CODDC form with Sections A-F and appendices for shareholding/beneficial "
        "owners), an SSM company search, constitutional documents, or an AML/NetReveal "
        "screening printout for the company or one of its individuals. This is the default "
        "category for anything that isn't clearly a TOMS screenshot."
    ),
}


def _render_for_vision(path: str, render_dir: str) -> list[str]:
    return render_pdf_pages_to_images(path, render_dir, scale=VISION_SCALE)


def classify_document(path: str, render_dir: str, categories: dict[str, str] = CATEGORIES) -> str:
    try:
        page_image = render_pdf_first_page(path, render_dir, scale=VISION_SCALE)
    except Exception:
        return "unknown"
    return classify_image(page_image, categories)


def _vision_extract(image_path: str, prompt: str, max_tokens: int = 1200) -> dict:
    b64, mime = ai_client.image_file_to_b64(image_path)
    return ai_client.vision_json(prompt, b64, mime, max_tokens=max_tokens)


def _text_extract(text: str, prompt_template: str, max_tokens: int = 500) -> dict:
    return ai_client.chat_json(prompt_template.format(text=text), max_tokens=max_tokens)


def _in_source(value: str, source_text: str) -> bool:
    """True if `value` literally appears in `source_text` (whitespace/case-insensitive).
    Even reading a real embedded text layer, the model occasionally garbles a name under
    the low thinking-budget config -- this catches that against the one thing that's
    actually authoritative here (the text extracted straight from the PDF, no OCR
    involved), so a bad read can be retried instead of silently trusted."""
    if not value:
        return False
    norm = lambda s: re.sub(r"\s+", "", s).upper()
    return norm(value) in norm(source_text)


def _text_extract_verified(text: str, prompt_template: str, field: str, max_tokens: int = 500) -> dict:
    """Like _text_extract, but retries once if `field` in the result doesn't literally
    appear in the source text -- the low-thinking-budget model occasionally garbles a name
    even when the exact text is right there."""
    data = _text_extract(text, prompt_template, max_tokens=max_tokens)
    if data.get(field) and not _in_source(data[field], text):
        data = _text_extract(text, prompt_template, max_tokens=max_tokens)
    return data


_AOF_PROMPT = """This is page 1 of an i-Invest Account Opening Form (individual). Section A "PARTICULARS OF PRINCIPAL APPLICANT" has fields written one character per box (like a cheque) -- read every box left to right and concatenate into a single value; do not stop at the first few boxes or drop leading/trailing characters.

Extract the Principal Applicant's:
- full name (field 1)
- new NRIC number (field 3, digits only)
- date of birth (field 5)
- residential address including postcode and country (field 6)
- nationality (field 9)
- name of employer (field 18)

Return strict JSON only, using "" for anything not visible:
{"name": "", "nric": "", "date_of_birth": "", "residential_address": "", "nationality": "", "employer": ""}"""

_AOF_SIGNATURE_PROMPT = """This page of an i-Invest Account Opening Form contains section G/I with the applicant's signing declaration and signature block. Extract the printed name of the Principal Applicant next to the signature, and the date signed. Return strict JSON only, using "" for anything not visible:
{"signatory_name": "", "signature_date": ""}"""


def extract_aof_fields(path: str, render_dir: str) -> dict:
    doc_name = Path(path).name
    if not ai_client.is_configured():
        return {"source_file": str(path), "error": "AI engine not configured", "sources": {}}
    pages = _render_for_vision(path, render_dir)
    principal = _vision_extract(pages[0], _AOF_PROMPT) if pages else {}
    # The signature block is on a later page (varies by scan) -- try the pages most likely to
    # carry it rather than assuming a fixed page number, and keep the first usable hit.
    signature: dict = {}
    signature_page_idx = None
    for idx in range(len(pages) - 1, max(len(pages) - 4, -1), -1):
        candidate = _vision_extract(pages[idx], _AOF_SIGNATURE_PROMPT)
        if candidate.get("signatory_name"):
            signature, signature_page_idx = candidate, idx
            break

    doc_source_p1 = f"{doc_name} (page 1, AI vision)"
    doc_source_sig = f"{doc_name} (page {signature_page_idx + 1}, AI vision)" if signature_page_idx is not None else doc_source_p1
    return {
        "source_file": str(path),
        "name": principal.get("name", ""),
        "nric": principal.get("nric", ""),
        "date_of_birth": principal.get("date_of_birth", ""),
        "residential_address": principal.get("residential_address", ""),
        "nationality": principal.get("nationality", ""),
        "employer": principal.get("employer", ""),
        "signatory_name": signature.get("signatory_name", ""),
        "signature_date": signature.get("signature_date", ""),
        "sources": {
            "name": doc_source_p1, "nric": doc_source_p1, "date_of_birth": doc_source_p1,
            "residential_address": doc_source_p1, "nationality": doc_source_p1, "employer": doc_source_p1,
            "signatory_name": doc_source_sig, "signature_date": doc_source_sig,
        },
    }


_ID_PROMPT = """This is a scanned Malaysian identity card (MyKad). Extract exactly what is printed on the card:
- full name
- NRIC number (format XXXXXX-XX-XXXX or run together)
- address (as printed on the card)

Return strict JSON only, using "" for anything not visible:
{"name": "", "nric": "", "address": ""}"""


def extract_id_fields(path: str, render_dir: str) -> dict:
    doc_name = Path(path).name
    if not ai_client.is_configured():
        return {"source_file": str(path), "error": "AI engine not configured", "sources": {}}
    pages = _render_for_vision(path, render_dir)
    data = _vision_extract(pages[0], _ID_PROMPT) if pages else {}
    doc_source = f"{doc_name} (AI vision)"
    return {
        "source_file": str(path),
        "name": data.get("name", ""),
        "nric": data.get("nric", ""),
        "address": data.get("address", ""),
        "sources": {k: doc_source for k in ("name", "nric", "address")},
    }


_FATCA_PROMPT = """This is a FATCA/CRS Self-Certification form. Extract:
- whether Part A indicates the person IS a U.S. person/citizen/resident (true if any "Yes" is ticked in the U.S. Indicia Status table, false if all are "No")
- the printed/signed name in the signature block (Name field, not the pre-printed applicant name if handwritten differs)
- the date next to the signature

Return strict JSON only, using false/"" for anything not visible or not determinable:
{"is_us_person": false, "signatory_name": "", "signature_date": ""}"""


def extract_fatca_fields(path: str, render_dir: str) -> dict:
    doc_name = Path(path).name
    if not ai_client.is_configured():
        return {"source_file": str(path), "error": "AI engine not configured", "sources": {}}
    pages = _render_for_vision(path, render_dir)
    combined: dict = {}
    for page in pages:
        data = _vision_extract(page, _FATCA_PROMPT)
        if data.get("signatory_name"):
            combined = data
            break
        if not combined:
            combined = data
    doc_source = f"{doc_name} (AI vision)"
    return {
        "source_file": str(path),
        "is_us_person": bool(combined.get("is_us_person")),
        "signatory_name": combined.get("signatory_name", ""),
        "signature_date": combined.get("signature_date", ""),
        "sources": {k: doc_source for k in ("is_us_person", "signatory_name", "signature_date")},
    }


_VCA_PROMPT = """This is a Vulnerable Client Assessment form. Extract:
- the applicant's name (Name of Applicant field)
- the applicant's NRIC/passport number
- whether the client is classified as a Vulnerable Client (true if "Yes" is marked in section (A) final tick-box, false if "No")
- the printed/signed name in the Acknowledgement signature block (section D), and the date

Return strict JSON only, using false/"" for anything not visible:
{"applicant_name": "", "nric": "", "is_vulnerable": false, "signatory_name": "", "signature_date": ""}"""


def extract_vca_fields(path: str, render_dir: str) -> dict:
    doc_name = Path(path).name
    if not ai_client.is_configured():
        return {"source_file": str(path), "error": "AI engine not configured", "sources": {}}
    pages = _render_for_vision(path, render_dir)
    combined: dict = {}
    for page in pages:
        data = _vision_extract(page, _VCA_PROMPT)
        if data.get("applicant_name") or data.get("signatory_name"):
            combined.update({k: v for k, v in data.items() if v not in (None, "", False)})
    doc_source = f"{doc_name} (AI vision)"
    return {
        "source_file": str(path),
        "applicant_name": combined.get("applicant_name", ""),
        "nric": combined.get("nric", ""),
        "is_vulnerable": bool(combined.get("is_vulnerable")),
        "signatory_name": combined.get("signatory_name", ""),
        "signature_date": combined.get("signature_date", ""),
        "sources": {k: doc_source for k in ("applicant_name", "nric", "is_vulnerable", "signatory_name", "signature_date")},
    }


_NETREVEAL_PROMPT = """This is an AmBank NetReveal AML/sanctions screening printout for one subject. Extract:
- the "subject_name" field value
- the "subject_identification_number" field value
- whether the "Results of Single Lookup" table has ANY non-empty value in its Content or Matches columns for any check name (true = at least one hit/match found, false = every row's Content/Matches columns are blank, meaning a clean screening result)

Return strict JSON only, using "" or false for anything not visible:
{"subject_name": "", "subject_identification_number": "", "has_matches": false}"""


_PRS_BUNDLE_PROMPT = """This is ONE PAGE from a scanned PRS (Private Retirement Scheme) account-opening evidence bundle. Depending on which page this is, it may show: a PRS Account Opening Form (applicant particulars and/or its own declaration/signature section), a MyKad/IC copy, a FATCA/CRS Self-Certification questionnaire (which may be a standalone form with its own signature, OR just a set of Yes/No questions embedded in the Account Opening Form with no signature of its own), a Vulnerable Client Assessment (whose Acknowledgement section, often labelled "(D)", has a table with the applicant's printed Name and Date), or an AML NetReveal screening printout -- or none of these (e.g. a terms-and-conditions or blank page).

Look ONLY at this page and extract whatever of the following is visible on it. Use "" for a text field not visible on this page, and null (not false) for a yes/no field not visible on this page -- do not guess or carry over information from other pages you have not seen.

Read every name character by character exactly as printed -- do not substitute a similar-looking letter or "autocorrect" toward a more common name/spelling. If the same name appears more than once on this page, cross-check your reading against every occurrence before answering.

- fatca_signatory_name / fatca_signature_date: ONLY if this page is a FATCA/CRS form that has ITS OWN dedicated signature block (separate from the general application signature).
- vca_signatory_name / vca_signature_date: the applicant's printed name and date from the Vulnerable Client Assessment's Acknowledgement/signature table.
- application_signatory_name / application_signature_date: the applicant's printed name and date from the Account Opening Form / PRS application's own general declaration or signature section (used when one signature covers multiple declarations together, e.g. "General Declaration; FATCA & CRS Declaration").

Return strict JSON only:
{"applicant_name": "", "applicant_nric": "", "date_of_birth": "", "residential_address": "", "employer": "", "is_us_person": null, "fatca_signatory_name": "", "fatca_signature_date": "", "is_vulnerable_client": null, "vca_signatory_name": "", "vca_signature_date": "", "application_signatory_name": "", "application_signature_date": "", "netreveal_subject_name": "", "netreveal_subject_id": "", "netreveal_has_matches": null}"""

_PRS_BUNDLE_PROMPT_TEXT = """Below is the extracted text from ONE PAGE of a PRS (Private Retirement Scheme) account-opening evidence bundle. Depending on which page this is, it may show: a PRS Account Opening Form (applicant particulars and/or its own declaration/signature section), a FATCA/CRS Self-Certification questionnaire (which may be a standalone form with its own signature, OR just a set of Yes/No questions embedded in the Account Opening Form with no signature of its own), a Vulnerable Client Assessment (whose Acknowledgement section, often labelled "(D)", has a table with the applicant's printed Name and Date), or an AML NetReveal screening printout -- or none of these (e.g. a terms-and-conditions or blank page).

Page text:
\"\"\"{text}\"\"\"

Look ONLY at this page's text and extract whatever of the following is present. Use "" for a text field not present on this page, and null (not false) for a yes/no field not present on this page -- do not guess or carry over information from other pages you have not seen.

- fatca_signatory_name / fatca_signature_date: ONLY if this page is a FATCA/CRS form that has ITS OWN dedicated signature block (separate from the general application signature).
- vca_signatory_name / vca_signature_date: the applicant's printed name and date from the Vulnerable Client Assessment's Acknowledgement/signature table.
- application_signatory_name / application_signature_date: the applicant's printed name and date from the Account Opening Form / PRS application's own general declaration or signature section (used when one signature covers multiple declarations together, e.g. "General Declaration; FATCA & CRS Declaration").

Return strict JSON only:
{{"applicant_name": "", "applicant_nric": "", "date_of_birth": "", "residential_address": "", "employer": "", "is_us_person": null, "fatca_signatory_name": "", "fatca_signature_date": "", "is_vulnerable_client": null, "vca_signatory_name": "", "vca_signature_date": "", "application_signatory_name": "", "application_signature_date": "", "netreveal_subject_name": "", "netreveal_subject_id": "", "netreveal_has_matches": null}}"""

_PRS_BUNDLE_TEXT_FIELDS = [
    "applicant_name", "applicant_nric", "date_of_birth", "residential_address", "employer",
    "fatca_signatory_name", "fatca_signature_date", "vca_signatory_name", "vca_signature_date",
    "application_signatory_name", "application_signature_date",
    "netreveal_subject_name", "netreveal_subject_id",
]


def extract_prs_bundle_fields(paths: list[str], render_dir: str) -> dict:
    """paths: one or more scanned PDFs making up a customer's PRS evidence (AOF + ID +
    FATCA + VCA + sometimes NetReveal). Unlike the i-Invest set, these aren't split into
    one file per document type -- a customer's evidence may be one combined multi-page
    scan, or spread across a few files (a transfer form, a checklist, a "verified" cover)
    -- so every page of every file is scanned and merged, whichever page carries which
    section varies from customer to customer."""
    if not ai_client.is_configured():
        return {"source_file": ", ".join(Path(p).name for p in paths), "error": "AI engine not configured", "sources": {}}
    combined: dict = {}
    sources: dict = {}
    netreveal_found = False
    netreveal_has_matches = False
    for path in paths:
        doc_name = Path(path).name
        page_texts = _page_texts(path)
        images: list[str] | None = None
        for idx, page_text in enumerate(page_texts):
            # A computer-generated page (form printout, transfer request) has a real text
            # layer -- reading it directly is both more accurate and cheaper than vision.
            # A scanned paper page (MyKad copy, wet signature) has no usable text layer,
            # so it's rendered to an image and read via vision instead.
            if len(page_text) >= MIN_TEXT_LAYER_CHARS:
                data = _text_extract_verified(page_text, _PRS_BUNDLE_PROMPT_TEXT, "applicant_name", max_tokens=500)
                source_tag = f"{doc_name} (page {idx + 1}, text)"
            else:
                if images is None:
                    images = render_pdf_pages_to_images(path, render_dir, scale=PRS_VISION_SCALE)
                data = _vision_extract(images[idx], _PRS_BUNDLE_PROMPT, max_tokens=500)
                source_tag = f"{doc_name} (page {idx + 1}, AI vision)"
            for key in _PRS_BUNDLE_TEXT_FIELDS:
                value = data.get(key)
                if value and key not in combined:
                    combined[key] = value
                    sources[key] = source_tag
            if data.get("is_us_person") is not None and "is_us_person" not in combined:
                combined["is_us_person"] = bool(data["is_us_person"])
            if data.get("is_vulnerable_client") is not None and "is_vulnerable_client" not in combined:
                combined["is_vulnerable_client"] = bool(data["is_vulnerable_client"])
            if data.get("netreveal_subject_name") or data.get("netreveal_has_matches") is not None:
                netreveal_found = True
                netreveal_has_matches = netreveal_has_matches or bool(data.get("netreveal_has_matches"))

    return {
        "source_file": ", ".join(Path(p).name for p in paths),
        "name": combined.get("applicant_name", ""),
        "nric": combined.get("applicant_nric", ""),
        "date_of_birth": combined.get("date_of_birth", ""),
        "residential_address": combined.get("residential_address", ""),
        "employer": combined.get("employer", ""),
        "is_us_person": bool(combined.get("is_us_person", False)),
        "fatca_signatory_name": combined.get("fatca_signatory_name", ""),
        "fatca_signature_date": combined.get("fatca_signature_date", ""),
        "is_vulnerable_client": bool(combined.get("is_vulnerable_client", False)),
        "vca_signatory_name": combined.get("vca_signatory_name", ""),
        "vca_signature_date": combined.get("vca_signature_date", ""),
        "application_signatory_name": combined.get("application_signatory_name", ""),
        "application_signature_date": combined.get("application_signature_date", ""),
        "netreveal_subject_name": combined.get("netreveal_subject_name", ""),
        "netreveal_subject_id": combined.get("netreveal_subject_id", ""),
        "netreveal_found": netreveal_found,
        "netreveal_has_matches": netreveal_has_matches,
        "sources": sources,
    }


_TOMS_SCREEN_PROMPT = """This is a screenshot of one screen from an internal bank system (TOMS) used to verify a PRS (Private Retirement Scheme) account during account opening -- one of several screens such as Account Inquiry (Master Account Details, Personal Details, List Of Addresses), Edit CIF Critical Details, or Opening New Account. Blue checkmarks next to a field mean it has been verified against source documents -- extract the field's value regardless of whether it carries a checkmark.

Extract whatever of the following is visible on THIS screen. Use "" for anything not visible on this screen. Read the name character by character exactly as printed -- do not substitute a similar-looking letter or "autocorrect" toward a more common name/spelling; if the name appears more than once on this screen, cross-check your reading against every occurrence before answering.

Return strict JSON only:
{"name": "", "nric": "", "date_of_birth": "", "address": "", "account_reference_no": ""}"""

_TOMS_SCREEN_PROMPT_TEXT = """Below is the extracted text from one screen of an internal bank system (TOMS) used to verify a PRS (Private Retirement Scheme) account during account opening -- one of several screens such as Account Inquiry (Master Account Details, Personal Details, List Of Addresses), Edit CIF Critical Details, or Opening New Account.

Screen text:
\"\"\"{text}\"\"\"

Extract whatever of the following is present in this text. Use "" for anything not present.

Return strict JSON only:
{{"name": "", "nric": "", "date_of_birth": "", "address": "", "account_reference_no": ""}}"""


def extract_toms_fields(paths: list[str], render_dir: str) -> dict:
    """paths: the (usually 5) numbered TOMS system-verification screenshots for one
    customer, in any order -- merge whichever screen shows each field. These are
    computer-generated print-to-PDF screenshots with a real text layer, so the embedded
    text is read directly rather than via vision/OCR wherever it's available -- far more
    reliable for names than reading pixels, and cheaper."""
    if not ai_client.is_configured():
        return {"source_file": ", ".join(Path(p).name for p in paths), "error": "AI engine not configured", "sources": {}}
    combined: dict = {}
    sources: dict = {}
    for path in paths:
        doc_name = Path(path).name
        page_texts = _page_texts(path)
        page_text = page_texts[0] if page_texts else ""
        if len(page_text) >= MIN_TEXT_LAYER_CHARS:
            data = _text_extract_verified(page_text, _TOMS_SCREEN_PROMPT_TEXT, "name", max_tokens=400)
            source_suffix = "text"
        else:
            page = render_pdf_first_page(path, render_dir, scale=PRS_VISION_SCALE)
            data = _vision_extract(page, _TOMS_SCREEN_PROMPT, max_tokens=400)
            source_suffix = "AI vision"
        for key in ("name", "nric", "date_of_birth", "address", "account_reference_no"):
            value = data.get(key)
            if value and key not in combined:
                combined[key] = value
                sources[key] = f"{doc_name} ({source_suffix})"
    return {
        "source_file": ", ".join(Path(p).name for p in paths),
        "name": combined.get("name", ""),
        "nric": combined.get("nric", ""),
        "date_of_birth": combined.get("date_of_birth", ""),
        "address": combined.get("address", ""),
        "account_reference_no": combined.get("account_reference_no", ""),
        "sources": sources,
    }


def extract_netreveal_fields(path: str, render_dir: str) -> dict:
    doc_name = Path(path).name
    if not ai_client.is_configured():
        return {"source_file": str(path), "error": "AI engine not configured", "sources": {}}
    pages = _render_for_vision(path, render_dir)
    combined: dict = {}
    has_matches = False
    for page in pages:
        data = _vision_extract(page, _NETREVEAL_PROMPT)
        has_matches = has_matches or bool(data.get("has_matches"))
        if data.get("subject_name") and not combined.get("subject_name"):
            combined = data
    doc_source = f"{doc_name} (AI vision, all pages)"
    return {
        "source_file": str(path),
        "subject_name": combined.get("subject_name", ""),
        "subject_identification_number": combined.get("subject_identification_number", ""),
        "has_matches": has_matches,
        "sources": {k: doc_source for k in ("subject_name", "subject_identification_number", "has_matches")},
    }


_CORP_BUNDLE_PROMPT = """This is ONE PAGE from a scanned corporate account-opening evidence bundle. Depending on which page this is, it may show: a corporate Account Opening Form (company name, registration number), a New Corporate Onboarding Checklist's Section D "Preparer, Checker and Approver's Signature" table (three roles: Prepared by / Checked by / Approved by, each with a printed Name and Date), that checklist's Appendix B "BO Data points" listing named Beneficial Owner(s) (Full Name, NRIC/Passport Number), or an AML/NetReveal screening printout for the company or one of its individuals -- or none of these (e.g. a blank/cover page).

Look ONLY at this page and extract whatever of the following is present. Use "" for a text field not present on this page, and null (not false) for a yes/no field not present on this page -- do not guess or carry over information from other pages you have not seen. Read every name and number character by character exactly as printed.

- company_name / registration_no: from the Account Opening Form's "Registered Name" / "Business Registration No." fields.
- prepared_by_name / prepared_by_date, checked_by_name / checked_by_date, approved_by_name / approved_by_date: ONLY from a Section D "Preparer, Checker and Approver's Signature" table -- the printed Name and Date for each of the three roles shown on that specific page.
- bo1_name / bo1_nric, bo2_name / bo2_nric: ONLY from an Appendix B "BO Data points" / "Beneficial Owner 1" / "Beneficial Owner 2" table -- the Full Name and NRIC/Passport Number for each.
- netreveal_subject_name / netreveal_has_matches: if this page is an AML/NetReveal screening result for any subject (the company or an individual), that subject's name, and whether the page shows any match/alert/hit for them (true) or a clean/no-record result (false).

Return strict JSON only:
{"company_name": "", "registration_no": "", "prepared_by_name": "", "prepared_by_date": "", "checked_by_name": "", "checked_by_date": "", "approved_by_name": "", "approved_by_date": "", "bo1_name": "", "bo1_nric": "", "bo2_name": "", "bo2_nric": "", "netreveal_subject_name": "", "netreveal_has_matches": null}"""

_CORP_BUNDLE_PROMPT_TEXT = """Below is the extracted text from ONE PAGE of a corporate account-opening evidence bundle. Depending on which page this is, it may show: a corporate Account Opening Form (company name, registration number), a New Corporate Onboarding Checklist's Section D "Preparer, Checker and Approver's Signature" table, that checklist's Appendix B "BO Data points" listing named Beneficial Owner(s), or an AML/NetReveal screening printout for the company or one of its individuals.

Page text:
\"\"\"{text}\"\"\"

Look ONLY at this page's text and extract whatever of the following is present. Use "" for a text field not present, and null (not false) for a yes/no field not present -- do not guess or carry over information from other pages you have not seen.

- company_name / registration_no: from the Account Opening Form's "Registered Name" / "Business Registration No." fields.
- prepared_by_name / prepared_by_date, checked_by_name / checked_by_date, approved_by_name / approved_by_date: ONLY from a Section D "Preparer, Checker and Approver's Signature" table.
- bo1_name / bo1_nric, bo2_name / bo2_nric: ONLY from an Appendix B "BO Data points" / "Beneficial Owner 1" / "Beneficial Owner 2" table.
- netreveal_subject_name / netreveal_has_matches: if this page is an AML/NetReveal screening result for any subject, that subject's name, and whether the page shows any match/alert/hit for them (true) or a clean/no-record result (false).

Return strict JSON only:
{{"company_name": "", "registration_no": "", "prepared_by_name": "", "prepared_by_date": "", "checked_by_name": "", "checked_by_date": "", "approved_by_name": "", "approved_by_date": "", "bo1_name": "", "bo1_nric": "", "bo2_name": "", "bo2_nric": "", "netreveal_subject_name": "", "netreveal_has_matches": null}}"""

_CORP_BUNDLE_TEXT_FIELDS = [
    "company_name", "registration_no", "prepared_by_name", "prepared_by_date",
    "checked_by_name", "checked_by_date", "approved_by_name", "approved_by_date",
    "bo1_name", "bo1_nric", "bo2_name", "bo2_nric",
]


def extract_corp_bundle_fields(paths: list[str], render_dir: str) -> dict:
    """paths: the corporate AOF, onboarding checklist, and any NetReveal screening files
    (company-level and/or named individuals) for one corporate customer. Scope note: this
    intentionally checks only the two Beneficial Owners the bank's own checklist names in
    Appendix B, not the full multi-tier shareholding chain some of these corporate groups
    have -- that matches the depth the real control itself verifies, not a shortcut."""
    if not ai_client.is_configured():
        return {"source_file": ", ".join(Path(p).name for p in paths), "error": "AI engine not configured", "sources": {}}
    combined: dict = {}
    sources: dict = {}
    netreveal_screenings: list[dict] = []
    for path in paths:
        doc_name = Path(path).name
        page_texts = _page_texts(path)
        images: list[str] | None = None
        for idx, page_text in enumerate(page_texts):
            if len(page_text) >= MIN_TEXT_LAYER_CHARS:
                data = _text_extract(page_text, _CORP_BUNDLE_PROMPT_TEXT, max_tokens=500)
                source_tag = f"{doc_name} (page {idx + 1}, text)"
            else:
                if images is None:
                    images = render_pdf_pages_to_images(path, render_dir, scale=PRS_VISION_SCALE)
                data = _vision_extract(images[idx], _CORP_BUNDLE_PROMPT, max_tokens=500)
                source_tag = f"{doc_name} (page {idx + 1}, AI vision)"
            for key in _CORP_BUNDLE_TEXT_FIELDS:
                value = data.get(key)
                if value and key not in combined:
                    combined[key] = value
                    sources[key] = source_tag
            if data.get("netreveal_subject_name"):
                netreveal_screenings.append({
                    "subject_name": data["netreveal_subject_name"],
                    "has_matches": bool(data.get("netreveal_has_matches")),
                    "source": source_tag,
                })

    return {
        "source_file": ", ".join(Path(p).name for p in paths),
        "company_name": combined.get("company_name", ""),
        "registration_no": combined.get("registration_no", ""),
        "prepared_by_name": combined.get("prepared_by_name", ""),
        "prepared_by_date": combined.get("prepared_by_date", ""),
        "checked_by_name": combined.get("checked_by_name", ""),
        "checked_by_date": combined.get("checked_by_date", ""),
        "approved_by_name": combined.get("approved_by_name", ""),
        "approved_by_date": combined.get("approved_by_date", ""),
        "bo1_name": combined.get("bo1_name", ""),
        "bo1_nric": combined.get("bo1_nric", ""),
        "bo2_name": combined.get("bo2_name", ""),
        "bo2_nric": combined.get("bo2_nric", ""),
        "netreveal_screenings": netreveal_screenings,
        "sources": sources,
    }


_PB_REGISTER_PROMPT_TEXT = """Below is the extracted text from ONE PAGE of a Private Banking Sales Register -- an internal batch transaction sheet for Money Market / Unit Trust fund purchases, NOT an individual account-opening form (it lists multiple client codes and amounts under one transaction reference, with a dual-control sign-off at the bottom: some combination of "Prepared by", "Entered by", "Approved by", "Maker", "Checker").

Page text:
\"\"\"{text}\"\"\"

Extract whatever of the following is present. A "signed" role only counts if there is an actual name, signature image reference (e.g. "Digitally signed by"), or checkmark next to it -- a blank line or label alone does not count. Use "" for anything not present, and null for a yes/no field not present.

Return strict JSON only:
{{"transaction_ref": "", "transaction_date": "", "fund_type": "", "grand_total": "", "maker_signed": null, "maker_name": "", "maker_date": "", "checker_signed": null, "checker_name": "", "checker_date": ""}}"""


def extract_pb_register_fields(paths: list[str], render_dir: str) -> dict:
    """paths: the Private Banking Sales Register PDF (and any other supporting file, e.g.
    an exported email) for one batch transaction. This is NOT an individual account-opening
    case -- there's no single applicant identity or TOMS record to reconcile against, so the
    only thing genuinely checkable from this evidence is dual-control (maker/checker)
    sign-off completeness, not identity/KYC accuracy."""
    if not ai_client.is_configured():
        return {"source_file": ", ".join(Path(p).name for p in paths), "error": "AI engine not configured", "sources": {}}
    combined: dict = {}
    sources: dict = {}
    text_fields = ["transaction_ref", "transaction_date", "fund_type", "grand_total", "maker_name", "maker_date", "checker_name", "checker_date"]
    for path in paths:
        doc_name = Path(path).name
        if Path(path).suffix.lower() != ".pdf":
            continue
        page_texts = _page_texts(path)
        images: list[str] | None = None
        for idx, page_text in enumerate(page_texts):
            if len(page_text) >= MIN_TEXT_LAYER_CHARS:
                data = _text_extract(page_text, _PB_REGISTER_PROMPT_TEXT, max_tokens=400)
                source_tag = f"{doc_name} (page {idx + 1}, text)"
            else:
                if images is None:
                    images = render_pdf_pages_to_images(path, render_dir, scale=PRS_VISION_SCALE)
                source_tag = f"{doc_name} (page {idx + 1}, AI vision)"
                data = {}
            for key in text_fields:
                value = data.get(key)
                if value and key not in combined:
                    combined[key] = value
                    sources[key] = source_tag
            if data.get("maker_signed") is not None and "maker_signed" not in combined:
                combined["maker_signed"] = bool(data["maker_signed"])
            if data.get("checker_signed") is not None and "checker_signed" not in combined:
                combined["checker_signed"] = bool(data["checker_signed"])

    return {
        "source_file": ", ".join(Path(p).name for p in paths),
        "transaction_ref": combined.get("transaction_ref", ""),
        "transaction_date": combined.get("transaction_date", ""),
        "fund_type": combined.get("fund_type", ""),
        "grand_total": combined.get("grand_total", ""),
        "maker_signed": bool(combined.get("maker_signed", False)),
        "maker_name": combined.get("maker_name", ""),
        "maker_date": combined.get("maker_date", ""),
        "checker_signed": bool(combined.get("checker_signed", False)),
        "checker_name": combined.get("checker_name", ""),
        "checker_date": combined.get("checker_date", ""),
        "sources": sources,
    }

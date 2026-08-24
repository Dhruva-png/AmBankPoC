from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from extract_text import render_pdf_first_page, render_pdf_pages_to_images  # noqa: E402
from classify import classify_image  # noqa: E402
import ai_client  # noqa: E402

VISION_SCALE = 1.3

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


def _render_for_vision(path: str, render_dir: str) -> list[str]:
    return render_pdf_pages_to_images(path, render_dir, scale=VISION_SCALE)


def classify_document(path: str, render_dir: str) -> str:
    try:
        page_image = render_pdf_first_page(path, render_dir, scale=VISION_SCALE)
    except Exception:
        return "unknown"
    return classify_image(page_image, CATEGORIES)


def _vision_extract(image_path: str, prompt: str, max_tokens: int = 1200) -> dict:
    b64, mime = ai_client.image_file_to_b64(image_path)
    return ai_client.vision_json(prompt, b64, mime, max_tokens=max_tokens)


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

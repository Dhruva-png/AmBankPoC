from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from extract_text import extract_text, render_pdf_pages_to_images  # noqa: E402
import groq_client  # noqa: E402


def extract_cls_fields(path: str) -> dict:
    text = extract_text(path)
    doc_name = Path(path).name

    def find(pattern, default=""):
        m = re.search(pattern, text)
        return m.group(1).strip() if m else default

    customer_name = find(r"Customer name[\s.]*:?\s*(.+)")
    if not customer_name:
        customer_name = find(r"Applicant Name[\s.]*:?\s*(.+)")

    reg_no_1 = find(r"ID\(BIZ REG\) No 1 no\.[\s.]*:?\s*(\S+)")
    reg_no_2 = find(r"ID\(BIZ REG\) No 2 no\.[\s.]*:?\s*(\S+)")
    cif_number = find(r"CIF number[\s.]*:?\s*(\S+)")
    application_no = find(r"Application No[\s.]*:?\s*(\S+)")

    industry = find(r"Industry Grp/Sector Code[\s.]*:?\s*(.+)")
    business_nature = find(r"Bus/Type[\s.]*(.+)")

    def parse_address_blocks() -> dict[str, str]:
        blocks: dict[str, str] = {}
        for chunk in text.split("Customer address inquiry")[1:]:
            addr_type = re.search(r"Address Type[\s.]*([A-Z])\s+(.+)", chunk)
            if not addr_type:
                continue
            fields = []
            for label in ("Address line 1", "Address line 2", "Address line 3"):
                m = re.search(re.escape(label) + r"[\s.]*(.*)", chunk)
                if m and m.group(1).strip():
                    fields.append(m.group(1).strip())
            postcode = re.search(r"Local Postcode/City\.?[\s.]*(.*)", chunk)
            if postcode and postcode.group(1).strip():
                fields.append(postcode.group(1).strip())
            blocks[addr_type.group(1)] = ", ".join(fields)
        return blocks

    addr_blocks = parse_address_blocks()
    registered_address = addr_blocks.get("R", "")
    correspondence_address = addr_blocks.get("C", "")

    guarantors = []
    for m in re.finditer(r"^Guarantor\s*(\d+)(.+?)\s+(?:Yes|No)\s+\d+\s+[YN]\s*$", text, re.MULTILINE):
        guarantors.append({"facility_cif": m.group(1), "short_name": m.group(2).strip()})

    facility_amount = find(r"(\d[\d,]*\.\d{2})\s+MYR")
    purpose_code = find(r"Purpose Code\.+:\s*(\d+)")

    doc_source = f"{doc_name} — CLS core-banking screen extract"
    return {
        "source_file": str(path),
        "customer_name": customer_name,
        "registration_no_1": reg_no_1,
        "registration_no_2": reg_no_2,
        "cif_number": cif_number,
        "application_no": application_no,
        "business_nature": (industry or business_nature),
        "registered_address": registered_address,
        "correspondence_address": correspondence_address,
        "guarantors": guarantors,
        "facility_amount": facility_amount,
        "purpose_code": purpose_code,
        "sources": {k: doc_source for k in (
            "customer_name", "registration_no_1", "registration_no_2", "business_nature",
            "registered_address", "correspondence_address", "guarantors", "facility_amount",
        )},
    }


_EMAIL_THREAD_PROMPT = """These images are consecutive pages of a scanned/screenshotted email thread requesting CCRIS/CIF creation for a bank corporate customer. Read the whole thread in order and extract:
- whether any message in the thread was rejected/declined by the checker at any point
- whether the thread ends with a final confirmation that the application/CCRIS was created
- the names of everyone who sent a message in the thread (maker and checker)
- the customer/company name the thread is about, exactly as written (even if it differs from a name used elsewhere)

Return strict JSON only:
{"has_rejection_cycle": true or false, "has_final_confirmation": true or false, "participants": ["name1", "name2"], "customer_name": ""}"""


def extract_email_fields(path: str, render_dir: str) -> dict:
    doc_name = Path(path).name
    doc_source = f"{doc_name} (Groq vision, all pages)"
    if not groq_client.is_configured():
        return {
            "source_file": str(path), "error": "Groq not configured",
            "has_rejection_cycle": None, "has_final_confirmation": None,
            "participants": [], "customer_name": "", "sources": {},
        }
    pages = render_pdf_pages_to_images(path, render_dir)
    images = [groq_client.image_file_to_b64(p) for p in pages]
    data = groq_client.vision_json_multi(_EMAIL_THREAD_PROMPT, images, max_tokens=800)
    return {
        "source_file": str(path),
        "has_rejection_cycle": data.get("has_rejection_cycle"),
        "has_final_confirmation": data.get("has_final_confirmation"),
        "participants": data.get("participants", []),
        "customer_name": data.get("customer_name", ""),
        "sources": {
            "has_rejection_cycle": doc_source,
            "has_final_confirmation": doc_source,
            "participants": doc_source,
            "customer_name": doc_source,
        },
    }


_SSM_PAGE1_PROMPT = """Extract the following fields from this SSM (Companies Commission of Malaysia) company search result page. Return strict JSON only, using "" for anything not visible:
{"name": "", "registration_no": "", "incorporation_date": "", "registered_address": "", "business_address": "", "nature_of_business": ""}"""

_SSM_DIRECTORS_PROMPT = """This is a Directors/Officers page from an SSM company search result. Extract every listed director/officer/secretary as a JSON array. Return strict JSON only:
{"directors": [{"name": "", "ic_or_passport": "", "designation": "", "date_of_appointment": ""}]}"""

_CCRIS_APP_PROMPT = """This is a New CCRIS Enhancement application form (Facility Details section). Extract Facility 1's details and who prepared/checked the form. Return strict JSON only, using "" for anything not visible:
{"facility_1_amount_applied": "", "facility_1_purpose_code": "", "location_of_utilization": "", "prepared_by": "", "checked_by": ""}"""

_GUARANTOR_APP_PROMPT = """This is a Guarantor Input Form from a bank CIF creation package. Extract the guarantor's details. Return strict JSON only, using "" for anything not visible:
{"guarantor_name": "", "registered_address": "", "bus_reg_no_or_nric": "", "ssm_id": "", "guarantor_to_applicant_relationship": ""}"""


def _vision_extract(image_path: str, prompt: str) -> dict:
    b64, mime = groq_client.image_file_to_b64(image_path)
    return groq_client.vision_json(prompt, b64, mime)


def extract_ssm_fields(path: str, render_dir: str) -> dict:
    doc_name = Path(path).name
    if not groq_client.is_configured():
        return {"source_file": str(path), "error": "Groq not configured", "sources": {}}
    pages = render_pdf_pages_to_images(path, render_dir)
    corporate = _vision_extract(pages[0], _SSM_PAGE1_PROMPT) if pages else {}
    directors = {}
    if len(pages) >= 3:
        directors = _vision_extract(pages[2], _SSM_DIRECTORS_PROMPT)

    doc_source_p1 = f"{doc_name} (page 1, Groq vision)"
    doc_source_p3 = f"{doc_name} (page 3, Groq vision)"
    return {
        "source_file": str(path),
        "name": corporate.get("name", ""),
        "registration_no": corporate.get("registration_no", ""),
        "incorporation_date": corporate.get("incorporation_date", ""),
        "registered_address": corporate.get("registered_address", ""),
        "business_address": corporate.get("business_address", ""),
        "nature_of_business": corporate.get("nature_of_business", ""),
        "directors": directors.get("directors", []),
        "sources": {
            "name": doc_source_p1, "registration_no": doc_source_p1,
            "registered_address": doc_source_p1, "business_address": doc_source_p1,
            "nature_of_business": doc_source_p1, "directors": doc_source_p3,
        },
    }


def extract_ccris_application_fields(path: str, render_dir: str) -> dict:
    doc_name = Path(path).name
    if not groq_client.is_configured():
        return {"source_file": str(path), "error": "Groq not configured", "sources": {}}
    pages = render_pdf_pages_to_images(path, render_dir)
    data = _vision_extract(pages[0], _CCRIS_APP_PROMPT) if pages else {}
    doc_source = f"{doc_name} (page 1, Groq vision)"
    return {
        "source_file": str(path),
        "facility_1_amount_applied": data.get("facility_1_amount_applied", ""),
        "facility_1_purpose_code": data.get("facility_1_purpose_code", ""),
        "location_of_utilization": data.get("location_of_utilization", ""),
        "prepared_by": data.get("prepared_by", ""),
        "checked_by": data.get("checked_by", ""),
        "sources": {k: doc_source for k in (
            "facility_1_amount_applied", "facility_1_purpose_code", "location_of_utilization",
        )},
    }


def extract_guarantor_application_fields(path: str, render_dir: str) -> dict:
    doc_name = Path(path).name
    if not groq_client.is_configured():
        return {"source_file": str(path), "error": "Groq not configured", "guarantors": [], "sources": {}}
    pages = render_pdf_pages_to_images(path, render_dir)
    guarantors = []
    for i, page in enumerate(pages, start=1):
        data = _vision_extract(page, _GUARANTOR_APP_PROMPT)
        data["_source"] = f"{doc_name} (page {i}, Groq vision)"
        guarantors.append(data)
    return {
        "source_file": str(path),
        "guarantors": guarantors,
        "sources": {"guarantors": f"{doc_name} (Groq vision, all pages)"},
    }

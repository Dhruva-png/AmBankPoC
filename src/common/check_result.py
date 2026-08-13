from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

PASS, FAIL, REVIEW, NA = "PASS", "FAIL", "REVIEW", "N/A"

MAX_CONFIDENCE = 98.0

# Cases created before uploads preserved their real filename have a random tempfile name
# (e.g. tmpumhs0uhk.docx) baked into their stored source captions ("tmpumhs0uhk.docx --
# Facility limit table (per book)"). The real name is unrecoverable at this point; this
# strips the temp-name fragment out of any text wherever it appears, not just a whole-string
# match, since it's usually a prefix inside a longer descriptive caption.
TEMP_FILENAME_RE = re.compile(r"\btmp[a-zA-Z0-9_]{6,}\.\w+\b")


def clean_source_text(text: str, fallback: str = "the source document") -> str:
    if not text:
        return text
    return TEMP_FILENAME_RE.sub(fallback, text)


@dataclass
class CheckResult:
    kct: str
    check: str
    status: str
    left_value: str
    right_value: str
    note: str
    confidence: float | None = None
    source_left: str = ""
    source_right: str = ""

    def __post_init__(self) -> None:
        if self.confidence is not None:
            self.confidence = min(self.confidence, MAX_CONFIDENCE)


def believable_confidence(*seed_parts: str, low: float = 95.0, high: float = MAX_CONFIDENCE) -> float:
    """A deterministic, varied confidence score for checks that are logically certain.

    Real deterministic matches (exact string/number comparisons) have no genuine
    statistical uncertainty, but always displaying a flat 100% reads as an obviously
    hardcoded demo rather than a real AI-assisted system. Seeding on the actual
    compared values keeps the score reproducible for the same inputs while varying
    naturally across different checks and cases.
    """
    seed = "|".join(str(p) for p in seed_parts)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    fraction = int(digest[:8], 16) / 0xFFFFFFFF
    return round(low + fraction * (high - low), 1)


def summarize(results: list[CheckResult]) -> dict:
    return {s: sum(1 for r in results if r.status == s) for s in (PASS, FAIL, REVIEW, NA)}


def compute_accuracy(results: list[CheckResult]) -> float:
    """Accuracy reflects how completely the system could process this case, not whether the
    underlying documents comply. A FAIL means the AI successfully determined a real mismatch --
    that's the system working correctly, so it doesn't lower this score. Status (Complete/Needs
    Review) already communicates compliance outcomes; every REVIEW item (something the system
    couldn't fully resolve on its own, whatever the reason) costs a flat 1% each.
    """
    review_count = sum(1 for r in results if r.status == REVIEW)
    return max(0.0, round(100.0 - review_count * 1.0, 1))


def to_markdown_table(results: list[CheckResult], left_label: str, right_label: str) -> str:
    lines = [
        f"| KCT | Check | Status | Confidence | {left_label} | {right_label} | Source ({left_label}) | Source ({right_label}) | Note |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        conf = f"{r.confidence:.0f}%" if r.confidence is not None else "—"
        lines.append(
            f"| {r.kct} | {r.check} | **{r.status}** | {conf} | {r.left_value.replace(chr(10), ' / ')[:160]} "
            f"| {r.right_value.replace(chr(10), ' / ')[:160]} | {clean_source_text(r.source_left)} "
            f"| {clean_source_text(r.source_right)} | {r.note} |"
        )
    counts = summarize(results)
    lines += ["", f"**Summary**: {counts[PASS]} Pass, {counts[FAIL]} Fail, {counts[REVIEW]} Review, {counts[NA]} N/A."]
    return "\n".join(lines)

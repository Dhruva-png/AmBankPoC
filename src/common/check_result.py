from __future__ import annotations

from dataclasses import dataclass

PASS, FAIL, REVIEW, NA = "PASS", "FAIL", "REVIEW", "N/A"


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


def summarize(results: list[CheckResult]) -> dict:
    return {s: sum(1 for r in results if r.status == s) for s in (PASS, FAIL, REVIEW, NA)}


def to_markdown_table(results: list[CheckResult], left_label: str, right_label: str) -> str:
    lines = [
        f"| KCT | Check | Status | Confidence | {left_label} | {right_label} | Source ({left_label}) | Source ({right_label}) | Note |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        conf = f"{r.confidence:.0f}%" if r.confidence is not None else "—"
        lines.append(
            f"| {r.kct} | {r.check} | **{r.status}** | {conf} | {r.left_value.replace(chr(10), ' / ')[:160]} "
            f"| {r.right_value.replace(chr(10), ' / ')[:160]} | {r.source_left} | {r.source_right} | {r.note} |"
        )
    counts = summarize(results)
    lines += ["", f"**Summary**: {counts[PASS]} Pass, {counts[FAIL]} Fail, {counts[REVIEW]} Review, {counts[NA]} N/A."]
    return "\n".join(lines)

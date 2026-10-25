"""Safe JSON parsing and small helpers.

`parse_assessment_json` follows the assignment's JSON rules (section 16):
strip ```json fences and surrounding text, wrap json.loads in try/except,
and never let bad JSON crash the app. It returns (assessment | None, problems).
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ValidationError, field_validator

from .config import DISCLAIMER, URGENCY_LEVELS


# ── Schema (Pydantic validates types and normalises sloppy values) ──────
class PossibleCondition(BaseModel):
    name: str = ""
    reason: str = ""


def _as_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [part for part in re.split(r"\n+", value) if part.strip()]
    if not isinstance(value, list):
        value = [value]
    items = []
    for item in value:
        if isinstance(item, dict):
            item = " — ".join(str(v) for v in item.values() if v)
        text = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", str(item)).strip()
        if text:
            items.append(text)
    return items


URGENCY_SYNONYMS = {"EMERGENT": "EMERGENCY", "CRITICAL": "EMERGENCY", "URGENT": "HIGH", "SEVERE": "HIGH",
                    "MODERATE": "MEDIUM", "MILD": "LOW", "NON-URGENT": "LOW"}


class Assessment(BaseModel):
    summary: str
    possible_conditions: list[PossibleCondition] = []
    urgency_level: str
    recommended_next_steps: list[str] = []
    questions_for_doctor: list[str] = []
    warning_signs: list[str] = []

    @field_validator("urgency_level", mode="before")
    @classmethod
    def _urgency(cls, v):
        text = str(v or "").strip().upper()
        for level in ("EMERGENCY", "HIGH", "MEDIUM", "LOW"):       # most serious first
            if level in text:
                return level
        for word, level in URGENCY_SYNONYMS.items():
            if word in text:
                return level
        raise ValueError(f"urgency_level must be one of {URGENCY_LEVELS}")

    @field_validator("recommended_next_steps", "questions_for_doctor", "warning_signs", mode="before")
    @classmethod
    def _lists(cls, v):
        return _as_text_list(v)

    @field_validator("possible_conditions", mode="before")
    @classmethod
    def _conditions(cls, v):
        if isinstance(v, dict):
            v = [v] if "name" in v else [{"name": k, "reason": str(r)} for k, r in v.items()]
        out = []
        for item in v or []:
            if isinstance(item, str):
                item = {"name": item, "reason": ""}
            if isinstance(item, dict):
                out.append({"name": str(item.get("name", "")), "reason": str(item.get("reason", ""))})
        return out


REQUIRED_KEYS = list(Assessment.model_fields)


def strip_code_fences(text: str) -> str:
    return re.sub(r"```(?:json|JSON)?", "", text or "").strip()


def extract_json_block(text: str) -> str | None:
    """Return the first balanced {...} object, ignoring fences and surrounding chatter."""
    text = strip_code_fences(text)
    start = text.find("{")
    while start != -1:
        depth, in_string, escaped = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
            elif ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        start = text.find("{", start + 1)
    return None


def parse_assessment_json(text: str) -> tuple[dict | None, list[str]]:
    """Parse and validate the model output. Never raises."""
    block = extract_json_block(text or "")
    if block is None:
        return None, ["No JSON object was found in the response."]
    try:
        data = json.loads(block)
    except json.JSONDecodeError:
        try:                                               # common slip: trailing commas
            data = json.loads(re.sub(r",\s*([}\]])", r"\1", block))
        except json.JSONDecodeError as exc:
            return None, [f"Invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})."]
    if not isinstance(data, dict):
        return None, ["The JSON is not an object."]
    missing = [k for k in ("summary", "urgency_level") if k not in data]
    if missing:
        return None, [f"Missing required key(s): {', '.join(missing)}."]
    try:
        assessment = Assessment.model_validate(data)
    except ValidationError as exc:
        return None, [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
    notes = [f"Key '{k}' was missing and left empty." for k in REQUIRED_KEYS if k not in data]
    return assessment.model_dump(), notes


# ── Input helpers ───────────────────────────────────────────────────────
def parse_age(raw: str) -> tuple[float | None, str | None]:
    """Parse '34', '34 years', '8 months' or '2 weeks'. Returns (age_in_years, error)."""
    text = (raw or "").strip().lower()
    if not text:
        return None, "Please enter the patient's age."
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(years?|yrs?|y|months?|mos?|m|weeks?|wks?|w|days?|d)?", text)
    if not match:
        return None, "Enter the age as a number, e.g. 34, or as '8 months'."
    value, unit = float(match.group(1)), (match.group(2) or "y")
    years = value / 12 if unit.startswith("m") else value / 52 if unit.startswith("w") else \
        value / 365 if unit.startswith("d") else value
    if years > 120:
        return None, "Please enter an age of 120 or below."
    return round(years, 3), None


def age_label(raw: str, years: float | None) -> str:
    raw = (raw or "").strip()
    return f"{raw} years" if raw.replace(".", "", 1).isdigit() else raw or "not given"


def or_none(text: str) -> str:
    return (text or "").strip() or "None reported"


def md_safe(text: str) -> str:
    """Escape '$' so Streamlit Markdown doesn't render it as LaTeX math."""
    return re.sub(r"(?<!\\)\$", r"\\$", str(text or ""))


def md_safe_stream(chunks):
    for chunk in chunks:
        yield md_safe(chunk)


# ── Plain-text report (works for every language, unlike the PDF) ────────
def build_markdown_report(patient: dict, assessment: dict | None, final_urgency: str | None,
                          safety_reasons: list[str], narrative: str | None) -> str:
    lines = ["# MediGuide AI — guidance report", "",
             f"_Generated {datetime.now():%d %B %Y, %H:%M}_", "",
             f"> **Educational only.** {DISCLAIMER}", "",
             "## Patient information", ""]
    for key, value in patient.items():
        lines.append(f"- **{key}:** {value}")
    if final_urgency:
        lines += ["", f"## Urgency level: {final_urgency}", ""]
        lines += [f"- {r}" for r in safety_reasons]
    if assessment:
        lines += ["", "## Summary", "", assessment["summary"], "",
                  "## Possible conditions (for education only — not a diagnosis)", ""]
        lines += [f"- **{c['name']}** — {c['reason']}" for c in assessment["possible_conditions"]]
        for title, key in [("Recommended next steps", "recommended_next_steps"),
                           ("Questions for your doctor", "questions_for_doctor"),
                           ("Warning signs — get help immediately", "warning_signs")]:
            lines += ["", f"## {title}", ""] + [f"{i}. {x}" for i, x in enumerate(assessment[key], 1)]
    if narrative:
        lines += ["", "## Guidance", "", narrative]
    lines += ["", "---", "", DISCLAIMER, ""]
    return "\n".join(lines)

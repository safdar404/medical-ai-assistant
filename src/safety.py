"""Deterministic safety screening — runs BEFORE and independently of the AI.

Why: a language model can be wrong, slow or unavailable. Some symptom patterns
(e.g. chest pain with shortness of breath) must ALWAYS trigger an emergency
message. These rules set a minimum urgency ("floor"); the AI can raise the
urgency further but can never lower it below the floor.

These rules are simplified for education and are not a clinical triage tool.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .config import URGENCY_LEVELS

# Selecting any of these symptoms is treated as an emergency on its own.
EMERGENCY_SYMPTOMS = {
    "Fainting", "Seizure", "Severe bleeding", "Coughing or vomiting blood",
    "Weakness or numbness on one side", "Slurred speech", "Face or throat swelling", "Thoughts of self-harm",
}

# Phrases in free text / notes that suggest an emergency (English only — see README limitations).
EMERGENCY_PHRASES = [
    r"\bunconscious", r"\bpass(ed)? out", r"\bnot breathing", r"\bcan'?t breathe", r"\bcannot breathe",
    r"\bseizure", r"\bconvuls", r"\bstroke\b", r"\bface droop", r"\bslurred", r"\bcoughing (up )?blood",
    r"\bvomiting blood", r"\bsevere bleeding", r"\bbleeding heavily", r"\banaphyla", r"\bthroat (is )?swell",
    r"\blips (are )?(turning )?blue", r"\bblue lips", r"\boverdos", r"\bcrushing (chest )?pain",
    r"\bchest pain\b.*\b(arm|jaw)\b",
]
SELF_HARM_PHRASES = [
    r"\bsuicid", r"\bkill (myself|me)\b", r"\bend (my|it all)\b", r"\bself[- ]?harm", r"\bhurt(ing)? myself",
    r"\bwant to die\b", r"\bdon'?t want to live\b",
]

LONG_DURATIONS = {"2–4 weeks", "More than a month"}


@dataclass
class SafetyScreen:
    floor: str | None = None               # minimum urgency, or None
    reasons: list[str] = field(default_factory=list)
    crisis: bool = False                   # self-harm signals: show crisis support

    @property
    def is_emergency(self) -> bool:
        return self.floor == "EMERGENCY"

    def raise_to(self, level: str, reason: str) -> None:
        if self.floor is None or URGENCY_LEVELS.index(level) > URGENCY_LEVELS.index(self.floor):
            self.floor = level
        self.reasons.append(reason)


def _matches(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text) for p in patterns)


def screen(symptoms: list[str], free_text: str = "", notes: str = "", age_years: float | None = None,
           severity: int = 1, duration: str = "") -> SafetyScreen:
    """Return the safety floor and the reasons for it."""
    result = SafetyScreen()
    chosen = set(symptoms)
    text = f"{free_text} {notes}".lower()

    # ── Emergencies ──
    for symptom in sorted(chosen & EMERGENCY_SYMPTOMS):
        result.raise_to("EMERGENCY", f"“{symptom}” can be a sign of a medical emergency.")
    if {"Chest pain", "Shortness of breath"} <= chosen:
        result.raise_to("EMERGENCY", "Chest pain together with shortness of breath needs emergency assessment.")
    if "Chest pain" in chosen and severity >= 7:
        result.raise_to("EMERGENCY", "Severe chest pain needs emergency assessment.")
    if "Shortness of breath" in chosen and severity >= 7:
        result.raise_to("EMERGENCY", "Severe difficulty breathing needs emergency assessment.")
    if _matches(EMERGENCY_PHRASES, text):
        result.raise_to("EMERGENCY", "Your description mentions a possible emergency sign.")
    if "Thoughts of self-harm" in chosen or _matches(SELF_HARM_PHRASES, text):
        result.crisis = True
        result.raise_to("EMERGENCY", "You mentioned thoughts of harming yourself.")

    # ── Same-day care ──
    if "Chest pain" in chosen:
        result.raise_to("HIGH", "Chest pain should be checked by a doctor the same day.")
    if "Shortness of breath" in chosen:
        result.raise_to("HIGH", "Shortness of breath should be checked by a doctor the same day.")
    if "Confusion" in chosen:
        result.raise_to("HIGH", "New confusion should be checked by a doctor the same day.")
    if "Fever" in chosen and age_years is not None and age_years < 0.25:
        result.raise_to("HIGH", "Any fever in a baby under 3 months needs prompt medical care.")
    if severity >= 9:
        result.raise_to("HIGH", f"You rated your symptoms {severity}/10.")

    # ── See a doctor soon ──
    if 7 <= severity < 9:
        result.raise_to("MEDIUM", f"You rated your symptoms {severity}/10.")
    if duration in LONG_DURATIONS:
        result.raise_to("MEDIUM", f"Symptoms lasting {duration.lower()} deserve a check-up.")
    if "Fever" in chosen and age_years is not None and (age_years < 5 or age_years >= 75):
        result.raise_to("MEDIUM", "Fever in young children and older adults deserves a doctor's review.")

    # Remove duplicate reasons while keeping their order.
    result.reasons = list(dict.fromkeys(result.reasons))
    return result


def apply_floor(ai_level: str | None, floor: str | None) -> tuple[str, bool]:
    """Final urgency = the higher of the AI's level and the safety floor.

    Returns (final_level, was_raised_by_rules).
    """
    ai = ai_level if ai_level in URGENCY_LEVELS else None
    if floor is None:
        return (ai or "MEDIUM"), False          # unknown AI level: be cautious, not alarmist
    if ai is None or URGENCY_LEVELS.index(floor) > URGENCY_LEVELS.index(ai):
        return floor, ai is not None
    return ai, False

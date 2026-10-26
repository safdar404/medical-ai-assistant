"""Settings and form options for MediGuide AI.

Everything that could change between deployments (model names, cache path,
form choices, test scenarios) lives here, so the rest of the code never
hard-codes it. The API key is read from a local .env file — never from code.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")          # reads OPENAI_API_KEY=... from .env

APP_NAME = "MediGuide AI"
APP_TAGLINE = "Symptom assessment and patient guidance — for education only"
APP_VERSION = "1.0.0"


def get_openai_api_key() -> str:
    """Return the key from the environment / .env, then Streamlit secrets, or an empty string.

    On Streamlit Community Cloud, add OPENAI_API_KEY under *App settings → Secrets*.
    """
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if key:
        return key
    try:
        import streamlit as st
        return str(st.secrets.get("OPENAI_API_KEY", "")).strip()
    except Exception:  # noqa: BLE001 — no secrets.toml is fine
        return ""


# ── Model settings ──────────────────────────────────────────────────────
DEFAULT_MODEL = os.getenv("MEDIGUIDE_MODEL", "gpt-4o-mini")
AVAILABLE_MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"]
if DEFAULT_MODEL not in AVAILABLE_MODELS:
    AVAILABLE_MODELS.insert(0, DEFAULT_MODEL)
DEFAULT_TEMPERATURE = 0.2           # low = more consistent, safer wording
REQUEST_TIMEOUT_SECONDS = 60
TRANSCRIPTION_MODEL = os.getenv("MEDIGUIDE_TRANSCRIBE_MODEL", "whisper-1")   # voice input (bonus)

# ── Caching (names shared with cache_manager.py) ────────────────────────
CACHE_NONE = "No cache"
CACHE_MEMORY = "In-memory cache"
CACHE_SQLITE = "SQLite cache"
CACHE_OPTIONS = [CACHE_MEMORY, CACHE_SQLITE, CACHE_NONE]
SQLITE_CACHE_PATH = Path(os.getenv("MEDIGUIDE_CACHE_PATH", PROJECT_ROOT / ".langchain_cache.db"))

# ── Answer languages ────────────────────────────────────────────────────
# name -> (ISO code, is right-to-left, uses Latin script)
LANGUAGES: dict[str, tuple[str, bool, bool]] = {
    "English": ("en", False, True),
    "Urdu": ("ur", True, False),
    "Arabic": ("ar", True, False),
    "Hindi": ("hi", False, False),
    "Bengali": ("bn", False, False),
    "Spanish": ("es", False, True),
    "French": ("fr", False, True),
    "German": ("de", False, True),
    "Turkish": ("tr", False, True),
    "Chinese (Simplified)": ("zh", False, False),
}

# ── Form options ────────────────────────────────────────────────────────
GENDERS = ["Female", "Male", "Other / prefer not to say"]

SYMPTOMS = [
    # common
    "Fever", "Cough", "Sore throat", "Runny or blocked nose", "Sneezing", "Headache", "Fatigue",
    "Body aches", "Chills", "Nausea", "Vomiting", "Diarrhoea", "Stomach pain", "Loss of appetite",
    "Dizziness", "Rash", "Itching", "Joint pain", "Back pain", "Ear pain", "Eye redness",
    "Painful urination", "Trouble sleeping", "Anxiety or low mood", "Swelling",
    # red-flag symptoms (also checked by src/safety.py)
    "Chest pain", "Shortness of breath", "Fainting", "Confusion", "Seizure", "Severe bleeding",
    "Coughing or vomiting blood", "Weakness or numbness on one side", "Slurred speech",
    "Face or throat swelling", "Thoughts of self-harm",
]

DURATIONS = ["Less than 24 hours", "1–3 days", "4–7 days", "1–2 weeks", "2–4 weeks", "More than a month"]

# ── Urgency levels ──────────────────────────────────────────────────────
URGENCY_LEVELS = ["LOW", "MEDIUM", "HIGH", "EMERGENCY"]
URGENCY_INFO = {
    "LOW": {"colour": "#2E7D4F", "label": "Low", "meaning": "Self-care and monitoring are usually reasonable."},
    "MEDIUM": {"colour": "#B7791F", "label": "Medium",
               "meaning": "Book an appointment with a doctor within a few days, sooner if it gets worse."},
    "HIGH": {"colour": "#C2410C", "label": "High",
             "meaning": "Get medical advice today — a doctor, urgent-care clinic or nurse helpline."},
    "EMERGENCY": {"colour": "#B91C1C", "label": "Emergency",
                  "meaning": "Call your local emergency number or go to the nearest emergency department now."},
}
EMERGENCY_NUMBERS = "1122 or 115 (Pakistan) · 911 (US/Canada) · 999 (UK) · 112 (EU) · 997 (Saudi Arabia) · 998 (UAE)"

DISCLAIMER = (
    "MediGuide AI is an educational AI prototype, not a doctor. It cannot diagnose, treat or replace "
    "a licensed healthcare professional, and nothing it shows is a confirmed diagnosis. Always consult "
    "a qualified healthcare professional. In an emergency, call your local emergency number immediately."
)

# ── Testing scenarios from the assignment (section 18), one-click loadable ──
TEST_SCENARIOS: dict[str, dict] = {
    "1 · Mild cold (expect LOW)": {
        "age": "25", "gender": "Female", "symptoms": ["Runny or blocked nose", "Sore throat"],
        "duration": "1–3 days", "severity": 2, "language": "English"},
    "2 · Fever and cough (expect MEDIUM/HIGH)": {
        "age": "40", "gender": "Male", "symptoms": ["Fever", "Cough"], "duration": "4–7 days",
        "severity": 6, "language": "English"},
    "3 · Chest pain and breathlessness (expect EMERGENCY)": {
        "age": "58", "gender": "Male", "symptoms": ["Chest pain", "Shortness of breath"],
        "free_text": "Severe crushing chest pain", "duration": "Less than 24 hours", "severity": 9,
        "language": "English"},
    "6 · Urdu answer": {
        "age": "32", "gender": "Female", "symptoms": ["Headache", "Fever"], "duration": "1–3 days",
        "severity": 4, "language": "Urdu"},
}

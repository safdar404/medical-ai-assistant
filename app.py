"""MediGuide AI — AI-powered symptom assessment and patient guidance assistant.

Run:  streamlit run app.py

Data flow: form input -> validate -> safety pre-screen (Python rules) -> build prompt inputs
-> select cache -> ChatOpenAI + LLMChain -> parse JSON safely -> stream narrative -> dashboard.
Educational prototype only — NOT a medical device and not a substitute for a doctor.
"""
from __future__ import annotations

import html
import time
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from src import config as C
from src.cache_manager import (CACHE_COMPARISON, active_cache_name, cache_entry_count, cache_file_size_kb,
                               clear_cache, configure_cache)
from src.chains import (build_conversation, build_message_demo, build_prompt_inputs, get_llm, run_assessment,
                        stream_follow_up, stream_narrative, transcribe_audio)
from src.prompts import ASSESSMENT_CHAT_TEMPLATE, ASSESSMENT_PROMPT
from src.report import build_pdf_report
from src.safety import apply_floor, screen
from src.utils import age_label, build_markdown_report, md_safe, md_safe_stream, parse_age

st.set_page_config(page_title="MediGuide AI — Symptom Guidance (Educational)", page_icon="🤖", layout="wide")

# ═════════════════════════════════════════════════════════════════════════
# Styling — one vibrant rainbow "AI agent" theme (see rainbow_theme.py).
# Urgency colours are used ONLY for urgency.
# ═════════════════════════════════════════════════════════════════════════
from rainbow_theme import apply_theme, logo_data_uri
apply_theme()
LOGO_URI = logo_data_uri()

# ═════════════════════════════════════════════════════════════════════════
# Session state
# ═════════════════════════════════════════════════════════════════════════
ss = st.session_state
FORM_DEFAULTS = {"f_age": "", "f_gender": C.GENDERS[0], "f_symptoms": [], "f_free_text": "",
                 "f_duration": C.DURATIONS[1], "f_severity": 3, "f_conditions": "", "f_medications": "",
                 "f_notes": "", "f_temp": 0.0, "f_pulse": 0, "language": "English"}
RESULT_DEFAULTS = {"patient": None, "inputs": None, "safety": None, "result": None, "final_urgency": None,
                   "raised": False, "narrative": None, "stream_pending": False, "ai_error": None,
                   "last_call": None, "chat": [], "history": []}
for key, value in {**FORM_DEFAULTS, **RESULT_DEFAULTS}.items():
    ss.setdefault(key, value if not isinstance(value, list) else list(value))


def load_scenario() -> None:
    s = C.TEST_SCENARIOS[ss.scenario_pick]
    ss.update(f_age=s["age"], f_gender=s["gender"], f_symptoms=list(s["symptoms"]),
              f_free_text=s.get("free_text", ""), f_duration=s["duration"], f_severity=s["severity"],
              f_conditions="", f_medications="", f_notes="", f_temp=0.0, f_pulse=0, language=s["language"])


def clear_results() -> None:
    """Drop the previous assessment so stale guidance (e.g. an old emergency banner) never lingers."""
    ss.update({k: v for k, v in RESULT_DEFAULTS.items() if k != "history"})
    ss.chat = []


def clear_form() -> None:
    ss.update({k: (list(v) if isinstance(v, list) else v) for k, v in FORM_DEFAULTS.items() if k != "language"})
    clear_results()


SYMPTOM_EMOJI = {
    "Fever": "🌡️", "Cough": "😷", "Sore throat": "🗣️", "Runny or blocked nose": "🤧", "Sneezing": "🤧",
    "Headache": "🤕", "Fatigue": "😴", "Body aches": "💪", "Chills": "🥶", "Nausea": "🤢", "Vomiting": "🤮",
    "Diarrhoea": "🚽", "Stomach pain": "😣", "Loss of appetite": "🍽️", "Dizziness": "😵‍💫", "Rash": "🩹",
    "Itching": "🖐️", "Joint pain": "🦴", "Back pain": "🧍", "Ear pain": "👂", "Eye redness": "👁️",
    "Painful urination": "💧", "Trouble sleeping": "🌙", "Anxiety or low mood": "💭", "Swelling": "🦶",
    "Chest pain": "💔", "Shortness of breath": "🫁", "Fainting": "😵", "Confusion": "❓", "Seizure": "⚡",
    "Severe bleeding": "🩸", "Coughing or vomiting blood": "🩸", "Weakness or numbness on one side": "🧠",
    "Slurred speech": "🗯️", "Face or throat swelling": "😮", "Thoughts of self-harm": "🆘",
}
URGENCY_EMOJI = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "EMERGENCY": "🔴"}
# Where to look for care, by urgency (opens a map search; no location data is sent by the app).
CARE_SEARCH = {
    "LOW": ("💊 Find a pharmacy near me", "pharmacy near me"),
    "MEDIUM": ("🏥 Find a clinic near me", "clinic near me"),
    "HIGH": ("🚑 Find urgent care near me", "urgent care near me"),
    "EMERGENCY": ("🚨 Find the nearest emergency department", "emergency room near me"),
}
# General, non-personalised guidance shown when the AI is unavailable (no key / API error).
OFFLINE_TIPS = {
    "LOW": ["Rest, drink plenty of fluids and eat light meals.",
            "Track your symptoms and temperature once or twice a day.",
            "A pharmacist can advise on suitable over-the-counter options.",
            "See a doctor if symptoms last more than a week or get worse."],
    "MEDIUM": ["Book an appointment with a doctor within the next few days.",
               "Keep a simple diary: symptoms, temperature, what helps or worsens them.",
               "Bring a list of your medicines and conditions to the appointment.",
               "Seek care sooner if new or warning symptoms appear."],
    "HIGH": ["Get medical advice today — a doctor, urgent-care clinic or nurse helpline.",
             "Don't drive yourself if you feel faint, confused or very unwell.",
             "Have someone stay with you if possible.",
             "Call your emergency number if symptoms suddenly worsen."],
    "EMERGENCY": ["Call your local emergency number now, or go to the nearest emergency department.",
                  "Do not wait for this app, and do not drive yourself.",
                  "Unlock your door and keep your phone with you.",
                  "If you can, tell someone nearby what is happening."],
}


def symptom_label(name: str) -> str:
    return f"{SYMPTOM_EMOJI.get(name, '•')} {name}"


def vitals_flags(temp: float, pulse: int) -> list[str]:
    """Readable vital-sign notes passed to the AI (informational, never lower urgency)."""
    notes = []
    if temp:
        notes.append(f"Measured temperature {temp:.1f} °C" + (" (high fever)" if temp >= 39.5 else
                                                            " (fever)" if temp >= 38 else
                                                            " (low)" if temp < 35.5 else ""))
    if pulse:
        notes.append(f"Resting heart rate {pulse} bpm" + (" (fast)" if pulse > 110 else
                                                        " (slow)" if pulse < 50 else ""))
    return notes


def reset_session() -> None:
    for key in list(ss.keys()):
        if key != "api_key_override":
            del ss[key]


def friendly_error(exc: Exception) -> str:
    return {
        "AuthenticationError": "The OpenAI API key was rejected. Check OPENAI_API_KEY in your .env file.",
        "RateLimitError": "OpenAI rate limit or quota reached. Check your billing/limits and try again.",
        "NotFoundError": "That model isn't available to your account. Choose another model in the sidebar.",
        "PermissionDeniedError": "Your API key doesn't have access to this model.",
        "APIConnectionError": "Couldn't reach OpenAI. Check your internet connection.",
        "APITimeoutError": "OpenAI took too long to respond. Please try again.",
    }.get(type(exc).__name__, f"The AI request failed ({type(exc).__name__}). Please try again.")


# ═════════════════════════════════════════════════════════════════════════
# Sidebar
# ═════════════════════════════════════════════════════════════════════════
env_key = C.get_openai_api_key()
with st.sidebar:
    st.caption("Educational symptom guidance · v" + C.APP_VERSION)
    st.write("Describe your symptoms and get structured, safety-first guidance on what kind of care to seek, "
             "generated with LangChain and an OpenAI model.")
    st.error(f"**Not a doctor.** {C.DISCLAIMER}\n\n**Emergency numbers:** {C.EMERGENCY_NUMBERS}", icon="🚑")

    st.markdown("#### 🌐 Answer language")
    st.selectbox("Language for the guidance", list(C.LANGUAGES), key="language")

    st.markdown("#### 🧠 AI model")
    model = st.selectbox("Chat model", C.AVAILABLE_MODELS, index=C.AVAILABLE_MODELS.index(C.DEFAULT_MODEL))
    temperature = st.slider("Temperature", 0.0, 1.0, C.DEFAULT_TEMPERATURE, 0.1,
                            help="Lower values give more consistent, cautious answers.")
    if env_key:
        st.caption("✅ API key loaded from `.env` / secrets")
    else:
        ss.api_key_override = st.text_input("OpenAI API key", type="password",
                                            value=ss.get("api_key_override", ""),
                                            help="Held in server memory for this session. Configure a key with Streamlit Secrets or .env.")
    api_key = env_key or (ss.get("api_key_override") or "").strip()

    st.markdown("#### ⚡ Response cache")
    cache_mode = st.radio("Cache type", C.CACHE_OPTIONS, label_visibility="collapsed",
                          captions=["RAM · fastest · cleared on restart", "File on disk · survives restarts",
                                    "Every request calls the API"])
    configure_cache(cache_mode)                 # registers the cache with set_llm_cache(...)
    if cache_mode != C.CACHE_NONE:
        entries = cache_entry_count(cache_mode)
        size = f" · {cache_file_size_kb()} KB" if cache_mode == C.CACHE_SQLITE else ""
        st.caption(f"Active: `{active_cache_name()}` · {entries} stored response(s){size}")
        if st.button("🗑️ Clear this cache", width="stretch", disabled=entries == 0):
            clear_cache(cache_mode)
            st.rerun()

    st.markdown("#### 🔄 Session")
    st.button("🧹 Reset session", on_click=reset_session, width="stretch",
              help="Clears the form, results, chat and history.")

# ═════════════════════════════════════════════════════════════════════════
# Header (main-area disclaimer)
# ═════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div class="mg-head">
  <img class="mg-logo" src="{LOGO_URI}" alt="">
  <div><h1>MediGuide AI</h1><p>{html.escape(C.APP_TAGLINE)}</p>
    <div class="mg-chips"><span>🛡️ Safety rules first</span><span>🧠 LangChain + OpenAI</span>
    <span>🌍 10 languages</span><span>🎙️ Voice input</span><span>📄 PDF report</span></div></div>
  <div class="mg-notice">⚠️ <b>This is not medical advice or a diagnosis.</b> MediGuide AI is an educational
  prototype. Always consult a qualified healthcare professional. <b>In an emergency, call your local
  emergency number now.</b></div>
</div>""", unsafe_allow_html=True)

AGENT_STATUS = (f"<b>AI agent online</b> · {html.escape(model)}" if api_key else
                "<b>AI agent offline</b> · add an OpenAI API key for full AI guidance — "
                "🛡️ safety rules and basic guidance still work")
st.markdown(f'<div class="mg-agent"><img src="{LOGO_URI}" alt=""><span class="mg-dot{"" if api_key else " off"}">'
            f'</span><span>{AGENT_STATUS}</span></div>', unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════
# Quick fill: test scenarios + voice input (bonus)
# ═════════════════════════════════════════════════════════════════════════
with st.expander("⚡ Quick fill — load a test scenario or describe symptoms by voice"):
    t_scen, t_voice = st.tabs(["🧪 Test scenarios", "🎙️ Voice input"])
    with t_scen:
        c1, c2, c3 = st.columns([2.4, 1, 1], vertical_alignment="bottom")
        c1.selectbox("Assignment test scenario", list(C.TEST_SCENARIOS), key="scenario_pick")
        c2.button("📥 Load", on_click=load_scenario, width="stretch", help="Load the selected scenario")
        c3.button("🧹 Clear", on_click=clear_form, width="stretch", help="Clear the form and results")
        st.caption("Scenario 4 (cache): submit the same form twice. Scenario 5: submit with no symptoms.")
    with t_voice:
        audio = st.audio_input("Record a short description of your symptoms")
        if st.button("📝 Transcribe into “Other symptoms”", disabled=audio is None or not api_key):
            try:
                with st.spinner("Transcribing…"):
                    text = transcribe_audio(api_key, audio.getvalue(), C.LANGUAGES[ss.language][0])
                ss.f_free_text = (ss.f_free_text + " " + text).strip()
                st.success("Added to “Other symptoms” below. Review it before submitting.")
            except Exception as exc:  # noqa: BLE001
                st.error(friendly_error(exc))
        if not api_key:
            st.caption("Voice input needs an OpenAI API key.")

# ═════════════════════════════════════════════════════════════════════════
# Main form
# ═════════════════════════════════════════════════════════════════════════
with st.form("symptom_form"):
    st.markdown("### 👤 About you")
    c1, c2 = st.columns(2)
    c1.text_input("Age", key="f_age", placeholder="e.g. 34, or 8 months for a baby")
    c2.selectbox("Gender", C.GENDERS, key="f_gender")

    st.markdown("### 🤒 Your symptoms")
    st.multiselect("Symptoms", C.SYMPTOMS, key="f_symptoms", placeholder="Choose one or more symptoms",
                   format_func=symptom_label)
    st.text_input("Other symptoms (optional)", key="f_free_text",
                  placeholder="Describe anything not in the list, in your own words")
    c1, c2 = st.columns(2)
    c1.selectbox("How long have you had them?", C.DURATIONS, key="f_duration")
    c2.slider("How severe? (1 = barely noticeable, 10 = worst imaginable)", 1, 10, key="f_severity")

    st.markdown("### 🩺 Vitals (optional)")
    c1, c2 = st.columns(2)
    c1.number_input("🌡️ Temperature (°C) — leave 0 if not measured", 0.0, 43.0, step=0.1, format="%.1f", key="f_temp")
    c2.number_input("💓 Resting heart rate (bpm) — leave 0 if not measured", 0, 220, step=1, key="f_pulse")

    st.markdown("### 📋 Medical background (optional)")
    c1, c2, c3 = st.columns(3)
    c1.text_area("Existing medical conditions", key="f_conditions", placeholder="e.g. asthma, diabetes")
    c2.text_area("Current medications", key="f_medications", placeholder="e.g. inhaler, metformin")
    c3.text_area("Additional notes", key="f_notes", placeholder="e.g. recent travel, pregnancy, allergies")
    submitted = st.form_submit_button("✨ Get AI guidance", type="primary", width="stretch")

if submitted:
    age_years, age_error = parse_age(ss.f_age)
    problems = [age_error] if age_error else []
    if not ss.f_symptoms and not ss.f_free_text.strip():
        problems.append("Please select at least one symptom or describe it under “Other symptoms”. "
                        "No request was sent to the AI.")
    for problem in problems:
        st.warning(problem, icon="✋")
    if problems:
        clear_results()          # never leave a previous result (e.g. an emergency banner) on screen
    else:
        # 1) Python safety pre-screen — independent of the AI.
        vitals = vitals_flags(ss.f_temp, ss.f_pulse)
        notes_plus = "; ".join([n for n in [ss.f_notes.strip(), *vitals] if n])
        safety = screen(ss.f_symptoms, ss.f_free_text, ss.f_notes, age_years, ss.f_severity, ss.f_duration)
        # 2) Prompt variables.
        inputs = build_prompt_inputs(
            age=age_label(ss.f_age, age_years), gender=ss.f_gender, symptoms=ss.f_symptoms,
            free_text=ss.f_free_text, duration=ss.f_duration, severity=ss.f_severity,
            existing_conditions=ss.f_conditions, medications=ss.f_medications, notes=notes_plus,
            language=ss.language, safety=safety)
        patient = {"Age": inputs["age"], "Gender": inputs["gender"], "Symptoms": inputs["symptoms"],
                   "Duration": inputs["duration"], "Severity": f"{ss.f_severity}/10",
                   "Existing conditions": inputs["existing_conditions"], "Medications": inputs["medications"],
                   "Notes": inputs["notes"], "Vitals": "; ".join(vitals) or "Not measured",
                   "Answer language": ss.language}
        ss.update(patient=patient, inputs=inputs, safety=safety, result=None, narrative=None,
                  stream_pending=False, ai_error=None, last_call=None, chat=[])
        ai_level = None
        if not api_key:
            ss.ai_error = ("The AI agent is offline — add an OpenAI API key (in `.env`, Streamlit secrets or the "
                           "sidebar) for full AI guidance. Safety rules and basic guidance are shown below.")
        else:
            before = cache_entry_count(cache_mode)
            started = time.perf_counter()
            try:
                # 3) ChatOpenAI + LLMChain -> 4) safe JSON parsing
                with st.status("🤖 AI agent is working…", expanded=False) as status:
                    st.write("🛡️ Safety rules checked" + (f" — minimum urgency **{safety.floor}**" if safety.floor else ""))
                    st.write(f"🧠 Analysing your symptoms with {model}…")
                    result = run_assessment(get_llm(api_key, model, temperature), inputs)
                    st.write("🧩 Structured answer parsed")
                    status.update(label="✅ Assessment ready", state="complete")
                ss.result = result.__dict__
                ai_level = (result.assessment or {}).get("urgency_level")
                ss.stream_pending = True
            except Exception as exc:  # noqa: BLE001 — never crash; the safety rules still apply
                ss.ai_error = friendly_error(exc)
            hit = cache_mode != C.CACHE_NONE and before > 0 and cache_entry_count(cache_mode) == before
            ss.last_call = {"seconds": round(time.perf_counter() - started, 2), "cache": cache_mode, "hit": hit}
        ss.final_urgency, ss.raised = apply_floor(ai_level, safety.floor) if (ai_level or safety.floor) else (None, False)
        ss.history.append({"Run": len(ss.history) + 1, "Time": datetime.now().strftime("%H:%M:%S"),
                           "Age": inputs["age"], "Symptoms": inputs["symptoms"], "Severity": ss.f_severity,
                           "Urgency": ss.final_urgency or "Not determined", "Language": ss.language})


def text_block(name: str):
    """Container for AI text; right-to-left for Urdu/Arabic answers."""
    rtl = C.LANGUAGES.get((ss.inputs or {}).get("language", "English"), ("", False, True))[1]
    return st.container(key=f"{'rtl' if rtl else 'ltr'}_{name}")


def show_list(items: list[str], numbered: bool = True) -> None:
    for i, item in enumerate(items, 1):
        st.markdown(f"{i}. {md_safe(item)}" if numbered else f"- {md_safe(item)}")


# ═════════════════════════════════════════════════════════════════════════
# Results dashboard
# ═════════════════════════════════════════════════════════════════════════
if ss.patient is None:
    st.info("Fill in the form above and select **✨ Get AI guidance**. Required: your age and at least one symptom.",
            icon="📝")
else:
    safety, final = ss.safety, ss.final_urgency
    result = ss.result or {}
    a = result.get("assessment")

    # Emergency first — shown even if the AI failed or no API key is set.
    if final == "EMERGENCY":
        crisis = ('<p>If you are thinking about harming yourself, please reach out now: call your local '
                  'emergency number or a crisis line, or tell someone you trust. You do not have to face this '
                  'alone.</p>') if safety.crisis else ""
        st.markdown(f"""<div class="mg-emergency" role="alert"><h3>🚨 Seek emergency help now</h3>
<p>Call your local emergency number or go to the nearest emergency department immediately.
Do not wait for this app or drive yourself if you feel unwell.</p>{crisis}
<p>📞 <b>Emergency numbers:</b> {html.escape(C.EMERGENCY_NUMBERS)}</p></div>""", unsafe_allow_html=True)

    st.warning("**Educational guidance only — not a diagnosis.** The information below may be incomplete or "
               "wrong. Please consult a qualified healthcare professional.", icon="⚠️")

    st.markdown("## 📊 Your guidance")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚦 Urgency", f"{URGENCY_EMOJI[final]} {C.URGENCY_INFO[final]['label']}" if final else "Not determined")
    c2.metric("📈 Severity", ss.patient["Severity"])
    c3.metric("⏱️ Duration", ss.patient["Duration"])
    c4.metric("🤒 Symptoms", len([s for s in ss.patient["Symptoms"].split(", ") if s]))

    if final:
        cells = []
        for level in C.URGENCY_LEVELS:
            info = C.URGENCY_INFO[level]
            on = level == final
            style = f' style="background:{info["colour"]}"' if on else ""
            cells.append(f'<div class="{"on" if on else ""}"{style} aria-current="{str(on).lower()}">'
                         f'<b>{URGENCY_EMOJI[level]} {info["label"]}</b><span>{html.escape(info["meaning"])}</span></div>')
        st.markdown(f'<div class="mg-triage" role="list" aria-label="Urgency level: {final}">{"".join(cells)}</div>',
                    unsafe_allow_html=True)
        alert = {"LOW": st.success, "MEDIUM": st.warning, "HIGH": st.error, "EMERGENCY": st.error}[final]
        alert(f"**{C.URGENCY_INFO[final]['label']} urgency.** {C.URGENCY_INFO[final]['meaning']}")
        if ss.raised and a:
            st.info(f"The AI suggested **{a['urgency_level']}**, but MediGuide's safety rules raised it to "
                    f"**{final}**. When in doubt, the more cautious level is shown.", icon="🛡️")
        label, query = CARE_SEARCH[final]
        st.link_button(label, "https://www.google.com/maps/search/" + query.replace(" ", "+"),
                       type="primary" if final in ("HIGH", "EMERGENCY") else "secondary")
        if safety.reasons:
            with st.expander("🛡️ Why this urgency level? (rule-based safety checks)"):
                for reason in safety.reasons:
                    st.markdown(f"- {reason}")
                st.caption("These checks run in Python before the AI and can only raise urgency, never lower it.")

    if ss.patient.get("Vitals", "Not measured") != "Not measured":
        chips = "".join(f'<span class="{"warn" if "(" in v else ""}">{"🌡️" if "temperature" in v else "💓"} '
                        f'{html.escape(v)}</span>' for v in ss.patient["Vitals"].split("; "))
        st.markdown(f'<div class="mg-vitals">{chips}</div>', unsafe_allow_html=True)

    if ss.ai_error:
        st.error(ss.ai_error, icon="🔌")
    if not a:
        level = final or "MEDIUM"
        with st.container(border=True):
            st.markdown(f"#### 🧭 Basic guidance (no AI) · {URGENCY_EMOJI[level]} {C.URGENCY_INFO[level]['label']}")
            if not final:
                st.caption("No safety rule fired and the AI is unavailable, so general advice for a "
                           "**Medium** level is shown to stay on the cautious side.")
            for tip in OFFLINE_TIPS[level]:
                st.markdown(f"- {tip}")
    if ss.last_call:
        note = "served from cache — no new API call" if ss.last_call["hit"] else "fresh API call"
        st.caption(f"Assessment: {ss.last_call['seconds']} s · {note} · {ss.last_call['cache']}")
    if result.get("source") == "failed":
        st.error("The AI's answer couldn't be read as valid JSON, so the structured results can't be shown. "
                 "Try again, or choose another model. The urgency above comes from the safety rules.", icon="🧩")
        with st.expander("Raw model output (for debugging)"):
            st.code(result["raw_output"] or "(empty)", language="json", wrap_lines=True)
            for p in result["problems"]:
                st.caption(f"• {p}")
    elif result.get("source") == "ai-repaired":
        st.info("The first AI answer had a JSON formatting problem and was repaired automatically.", icon="🛠️")

    # Streamed narrative — "AI-generated general information"
    if result:
        st.markdown("### 💬 What this may mean and what to do")
        with text_block("narrative"):
            if ss.stream_pending:
                try:
                    llm = get_llm(api_key, model, temperature)
                    shown = st.write_stream(md_safe_stream(stream_narrative(
                        llm, {**ss.inputs, "urgency_level": final or "not determined"})))
                    ss.narrative = shown.replace("\\$", "$")
                except Exception as exc:  # noqa: BLE001
                    st.error(friendly_error(exc))
                ss.stream_pending = False
            elif ss.narrative:
                st.markdown(md_safe(ss.narrative))

    if a:
        tabs = st.tabs(["📝 Summary", "🔍 Possible conditions", "✅ Next steps", "❓ Doctor questions",
                        "🚨 Warning signs", "💬 Ask the AI", "⚙️ Under the hood"])
        with tabs[0]:
            c1, c2 = st.columns([2, 3])
            with c1:
                st.markdown("**👤 What you told us**")
                st.markdown("  \n".join(f"**{key}:** {md_safe(ss.patient[key])}" for key in
                                        ["Age", "Gender", "Symptoms", "Duration", "Severity", "Vitals",
                                         "Existing conditions", "Medications", "Notes"]))
            with c2:
                st.markdown("**🤖 AI summary**")
                with text_block("summary"):
                    st.info(md_safe(a["summary"]))
        with tabs[1], text_block("conditions"):
            st.warning("These are possibilities for education only — **not a diagnosis**. Only a healthcare "
                       "professional who examines you can diagnose a condition.")
            for i, cond in enumerate(a["possible_conditions"]):
                with st.expander("🔹 " + (cond["name"] or "Possible condition"), expanded=i == 0):
                    st.markdown(md_safe(cond["reason"]) or "_No explanation given._")
        with tabs[2], text_block("steps"):
            for step in a["recommended_next_steps"]:
                st.success(md_safe(step), icon="✅")
        with tabs[3], text_block("questions"):
            st.caption("Write these down or show this screen at your appointment.")
            show_list(a["questions_for_doctor"])
        with tabs[4], text_block("warnings"):
            st.error("**Get help immediately if you notice any of these:**", icon="🚨")
            show_list(a["warning_signs"], numbered=False)
            st.caption(f"Emergency numbers: {C.EMERGENCY_NUMBERS}")
        with tabs[5]:
            st.caption("Ask about this guidance. The conversation is sent as System → Human → AI messages.")
            for turn in ss.chat:
                st.chat_message("user").markdown(md_safe(turn["question"]))
                with st.chat_message("assistant", avatar=LOGO_URI), text_block(f"chat_{len(turn['question'])}_{turn['n']}"):
                    st.markdown(md_safe(turn["answer"]))
            question = st.chat_input("e.g. What can I do at home to feel better?", disabled=not api_key)
            if question:
                st.chat_message("user").markdown(md_safe(question))
                with st.chat_message("assistant", avatar=LOGO_URI):
                    try:
                        messages = build_conversation(ss.inputs, a, ss.chat, question)
                        shown = st.write_stream(md_safe_stream(
                            stream_follow_up(get_llm(api_key, model, temperature), messages)))
                        ss.chat.append({"question": question, "answer": shown.replace("\\$", "$"),
                                        "n": len(ss.chat)})
                    except Exception as exc:  # noqa: BLE001
                        st.error(friendly_error(exc))
        with tabs[6]:
            st.markdown("**Pipeline:** form → safety rules (Python) → `PromptTemplate` inside a "
                        "`ChatPromptTemplate` → `LLMChain` with `ChatOpenAI` (JSON mode) → safe JSON parsing → "
                        "`llm.stream()` → `st.write_stream()`.")
            with st.expander("Messages sent by the LLMChain (System + Human)"):
                for msg in ASSESSMENT_CHAT_TEMPLATE.format_messages(**ss.inputs):
                    st.markdown(f"**{type(msg).__name__}**")
                    st.code(msg.content, language=None, wrap_lines=True)
            with st.expander("System / Human / AI message example"):
                for msg in build_message_demo(ss.inputs, a):
                    st.markdown(f"**{type(msg).__name__}**")
                    st.code(msg.content, language=None, wrap_lines=True)
            with st.expander("PromptTemplate variables"):
                st.json({k: ss.inputs[k] for k in ASSESSMENT_PROMPT.input_variables})
            with st.expander("Raw JSON from the model"):
                st.code(result["raw_output"], language="json", wrap_lines=True)
                for p in result["problems"]:
                    st.caption(f"• {p}")
            with st.expander("Caching explained"):
                st.dataframe(pd.DataFrame(CACHE_COMPARISON).set_index(""), width="stretch")
                st.caption("`set_llm_cache(...)` registers one global cache. LangChain checks it before every "
                           "model call; an identical request returns instantly without calling the API.")

    # ── Downloads ──
    st.markdown("### 💾 Save this guidance")
    reasons = safety.reasons if safety else []
    lang = (ss.inputs or {}).get("language", "English")
    c1, c2 = st.columns(2)
    c1.download_button("⬇️ Report (Markdown)",
                       build_markdown_report(ss.patient, a, final, reasons, ss.narrative),
                       f"mediguide-{datetime.now():%Y%m%d-%H%M}.md", "text/markdown", width="stretch")
    if C.LANGUAGES[lang][2]:
        c2.download_button("📄 Report (PDF)", build_pdf_report(ss.patient, a, final, reasons, ss.narrative),
                           f"mediguide-{datetime.now():%Y%m%d-%H%M}.pdf", "application/pdf", width="stretch")
    else:
        c2.button("📄 Report (PDF)", disabled=True, width="stretch",
                  help=f"PDF export supports Latin-script languages. Use the Markdown report for {lang}.")

    # ── Session history + urgency analytics (bonus) ──
    if len(ss.history) > 1:
        st.markdown("### 🕘 Session history")
        hist = pd.DataFrame(ss.history)
        left, right = st.columns([3, 2])
        left.dataframe(hist, hide_index=True, width="stretch")
        counts = hist["Urgency"].value_counts().reindex(C.URGENCY_LEVELS + ["Not determined"], fill_value=0)
        chart_df = counts.rename_axis("Urgency").reset_index(name="Assessments")
        right.altair_chart(alt.Chart(chart_df).mark_bar(cornerRadiusEnd=3).encode(
            x=alt.X("Assessments:Q", axis=alt.Axis(tickMinStep=1)),
            y=alt.Y("Urgency:N", sort=C.URGENCY_LEVELS + ["Not determined"], title=None),
            color=alt.Color("Urgency:N", legend=None, scale=alt.Scale(
                domain=C.URGENCY_LEVELS + ["Not determined"],
                range=[C.URGENCY_INFO[l]["colour"] for l in C.URGENCY_LEVELS] + ["#9AA5B1"]))
        ).properties(height=200, title="Urgency distribution"), width="stretch")

st.markdown(f'<div class="mg-foot">{html.escape(C.DISCLAIMER)}</div>', unsafe_allow_html=True)


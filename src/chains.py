"""LangChain logic: ChatOpenAI, the reusable LLMChain, streaming and messages."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterator

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

try:                                    # LangChain 0.x
    from langchain.chains import LLMChain
except ImportError:                     # LangChain 1.x moved legacy chains to langchain-classic
    from langchain_classic.chains import LLMChain

from .config import DEFAULT_MODEL, DEFAULT_TEMPERATURE, REQUEST_TIMEOUT_SECONDS, TRANSCRIPTION_MODEL
from .prompts import (ASSESSMENT_CHAT_TEMPLATE, ASSESSMENT_PROMPT, FOLLOW_UP_SYSTEM, NARRATIVE_CHAT_TEMPLATE,
                      REPAIR_TEMPLATE)
from .safety import SafetyScreen
from .utils import or_none, parse_assessment_json


# ── 1. Model ────────────────────────────────────────────────────────────
def get_llm(api_key: str, model: str = DEFAULT_MODEL, temperature: float = DEFAULT_TEMPERATURE) -> ChatOpenAI:
    """Create the OpenAI chat model. The key comes from .env (see config.py)."""
    return ChatOpenAI(model=model, temperature=temperature, api_key=api_key,
                      timeout=REQUEST_TIMEOUT_SECONDS, max_retries=2)


# ── 2. Prompt inputs ────────────────────────────────────────────────────
def build_prompt_inputs(*, age: str, gender: str, symptoms: list[str], free_text: str, duration: str,
                        severity: int, existing_conditions: str, medications: str, notes: str,
                        language: str, safety: SafetyScreen) -> dict:
    """Turn the form values into the variables the prompt templates expect."""
    all_symptoms = list(symptoms) + ([free_text.strip()] if free_text.strip() else [])
    flags = "\n".join(f"- {r}" for r in safety.reasons) or "- No red flags detected by the rules."
    if safety.floor:
        flags += f"\nMinimum urgency set by the rules: {safety.floor}."
    return {
        "age": age, "gender": gender, "symptoms": ", ".join(all_symptoms), "duration": duration,
        "severity": str(severity), "existing_conditions": or_none(existing_conditions),
        "medications": or_none(medications), "notes": or_none(notes), "language": language,
        "safety_flags": flags,
    }


# ── 3. Reusable LLMChain ────────────────────────────────────────────────
def build_assessment_chain(llm) -> LLMChain:
    """LLMChain = ChatPromptTemplate (System + Human) -> ChatOpenAI in JSON mode.

    JSON mode makes the reply a JSON object; we still validate it against our schema.
    """
    json_llm = llm.bind(response_format={"type": "json_object"}) if isinstance(llm, ChatOpenAI) else llm
    return LLMChain(llm=json_llm, prompt=ASSESSMENT_CHAT_TEMPLATE, output_key="assessment_json")


@dataclass
class AssessmentResult:
    assessment: dict | None          # None when the JSON could not be parsed
    raw_output: str                  # shown for debugging when parsing fails
    source: str                      # "ai", "ai-repaired" or "failed"
    problems: list = field(default_factory=list)


def run_assessment(llm, inputs: dict) -> AssessmentResult:
    """Run the chain and parse the JSON safely. One automatic repair attempt on failure."""
    chain = build_assessment_chain(llm)
    raw = chain.invoke(inputs)["assessment_json"]
    assessment, problems = parse_assessment_json(raw)
    if assessment is not None:
        return AssessmentResult(assessment, raw, "ai", problems)
    try:
        fixed = llm.invoke(REPAIR_TEMPLATE.format(errors="; ".join(problems), bad_output=raw[:6000])).content
        assessment, more = parse_assessment_json(fixed)
        if assessment is not None:
            return AssessmentResult(assessment, fixed, "ai-repaired", problems + more)
        problems += more
    except Exception as exc:  # noqa: BLE001 — repair is best effort
        problems.append(f"Repair attempt failed: {type(exc).__name__}")
    return AssessmentResult(None, raw, "failed", problems)


# ── 4. Streaming ────────────────────────────────────────────────────────
def stream_narrative(llm, inputs: dict) -> Iterator[str]:
    """Yield the guidance narrative piece by piece (st.write_stream prints each piece)."""
    messages = NARRATIVE_CHAT_TEMPLATE.format_messages(**inputs)
    for chunk in llm.stream(messages):
        if chunk.content:
            yield chunk.content


# ── 5. System / Human / AI messages ─────────────────────────────────────
def build_message_demo(inputs: dict, assessment: dict | None) -> list[BaseMessage]:
    """A minimal conversation showing how each message type is represented."""
    return [
        SystemMessage(content="You are MediGuide AI, an educational assistant. Never give a confirmed "
                              "diagnosis; always recommend a healthcare professional."),
        HumanMessage(content=f"I am {inputs['age']} ({inputs['gender']}). I have had {inputs['symptoms']} "
                             f"for {inputs['duration']}, severity {inputs['severity']}/10. What should I do?"),
        AIMessage(content=(assessment or {}).get("summary")
                  or "(The assistant's reply appears here after an assessment.)"),
    ]


def build_conversation(inputs: dict, assessment: dict, history: list[dict], question: str) -> list[BaseMessage]:
    """System rules + patient data (Human) + earlier assessment (AI) + chat turns + new question."""
    patient = ASSESSMENT_PROMPT.format(**{k: inputs[k] for k in ASSESSMENT_PROMPT.input_variables})
    messages: list[BaseMessage] = [
        SystemMessage(content=FOLLOW_UP_SYSTEM.format(language=inputs["language"])),
        HumanMessage(content=patient),
        AIMessage(content=json.dumps(assessment, ensure_ascii=False)),
    ]
    for turn in history[-6:]:
        messages += [HumanMessage(content=turn["question"]), AIMessage(content=turn["answer"])]
    messages.append(HumanMessage(content=question))
    return messages


def stream_follow_up(llm, messages: list[BaseMessage]) -> Iterator[str]:
    for chunk in llm.stream(messages):
        if chunk.content:
            yield chunk.content


# ── 6. Voice input (bonus) ──────────────────────────────────────────────
def transcribe_audio(api_key: str, audio_bytes: bytes, language_code: str | None = None) -> str:
    """Speech-to-text with OpenAI's transcription endpoint (not cached)."""
    from openai import OpenAI
    client = OpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS)
    kwargs = {"model": TRANSCRIPTION_MODEL, "file": ("symptoms.wav", audio_bytes)}
    if language_code:
        kwargs["language"] = language_code
    return client.audio.transcriptions.create(**kwargs).text.strip()

# 🩺 MediGuide AI — Symptom Assessment & Patient Guidance Assistant

An educational LangChain + Streamlit prototype. You enter your age, symptoms, duration, severity and
medical background; MediGuide AI returns structured, safety-first guidance: a summary, possible
conditions (for education only), an urgency level, next steps, questions for your doctor and warning
signs — plus a streamed explanation in your chosen language.

> 🚑 **Medical & safety notice.** MediGuide AI is an educational AI prototype, **not a doctor** and not a
> medical device. It never gives a confirmed diagnosis and cannot replace a licensed healthcare
> professional, a diagnosis or emergency services. **In an emergency, call your local emergency number
> immediately** (e.g. 1122 or 115 in Pakistan, 911 in the US, 999 in the UK, 112 in the EU).

---

## 1. Setup

Requires **Python 3.10+**.

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env            # Windows: copy .env.example .env
# edit .env:  OPENAI_API_KEY=sk-...
```

Create a key at <https://platform.openai.com> → *API keys*. `.env` is in `.gitignore`, so it is never
committed. The key is read with `python-dotenv` in `src/config.py` and is never hard-coded.

## 2. Run

```bash
streamlit run app.py
```

Open <http://localhost:8501>. To try the assignment's test cases, open **Quick fill → Test scenarios**.

```bash
# Tests — no API key needed (a fake chat model is used)
pip install -r requirements-dev.txt
python -m pytest

# Docker (optional)
docker build -t mediguide-ai .
docker run -p 8501:8501 --env-file .env -v mediguide-cache:/app/data mediguide-ai
```

---

## 3. Project structure

```
medical_ai_assistant/
├── app.py                 Streamlit UI — run this
├── requirements.txt       requirements-dev.txt (adds pytest)
├── .env.example           copy to .env and add your key
├── Dockerfile, .dockerignore, .gitignore, pytest.ini
├── .streamlit/config.toml theme
├── src/
│   ├── config.py          settings, form options, languages, urgency levels, test scenarios
│   ├── prompts.py         system prompt + safety rules, JSON schema, PromptTemplate, ChatPromptTemplates
│   ├── chains.py          ChatOpenAI, LLMChain, JSON repair, streaming, messages, voice transcription
│   ├── cache_manager.py   InMemoryCache / SQLiteCache switching
│   ├── utils.py           safe JSON parsing (Pydantic), age parsing, Markdown report
│   ├── safety.py          rule-based red-flag screening (runs before the AI)
│   └── report.py          PDF report (bonus)
├── tests/                 42 tests: safety rules, parsing, prompts, chains, caching, PDF, full UI
└── docs/Medical_AI_Assignment.pdf
```

## 4. Data flow

```
form input ─► validate (age, at least one symptom) ── invalid ─► warning, NO API call
     │
     ▼
safety.screen()  ← Python red-flag rules: sets a minimum urgency ("floor")
     │                (an EMERGENCY banner shows even if the AI fails or there is no key)
     ▼
build_prompt_inputs() ─► select cache (set_llm_cache) ─► ChatOpenAI + LLMChain
     │
     ▼
parse JSON safely ── invalid ─► one repair call ── still invalid ─► friendly error + raw output
     │
     ▼
final urgency = max(AI urgency, safety floor) ─► stream narrative (st.write_stream) ─► dashboard
```

## 5. Safety design

The assignment's safety rules are enforced in **three layers**:

1. **System prompt** (`prompts.py`) — the model is told it is an educational assistant, must never give a
   confirmed diagnosis, must not prescribe or give doses, must use EMERGENCY for red-flag symptoms, must
   respond with compassion to self-harm, and must treat patient text as data rather than instructions.
2. **Deterministic safety rules** (`safety.py`) — Python checks run *before* the AI. Examples: chest pain
   with shortness of breath, fainting, seizure, stroke signs, severe bleeding, a severe allergic reaction
   or thoughts of self-harm → **EMERGENCY**; chest pain alone, confusion, fever in a baby under 3 months, or
   severity 9–10 → at least **HIGH**; severity 7–8 or symptoms lasting 2+ weeks → at least **MEDIUM**.
   The final urgency is the **higher** of the AI's level and the rule-based floor, so the AI can raise
   urgency but never lower it. The dashboard says when the rules raised the AI's level, and why.
3. **Interface** — disclaimers in the sidebar, the header, above the results, in the footer and in every
   report; a full-width red emergency banner with emergency numbers; "not a diagnosis" on the possible
   conditions tab; crisis-support wording when self-harm is mentioned.

Urgency colours: **LOW** green (`st.success`), **MEDIUM** amber (`st.warning`), **HIGH** orange-red and
**EMERGENCY** red (`st.error` + emergency banner). They are shown on a four-step triage tag.

**Limitations.** The rules are simplified for education and are not a clinical triage system. Free-text
red-flag phrases are matched in English only; answers in other languages still rely on the selected
symptoms, the severity and the model.

---

## 6. LangChain concepts

| Concept | Where |
|---|---|
| `ChatOpenAI` | `chains.get_llm()` |
| `SystemMessage` / `HumanMessage` / `AIMessage` | `chains.build_message_demo()` (shown under *Under the hood*) and `build_conversation()` (follow-up chat: System rules → Human patient data → AI assessment → turns) |
| `PromptTemplate` | `prompts.ASSESSMENT_PROMPT` — age, gender, symptoms, duration, severity, existing_conditions, medications, notes, language, safety_flags + JSON schema |
| `ChatPromptTemplate` | `prompts.ASSESSMENT_CHAT_TEMPLATE` (System safety rules + Human built from the PromptTemplate) and `NARRATIVE_CHAT_TEMPLATE` |
| `LLMChain` | `chains.build_assessment_chain()` — ChatOpenAI in JSON mode |
| Structured JSON | Exact schema from section 10; validated in `utils.parse_assessment_json()` |
| Streaming | `chains.stream_narrative()` (as in section 15) → `st.write_stream()`; follow-up answers stream too |
| Caching | `cache_manager.configure_cache()` → `set_llm_cache()` |

> **Note on `LLMChain`:** the assignment requires it, but LangChain has deprecated it in favour of
> `prompt | llm`. In LangChain 1.x it lives in `langchain-classic`, which is why that package is in
> `requirements.txt`; `chains.py` imports it from either location. The deprecation warning is expected.

### Safe JSON handling (section 16)

`parse_assessment_json()` never raises. It strips ```` ```json ```` fences and any text around the object,
wraps `json.loads()` in `try/except` (and tolerates trailing commas), then validates with Pydantic:
urgency synonyms are normalised (`"Emergent"` → EMERGENCY, `"moderate"` → MEDIUM), and lists given as
numbered text become proper lists. If parsing fails, the model gets one chance to fix its output; if that
fails too, the app shows a friendly message **and the raw output for debugging** — the rule-based
urgency still shows.

---

## 7. Caching

Choose the cache in the sidebar. `set_llm_cache(...)` registers **one global cache**. Before every
model call, LangChain builds a key from the prompt and model settings and checks the cache: on a hit it
returns the stored answer instantly with **no API call and no cost**.

| | InMemoryCache | SQLiteCache |
|---|---|---|
| Stored in | RAM (memory) | A file on disk (`.langchain_cache.db`) |
| Speed | Fastest | Fast, slightly slower |
| Survives restart? | No | Yes |
| Best for | One session | Reusing across sessions |

**Test scenario 4:** submit the same form twice. The caption under *Your guidance* changes from
"fresh API call" to "served from cache — no new API call", the time drops to milliseconds, the result is
identical, and the streamed narrative appears at once. Changing any input, the language, the model or the
temperature creates a new cache entry. The sidebar shows the number of stored responses and can clear them.

---

## 8. Testing scenarios (section 18)

| # | Input | Expected | How it's handled |
|---|---|---|---|
| 1 | Age 25, runny nose + sore throat, 1–3 days, severity 2 | LOW, calm monitoring | No safety flags; the AI's level is used |
| 2 | Age 40, fever + cough, 4–7 days, severity 6 | MEDIUM/HIGH, see a professional | AI level; prompt asks for a doctor visit |
| 3 | Severe chest pain + shortness of breath | HIGH/EMERGENCY, urge immediate help | Rules force **EMERGENCY** + red banner, even if the AI says lower |
| 4 | Same form twice, cache on | Faster, identical | Cache hit shown in the caption |
| 5 | Empty symptoms | Warning, no API call | Validation stops before any request |
| 6 | Language = Urdu | Urdu guidance | Language goes into every prompt; Urdu/Arabic display right-to-left |

Scenarios 1, 2, 3 and 6 load from **Quick fill → Test scenarios**. All six are covered by automated tests
(`tests/test_app.py`, `tests/test_safety.py`) using a fake model, so the AI *wording* still needs checking
with a real key during your demo.

## 9. Features

**Required:** sidebar (name, description, disclaimer, model configuration, language); form with
`text_input`, `text_area`, `selectbox`, `multiselect`, `slider` and buttons; dashboard with `st.metric`,
`st.warning`, `st.info`, `st.error`, `st.success`, `st.expander`, tabs, columns and `st.write_stream`.

**Bonus:**
- Follow-up conversation that remembers earlier turns, plus session history.
- Urgency-distribution chart for the session (analytics).
- Report download: Markdown for every language, PDF for Latin-script languages (ReportLab's built-in
  fonts can't render Urdu, Arabic, Hindi, Bengali or Chinese).
- 10 answer languages, with right-to-left layout for Urdu and Arabic.
- Voice symptom input (records in the browser, transcribed with OpenAI `whisper-1`).
- Docker deployment.
- *Under the hood* tab: exact messages, prompt variables, raw JSON.

## 10. Troubleshooting

| Message | Fix |
|---|---|
| "API key was rejected" | Check `OPENAI_API_KEY` in `.env`, then restart Streamlit. |
| "Model isn't available" | Choose another model in the sidebar. |
| "Rate limit or quota reached" | Check billing/limits at platform.openai.com. |
| Deprecation warnings in the terminal | Expected — `LLMChain` and `langchain-community` are being phased out by LangChain; both still work. |

---

*This project is for education only. It is not a medical device and must not be used for real diagnosis
or treatment.*

"""Vibrant rainbow "AI agent" theme for MediGuide AI — presentation only, no app state.

One stylesheet replaces the earlier stacked themes (aesthetic_theme.py + purple_palette.py).
Rainbow colours are decorative only; urgency colours (LOW/MEDIUM/HIGH/EMERGENCY) stay
semantic and are never reused for decoration.
"""
from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parent / "assets"


def logo_data_uri() -> str:
    return "data:image/svg+xml;base64," + base64.b64encode((ASSETS / "logo.svg").read_bytes()).decode()


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&family=Atkinson+Hyperlegible:wght@400;700&family=Noto+Nastaliq+Urdu:wght@400;700&family=Noto+Naskh+Arabic:wght@400;700&display=swap');

:root{
  color-scheme:dark;
  --bg:#0B0A1F; --bg2:#121033; --surface:rgba(255,255,255,.045); --surface-2:rgba(255,255,255,.075);
  --line:rgba(170,160,255,.22); --ink:#F5F3FF; --muted:#BDB8E6;
  --r1:#FF4D6D; --r2:#FF9F1C; --r3:#FFE14D; --r4:#2EE59D; --r5:#2EC5FF; --r6:#A66CFF;
  --rainbow:linear-gradient(90deg,var(--r1),var(--r2),var(--r3),var(--r4),var(--r5),var(--r6));
  --rainbow-soft:linear-gradient(120deg,#FF4D6D33,#FF9F1C26,#2EE59D22,#2EC5FF26,#A66CFF33);
  --radius:14px; --shadow:0 10px 30px -18px #000, inset 0 1px 0 #ffffff14;
}

/* ── Base ─────────────────────────────────────────────────────────── */
html,body,.stApp,[class*="css"],button,input,textarea,select{font-family:"Atkinson Hyperlegible",system-ui,sans-serif}
.stApp{color:var(--ink);background:
  radial-gradient(900px 500px at 0% -10%,#FF4D6D22,transparent 60%),
  radial-gradient(800px 500px at 100% 0%,#2EC5FF22,transparent 60%),
  radial-gradient(900px 600px at 50% 110%,#A66CFF26,transparent 60%),var(--bg)!important;background-attachment:fixed!important}
[data-testid="stHeader"]{background:#0B0A1Fcc!important;backdrop-filter:blur(12px)}
[data-testid="stHeader"]::after{content:"";position:absolute;left:0;right:0;bottom:0;height:2px;background:var(--rainbow);opacity:.85}
.stApp .block-container{max-width:1180px!important;padding:3.4rem clamp(14px,2.4vw,36px) 2.4rem!important}
.stApp h1,.stApp h2,.stApp h3,.stApp h4{font-family:Poppins,"Atkinson Hyperlegible",sans-serif;color:var(--ink)!important;letter-spacing:-.01em;line-height:1.25!important}
.stApp h2{font-size:1.45rem!important;padding:.4rem 0 .2rem!important}
.stApp h3{font-size:1.12rem!important;padding:.3rem 0 .1rem!important}
.stApp h4{font-size:.98rem!important}
.stApp p,.stApp li{line-height:1.6}
.stApp label,.stApp summary,[data-testid="stCaptionContainer"] p,[data-testid="stWidgetLabel"] p{color:var(--muted)!important}
[data-testid="stVerticalBlock"]{gap:.7rem}

/* ── Sidebar ─────────────────────────────────────────────────────── */
[data-testid="stSidebar"]{background:linear-gradient(180deg,#141238,#0D0B26)!important;border-right:1px solid var(--line)!important}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:.55rem}
[data-testid="stSidebar"] h4{margin-top:.4rem}
[data-testid="stSidebarHeader"]{padding-bottom:.3rem}
[data-testid="stSidebarLogo"],[data-testid="stLogo"]{height:46px!important;max-height:46px!important;width:auto!important;max-width:100%!important}

/* ── Cards (form, metrics, expanders, chat) ─────────────────────── */
[data-testid="stForm"],[data-testid="stExpander"],[data-testid="stChatMessage"]{
  background:var(--surface)!important;border:1px solid var(--line)!important;border-radius:var(--radius)!important;box-shadow:var(--shadow)!important;backdrop-filter:blur(6px)}
[data-testid="stForm"]{padding:1rem 1.2rem!important;position:relative;overflow:hidden}
[data-testid="stForm"]::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;background:var(--rainbow)}
[data-testid="stExpander"] details summary{padding:.55rem .9rem!important}
[data-testid="stMetric"]{background:var(--surface)!important;border:1px solid var(--line)!important;border-radius:12px!important;padding:.65rem .9rem!important;position:relative;overflow:hidden;box-shadow:var(--shadow)}
[data-testid="stMetric"]::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--r5)}
[data-testid="stColumn"]:nth-child(1) [data-testid="stMetric"]::before{background:var(--r1)}
[data-testid="stColumn"]:nth-child(2) [data-testid="stMetric"]::before{background:var(--r3)}
[data-testid="stColumn"]:nth-child(3) [data-testid="stMetric"]::before{background:var(--r4)}
[data-testid="stColumn"]:nth-child(4) [data-testid="stMetric"]::before{background:var(--r6)}
[data-testid="stMetricLabel"] p{color:var(--muted)!important;font-size:.8rem!important}
[data-testid="stMetricValue"]{font-family:Poppins,sans-serif;font-size:1.25rem!important;color:var(--ink)!important;line-height:1.25}
[data-testid="stMetricValue"]>div{white-space:normal!important;overflow:visible!important}

/* ── Inputs ──────────────────────────────────────────────────────── */
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea,[data-testid="stNumberInput"] input,[data-testid="stChatInput"] textarea{
  background:#0F0D2A!important;color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important;caret-color:var(--r5)!important}
[data-baseweb="select"]>div,[data-baseweb="input"],[data-baseweb="textarea"]{background:#0F0D2A!important;border-color:#3A3670!important;border-radius:10px!important}
[data-baseweb="select"]>div:focus-within,[data-baseweb="input"]:focus-within,[data-baseweb="textarea"]:focus-within{border-color:var(--r5)!important;box-shadow:0 0 0 3px #2EC5FF33!important}
input::placeholder,textarea::placeholder{color:#8E89BE!important;-webkit-text-fill-color:#8E89BE!important}
[data-baseweb="tag"]{background:linear-gradient(90deg,#A66CFF55,#2EC5FF44)!important;border:1px solid #A66CFF88!important;border-radius:999px!important}
[data-baseweb="tag"] span{color:#fff!important}
[data-testid="stSlider"] [role="slider"]{background:#fff!important;box-shadow:0 0 0 4px #A66CFF55!important}
[data-testid="stSliderThumbValue"]{color:var(--r3)!important}
[data-testid="stChatInput"]{background:linear-gradient(#0F0D2A,#0F0D2A) padding-box,var(--rainbow) border-box!important;border:2px solid transparent!important;border-radius:16px!important}
[data-testid="stBottom"]>div,[data-testid="stBottomBlockContainer"]{background:#0B0A1Ff2!important}

/* ── Buttons ─────────────────────────────────────────────────────── */
.stButton>button,.stDownloadButton>button,.stFormSubmitButton>button,.stLinkButton>a{
  background:var(--surface-2)!important;color:var(--ink)!important;border:1px solid #4A4590!important;border-radius:11px!important;
  min-height:40px;padding:.4rem .9rem!important;font-weight:600;transition:transform .15s,box-shadow .15s,border-color .15s!important;white-space:nowrap}
.stButton>button p,.stDownloadButton>button p,.stLinkButton>a p{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
button[kind="primary"],button[kind="primaryFormSubmit"],.stLinkButton>a[kind="primary"]{
  background:var(--rainbow)!important;background-size:200% 100%!important;color:#14102E!important;border:0!important;font-weight:700!important;
  box-shadow:0 8px 22px -10px #A66CFFaa!important;animation:mg-flow 8s linear infinite}
button[kind="primary"] p,button[kind="primaryFormSubmit"] p,.stLinkButton>a[kind="primary"] p{color:#14102E!important;font-weight:700!important}
@media(hover:hover){.stButton>button:not(:disabled):hover,.stDownloadButton>button:not(:disabled):hover,.stFormSubmitButton>button:hover,.stLinkButton>a:hover{
  transform:translateY(-1px);border-color:var(--r5)!important;box-shadow:0 8px 20px -12px #2EC5FFaa!important}}
button:disabled{opacity:.45!important}
@keyframes mg-flow{0%{background-position:0% 0}100%{background-position:200% 0}}

/* ── Tabs ────────────────────────────────────────────────────────── */
[role="tablist"]{background:#0F0D2A!important;border:1px solid var(--line)!important;border-radius:12px!important;padding:4px!important;gap:4px!important;overflow-x:auto}
[role="tab"]{border-radius:9px!important;padding:.35rem .8rem!important;min-height:34px!important;color:var(--muted)!important}
[role="tab"][aria-selected="true"]{background:linear-gradient(100deg,#FF4D6D,#A66CFF 60%,#2EC5FF)!important;color:#fff!important}
[role="tab"][aria-selected="true"] p{color:#fff!important;font-weight:700}
[data-baseweb="tab-highlight"],[data-baseweb="tab-border"]{display:none!important}

/* ── Alerts ──────────────────────────────────────────────────────── */
[data-testid="stAlert"]{border-radius:12px!important}
[data-testid="stAlert"]>div{padding:.6rem .85rem!important}
[data-testid="stAlert"] p,[data-testid="stAlert"] li{color:var(--ink)!important}
[data-testid="stMarkdownContainer"] code{background:#231F4D!important;color:#9EF0FF!important}

/* ── Hero header ─────────────────────────────────────────────────── */
.mg-head{position:relative;display:grid;grid-template-columns:auto minmax(0,1fr) minmax(0,380px);gap:1rem;align-items:center;
  background:var(--rainbow-soft),var(--bg2);border:1px solid var(--line);border-radius:18px;padding:1rem 1.2rem;margin-bottom:.9rem;overflow:hidden;box-shadow:var(--shadow)}
.mg-head::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;background:var(--rainbow);background-size:200% 100%;animation:mg-flow 6s linear infinite}
.mg-head img.mg-logo{width:64px;height:64px;filter:drop-shadow(0 6px 16px #A66CFF66)}
.mg-head h1{font-size:clamp(1.6rem,3vw,2.2rem)!important;margin:0!important;padding:0!important;line-height:1.1!important;
  background:var(--rainbow);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent!important}
.mg-head p{margin:.25rem 0 0;color:var(--muted);font-size:.92rem}
.mg-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:.5rem}
.mg-chips span{font-size:.74rem;padding:3px 9px;border-radius:999px;background:#ffffff0d;border:1px solid #ffffff22;color:#E9E6FF}
.mg-notice{border:1px solid #FFB86B88;border-radius:12px;background:#2A1C2Ecc;color:#FFE7C2;padding:.6rem .8rem;font-size:.84rem;line-height:1.45}
.mg-notice b{color:#FF9DB0}
@media(max-width:900px){.mg-head{grid-template-columns:auto minmax(0,1fr)}.mg-notice{grid-column:1/-1}}
@media(max-width:520px){.mg-head img.mg-logo{width:48px;height:48px}.mg-chips{display:none}}

/* ── AI agent status pill ────────────────────────────────────────── */
[data-testid="stSidebar"] [data-testid="stAlert"] p{font-size:.84rem!important;line-height:1.45!important}
.mg-agent{margin-bottom:.2rem;display:flex;align-items:center;gap:.55rem;padding:.45rem .7rem;border-radius:12px;background:var(--surface);border:1px solid var(--line);font-size:.85rem;color:var(--muted)}
.mg-agent img{width:26px;height:26px}
.mg-dot{width:8px;height:8px;border-radius:50%;background:var(--r4);box-shadow:0 0 0 0 #2EE59D88;animation:mg-pulse 2s infinite}
.mg-dot.off{background:#8E89BE;animation:none}
@keyframes mg-pulse{0%{box-shadow:0 0 0 0 #2EE59D88}70%{box-shadow:0 0 0 8px #2EE59D00}100%{box-shadow:0 0 0 0 #2EE59D00}}

/* ── Triage strip (urgency colours stay semantic) ───────────────── */
.mg-triage{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:.3rem 0 .7rem}
.mg-triage div{border:1px solid var(--line);border-radius:10px;padding:.45rem .6rem;background:#0F0D2A;color:var(--muted)}
.mg-triage div b{display:block;font-size:.92rem}
.mg-triage div span{font-size:.74rem;line-height:1.3;display:block}
.mg-triage div.on{color:#fff;border-color:transparent;box-shadow:0 8px 20px -10px currentColor}
@media(max-width:760px){.mg-triage{grid-template-columns:repeat(2,1fr)}}

.mg-emergency{background:linear-gradient(120deg,#B91C1C,#E11D48);color:#fff;border-radius:14px;padding:.9rem 1.1rem;margin:.4rem 0 .8rem;box-shadow:0 12px 28px -14px #E11D48}
.mg-emergency h3{color:#fff!important;margin:0 0 .3rem!important;font-size:1.25rem!important;padding:0!important}
.mg-emergency p{margin:.15rem 0;font-size:.95rem;line-height:1.5}

/* ── Vitals chips ────────────────────────────────────────────────── */
.mg-vitals{display:flex;flex-wrap:wrap;gap:8px;margin:.2rem 0 .4rem}
.mg-vitals span{padding:4px 10px;border-radius:999px;font-size:.82rem;background:#ffffff0d;border:1px solid #ffffff22}
.mg-vitals span.warn{border-color:#FF9F1C;color:#FFD39A}

.mg-foot{margin-top:1.8rem;padding-top:.8rem;border-top:1px solid var(--line);font-size:.78rem;color:var(--muted)}

/* ── Right-to-left answers (Urdu, Arabic) ───────────────────────── */
[class*="st-key-rtl_"],[class*="st-key-rtl_"] [data-testid="stMarkdownContainer"],[class*="st-key-rtl_"] p,
[class*="st-key-rtl_"] li,[class*="st-key-rtl_"] ol,[class*="st-key-rtl_"] ul{direction:rtl!important;text-align:right!important}
[class*="st-key-rtl_"] p,[class*="st-key-rtl_"] li{font-family:"Noto Nastaliq Urdu","Noto Naskh Arabic","Atkinson Hyperlegible",sans-serif;line-height:2.1}

:focus-visible{outline:3px solid var(--r5)!important;outline-offset:2px!important}
@media(max-width:720px){.stApp .block-container{padding:3.2rem 14px 2rem!important}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
</style>
"""


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.logo(str(ASSETS / "wordmark.svg"), icon_image=str(ASSETS / "logo.svg"), size="large")

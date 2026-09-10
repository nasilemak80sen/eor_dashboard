"""PETRONAS-inspired visual system for EOR Atlas."""

from __future__ import annotations

import streamlit as st


PETRONAS_GREEN = "#00A19C"
PETRONAS_GREEN_ALT = "#00A99D"
PETRONAS_BLUE = "#20419A"
PETRONAS_LIME = "#BFD730"
PETRONAS_YELLOW = "#FDB924"
PETRONAS_PURPLE = "#763F98"
WHITE = "#FFFFFF"
TEXT = "#111827"
MUTED = "#667085"
BORDER = "#E4E7EC"
SURFACE = "#F5F7F9"
SURFACE_ALT = "#EEF2F4"
DANGER = "#B42318"
SUCCESS = "#087443"


def inject_theme() -> None:
    """Apply the EOR Atlas application shell styling."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        :root {{
            --petronas-green: {PETRONAS_GREEN};
            --petronas-blue: {PETRONAS_BLUE};
            --petronas-lime: {PETRONAS_LIME};
            --petronas-yellow: {PETRONAS_YELLOW};
            --petronas-purple: {PETRONAS_PURPLE};
            --atlas-text: {TEXT};
            --atlas-muted: {MUTED};
            --atlas-border: {BORDER};
            --atlas-surface: {SURFACE};
            --atlas-surface-alt: {SURFACE_ALT};
        }}

        html, body, [class*="css"] {{
            font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
            color: var(--atlas-text);
        }}

        .stApp {{
            background: #F7F8FA;
            color: var(--atlas-text);
        }}

        .block-container {{
            max-width: 1500px;
            padding-top: 1.1rem;
            padding-bottom: 2.2rem;
        }}

        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #0E3038 0%, #0A252C 100%);
            border-right: 1px solid rgba(255,255,255,0.08);
        }}
        [data-testid="stSidebar"] > div:first-child {{
            padding-top: 1rem;
        }}
        [data-testid="stSidebar"] * {{
            color: #EAF7F6;
        }}

        .atlas-brand {{ display:flex; align-items:center; gap:.75rem; padding:.35rem .25rem 1rem; }}
        .atlas-brand-mark {{
            width:38px; height:38px; border-radius:11px;
            background:linear-gradient(135deg,var(--petronas-green),var(--petronas-lime));
            display:flex; align-items:center; justify-content:center;
            color:#fff; font-weight:700; font-size:1rem;
            box-shadow:0 8px 20px rgba(0,161,156,.22);
        }}
        .atlas-brand-title {{ font-size:1rem; font-weight:700; letter-spacing:.02em; }}
        .atlas-brand-subtitle {{ font-size:.7rem; color:rgba(234,247,246,.68); margin-top:.1rem; }}
        .nav-section-label {{
            margin:.9rem .25rem .4rem; font-size:.67rem; font-weight:700;
            letter-spacing:.11em; text-transform:uppercase; color:rgba(234,247,246,.45);
        }}

        .page-kicker {{ color:var(--petronas-green); font-size:.72rem; font-weight:700; letter-spacing:.11em; text-transform:uppercase; margin-bottom:.25rem; }}
        .page-title {{ font-size:2rem; line-height:1.12; font-weight:700; color:#12252D; margin:0; }}
        .page-subtitle {{ color:var(--atlas-muted); font-size:.93rem; margin-top:.4rem; margin-bottom:1.1rem; }}
        .section-title {{ color:#162A32; font-size:1.05rem; font-weight:700; margin:.2rem 0 .65rem; }}
        .section-caption {{ color:var(--atlas-muted); font-size:.82rem; margin-top:-.35rem; margin-bottom:.75rem; }}

        .atlas-divider {{ height:1px; background:var(--atlas-border); margin:1.15rem 0; }}

        .atlas-card, .atlas-card-white {{
            background:#fff; border:1px solid var(--atlas-border); border-radius:16px;
            padding:1rem 1.05rem; box-shadow:0 5px 18px rgba(16,24,40,.035);
        }}

        .kpi-card {{
            position:relative; background:#fff; border:1px solid var(--atlas-border); border-radius:16px;
            padding:1rem 1.05rem .95rem; min-height:112px;
            box-shadow:0 5px 18px rgba(16,24,40,.035); overflow:hidden;
        }}
        .kpi-card::before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--petronas-green); }}
        .kpi-label {{ color:#667085; font-size:.68rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }}
        .kpi-value {{ color:#101828; font-size:1.62rem; line-height:1.05; font-weight:700; margin-top:.55rem; }}
        .kpi-note {{ color:#667085; font-size:.74rem; margin-top:.45rem; line-height:1.35; }}

        .micro-kpi {{
            background:#fff; border:1px solid var(--atlas-border); border-radius:14px;
            padding:.75rem .85rem; min-height:82px; box-shadow:0 4px 12px rgba(16,24,40,.028);
        }}
        .micro-kpi-label {{ color:#667085; font-size:.64rem; font-weight:700; letter-spacing:.075em; text-transform:uppercase; }}
        .micro-kpi-value {{ color:#101828; font-size:1.05rem; font-weight:700; line-height:1.2; margin-top:.35rem; }}
        .micro-kpi-note {{ color:#98A2B3; font-size:.68rem; margin-top:.25rem; }}
        .micro-kpi.accent {{ border-top:3px solid var(--petronas-green); }}
        .micro-kpi.blue {{ border-top:3px solid var(--petronas-blue); }}
        .micro-kpi.lime {{ border-top:3px solid var(--petronas-lime); }}
        .micro-kpi.warning {{ border-top:3px solid var(--petronas-yellow); }}

        .status-strip {{
            display:flex; justify-content:space-between; align-items:center; gap:.7rem;
            padding:.62rem .8rem; border-radius:12px; background:rgba(0,161,156,.055);
            border:1px solid rgba(0,161,156,.11); margin:.4rem 0;
        }}
        .status-strip > span:first-child {{ color:#EAF7F6; }}
        .status-pill {{ padding:.2rem .5rem; border-radius:999px; font-size:.68rem; font-weight:700; letter-spacing:.02em; }}
        .status-pill.ready {{ background:rgba(52,211,153,.12); color:#A7F3D0; }}
        .status-pill.warn {{ background:rgba(251,191,36,.14); color:#FDE68A; }}
        .status-pill.error {{ background:rgba(248,113,113,.14); color:#FECACA; }}

        .decision-card {{
            background:linear-gradient(135deg,#102F37 0%,#124C55 100%); border-radius:18px;
            padding:1.25rem; color:#fff; box-shadow:0 10px 28px rgba(15,57,65,.13);
        }}
        .decision-card .label {{ color:rgba(255,255,255,.7); font-size:.68rem; font-weight:700; letter-spacing:.1em; text-transform:uppercase; }}
        .decision-card .value {{ font-size:1.7rem; font-weight:700; margin-top:.35rem; }}
        .decision-card .meta {{ color:rgba(255,255,255,.78); font-size:.77rem; margin-top:.35rem; }}

        .insight-card {{ border-radius:15px; padding:.9rem 1rem; border:1px solid var(--atlas-border); background:#fff; min-height:102px; }}
        .insight-tag {{ display:inline-block; font-size:.63rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--petronas-purple); margin-bottom:.25rem; }}
        .insight-title {{ color:#162F38; font-weight:700; font-size:.88rem; }}
        .insight-body {{ color:var(--atlas-muted); font-size:.76rem; margin-top:.2rem; line-height:1.45; }}

        .context-bar {{
            display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:.75rem 1rem;
            background:#fff; border:1px solid var(--atlas-border); border-radius:14px;
            box-shadow:0 4px 14px rgba(16,24,40,.03); margin-bottom:1rem;
        }}
        .context-label {{ color:#98A2B3; font-size:.64rem; font-weight:700; text-transform:uppercase; letter-spacing:.08em; }}
        .context-value {{ color:#152D36; font-size:.92rem; font-weight:700; margin-top:.15rem; }}

        /* Streamlit controls: readable dark text on light inputs. */
        div[data-testid="stButton"] > button,
        div[data-testid="stDownloadButton"] > button {{
            border-radius:10px; min-height:2.5rem; font-weight:600;
            border:1px solid #D0D5DD; background:#fff; color:#182230;
        }}
        div[data-testid="stButton"] > button:hover,
        div[data-testid="stDownloadButton"] > button:hover {{
            border-color:#98A2B3; background:#F9FAFB; color:#101828;
        }}
        div[data-testid="stButton"] > button[kind="primary"] {{
            background:var(--petronas-green); border-color:var(--petronas-green); color:#fff;
            box-shadow:0 4px 10px rgba(0,161,156,.15);
        }}
        div[data-testid="stButton"] > button[kind="primary"]:hover {{ background:#008F89; border-color:#008F89; color:#fff; }}

        /* Inputs / menus / text: avoid low-contrast browser defaults. */
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="base-input"] > div,
        div[data-baseweb="textarea"] > div {{
            background:#fff; border-color:#D0D5DD; color:#182230;
        }}
        div[data-baseweb="select"] span,
        div[data-baseweb="input"] input,
        div[data-baseweb="textarea"] textarea {{ color:#182230 !important; }}
        [data-baseweb="popover"] {{ background:#fff; }}
        [role="option"] {{ color:#182230 !important; background:#fff; }}
        [role="option"][aria-selected="true"] {{ background:#EAF7F6 !important; color:#0F4B4A !important; }}
        input::placeholder, textarea::placeholder {{ color:#98A2B3 !important; opacity:1; }}
        label, [data-testid="stWidgetLabel"] p {{ color:#344054 !important; font-weight:600; }}
        .stMarkdown, .stCaption, .stText {{ color:#344054; }}
        [data-testid="stMetricValue"] {{ color:#101828 !important; }}
        [data-testid="stMetricLabel"] {{ color:#667085 !important; }}
        [data-testid="stDataFrame"] {{ border:1px solid var(--atlas-border); border-radius:12px; overflow:hidden; }}
        .stExpander {{ border:1px solid var(--atlas-border); border-radius:14px; background:#fff; }}
        .stExpander summary p {{ color:#182230 !important; font-weight:700; }}
        .stTabs [role="tablist"] {{ gap:.25rem; border-bottom:1px solid var(--atlas-border); }}

        /* Backward-compatible legacy card classes used by older analytics code. */
        .exec-kpi-card {{
            background:#fff !important; border:1px solid var(--atlas-border); border-radius:16px;
            padding:1rem 1.05rem; min-height:112px; box-shadow:0 5px 18px rgba(16,24,40,.035);
            border-left:4px solid var(--petronas-green);
        }}
        .exec-kpi-label {{ color:#667085 !important; font-size:.68rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; margin-bottom:.45rem; }}
        .exec-kpi-value {{ color:#101828 !important; font-size:1.65rem; font-weight:700; line-height:1.05; }}
        .exec-kpi-subtext {{ color:#667085 !important; font-size:.74rem; margin-top:.42rem; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

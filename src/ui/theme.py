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
TEXT = "#1F2937"
MUTED = "#64748B"
BORDER = "#E2E8F0"
SURFACE = "#F8FAFC"
DANGER = "#C2410C"
SUCCESS = "#15803D"


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
        }}

        html, body, [class*="css"] {{
            font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
        }}

        .stApp {{
            background: #ffffff;
            color: var(--atlas-text);
        }}

        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #0F2F38 0%, #0D2630 100%);
            border-right: 1px solid rgba(255,255,255,0.08);
        }}

        [data-testid="stSidebar"] > div:first-child {{
            padding-top: 1rem;
        }}

        [data-testid="stSidebar"] * {{
            color: #E5F7F6;
        }}

        .block-container {{
            max-width: 1500px;
            padding-top: 1.1rem;
            padding-bottom: 2.2rem;
        }}

        .atlas-brand {{
            display:flex;
            align-items:center;
            gap:.75rem;
            padding:.35rem .25rem 1rem;
        }}
        .atlas-brand-mark {{
            width:38px;
            height:38px;
            border-radius:11px;
            background: linear-gradient(135deg, var(--petronas-green), var(--petronas-lime));
            display:flex;
            align-items:center;
            justify-content:center;
            color:#fff;
            font-weight:700;
            font-size:1rem;
            box-shadow:0 8px 20px rgba(0,161,156,.22);
        }}
        .atlas-brand-title {{
            font-size:1rem;
            font-weight:700;
            letter-spacing:.02em;
        }}
        .atlas-brand-subtitle {{
            font-size:.7rem;
            color:rgba(229,247,246,.68);
            margin-top:.1rem;
        }}

        .nav-section-label {{
            margin:.85rem .25rem .35rem;
            font-size:.67rem;
            font-weight:700;
            letter-spacing:.11em;
            text-transform:uppercase;
            color:rgba(229,247,246,.45);
        }}

        .page-kicker {{
            color: var(--petronas-green);
            font-size:.72rem;
            font-weight:700;
            letter-spacing:.11em;
            text-transform:uppercase;
            margin-bottom:.25rem;
        }}
        .page-title {{
            font-size:2rem;
            line-height:1.12;
            font-weight:700;
            color:#102A32;
            margin:0;
        }}
        .page-subtitle {{
            color:var(--atlas-muted);
            font-size:.93rem;
            margin-top:.4rem;
            margin-bottom:1.1rem;
        }}

        .atlas-card {{
            background:var(--atlas-surface);
            border:1px solid var(--atlas-border);
            border-radius:16px;
            padding:1rem 1.05rem;
            box-shadow:0 6px 18px rgba(15,23,42,.04);
        }}
        .atlas-card-white {{
            background:#fff;
            border:1px solid var(--atlas-border);
            border-radius:16px;
            padding:1rem 1.05rem;
            box-shadow:0 6px 18px rgba(15,23,42,.04);
        }}

        .kpi-card {{
            position:relative;
            background:#fff;
            border:1px solid var(--atlas-border);
            border-radius:16px;
            padding:1rem 1.05rem .95rem;
            min-height:112px;
            box-shadow:0 6px 18px rgba(15,23,42,.04);
            overflow:hidden;
        }}
        .kpi-card::before {{
            content:"";
            position:absolute;
            left:0;
            top:0;
            bottom:0;
            width:4px;
            background:var(--petronas-green);
        }}
        .kpi-label {{
            color:var(--atlas-muted);
            font-size:.7rem;
            font-weight:700;
            letter-spacing:.08em;
            text-transform:uppercase;
        }}
        .kpi-value {{
            color:#0F2932;
            font-size:1.75rem;
            line-height:1;
            font-weight:700;
            margin-top:.55rem;
        }}
        .kpi-note {{
            color:var(--atlas-muted);
            font-size:.76rem;
            margin-top:.45rem;
        }}

        .status-strip {{
            display:flex;
            justify-content:space-between;
            align-items:center;
            gap:.7rem;
            padding:.65rem .8rem;
            border-radius:12px;
            background:rgba(0,161,156,.08);
            border:1px solid rgba(0,161,156,.12);
            margin:.4rem 0;
        }}
        .status-dot {{
            width:8px;
            height:8px;
            border-radius:50%;
            background:var(--petronas-lime);
            box-shadow:0 0 0 4px rgba(191,215,48,.12);
        }}

        .section-title {{
            color:#132E37;
            font-size:1.05rem;
            font-weight:700;
            margin:.2rem 0 .65rem;
        }}
        .section-caption {{
            color:var(--atlas-muted);
            font-size:.82rem;
            margin-top:-.35rem;
            margin-bottom:.75rem;
        }}

        .decision-card {{
            background:linear-gradient(135deg, #0F3941 0%, #124D56 100%);
            border-radius:18px;
            padding:1.25rem;
            color:#fff;
            box-shadow:0 10px 28px rgba(15,57,65,.16);
        }}
        .decision-card .label {{
            color:rgba(255,255,255,.68);
            font-size:.7rem;
            font-weight:700;
            letter-spacing:.1em;
            text-transform:uppercase;
        }}
        .decision-card .value {{
            font-size:1.75rem;
            font-weight:700;
            margin-top:.35rem;
        }}
        .decision-card .meta {{
            color:rgba(255,255,255,.78);
            font-size:.78rem;
            margin-top:.35rem;
        }}

        .insight-card {{
            border-radius:15px;
            padding:.9rem 1rem;
            border:1px solid var(--atlas-border);
            background:#fff;
            min-height:102px;
        }}
        .insight-tag {{
            display:inline-block;
            font-size:.64rem;
            font-weight:700;
            letter-spacing:.08em;
            text-transform:uppercase;
            color:var(--petronas-purple);
            margin-bottom:.25rem;
        }}
        .insight-title {{
            color:#162F38;
            font-weight:700;
            font-size:.88rem;
        }}
        .insight-body {{
            color:var(--atlas-muted);
            font-size:.76rem;
            margin-top:.2rem;
            line-height:1.45;
        }}

        .context-bar {{
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:1rem;
            padding:.75rem 1rem;
            background:#fff;
            border:1px solid var(--atlas-border);
            border-radius:14px;
            box-shadow:0 4px 14px rgba(15,23,42,.04);
            margin-bottom:1rem;
        }}
        .context-label {{
            color:var(--atlas-muted);
            font-size:.65rem;
            font-weight:700;
            text-transform:uppercase;
            letter-spacing:.08em;
        }}
        .context-value {{
            color:#12313A;
            font-size:.92rem;
            font-weight:700;
            margin-top:.15rem;
        }}

        .atlas-divider {{
            height:1px;
            background:var(--atlas-border);
            margin:1.15rem 0;
        }}

        div[data-testid="stButton"] > button[kind="primary"] {{
            background:var(--petronas-green);
            border-color:var(--petronas-green);
            color:white;
            border-radius:10px;
            font-weight:700;
        }}
        div[data-testid="stButton"] > button[kind="primary"]:hover {{
            background:#008F89;
            border-color:#008F89;
        }}

        [data-testid="stMetricValue"] {{
            color:#12313A;
        }}

        .stTabs [role="tablist"] {{
            gap:.25rem;
            border-bottom:1px solid var(--atlas-border);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

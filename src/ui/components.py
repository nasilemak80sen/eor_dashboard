"""Reusable UI primitives for EOR Atlas."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

import streamlit as st

from ui.theme import PETRONAS_GREEN, PETRONAS_LIME, PETRONAS_PURPLE, PETRONAS_YELLOW, MUTED


def _materialize(items: Iterable[Any]) -> list[Any]:
    return list(items)


def page_header(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="page-kicker">{kicker}</div><div class="page-title">{title}</div><div class="page-subtitle">{subtitle}</div>',
        unsafe_allow_html=True,
    )


def section_title(title: str, caption: str | None = None) -> None:
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if caption:
        st.markdown(f'<div class="section-caption">{caption}</div>', unsafe_allow_html=True)


def kpi_cards(items: Iterable[tuple[str, Any, str | None]]) -> None:
    materialized = _materialize(items)
    if not materialized:
        return
    cols = st.columns(len(materialized))
    for col, (label, value, note) in zip(cols, materialized):
        with col:
            note_html = f'<div class="kpi-note">{note}</div>' if note else ''
            st.markdown(
                f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div>{note_html}</div>',
                unsafe_allow_html=True,
            )


def status_badge(label: str, ready: bool) -> str:
    cls = "ready" if ready else "warn"
    state = "READY" if ready else "CHECK"
    return f'<span class="status-pill {cls}">{label}: {state}</span>'


def status_grid(items: Iterable[tuple[str, bool]]) -> None:
    for label, ready in items:
        color = PETRONAS_LIME if ready else PETRONAS_YELLOW
        st.markdown(
            f'<div class="status-strip"><span>●&nbsp; {label}</span><span style="color:{color};font-weight:700;">{"READY" if ready else "CHECK"}</span></div>',
            unsafe_allow_html=True,
        )


def insight_cards(items: Iterable[tuple[str, str, str]]) -> None:
    materialized = _materialize(items)
    if not materialized:
        return
    cols = st.columns(len(materialized))
    for col, (tag, title, body) in zip(cols, materialized):
        with col:
            st.markdown(
                f'<div class="insight-card"><div class="insight-tag">{tag}</div><div class="insight-title">{title}</div><div class="insight-body">{body}</div></div>',
                unsafe_allow_html=True,
            )


def context_bar(field: str | None, reservoir: str | None, extra: Mapping[str, Any] | None = None) -> None:
    if not field and not reservoir:
        return
    identity = " / ".join(x for x in [field, reservoir] if x)
    pieces = [f"{label} {value}" for label, value in (extra or {}).items() if value is not None and value != ""]
    right = " · ".join(pieces)
    st.markdown(
        f'<div class="context-bar"><div><div class="context-label">Selected Reservoir</div><div class="context-value">{identity}</div></div><div style="color:{MUTED};font-size:.76rem;">{right}</div></div>',
        unsafe_allow_html=True,
    )

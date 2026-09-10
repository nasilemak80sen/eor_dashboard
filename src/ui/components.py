"""Reusable UI primitives for EOR Atlas."""

from __future__ import annotations

from html import escape
from typing import Any, Iterable, Mapping

import streamlit as st

from ui.theme import MUTED, PETRONAS_GREEN, PETRONAS_LIME, PETRONAS_PURPLE, PETRONAS_YELLOW


def _materialize(items: Iterable[Any]) -> list[Any]:
    return list(items)


def _display(value: Any) -> str:
    if value is None:
        return "—"
    return escape(str(value))


def page_header(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="page-kicker">{escape(kicker)}</div><div class="page-title">{escape(title)}</div><div class="page-subtitle">{escape(subtitle)}</div>',
        unsafe_allow_html=True,
    )


def section_title(title: str, caption: str | None = None) -> None:
    st.markdown(f'<div class="section-title">{escape(title)}</div>', unsafe_allow_html=True)
    if caption:
        st.markdown(f'<div class="section-caption">{escape(caption)}</div>', unsafe_allow_html=True)


def kpi_cards(items: Iterable[tuple[str, Any, str | None]]) -> None:
    materialized = _materialize(items)
    if not materialized:
        return
    cols = st.columns(len(materialized))
    for col, (label, value, note) in zip(cols, materialized):
        with col:
            note_html = f'<div class="kpi-note">{escape(str(note))}</div>' if note else ""
            st.markdown(
                f'<div class="kpi-card"><div class="kpi-label">{escape(label)}</div><div class="kpi-value">{_display(value)}</div>{note_html}</div>',
                unsafe_allow_html=True,
            )


def metric_cards(items: Iterable[tuple[str, Any, str | None]], columns: int | None = None, tone: str = "accent") -> None:
    """Render compact, high-contrast KPI cards for contextual engineering metrics."""
    materialized = _materialize(items)
    if not materialized:
        return
    ncols = max(1, min(columns or len(materialized), 6))
    cols = st.columns(ncols)
    for index, (label, value, note) in enumerate(materialized):
        with cols[index % ncols]:
            note_html = f'<div class="micro-kpi-note">{escape(str(note))}</div>' if note else ""
            st.markdown(
                f'<div class="micro-kpi {escape(tone)}"><div class="micro-kpi-label">{escape(label)}</div><div class="micro-kpi-value">{_display(value)}</div>{note_html}</div>',
                unsafe_allow_html=True,
            )


def detail_metric_cards(
    items: Iterable[tuple[str, Any, str | None]],
    columns: int = 4,
    highlight_labels: Iterable[str] | None = None,
) -> None:
    """Render detail records as readable metric cards, optionally highlighting important values."""
    highlights = set(highlight_labels or [])
    materialized = _materialize(items)
    if not materialized:
        return
    ncols = max(1, min(columns, 6))
    cols = st.columns(ncols)
    for index, (label, value, note) in enumerate(materialized):
        tone = "accent" if label in highlights else ""
        with cols[index % ncols]:
            note_html = f'<div class="micro-kpi-note">{escape(str(note))}</div>' if note else ""
            st.markdown(
                f'<div class="micro-kpi {tone}"><div class="micro-kpi-label">{escape(label)}</div><div class="micro-kpi-value">{_display(value)}</div>{note_html}</div>',
                unsafe_allow_html=True,
            )


def reset_page_state(
    prefixes: str | Iterable[str],
    result_keys: Iterable[str] = (),
) -> bool:
    """Clear only the widget/result state owned by the current page."""
    prefix_tuple = (prefixes,) if isinstance(prefixes, str) else tuple(prefixes)
    changed = False
    for key in list(st.session_state.keys()):
        if any(str(key).startswith(prefix) for prefix in prefix_tuple):
            del st.session_state[key]
            changed = True
    for key in result_keys:
        if key in st.session_state:
            st.session_state.pop(key, None)
            changed = True
    return changed


def reset_button(label: str, prefixes: str | Iterable[str], result_keys: Iterable[str] = (), key: str = "reset_page") -> None:
    """Render a consistent local page reset action and rerun after clearing state."""
    if st.button(label, key=key, use_container_width=True, type="secondary"):
        reset_page_state(prefixes, result_keys)
        st.rerun()


def page_tabs(labels: Iterable[str]):
    """Create consistent contextual tabs for a page workflow."""
    return st.tabs(list(labels))


def status_badge(label: str, ready: bool) -> str:
    cls = "ready" if ready else "warn"
    state = "READY" if ready else "CHECK"
    return f'<span class="status-pill {cls}">{escape(label)}: {state}</span>'


def status_grid(items: Iterable[tuple[str, bool]]) -> None:
    for label, ready in items:
        color = PETRONAS_LIME if ready else PETRONAS_YELLOW
        st.markdown(
            f'<div class="status-strip"><span>{escape(label)}</span><span style="color:{color};font-weight:700;">{"READY" if ready else "CHECK"}</span></div>',
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
                f'<div class="insight-card"><div class="insight-tag">{escape(tag)}</div><div class="insight-title">{escape(title)}</div><div class="insight-body">{escape(body)}</div></div>',
                unsafe_allow_html=True,
            )


def context_bar(field: str | None, reservoir: str | None, extra: Mapping[str, Any] | None = None) -> None:
    if not field and not reservoir:
        return
    identity = " / ".join(x for x in [field, reservoir] if x)
    pieces = [f"{label} {value}" for label, value in (extra or {}).items() if value is not None and value != ""]
    right = " · ".join(pieces)
    st.markdown(
        f'<div class="context-bar"><div><div class="context-label">Selected Reservoir</div><div class="context-value">{escape(identity)}</div></div><div style="color:{MUTED};font-size:.76rem;">{escape(right)}</div></div>',
        unsafe_allow_html=True,
    )

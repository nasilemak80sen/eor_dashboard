"""Reusable UI primitives for EOR Atlas."""

from __future__ import annotations

from copy import deepcopy
from html import escape
import re
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


def workflow_steps(steps: Iterable[str], current_step: int = 0) -> None:
    materialized = list(steps)
    if not materialized:
        return

    html = ['<div class="atlas-workflow">']
    for index, step in enumerate(materialized):
        state = "complete" if index < current_step else "active" if index == current_step else "pending"
        html.append(
            f'<div class="atlas-workflow-step {state}"><span class="atlas-workflow-index">{index + 1}</span><span>{escape(step)}</span></div>'
        )
    html.append('</div>')
    st.markdown("".join(html), unsafe_allow_html=True)


def render_decision_summary(title: str, subtitle: str, status: str, details: Iterable[tuple[str, Any]]) -> None:
    items = list(details)
    body = "".join(
        f'<div class="decision-detail"><span>{escape(str(label))}</span><strong>{escape(_display(value))}</strong></div>'
        for label, value in items
    )
    st.markdown(
        f'''
        <div class="decision-summary-card">
            <div class="decision-summary-header">
                <div>
                    <div class="decision-summary-kicker">Decision summary</div>
                    <div class="decision-summary-title">{escape(title)}</div>
                </div>
                <span class="decision-summary-status {escape(status.lower())}">{escape(status)}</span>
            </div>
            <div class="decision-summary-subtitle">{escape(subtitle)}</div>
            <div class="decision-detail-grid">{body}</div>
        </div>
        ''',
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



def render_detail_drawer(title: str, subtitle: str, details: Iterable[tuple[str, Any]], *, columns: int = 2) -> None:
    """Render a reusable right-column detail drawer without changing source data."""
    materialized = list(details)
    with st.container(border=True):
        st.markdown(f"#### {escape(title)}")
        if subtitle:
            st.caption(subtitle)
        ncols = max(1, min(int(columns), 4))
        cells = st.columns(ncols)
        for index, (label, value) in enumerate(materialized):
            with cells[index % ncols]:
                st.markdown(
                    f'<div class="atlas-detail-label">{escape(str(label))}</div>'
                    f'<div class="atlas-detail-value">{_display(value)}</div>',
                    unsafe_allow_html=True,
                )


def render_evidence_provenance(*, source_name: str, worksheets: Iterable[str] | str | None = None,
                               evidence_scope: str | None = None, field_attribution: str | None = None,
                               source_reference: str | None = None, note: str | None = None) -> None:
    """Render source facts supplied by the loader; never infer missing provenance."""
    sheet_values = [worksheets] if isinstance(worksheets, str) else list(worksheets or [])
    sheet_text = ", ".join(str(item) for item in sheet_values if item) or "Not specified"
    reference = str(source_reference).strip() if source_reference else ""
    if reference:
        reference = reference[:16] + ("…" if len(reference) > 16 else "")
    with st.container(border=True):
        st.markdown("**Evidence provenance**")
        st.caption("Source metadata supplied by the active evidence loader.")
        meta_cols = st.columns(2)
        with meta_cols[0]:
            st.markdown("**Source workbook**")
            st.write(source_name or "Not specified")
            st.markdown("**Worksheets**")
            st.write(sheet_text)
        with meta_cols[1]:
            st.markdown("**Evidence scope**")
            st.write(evidence_scope or "Not specified")
            st.markdown("**Field attribution**")
            st.write(field_attribution or "See source-level field tags")
        if reference:
            st.caption(f"Source SHA-256 prefix: {reference}")
        if note:
            st.info(note)


def render_saved_filter_controls(scope: str, widget_keys: Iterable[str]) -> None:
    """Manage named filter snapshots for this Streamlit session.

    Phase 1 presets are session-scoped, not shared across users or durable
    across a new session or server restart.
    """
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", str(scope)).strip("_").lower() or "default"
    storage_key = f"atlas_saved_filters_{slug}"
    presets = st.session_state.setdefault(storage_key, {})
    keys = tuple(widget_keys)
    with st.expander("Saved filters", expanded=False):
        name = st.text_input("Preset name", key=f"{storage_key}_name", placeholder="e.g. Mature carbonate candidates")
        if st.button("Save current filters", key=f"{storage_key}_save"):
            snapshot = {key: deepcopy(st.session_state[key]) for key in keys if key in st.session_state}
            if not name.strip():
                st.warning("Enter a name for this filter preset.")
            elif not snapshot:
                st.warning("Set at least one filter before saving a preset.")
            else:
                presets[name.strip()] = snapshot
                st.session_state[storage_key] = presets
                st.success(f"Saved filter preset: {name.strip()}")
        if presets:
            selected_name = st.selectbox("Available presets", sorted(presets), key=f"{storage_key}_selected")
            apply_col, delete_col = st.columns(2)
            with apply_col:
                if st.button("Apply preset", key=f"{storage_key}_apply", type="primary"):
                    for key, value in presets[selected_name].items():
                        st.session_state[key] = deepcopy(value)
                    st.rerun()
            with delete_col:
                if st.button("Delete preset", key=f"{storage_key}_delete"):
                    presets.pop(selected_name, None)
                    st.session_state[storage_key] = presets
                    st.rerun()
        else:
            st.caption("No presets saved in this session yet.")

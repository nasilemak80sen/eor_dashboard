"""Local EOR Atlas UI/UX proof of concept.

Run with: streamlit run src/eor_atlas_poc.py --server.address 127.0.0.1
This entry point uses local SQLite only for demo accounts. Engineering results are
kept in Streamlit session state and are not persisted by POC workflows.
"""
from __future__ import annotations

import os

# The existing UI pages use this flag to disable screening/history writes.
os.environ["EOR_POC_MODE"] = "1"

import streamlit as st

import eor_atlas as atlas
from auth.local_auth import logout_local_user, render_auth_gate
from config.settings import settings


def _render_poc_history() -> None:
    """Show sample history without opening or migrating the engineering database."""
    st.subheader("Example run history")
    st.caption("Synthetic records are shown to design the read-only history experience. This page does not query or write the engineering history database.")
    st.info("Sample data only · not real reservoir cases · no new records are created.")
    st.dataframe(
        [
            {"Run ID": "POC-1001", "Timestamp": "2026-10-20 09:15", "Formation": "Sandstone", "Mode": "Engineering", "Example technique": "Polymer", "Status": "SYNTHETIC"},
            {"Run ID": "POC-1002", "Timestamp": "2026-10-18 14:40", "Formation": "Carbonate", "Mode": "Hybrid", "Example technique": "Miscible CO2", "Status": "SYNTHETIC"},
            {"Run ID": "POC-1003", "Timestamp": "2026-10-14 11:05", "Formation": "Unconsolidated sands", "Mode": "Engineering", "Example technique": "Steam", "Status": "SYNTHETIC"},
        ],
        use_container_width=True,
        hide_index=True,
    )
    with st.expander("History workflow notes"):
        st.markdown("- Existing records are viewed only.\n- New screening submissions remain in session memory.\n- Enterprise history/API integration is intentionally out of scope for this POC.")


def main() -> None:
    st.set_page_config(
        page_title="EOR Atlas · UI/UX POC",
        page_icon=settings.ui_config["page_icon"],
        layout="wide",
        initial_sidebar_state="expanded",
    )

    username = st.session_state.get("local_poc_username")
    if not username:
        render_auth_gate()
        st.stop()

    # Authenticated UI reruns do not issue any API requests.
    atlas.initialize_ui()
    with st.sidebar:
        st.markdown("### Local POC session")
        st.caption(f"Signed in as **{username}**")
        st.caption("SQLite local account · UI/UX proof of concept")
        if st.button("Sign out", key="poc_sign_out", use_container_width=True):
            logout_local_user()

    services = atlas._safe_services()
    page = atlas.select_page(atlas._system_state(services))
    atlas.render_shell_header()
    st.info("UI/UX POC · Local account login · Streamlit uses the existing Python services on submit; new screening and hybrid results remain in session memory and are not written to the engineering history database.", icon="🧪")
    kicker, title, subtitle = atlas.PAGE_META.get(page, atlas.PAGE_META["overview"])
    atlas.render_page_intro(kicker, title, subtitle)
    if page == "historical":
        _render_poc_history()
    else:
        atlas._render_page(page, services)


if __name__ == "__main__":
    main()

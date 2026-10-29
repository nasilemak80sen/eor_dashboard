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
    kicker, title, subtitle = atlas.PAGE_META.get(page, atlas.PAGE_META["overview"])
    atlas.render_page_intro(kicker, title, subtitle)
    atlas._render_page(page, services)


if __name__ == "__main__":
    main()

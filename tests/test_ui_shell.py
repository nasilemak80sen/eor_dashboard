import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hybrid_app_direct_entrypoint_delegates_to_eor_atlas():
    source = (ROOT / "src" / "hybrid_app.py").read_text(encoding="utf-8")
    assert "from eor_atlas import main as atlas_main" in source
    assert "_app.render_executive_overview_section()" not in source
    assert "tabs = st.tabs(" not in source


def test_eor_atlas_does_not_depend_on_private_hybrid_app_internals():
    source = (ROOT / "src" / "eor_atlas.py").read_text(encoding="utf-8")
    assert "engine._app" not in source
    assert 'logging.getLogger("eor_atlas")' in source
    assert "st.exception(exc)" in source


def test_new_ui_entrypoint_exists():
    assert (ROOT / "src" / "eor_atlas.py").exists()


def test_theme_has_high_contrast_controls_and_metric_tiles():
    source = (ROOT / "src" / "ui" / "theme.py").read_text(encoding="utf-8")
    assert "background:#fff;color:#182230" in source
    assert '[data-testid="stMetric"]' in source
    assert "--atlas-text:#111827" in source
    assert ".exec-kpi-card" in source


def test_decision_pages_use_submit_driven_forms():
    screening = (ROOT / "src" / "pages_ui" / "screening.py").read_text(encoding="utf-8")
    intelligence = (ROOT / "src" / "pages_ui" / "intelligence.py").read_text(encoding="utf-8")
    assert 'st.form("screening_reservoir_form"' in screening
    assert "st.form_submit_button(" in screening
    assert 'st.form("hybrid_reservoir_form"' in intelligence
    assert "st.form_submit_button(" in intelligence


def test_legacy_app_is_import_safe():
    source = (ROOT / "src" / "app_2.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    top_level_streamlit_calls = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                if isinstance(child.func.value, ast.Name) and child.func.value.id == "st":
                    top_level_streamlit_calls.append(child.func.attr)

    assert "set_page_config" not in top_level_streamlit_calls
    assert "markdown" not in top_level_streamlit_calls
    assert "def configure_legacy_page()" in source
    assert "configure_legacy_page()" in source


def test_production_entrypoint_configures_streamlit_before_rendering():
    source = (ROOT / "src" / "eor_atlas.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")

    first_stmt = main.body[0]
    assert isinstance(first_stmt, ast.Expr)
    assert isinstance(first_stmt.value, ast.Call)
    assert isinstance(first_stmt.value.func, ast.Attribute)
    assert isinstance(first_stmt.value.func.value, ast.Name)
    assert first_stmt.value.func.value.id == "st"
    assert first_stmt.value.func.attr == "set_page_config"


def test_application_services_are_cached_across_reruns():
    source = (ROOT / "src" / "eor_atlas.py").read_text(encoding="utf-8")
    assert "@st.cache_resource(show_spinner=False)" in source
    assert "def _safe_services()" in source


def test_top_navigation_uses_buttons_not_radio():
    navigation = (ROOT / "src" / "ui" / "navigation.py").read_text(encoding="utf-8")
    shell = (ROOT / "src" / "ui" / "app_shell.py").read_text(encoding="utf-8")
    assert "st.button(" in navigation
    assert "st.radio(" not in navigation
    assert "render_top_nav()" in shell


def test_sidebar_starts_expanded_for_primary_navigation():
    settings = (ROOT / "src" / "config" / "settings.py").read_text(encoding="utf-8")
    assert '"initial_sidebar_state": "expanded"' in settings


def test_r_and_d_navigation_routes_to_new_page():
    navigation = (ROOT / "src" / "ui" / "navigation.py").read_text(encoding="utf-8")
    app = (ROOT / "src" / "eor_atlas.py").read_text(encoding="utf-8")
    assert 'NavItem("ceor", "R&D", "🧪")' in navigation
    assert "from pages_ui import challenges, ceor, rd," in app
    assert '"ceor": rd.render' in app


def test_r_and_d_page_routes_ceor_by_field_without_a_legacy_expander():
    page = (ROOT / "src" / "pages_ui" / "rd.py").read_text(encoding="utf-8")
    assert 'options=["CEOR", "WAG"]' in page
    assert 'st.tabs(["Fluid–Fluid", "Fluid–Rock"])' in page
    assert 'st.selectbox(\n        "Field"' in page
    assert "_render_fluid_fluid(field_data)" in page
    assert "_render_fluid_rock(field_data)" in page
    assert "Legacy CEOR evidence" not in page
    assert "render_legacy_ceor" not in page
    assert "Other · field mapping incomplete" in page


def test_r_and_d_data_loader_preserves_source_ift_bounds():
    loader = (ROOT / "src" / "data" / "rd_lab_evidence.py").read_text(encoding="utf-8")
    assert '"IFT low (source)"' in loader
    assert '"IFT high (source)"' in loader
    assert "ift_polymer_reversed_bounds" in loader


def test_ceor_field_options_include_all_fields_without_duplicate_field_values():
    from pages_ui.rd import _ceor_field_options, ALL_FIELDS_LABEL, OTHER_FIELD_LABEL

    options = _ceor_field_options(
        ["Angsi", "D18", "St. Joseph", "Temana", "St Joseph"],
        include_other=True,
    )
    assert options == [
        ALL_FIELDS_LABEL,
        "St. Joseph",
        "Angsi",
        "D18",
        "Temana",
        OTHER_FIELD_LABEL,
    ]


def test_ceor_all_fields_view_keeps_each_field_and_source_separate():
    page = (ROOT / "src" / "pages_ui" / "rd.py").read_text(encoding="utf-8")
    assert 'if selected_field == ALL_FIELDS_LABEL:' in page
    assert "def _render_ceor_all_fields(" in page
    assert "_render_thermal_all_fields(thermal)" in page
    assert "Colour identifies the source field" in page
    assert "EOR_Screening_Tool_2026.xlsx. Records are kept separate" in page



def test_sidebar_navigation_is_grouped_and_preserves_route_keys():
    navigation = (ROOT / "src" / "ui" / "navigation.py").read_text(encoding="utf-8")
    assert "NAV_GROUPS" in navigation
    assert '"WORKSPACE"' in navigation
    assert '"ENGINEERING"' in navigation
    assert '"KNOWLEDGE & R&D"' in navigation
    assert '"GOVERNANCE"' in navigation
    assert 'st.session_state["atlas_page"] = selected' in navigation


def test_global_search_uses_loaded_workbook_and_does_not_initialize_backend():
    shell = (ROOT / "src" / "ui" / "app_shell.py").read_text(encoding="utf-8")
    assert "def _search_catalog(" in shell
    assert 'workbook.get("PROP_updatedNov25_v2")' in shell
    assert 'st.session_state["candidate_global_search_selection"]' in shell
    assert "render_shell_header(services)" in (ROOT / "src" / "eor_atlas.py").read_text(encoding="utf-8")


def test_shared_ux_primitives_exist_and_saved_filters_are_session_scoped():
    components = (ROOT / "src" / "ui" / "components.py").read_text(encoding="utf-8")
    assert "def render_detail_drawer(" in components
    assert "def render_evidence_provenance(" in components
    assert "def render_saved_filter_controls(" in components
    assert "session-scoped" in components


def test_candidate_filter_presets_and_detail_drawer_are_integrated():
    candidate = (ROOT / "src" / "candidate_analytics" / "ui.py").read_text(encoding="utf-8")
    assert "render_saved_filter_controls(" in candidate
    assert "render_detail_drawer(" in candidate
    assert "candidate_global_search_selection" in candidate


def test_r_and_d_pages_render_source_provenance_without_rewriting_charts():
    page = (ROOT / "src" / "pages_ui" / "rd.py").read_text(encoding="utf-8")
    assert "render_evidence_provenance(" in page
    assert "def _render_wag_performance(" in page
    assert "def _render_fluid_fluid(" in page
    assert 'st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})' in page



def test_ceor_provenance_uses_the_loader_sheet_names_metadata():
    page = (ROOT / "src" / "pages_ui" / "rd.py").read_text(encoding="utf-8")
    assert 'worksheets=metadata.get("sheet_names") or metadata.get("sheets")' in page


def test_global_reservoir_search_clears_only_candidate_live_filters():
    shell = (ROOT / "src" / "ui" / "app_shell.py").read_text(encoding="utf-8")
    assert '"candidate_injected_fluid"' in shell
    assert '"candidate_analytics_selected_reservoir"' in shell
    assert 'st.session_state["candidate_global_search_selection"]' in shell



def test_executive_overview_uses_hierarchical_kpis_and_clear_workflow_shortcuts():
    page = (ROOT / "src" / "pages_ui" / "overview.py").read_text(encoding="utf-8")
    assert "def _render_primary_kpis(" in page
    assert '"Fields", fields, "Portfolio coverage"' in page
    assert '"Reservoirs", reservoirs, "Screening universe"' in page
    assert '"RF Gap",' in page
    assert "Mapped fields" in page
    assert "EOR methods" in page
    assert "def _render_workflow_shortcuts(" in page
    assert '"screening",' in page
    assert '"intelligence",' in page


def test_executive_overview_keeps_existing_openglobus_configuration_and_full_visibility():
    page = (ROOT / "src" / "pages_ui" / "overview.py").read_text(encoding="utf-8")
    assert "render_openglobus_map(" in page
    assert 'latitude="Latitude"' in page
    assert 'longitude="Longitude"' in page
    assert 'name="Field"' in page
    assert 'value="Methods"' in page
    assert "height=620" in page
    assert "show_labels=False" in page
    assert "st.tabs(" not in page


def test_executive_overview_retains_rf_gap_chart_definition_and_rendering():
    page = (ROOT / "src" / "pages_ui" / "overview.py").read_text(encoding="utf-8")
    assert 'temp = df[["Field", "RF Gap"]].copy()' in page
    assert 'temp["RF Gap"] = pd.to_numeric(temp["RF Gap"], errors="coerce")' in page
    assert 'ranked = temp.dropna().groupby("Field")["RF Gap"].sum().sort_values(ascending=False).reset_index()' in page
    assert 'x=alt.X("RF Gap:Q", title="Aggregate RF Gap")' in page
    assert 'y=alt.Y("Field:N", sort="-x", title=None)' in page
    assert "st.altair_chart(chart, use_container_width=True)" in page
    assert ".properties(height=440).interactive()" in page



def test_executive_overview_distinguishes_loaded_map_source_from_usable_coordinates():
    page = (ROOT / "src" / "pages_ui" / "overview.py").read_text(encoding="utf-8")
    assert "map_source_available = isinstance(map_df, pd.DataFrame) and not map_df.empty" in page
    assert "map_ready = not mapped.empty" in page
    assert "int(map_df.shape[0])" in page



def test_candidates_page_uses_the_shared_workspace_header_and_live_map():
    page = (ROOT / "src" / "pages_ui" / "candidates.py").read_text(encoding="utf-8")
    analytics = (ROOT / "src" / "candidate_analytics" / "ui.py").read_text(encoding="utf-8")
    assert 'page_header(\n        "WORKSPACE / PORTFOLIO",\n        "Candidates",' in page
    assert "candidate_ui._render_candidate_map = _render_reactive_location_map" in page
    assert "render_field_reservoir_parameters_tab(show_header=False)" in page
    assert "st.tabs(" not in page
    assert "st.tabs(" not in analytics
    assert 'section_title(\n        "Portfolio geography",' in analytics
    assert 'section_title(\n        "Relationship explorer",' in analytics
    assert 'section_title(\n        "Reservoir register",' in analytics


def test_candidate_discovery_preserves_filter_keys_chart_map_and_detail_contracts():
    analytics = (ROOT / "src" / "candidate_analytics" / "ui.py").read_text(encoding="utf-8")
    page = (ROOT / "src" / "pages_ui" / "candidates.py").read_text(encoding="utf-8")

    for key in (
        "candidate_injected_fluid",
        "candidate_status",
        "candidate_api",
        "candidate_porosity",
        "candidate_perm",
        "candidate_temperature",
        "candidate_oil_column",
        "candidate_viscosity",
        "candidate_x_axis",
        "candidate_y_axis",
        "candidate_group_by",
        "candidate_analytics_selected_reservoir",
    ):
        assert f'"{key}"' in analytics

    assert "filtered = analysis.filter(" in analytics
    assert "injected_fluids=fluids" in analytics
    assert "statuses=statuses" in analytics
    assert "oil_api=api_range" in analytics
    assert "porosity=porosity_range" in analytics
    assert "permeability=permeability_range" in analytics
    assert "temperature_c=temperature_range" in analytics
    assert "oil_column=oil_column_range" in analytics
    assert "viscosity=viscosity_range" in analytics
    assert "_render_scatter(analysis, filtered, x_column, y_column, group_by)" in analytics

    assert "render_openglobus_map(" in page
    assert 'latitude="LATITUDE"' in page
    assert 'longitude="LONGITUDE"' in page
    assert 'name="Reservoir"' in page
    assert 'value="CR_Potential"' in page
    assert "height=620" in page
    assert "show_labels=False" in page
    assert "render_detail_drawer(" in analytics
    assert "candidate_global_search_selection" in analytics
    assert "render_saved_filter_controls(" in analytics


def test_candidate_scatter_and_location_implementations_remain_separate_from_layout():
    analytics = (ROOT / "src" / "candidate_analytics" / "ui.py").read_text(encoding="utf-8")
    page = (ROOT / "src" / "pages_ui" / "candidates.py").read_text(encoding="utf-8")
    assert ".mark_circle(opacity=0.72)" in analytics
    assert 'size=alt.Size(\n                    "CR Potential:Q"' in analytics
    assert ".properties(height=560)" in analytics
    assert "st.altair_chart(chart, use_container_width=True)" in analytics
    assert "render_openglobus_map(" in page
    assert 'camera_height=5000000 if focus != "All fields" else 12000000' in page



def test_screening_page_uses_a_guided_single_flow_and_preserves_submission_contract():
    page = (ROOT / "src" / "pages_ui" / "screening.py").read_text(encoding="utf-8")
    assert 'page_header(\n        "ENGINEERING WORKSPACE",\n        "EOR Screening",' in page
    assert 'st.form("screening_reservoir_form", clear_on_submit=False)' in page
    assert '_hybrid.render_eor_input_form("screening")' in page
    assert "st.form_submit_button(" in page
    assert "if submitted:" in page
    assert "_app.ExcelScreeningService().screen(inputs, formation)" in page
    assert "persist_engineering_run(inputs, formation, result)" in page
    assert 'st.session_state["excel_screening_result"] = result' in page
    assert 'st.session_state["screening_last_run"] = persist_engineering_run(inputs, formation, result)' in page
    assert "_app.render_excel_screening_result(result)" in page
    assert "workflow_steps(" in page
    assert "st.tabs(" not in page


def test_screening_gate_and_report_card_side_effects_are_inside_explicit_submit_guard():
    page = (ROOT / "src" / "pages_ui" / "screening.py").read_text(encoding="utf-8")
    tree = ast.parse(page)
    render = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "render"
    )
    parents = {
        child: parent
        for parent in ast.walk(render)
        for child in ast.iter_child_nodes(parent)
    }

    def inside_submit_guard(node):
        current = node
        while current in parents:
            current = parents[current]
            if isinstance(current, ast.If) and ast.dump(current.test) == ast.dump(ast.Name(id="submitted", ctx=ast.Load())):
                return True
        return False

    gate_calls = [
        node for node in ast.walk(render)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "screen"
        and isinstance(node.func.value, ast.Call)
        and isinstance(node.func.value.func, ast.Attribute)
        and node.func.value.func.attr == "ExcelScreeningService"
    ]
    save_calls = [
        node for node in ast.walk(render)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "persist_engineering_run"
    ]
    assert len(gate_calls) == 1
    assert len(save_calls) == 1
    assert inside_submit_guard(gate_calls[0])
    assert inside_submit_guard(save_calls[0])
    assert gate_calls[0].lineno < save_calls[0].lineno


def test_screening_result_summary_and_result_renderer_contracts_are_retained():
    page = (ROOT / "src" / "pages_ui" / "screening.py").read_text(encoding="utf-8")
    assert "def _screening_summary(result: dict | None)" in page
    assert 'str(item.get("Status", "")).upper() == "PASS"' in page
    assert 'str(item.get("Status", "")).upper() == "CONDITIONAL"' in page
    assert 'str(item.get("Status", "")).upper() == "FAIL (CRITICAL)"' in page
    assert "_app.render_excel_screening_result(result)" in page
    assert 'last_run["reference"]' in page

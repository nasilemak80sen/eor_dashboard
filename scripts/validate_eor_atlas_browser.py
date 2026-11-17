"""Browser-level EOR Atlas workspace and persistence smoke test.

Run against a live local Streamlit process with STREAMLIT_APP_URL configured.
Uses the checked-in production workbook/model artifacts and the CI-local SQLite
database; CI workspace mutations are discarded with the runner.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


APP_URL = os.environ.get("STREAMLIT_APP_URL", "http://127.0.0.1:8501")
ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "eor_atlas.db"
REPORTS = ROOT / "reports"


def _run_count() -> int:
    """Read the durable screening row count without creating application state."""
    if not DATABASE.is_file():
        return 0
    with sqlite3.connect(DATABASE, timeout=15) as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='screening_runs'"
        ).fetchone()
        if not exists:
            return 0
        return int(connection.execute("SELECT COUNT(*) FROM screening_runs").fetchone()[0])


def _latest_run() -> tuple[int, str]:
    with sqlite3.connect(DATABASE, timeout=15) as connection:
        row = connection.execute(
            "SELECT id, recommendation_mode FROM screening_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise AssertionError("No screening report card was persisted.")
    return int(row[0]), str(row[1] or "")


def _assert_workspace(page, expected_title: str, screenshot_name: str) -> None:
    title = page.locator(".page-title").filter(has_text=expected_title).last
    title.wait_for(state="visible", timeout=60_000)
    body = page.locator("body").inner_text()
    failure_markers = (
        "page could not be rendered",
        "Candidate analytics could not be rendered",
        "Candidate analytics could not load the workbook",
    )
    for marker in failure_markers:
        if marker.lower() in body.lower():
            raise AssertionError(f"Workspace '{expected_title}' displayed: {marker}")
    if page.locator('[data-testid="stException"]').count():
        raise AssertionError(f"Workspace '{expected_title}' raised a Streamlit exception.")
    REPORTS.mkdir(exist_ok=True)
    page.screenshot(path=str(REPORTS / screenshot_name), full_page=True)


def _navigate_sidebar(page, label_pattern: str, expected_title: str, screenshot: str) -> None:
    page.get_by_role("button", name=re.compile(label_pattern, re.IGNORECASE)).click(timeout=20_000)
    _assert_workspace(page, expected_title, screenshot)


def _verify_openglobus(page, label: str) -> None:
    """Require the embedded OpenGlobus renderer to create a canvas and finish init."""
    deadline = time.monotonic() + 35
    map_frame = None
    while time.monotonic() < deadline:
        for frame in page.frames:
            try:
                if frame.locator("#globus").count():
                    map_frame = frame
                    break
            except Exception:
                continue
        if map_frame is not None:
            break
        page.wait_for_timeout(500)

    if map_frame is None:
        raise AssertionError(f"{label}: OpenGlobus iframe/container was not rendered.")

    canvas = map_frame.locator("#globus canvas")
    try:
        canvas.wait_for(state="attached", timeout=25_000)
        map_frame.locator("#status.hidden").wait_for(state="attached", timeout=25_000)
    except Exception as exc:
        status = map_frame.locator("#status")
        message = status.inner_text() if status.count() else "map status unavailable"
        raise AssertionError(f"{label}: OpenGlobus failed to initialize: {message}") from exc

    bounds = canvas.bounding_box()
    if not bounds or bounds["width"] < 100 or bounds["height"] < 100:
        raise AssertionError(f"{label}: OpenGlobus canvas has no usable display area.")


def _assert_report_reference(page, label: str) -> str:
    text = page.locator("body").inner_text()
    match = re.search(rf"{re.escape(label)}:\\s*(EOR-\\d{{4}}-\\d{{6}})", text)
    if not match:
        raise AssertionError(f"Expected a saved report reference after {label} submission.")
    return match.group(1)


def main() -> None:
    REPORTS.mkdir(exist_ok=True)
    page_errors: list[str] = []
    completed: list[str] = []
    references: dict[str, str] = {}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--use-gl=swiftshader",
                "--enable-webgl",
                "--ignore-gpu-blocklist",
                "--disable-dev-shm-usage",
            ],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: page_errors.append(str(error)))

        try:
            response = page.goto(APP_URL, wait_until="domcontentloaded", timeout=120_000)
            if response is None or response.status != 200:
                raise AssertionError(
                    f"Streamlit app returned {None if response is None else response.status}."
                )

            _assert_workspace(page, "Executive Overview", "eor-atlas-overview.png")
            _verify_openglobus(page, "Executive Overview")
            completed.append("Executive Overview: page and OpenGlobus canvas")

            # Global search must hand off to the chosen destination.
            search = page.locator('input[placeholder="Search pages, fields or reservoirs..."]')
            search.fill("EOR Screening")
            page.get_by_role("button", name="Open result").wait_for(timeout=20_000)
            page.get_by_role("button", name="Open result").click()
            _assert_workspace(page, "EOR Screening", "eor-atlas-screening.png")
            completed.append("Global search: EOR Screening route handoff")

            # Submitting a valid default engineering case must persist exactly one run.
            before_engineering = _run_count()
            page.get_by_role("button", name=re.compile("Run EOR Screening")).click(timeout=20_000)
            page.get_by_text(re.compile(r"Saved report card:.*EOR-\\d{4}-\\d{6}")).wait_for(
                state="visible", timeout=60_000
            )
            after_engineering = _run_count()
            if after_engineering != before_engineering + 1:
                raise AssertionError(
                    "Engineering submission did not persist exactly one report card "
                    f"(before={before_engineering}, after={after_engineering})."
                )
            engineering_id, engineering_mode = _latest_run()
            if engineering_mode != "ENGINEERING":
                raise AssertionError(
                    f"Expected ENGINEERING persistence mode, received {engineering_mode!r}."
                )
            references["engineering"] = _assert_report_reference(page, "Saved report card")
            completed.append("EOR Screening: submit, gate result and one ENGINEERING report card")

            # Candidate discovery, filter controls and session-scoped saved presets.
            _navigate_sidebar(page, "Portfolio Explorer", "Candidates", "eor-atlas-candidates.png")
            page.get_by_text("Portfolio filters", exact=True).wait_for(timeout=30_000)
            page.get_by_role("button", name=re.compile("Saved filters")).click()
            page.get_by_label("Preset name").fill("EOR Atlas CI smoke")
            page.get_by_role("button", name="Save current filters").click()
            page.get_by_text("Saved filter preset: EOR Atlas CI smoke").wait_for(
                state="visible", timeout=20_000
            )
            page.get_by_role("button", name="Apply preset").click()
            page.locator(".page-title").filter(has_text="Candidates").last.wait_for(
                state="visible", timeout=30_000
            )
            _verify_openglobus(page, "Candidates")
            completed.append("Candidates: filters, save/apply preset and OpenGlobus canvas")

            # Hybrid execution must keep the three result layers visible and persist model data.
            _navigate_sidebar(page, "Hybrid Intelligence", "Hybrid Intelligence", "eor-atlas-hybrid.png")
            before_hybrid = _run_count()
            page.get_by_role("button", name=re.compile("Run Hybrid Intelligence")).click(timeout=20_000)
            page.get_by_text(re.compile(r"Saved hybrid report card:.*EOR-\\d{4}-\\d{6}")).wait_for(
                state="visible", timeout=90_000
            )
            after_hybrid = _run_count()
            if after_hybrid != before_hybrid + 1:
                raise AssertionError(
                    "Hybrid submission did not persist exactly one report card "
                    f"(before={before_hybrid}, after={after_hybrid})."
                )

            hybrid_id, hybrid_mode = _latest_run()
            if hybrid_mode != "HYBRID":
                raise AssertionError(f"Expected HYBRID persistence mode, received {hybrid_mode!r}.")
            with sqlite3.connect(DATABASE, timeout=15) as connection:
                probability_rows = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM ml_results WHERE screening_id = ?",
                        (hybrid_id,),
                    ).fetchone()[0]
                )
                fusion_rows = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM hybrid_results WHERE screening_id = ?",
                        (hybrid_id,),
                    ).fetchone()[0]
                )
            if probability_rows <= 0:
                raise AssertionError(
                    "Hybrid report card was saved without CatBoost probability rows."
                )
            if page.get_by_text("CatBoost class", exact=True).count() == 0:
                raise AssertionError("Hybrid workspace did not display CatBoost class probabilities.")
            if page.get_by_text("01 · Engineering feasibility", exact=True).count() == 0:
                raise AssertionError("Hybrid workspace did not display the engineering feasibility layer.")
            if page.get_by_text("03 · Decision Fusion recommendation", exact=True).count() == 0:
                raise AssertionError("Hybrid workspace did not display the Decision Fusion layer.")

            references["hybrid"] = _assert_report_reference(page, "Saved hybrid report card")
            completed.append(
                "Hybrid Intelligence: Excel Gate, CatBoost probabilities, Decision Fusion "
                f"and one HYBRID report card ({probability_rows} ML rows, {fusion_rows} fusion rows)"
            )

            # Basic narrow-screen layout sanity check without assuming pixel-perfect breakpoints.
            page.set_viewport_size({"width": 390, "height": 844})
            page.locator(".page-title").filter(has_text="Hybrid Intelligence").last.wait_for(
                state="visible", timeout=15_000
            )
            viewport = page.evaluate(
                "() => ({width: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth})"
            )
            REPORTS.mkdir(exist_ok=True)
            page.screenshot(path=str(REPORTS / "eor-atlas-hybrid-mobile.png"), full_page=True)
            if viewport["scrollWidth"] - viewport["width"] > 80:
                raise AssertionError(f"Unexpected horizontal overflow at mobile width: {viewport}")

            if page_errors:
                raise AssertionError("Uncaught browser page errors: " + " | ".join(page_errors))

        finally:
            browser.close()

    result = {
        "app_url": APP_URL,
        "completed_checks": completed,
        "report_card_references": references,
        "browser_page_errors": page_errors,
    }
    print(json.dumps(result, indent=2))
    (REPORTS / "browser-validation.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()

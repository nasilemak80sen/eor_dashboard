import os
import sys

from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
)
from playwright.sync_api import sync_playwright


STREAMLIT_URL = os.environ.get(
    "STREAMLIT_APP_URL"
)

if not STREAMLIT_URL:
    raise RuntimeError(
        "STREAMLIT_APP_URL is not configured."
    )


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 900,
            }
        )

        try:
            page.goto(
                STREAMLIT_URL,
                wait_until="domcontentloaded",
                timeout=120_000,
            )

            wake_button = page.get_by_role(
                "button",
                name="Yes, get this app back up!",
            )

            try:
                wake_button.wait_for(
                    state="visible",
                    timeout=15_000,
                )

                wake_button.click()

                print(
                    "Sleep screen detected. "
                    "Wake-up button clicked."
                )

            except PlaywrightTimeoutError:
                print(
                    "No sleep screen detected."
                )

            page.wait_for_timeout(
                15_000
            )

            print(
                "Final page title:",
                page.title(),
            )

        finally:
            browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"Wake-up check failed: {exc}"
        )

        sys.exit(1)
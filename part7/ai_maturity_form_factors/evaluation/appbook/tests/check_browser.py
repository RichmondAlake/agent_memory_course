"""Browser checks in headless Chromium: every page renders with no console errors, the playground answers, a suite
streams live rows and stops, and the Data Explorer reads the evidence.

    python -m playwright install chromium        # once
    python tests/check_browser.py                 # against http://127.0.0.1:8705 (APPBOOK_URL to override)

Screenshots land in tests/artifacts/. Prints one PASS/FAIL line per check and exits non-zero if any fails.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.getenv("APPBOOK_URL", "http://127.0.0.1:8705")
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)
failures: list[str] = []
PAGES = [("", "How well does each rung"), ("graders", "trust"), ("chatbot", "confident errors"), ("rag", "grounded"),
         ("workflow", "end to end"), ("agent", "end state"), ("autonomous", "never saw"), ("gates", "per rung")]


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}: {label}" + ("" if condition else f"  {str(detail)[:300]}"), flush=True)
    if not condition:
        failures.append(label)


def main() -> None:
    started = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 960}, color_scheme="dark")
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        for n, (route, heading) in enumerate(PAGES, 1):
            page.goto(f"{BASE}/#/{route}")
            page.wait_for_function("document.querySelector('#stage .eval-title') !== null", timeout=20000)
            page.wait_for_timeout(1800)
            title = page.inner_text("#stage .eval-title")
            check(f"page {route or 'overview'} · renders its heading", heading.lower() in title.lower(), title)
            if route in ("chatbot", "rag", "workflow", "agent", "autonomous"):
                page.wait_for_function(f"!document.querySelector('#last-{route}').textContent.includes('Reading the evidence')",
                                       timeout=30000)
                stored = page.inner_text(f"#last-{route}").lower()          # headings are upper-cased by CSS
                check(f"page {route} · shows the latest stored results or says none exist",
                      "gates for this rung" in stored or "no stored run" in stored, stored[:200])
            page.screenshot(path=str(ARTIFACTS / f"{n:02d}-{route or 'overview'}.png"))

        page.goto(f"{BASE}/#/")
        page.wait_for_selector("#score-cards .rung-card", timeout=30000)
        check("overview · scorecard cards for the selected run", page.locator("#score-cards .rung-card").count() == 6)
        check("overview · the runs table lists runs", page.locator("#runs-table tbody tr").count() >= 1)

        page.goto(f"{BASE}/#/graders")
        page.wait_for_selector("#try-run", timeout=20000)
        page.click("#try-run")
        page.wait_for_selector("#try-answers .answer-card .p", timeout=180000)
        cards = page.locator("#try-answers .answer-card").count()
        check("graders · the playground asks every grader", cards >= 2, cards)
        page.screenshot(path=str(ARTIFACTS / "09-playground.png"), full_page=False)

        # A quick grader validation streams one row per check within seconds; a stopped validation run stores nothing,
        # so this never changes the graders the rung suites choose.
        page.goto(f"{BASE}/#/graders")
        page.wait_for_selector("#run-graders", timeout=20000)
        page.click("#run-graders")
        page.wait_for_function("document.querySelector('#graders-live-table tbody tr') !== null", timeout=240000)
        check("graders · a quick run streams live checks", page.locator("#graders-live-table tbody tr").count() >= 1)
        page.screenshot(path=str(ARTIFACTS / "10-live-graders.png"))
        page.click("#stop-graders")
        page.wait_for_function("/stopped|done/.test(document.querySelector('#status-graders').textContent)", timeout=300000)
        check("graders · Stop ends the run", "stopped" in page.inner_text("#status-graders"), page.inner_text("#status-graders"))

        page.click("#explorer-toggle")
        page.wait_for_selector("#explorer-table-list [data-t]", timeout=20000)
        page.click("#explorer-table-list [data-t='ffeval_results']")
        page.wait_for_selector("#explorer-grid table", timeout=20000)
        check("data explorer · reads FFEVAL_RESULTS", page.locator("#explorer-grid tbody tr").count() >= 1)
        page.screenshot(path=str(ARTIFACTS / "11-data-explorer.png"))

        mobile = browser.new_page(viewport={"width": 390, "height": 844}, color_scheme="light")
        mobile.on("pageerror", lambda e: errors.append(str(e)))
        mobile.goto(f"{BASE}/#/workflow")
        mobile.wait_for_selector("#stage .eval-title", timeout=20000)
        mobile.wait_for_timeout(1500)
        width = mobile.evaluate("document.querySelector('#stage').scrollWidth <= window.innerWidth + 2")
        check("mobile · the workflow page fits the screen width", width)
        mobile.screenshot(path=str(ARTIFACTS / "12-mobile.png"))

        check("no console errors on any page", not errors, errors[:5])
        browser.close()
    print(f"\n{'PASSED' if not failures else f'FAILED: {len(failures)} failing check(s)'} · {time.time() - started:.0f}s")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()

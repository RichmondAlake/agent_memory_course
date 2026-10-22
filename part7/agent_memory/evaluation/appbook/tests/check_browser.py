"""Browser checks in headless Chromium: every page renders with no console errors, the stored runs load, the playground
answers, and the Data Explorer reads the evidence. Live suite runs are checked by tests/check_live.py.

    python -m playwright install chromium        # once
    python tests/check_browser.py                 # against http://127.0.0.1:8715 (APPBOOK_URL to override)

Screenshots land in tests/artifacts/. Prints one PASS/FAIL line per check and exits non-zero if any fails.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.getenv("APPBOOK_URL", "http://127.0.0.1:8715")
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)
failures: list[str] = []
PAGES = [("", "actually work"), ("graders", "trust"), ("longmemeval", "long"), ("factconsolidation", "overwrite"),
         ("operations", "stores"), ("gates", "per Memo")]


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
            page.wait_for_timeout(1500)
            title = page.inner_text("#stage .eval-title")
            check(f"page {route or 'overview'} · renders its heading", heading.lower() in title.lower(), title)
            if route in ("graders", "longmemeval", "factconsolidation", "operations"):
                page.wait_for_function(f"!document.querySelector('#last-{route}').textContent.includes('Reading the evidence')", timeout=60000)
                stored = page.inner_text(f"#last-{route}")
                check(f"page {route} · shows the latest stored run or says none exists",
                      "No stored run" in stored or "No validation run" in stored or len(stored) > 80, stored[:200])
            page.screenshot(path=str(ARTIFACTS / f"{n:02d}-{route or 'overview'}.png"))

        page.goto(f"{BASE}/#/")
        page.wait_for_selector("#score-body table", timeout=30000)
        check("overview · scorecard for the selected run has the three agents",
              all(name in page.inner_text("#score-body").lower() for name in ("naive", "scratch", "memorizz")))
        check("overview · the runs table lists runs", page.locator("#runs-table tbody tr").count() >= 1)

        page.goto(f"{BASE}/#/graders")
        page.wait_for_selector("#try-run", timeout=20000)
        page.select_option("#try-check", "uses_old_value")
        page.select_option("#try-example", "old")
        page.click("#try-run")
        page.wait_for_selector("#try-answers .answer-card .p", timeout=180000)
        cards = page.locator("#try-answers .answer-card").count()
        check("graders · the playground asks every grader", cards >= 2, cards)
        page.screenshot(path=str(ARTIFACTS / "07-playground.png"))

        page.click("#explorer-toggle")
        page.wait_for_selector("#explorer-table-list [data-t]", timeout=20000)
        page.click("#explorer-table-list [data-t='memeval_results']")
        page.wait_for_selector("#explorer-grid table", timeout=20000)
        check("data explorer · reads MEMEVAL_RESULTS", page.locator("#explorer-grid tbody tr").count() >= 1)
        page.screenshot(path=str(ARTIFACTS / "08-data-explorer.png"))

        mobile = browser.new_page(viewport={"width": 390, "height": 844}, color_scheme="light")
        mobile.on("pageerror", lambda e: errors.append(str(e)))
        mobile.goto(f"{BASE}/#/longmemeval")
        mobile.wait_for_selector("#stage .eval-title", timeout=20000)
        mobile.wait_for_timeout(2500)
        width = mobile.evaluate("document.querySelector('#stage').scrollWidth <= window.innerWidth + 2")
        check("mobile · the LongMemEval page fits the screen width", width)
        mobile.screenshot(path=str(ARTIFACTS / "09-mobile.png"))

        check("no console errors on any page", not errors, errors[:5])
        browser.close()
    print(f"\n{'PASSED' if not failures else f'FAILED: {len(failures)} failing check(s)'} · {time.time() - started:.0f}s")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()

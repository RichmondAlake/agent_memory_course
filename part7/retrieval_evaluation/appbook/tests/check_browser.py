"""Browser checks in headless Chromium: every page renders with no console errors, the leaderboard shows every
dataset and the BM25 note, the query explorer runs a stored and a typed query, the playground builds its cache and
moves with a slider, the decision guide shows its evidence, the Data Explorer reads rows without vectors, and a
phone-width page fits the screen.

    python -m playwright install chromium        # once
    python tests/check_browser.py                 # against http://127.0.0.1:8725 (APPBOOK_URL to override)

Screenshots land in tests/artifacts/. Prints one PASS/FAIL line per check and exits non-zero if any fails.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.getenv("APPBOOK_URL", "http://127.0.0.1:8725")
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)
failures: list[str] = []
PAGES = [("", "by how much"), ("explore", "five strategies"), ("playground", "dev score"), ("guide", "which data")]


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
            title = page.inner_text("#stage .eval-title")
            check(f"page {route or 'leaderboard'} · renders its heading", heading.lower() in title.lower(), title)

        page.goto(f"{BASE}/#/")
        page.wait_for_selector("#lb-body [data-ds]", timeout=60000)
        check("leaderboard · a panel per dataset", page.locator("#lb-body [data-ds]").count() == 3)
        check("leaderboard · five strategies in the FiQA table",
              page.locator("#lb-body [data-ds='fiqa'] tbody tr").count() == 5)
        body = page.inner_text("#lb-body")
        check("leaderboard · paired tests with Holm p", "p (Holm)" in body or "P (HOLM)" in body.upper())
        check("leaderboard · the Oracle Text vs BM25 note appears once", body.lower().count("published bm25") == 1 and "0.236" in body)
        page.screenshot(path=str(ARTIFACTS / "01-leaderboard.png"), full_page=False)

        page.goto(f"{BASE}/#/explore")
        page.wait_for_function("document.querySelectorAll('#qx-query option').length > 10", timeout=30000)
        page.click("#qx-run")
        page.wait_for_selector("#qx-grid .qx-col", timeout=180000)
        check("explorer · five columns for a stored query", page.locator("#qx-grid .qx-col").count() == 5)
        check("explorer · per-query metrics and the stored value", "stored" in page.inner_text("#qx-grid"))
        first = page.locator("#qx-grid .qx-doc summary").first
        first.click()
        check("explorer · expanding a document shows its text", page.locator("#qx-grid .qx-doc[open] .body").count() >= 1)
        page.screenshot(path=str(ARTIFACTS / "02-explorer.png"))
        page.fill("#qx-text", "Is it better to rent or to buy a home when rates are high?")
        page.click("#qx-run-typed")
        page.wait_for_function("document.querySelector('#qx-out') && document.querySelector('#qx-out').innerText.includes('no relevance marks')", timeout=180000)
        check("explorer · a typed query says it has no judgements", page.locator("#qx-grid .gr").count() == 0)
        page.screenshot(path=str(ARTIFACTS / "03-explorer-typed.png"))

        page.goto(f"{BASE}/#/playground")
        page.select_option("#pg-ds", "scifact")
        page.wait_for_selector("#pg-hybrid-tiles .tile", timeout=600000)
        check("playground · the cache is ready and the hybrid tiles fill", page.locator("#pg-hybrid-tiles .tile").count() == 3)
        check("playground · the notebook's choice is marked", page.locator("#pg-hybrid .mark").count() >= 1)
        page.wait_for_function("document.querySelector('#pg-hybrid-note').innerText.includes('notebook')", timeout=30000)
        note = page.inner_text("#pg-hybrid-note")
        tile = page.inner_text("#pg-hybrid-tiles .tile .tv")
        check("playground · at SciFact's chosen setting the live score equals the notebook's stored dev score",
              "0.70" in page.inner_text("#pg-hybrid .mark-label") and f"stored {tile}" in note, (tile, note))
        before = page.inner_text("#pg-graph-tiles")
        page.locator("#pg-decay").fill("7")
        page.wait_for_function(f"document.querySelector('#pg-graph-tiles').innerText !== {before!r}", timeout=20000)
        check("playground · moving a slider rescores", page.inner_text("#pg-graph-tiles") != before)
        page.screenshot(path=str(ARTIFACTS / "04-playground.png"))

        page.goto(f"{BASE}/#/guide")
        page.wait_for_selector("#gd-steps .step", timeout=60000)
        page.wait_for_function("document.querySelectorAll('#gd-diag tbody tr').length === 3", timeout=300000)
        check("guide · diagnostics for three datasets and five evidence steps",
              page.locator("#gd-diag tbody tr").count() == 3 and page.locator("#gd-steps .step").count() == 5)
        check("guide · the flowchart image loads", page.evaluate("document.querySelector('.guide-grid img').naturalWidth > 0"))
        page.screenshot(path=str(ARTIFACTS / "05-guide.png"))

        page.click("#explorer-toggle")
        page.wait_for_selector("#explorer-table-list [data-t]", timeout=20000)
        page.click("#explorer-table-list [data-t='beir7_fiqa_bge']")
        page.wait_for_function("document.querySelector('#explorer-table-name').textContent === 'beir7_fiqa_bge'", timeout=20000)
        grid = page.inner_text("#explorer-grid")
        check("data explorer · a vector table shows placeholders, never vectors", "vector (not shown)" in grid.lower(), grid[:200])
        page.click("#explorer-table-list [data-t='beir7_results']")
        page.wait_for_function("document.querySelector('#explorer-table-name').textContent === 'beir7_results'", timeout=20000)
        check("data explorer · reads BEIR7_RESULTS", page.locator("#explorer-grid tbody tr").count() >= 1)
        page.screenshot(path=str(ARTIFACTS / "06-data-explorer.png"))

        mobile = browser.new_page(viewport={"width": 390, "height": 844}, color_scheme="light")
        mobile.on("pageerror", lambda e: errors.append(str(e)))
        mobile.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        mobile.goto(f"{BASE}/#/")
        mobile.wait_for_selector("#lb-body [data-ds]", timeout=60000)
        fits = mobile.evaluate("document.querySelector('#stage').scrollWidth <= window.innerWidth + 2")
        check("mobile · the leaderboard fits a phone's width", fits)
        mobile.screenshot(path=str(ARTIFACTS / "07-mobile.png"))

        check("no console errors on any page", not errors, errors[:5])
        browser.close()
    print(f"\n{'PASSED' if not failures else f'FAILED: {len(failures)} failing check(s)'} · {time.time() - started:.0f}s")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()

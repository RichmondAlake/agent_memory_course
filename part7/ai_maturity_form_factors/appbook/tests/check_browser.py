"""Headless browser checks for a running AI Maturity Ladder appbook (Acme Home Loans).

Opens every page in Chromium, performs each page's main interaction against the
live backend (real Claude, Oracle, Clef-Flash and agent runs), and fails on any
console error or uncaught page error. Screenshots land in tests/artifacts/ (gitignored).

    python -m playwright install chromium            # once
    python tests/check_browser.py                    # http://127.0.0.1:8700
    python tests/check_browser.py --skip-agents      # no Agent SDK runs (Form Factors 4-5 open, not sent)
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

BASE = os.getenv("APPBOOK_URL", "http://127.0.0.1:8700")
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
LONG = 300_000          # ms allowed for one model, workflow or agent turn
failures: list[str] = []
errors: list[str] = []  # console errors and uncaught page errors, from every page


def check(label: str, action) -> None:
    try:
        action()
        print(f"PASS: {label}", flush=True)
    except Exception as exc:  # noqa: BLE001 — report every failed check, keep going
        failures.append(label)
        print(f"FAIL: {label}  {str(exc).splitlines()[0][:300]}", flush=True)


def shot(page: Page, name: str) -> None:
    page.screenshot(path=str(ARTIFACTS / f"{name}.png"))


def go(page: Page, route: str) -> None:
    page.goto(f"{BASE}/#/{route}")
    page.wait_for_load_state("networkidle")


def click(page: Page, selector: str) -> None:
    """Scroll the target to the middle first: the Data Explorer bar covers the bottom of the viewport."""
    page.locator(selector).first.evaluate("e => e.scrollIntoView({block: 'center'})")
    page.click(selector)


def overview(page: Page) -> None:
    go(page, "")
    expect(page.locator("a.lcard")).to_have_count(5)
    expect(page.locator("#ledger table tbody tr").first).to_be_visible(timeout=30_000)
    shot(page, "01-overview")
    page.locator("a.lcard").first.click()
    expect(page).to_have_url(re.compile(r"#/chatbot$"))


def theme_toggle(page: Page) -> None:
    root = page.locator("html")
    before = root.get_attribute("data-theme")
    page.click("#theme-toggle")
    expect(root).not_to_have_attribute("data-theme", before or "")
    page.click("#theme-toggle")
    expect(root).to_have_attribute("data-theme", before or "dark")


def chatbot(page: Page) -> None:
    go(page, "chatbot")
    page.fill("#chat-input", "I'm Dana. I earn $9,000 a month and want a $350,000 home.")
    page.click("#chat-send")
    expect(page.locator(".msg.bot .bubble")).to_have_count(1, timeout=LONG)
    expect(page.locator("#chat-send")).to_be_enabled(timeout=LONG)
    page.fill("#chat-input", "What's my name and monthly income?")
    page.click("#chat-send")
    expect(page.locator(".msg.bot .bubble")).to_have_count(2, timeout=LONG)
    expect(page.locator(".msg.bot .bubble").last).to_contain_text("Dana", timeout=LONG)
    expect(page.locator("#turn-bars .tb-row")).to_have_count(2, timeout=LONG)
    shot(page, "02-chatbot")


def rag(page: Page) -> None:
    go(page, "rag")
    expect(page.locator(".pol-list")).to_be_visible(timeout=30_000)
    page.fill("#rag-input", "Do I need mortgage insurance with a small down payment?")
    click(page, '#rag-tech button[data-t="keyword"]')
    click(page, "#rag-ask")
    expect(page.locator("#viz .kw-svg")).to_be_visible(timeout=LONG)
    expect(page.locator("#viz .posting").first).to_be_visible()
    expect(page.locator("#rag-sources .source").first).to_be_visible(timeout=LONG)
    for technique, selector in (("vector", "#n3d-canvas"), ("hybrid", ".hy-svg"), ("graph", ".g-svg")):
        click(page, f'#rag-tech button[data-t="{technique}"]')
        expect(page.locator(f"#viz {selector}")).to_be_visible(timeout=LONG)
        expect(page.locator("#rag-src-note")).to_contain_text(technique.split()[0], timeout=LONG)
        box = page.locator(f"#viz {selector}").bounding_box()
        assert box and box["height"] > 150, f"{technique} diagram is {box and box['height']}px tall"
    click(page, '#rag-tech button[data-t="vector"]')
    expect(page.locator("#viz #n3d-canvas")).to_be_visible(timeout=LONG)
    box = page.locator("#viz #n3d-canvas").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down(); page.mouse.move(box["x"] + box["width"] / 2 + 80, box["y"] + box["height"] / 2 + 20); page.mouse.up()
    page.check("#rag-rerank")
    expect(page.locator("#viz-rerank .rr-svg")).to_be_visible(timeout=LONG)
    expect(page.locator("#rag-sources .rr-move").first).to_be_visible(timeout=LONG)
    page.uncheck("#rag-rerank")
    shot(page, "03-rag")


def hnsw_lab(page: Page) -> None:
    go(page, "rag")
    page.locator("#hnsw-panel").evaluate("e => e.scrollIntoView({block: 'start'})")
    expect(page.locator("#hl-stats .hl-res")).to_be_visible(timeout=60_000)        # the policy index is built and searched
    expect(page.locator("#hl-sweep svg")).to_be_visible()
    click(page, "#hl-dataset button[data-d='points']")
    page.locator("#hl-m").fill("8")
    page.locator("#hl-speed").fill("30")
    click(page, "#hl-ingest")
    page.wait_for_timeout(1500)
    expect(page.locator("#hl-narr")).to_contain_text(re.compile(r"level|layer|entry point"), timeout=10_000)
    click(page, "#hl-finish")
    page.locator("#hl-canvas").evaluate("e => e.scrollIntoView({block: 'end'})")
    page.mouse.wheel(0, 120)                                                             # clear the Data Explorer bar
    page.wait_for_timeout(300)
    box = page.locator("#hl-canvas").bounding_box()
    page.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + box["height"] - 120)      # a query on layer 0
    expect(page.locator("#hl-stats .hl-res")).to_be_visible(timeout=60_000)
    page.locator("#hnsw-panel").screenshot(path=str(ARTIFACTS / "04-hnsw-lab.png"))


def latent_space(page: Page) -> None:
    page.fill("#space-q", "how much house can I afford with my salary")
    page.select_option("#space-cat", "compliance")
    click(page, "#space-mode button[data-m='post']")
    click(page, "#space-run")
    expect(page.locator("#space-table table")).to_be_visible(timeout=60_000)
    expect(page.locator(".cmp-row.sel")).to_contain_text("0/", timeout=30_000)   # post-filter under-returns
    click(page, "#space-dim button[data-d='3d']")
    page.locator("#space-panel").screenshot(path=str(ARTIFACTS / "04-latent-space.png"))


def workflow(page: Page) -> None:
    go(page, "workflow")
    click(page, "#wf-samples .chip[data-s='sam']")
    click(page, "#wf-run")
    expect(page.locator(".lane .outcome")).to_contain_text("refer", ignore_case=True, timeout=LONG)
    expect(page.locator(".tree-svg .t-edge.taken").first).to_be_attached()
    expect(page.locator(".tree-svg .t-out.taken.refer")).to_have_count(1)
    shot(page, "05-workflow")


def workflow_batch(page: Page) -> None:
    go(page, "workflow")
    expect(page.locator("#wf-batch input")).to_have_count(6, timeout=30_000)
    click(page, "#wf-batch-run")
    expect(page.locator(".lane")).to_have_count(4, timeout=30_000)
    expect(page.locator(".gantt-track i.gq").first).to_be_attached(timeout=LONG)    # someone waited for Clef
    page.wait_for_function("document.querySelectorAll('.lane .outcome').length >= 4", timeout=LONG)
    shot(page, "06-workflow-batch")


def agent(page: Page, send: bool) -> None:
    go(page, "agent")
    if send:
        page.fill("#ag-input", "Hi, it's Maya Patel. Was my application approved?")
        click(page, "#ag-send")
        expect(page.locator("#ag-chat .tool-chip").first).to_be_visible(timeout=LONG)
        expect(page.locator("#ag-send")).to_be_enabled(timeout=LONG)
        page.reload(); page.wait_for_load_state("networkidle")     # session memory survives a refresh
        expect(page.locator("#ag-chat .sys-note")).to_contain_text("Oracle", timeout=30_000)
    expect(page.locator("#ag-sessions .sess").first).to_be_visible(timeout=30_000)
    click(page, "#ag-sessions .sess")
    expect(page.locator("#ag-chat .msg").first).to_be_visible(timeout=30_000)
    expect(page.locator("#ag-chat .branch-btn").first).to_be_attached()
    shot(page, "07-agent")


def builder(page: Page, send: bool) -> None:
    go(page, "builder")
    expect(page.locator("#live-svg .an")).to_have_count(12)
    expect(page.locator("#ref-svg .an")).to_have_count(12)
    click(page, ".scen[data-sc='escape']")
    for _ in range(2):
        click(page, "#sc-step")
        page.wait_for_timeout(1800)
    expect(page.locator("#ref-n-hook")).to_have_class(re.compile(r"\bdeny\b"))
    click(page, "#ref-n-store")
    expect(page.locator("#comp-detail")).to_contain_text("OracleSessionStore")
    if send:
        page.fill("#bd-input", "Draw a simple diagram image of the pre-screen pipeline (inputs → checks → "
                               "pass/refer/fail) with matplotlib and save it as pipeline_check.png.")
        click(page, "#bd-send")
        expect(page.locator("#bd-chat .img-card img").first).to_be_visible(timeout=LONG)
        expect(page.locator("#live-log .ll").first).to_be_visible()
        expect(page.locator("#bd-send")).to_be_enabled(timeout=LONG)
        natural = page.locator("#bd-chat .img-card img").first.evaluate("i => i.naturalWidth")
        assert natural > 100, f"image did not load ({natural}px)"
    page.locator(".builder3").screenshot(path=str(ARTIFACTS / "08-builder.png"))


def data_explorer(page: Page) -> None:
    go(page, "")
    page.click("#explorer-toggle")
    table = page.locator('[data-explorer-table="policy_docs"]')
    expect(table).to_be_visible(timeout=30_000)
    table.click()
    expect(page.locator("#explorer-table-name")).to_contain_text("policy_docs", ignore_case=True)
    expect(page.locator("#explorer-grid tbody tr")).to_have_count(17, timeout=30_000)
    shot(page, "09-data-explorer")
    page.click("#explorer-toggle")


def mobile_layout(browser) -> None:
    page = browser.new_page(viewport={"width": 390, "height": 844})
    for route in ("", "rag", "workflow", "agent", "builder"):
        go(page, route)
        overflow = page.evaluate("document.scrollingElement.scrollWidth - window.innerWidth")
        assert overflow <= 1, f"#{route or '/'} scrolls sideways by {overflow}px at phone width"
    shot(page, "10-mobile")
    page.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-agents", action="store_true", help="open Form Factors 4-5 without sending a message")
    args = parser.parse_args()
    send = not args.skip_agents
    ARTIFACTS.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1680, "height": 1050}, color_scheme="dark")
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}")
                if m.type == "error" and "fonts.g" not in m.text else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e} | {(e.stack or '').splitlines()[1:3]}"))
        check("Overview shows the five-rung ladder and the memory ledger", lambda: overview(page))
        check("Theme toggle switches and restores light/dark", lambda: theme_toggle(page))
        check("Chatbot remembers within the conversation and charts input tokens per turn", lambda: chatbot(page))
        check("RAG draws every technique (vector in 3-D) and reranks the candidates", lambda: rag(page))
        check("Latent space viewer shows the post-filter coming up short", lambda: latent_space(page))
        check("HNSW lab builds, animates ingestion and searches", lambda: hnsw_lab(page))
        check("Workflow refers Sam and highlights the path in the decision tree", lambda: workflow(page))
        check("Parallel batch runs four lanes that queue for Clef", lambda: workflow_batch(page))
        check("Agent sessions load from Oracle (and survive a refresh)", lambda: agent(page, send))
        check("Autonomous agent: architecture, scenario simulation" + (" and an image made in the sandbox" if send else ""),
              lambda: builder(page, send))
        check("Data Explorer lists the 17 POLICY_DOCS rows", lambda: data_explorer(page))
        check("No sideways scrolling at phone width", lambda: mobile_layout(browser))
        browser.close()

    def no_errors() -> None:
        assert not errors, "; ".join(errors)

    check("No console errors or uncaught page errors", no_errors)
    print(f"\nScreenshots: {ARTIFACTS}")
    print(f"{'ALL BROWSER CHECKS PASSED' if not failures else f'{len(failures)} BROWSER CHECK(S) FAILED'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()

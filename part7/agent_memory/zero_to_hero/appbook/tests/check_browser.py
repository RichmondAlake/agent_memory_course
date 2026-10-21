"""Browser checks with Playwright (headless Chromium) against a running appbook.

    ./run.sh &                                            # from appbook/, port 8710
    ../../../.venv/bin/python tests/check_browser.py      # APPBOOK_URL overrides the address

Visits the overview and all sixteen Part pages, runs the main interaction of the
key pages (a message to both agents, knowledge search, tool preview, persona
evolution, Jev routing, operational evidence), opens the Data Explorer, toggles
the theme, and checks the phone layout has no sideways scroll. Fails on any
console error or page error. Screenshots go to tests/artifacts/ (git-ignored).
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.getenv("APPBOOK_URL", "http://127.0.0.1:8710")
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)
failures: list[str] = []
problems: list[str] = []
started = time.perf_counter()


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}{'' if condition else '  ' + str(detail)[:240]}", flush=True)
    if not condition:
        failures.append(label)


def watch(page) -> None:
    def on_console(message):
        if message.type == "error" and "fonts.g" not in message.text:
            problems.append(f"console: {message.text}")
    page.on("console", on_console)
    page.on("pageerror", lambda error: problems.append(f"pageerror: {error}"))


def run_action(page, name: str, wait_for: str, timeout: int = 240_000) -> bool:
    page.locator(f'form[data-action="{name}"] button[type="submit"]').click()
    try:
        page.wait_for_selector(f"#action-result {wait_for}", timeout=timeout)
        return True
    except Exception as exc:  # noqa: BLE001
        problems.append(f"action {name}: {exc}")
        return False


with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    watch(page)
    page.request.post(f"{BASE}/api/session/reset")

    page.goto(f"{BASE}/#/")
    page.wait_for_selector(".rung")
    page.wait_for_function("document.querySelector('#status-card')?.textContent.includes('Oracle')", timeout=60_000)
    check("overview lists sixteen Parts and Oracle is connected", page.locator(".rung").count() == 16)
    page.screenshot(path=str(ARTIFACTS / "00-overview.png"))

    for n in range(1, 17):
        page.goto(f"{BASE}/#/{n}")
        page.wait_for_selector("#send")
        if n > 1:
            page.wait_for_selector("#tables-scratch .table-card", timeout=60_000)
        check(f"Part {n} page renders both columns",
              page.locator(".side.scratch").count() == 1 and page.locator(".side.memorizz").count() == 1)
        if n > 1:
            check(f"Part {n} shows the memory unit: definition, uses and a stored row",
                  page.locator(".unit-card .unit-definition").count() == 1 and page.locator(".unit-uses li").count() >= 3
                  and page.locator(".unit-json").inner_text().strip().startswith("{"))
        page.screenshot(path=str(ARTIFACTS / f"part-{n:02d}.png"), full_page=True)

    # The stored unit as JSON or as a table row; the choice carries to every Part and survives a reload
    page.goto(f"{BASE}/#/8")
    page.wait_for_selector(".unit-view [data-view='row']")
    page.locator(".unit-view [data-view='row']").click()
    visible = lambda selector: page.locator(selector).first.is_visible()  # noqa: E731
    headers = page.locator(".unit-table th").all_inner_texts()
    check("Unit card · Row shows the stored unit as one table row, column by column",
          visible(".unit-table") and not visible(".unit-json") and "canonical_hash" in headers
          and page.locator(".unit-table tbody tr").count() == 1, headers)
    page.screenshot(path=str(ARTIFACTS / "unit-row.png"))
    page.goto(f"{BASE}/#/11")
    page.wait_for_selector(".unit-table")
    page.reload()
    page.wait_for_selector(".unit-view [data-view='row'][aria-pressed='true']", timeout=30_000)
    check("Unit card · the Row choice carries to other Parts and survives a reload",
          visible(".unit-table") and "source_ids" in page.locator(".unit-table th").all_inner_texts())
    page.goto(f"{BASE}/#/10")
    page.wait_for_selector(".unit-card")
    check("Unit card · Part 10's unit is never stored, so it stays JSON with no toggle",
          page.locator(".unit-view").count() == 0 and visible(".unit-json"))
    page.goto(f"{BASE}/#/8")
    page.wait_for_selector(".unit-view [data-view='json']")
    page.locator(".unit-view [data-view='json']").click()
    check("Unit card · JSON brings the document back", visible(".unit-json") and not visible(".unit-table"))

    # Part 2 · one message to both agents
    page.goto(f"{BASE}/#/2")
    page.wait_for_selector("#tables-scratch .table-card")
    page.locator("[data-suggest]").first.click()
    page.locator("#send").click()
    page.wait_for_selector("#reply-memorizz .answer-body", timeout=240_000)
    page.wait_for_selector("#send:not([disabled])", timeout=60_000)
    check("Part 2 · both agents answer and the context rail fills",
          page.locator("#reply-scratch .answer-body").count() == 1 and "from scratch" in page.locator("#ctxrail").inner_text().lower())
    page.wait_for_function("document.querySelector('#tables-scratch .table-card-head span')?.textContent.startsWith('2 rows')",
                           timeout=30_000)
    check("Part 2 · the scratch table shows the new rows", True)
    page.screenshot(path=str(ARTIFACTS / "part-02-chat.png"), full_page=True)

    # Tokenomics · the Part 2 turn above is measured on both sides; a golden question is judged
    page.request.post(f"{BASE}/api/parts/3/chat", data={"message": "Who are you, and how do you answer?"},
                      timeout=300_000)
    page.goto(f"{BASE}/#/tokenomics")
    page.wait_for_selector("#tk-latency svg", timeout=60_000)
    check("Tokenomics · the accuracy chart plots the judged golden answer for both agents",
          page.locator("#tk-accuracy svg circle").count() >= 2 and "Accuracy (LLM judge" in page.locator("#tk-summary").inner_text())
    check("Tokenomics · latency renders as bars; cumulative cost and context size render as lines, for both agents",
          page.locator("#tk-latency svg rect[data-tip]").count() >= 2
          and all(page.locator(f"#tk-{chart} svg polyline").count() >= 2 for chart in ("cost", "tokens")))
    check("Tokenomics · legends and the session summary are present",
          page.locator(".tk-charts .tk-legend").count() == 4 and "Total cost" in page.locator("#tk-summary").inner_text())
    check("Tokenomics · accuracy by memory test lists the judged turn for both agents",
          page.locator("#tk-tests .tk-test-row").count() >= 1 and page.locator("#tk-tests .tk-test-track span").count() >= 2)
    check("Tokenomics · the workload lists 30 turns with their memory test, threads and the compaction point",
          page.locator("#tk-workload-list li").count() == 30 and page.locator("#tk-workload-list .tk-thread-tag").count() == 4
          and page.locator("#tk-workload-list .tk-compact-mark").count() == 1)
    page.locator("#tk-cost").click()
    page.wait_for_selector(".tk-modal:not([hidden]) .tk-modal-chart svg", timeout=10_000)
    size = page.evaluate("(() => { const r = document.querySelector('.tk-modal-chart svg').getBoundingClientRect(); return [r.width, r.height]; })()")
    check("Tokenomics · a chart enlarges, large and readable, with its table view",
          page.locator(".tk-modal .tk-table").count() == 1 and size[0] > 600 and size[1] > 200, size)
    page.screenshot(path=str(ARTIFACTS / "tokenomics-modal.png"))
    page.keyboard.press("Escape")
    check("Tokenomics · Escape closes the enlarged chart", page.locator(".tk-modal[hidden]").count() == 1)
    page.screenshot(path=str(ARTIFACTS / "tokenomics.png"), full_page=True)
    check("Tokenomics · each row of the turn table links to its context window",
          page.locator("#tk-turns a[href^='#/context/']").count() >= 4)

    # Tokenomics · Stop run ends the workload after the turn in progress; measured turns stay
    before = len(page.request.get(f"{BASE}/api/tokenomics").json()["turns"])
    check("Tokenomics · Stop run is hidden while nothing runs", page.locator("#tk-stop[hidden]").count() == 1)
    page.locator("#tk-run").click()
    page.wait_for_selector("#tk-stop:not([hidden])", timeout=10_000)
    # "Turn 1" shows only until the setup messages replace it, so wait for any turn line (turn 1 is then measured)
    page.wait_for_function("/^Turn \\d+ of 30/.test(document.querySelector('#tk-progress').textContent)", timeout=300_000)
    page.locator("#tk-stop").click()
    page.wait_for_function("document.querySelector('#tk-progress').textContent.startsWith('Stopped after turn')", timeout=300_000)
    after = page.request.get(f"{BASE}/api/tokenomics").json()
    measured = len(after["turns"]) - before
    check("Tokenomics · Stop run ends the workload after the turn in progress and keeps what it measured",
          not after["running"] and measured in (3, 6, 9) and page.locator("#tk-stop[hidden]").count() == 1
          and page.locator("#tk-run:not([disabled])").count() == 1, (measured, page.locator("#tk-progress").inner_text()))

    # Tokenomics · a run keeps going when you leave the page; other pages show its notification, which can stop it
    before = len(page.request.get(f"{BASE}/api/tokenomics").json()["turns"])
    page.locator("#tk-run").click()
    page.wait_for_function("/^Turn \\d+ of 30/.test(document.querySelector('#tk-progress').textContent)", timeout=300_000)
    page.evaluate("location.hash = '#/4'")
    page.wait_for_selector(".run-toast:not([hidden]) [data-stop]", timeout=15_000)
    toast = page.locator(".run-toast").inner_text()
    check("Run notification · on another page the run keeps going and the notification shows how far it is",
          "Memory workload" in toast and bool(re.search(r"Turn \d+ of 30|Setting up", toast))
          and page.request.get(f"{BASE}/api/tokenomics/status").json()["running"], toast)
    page.screenshot(path=str(ARTIFACTS / "run-notification.png"))
    page.evaluate("location.hash = '#/7'")
    page.wait_for_selector(".run-toast:not([hidden]) [data-stop]", timeout=15_000)
    page.locator(".run-toast [data-stop]").click()
    page.wait_for_function("document.querySelector('.run-toast').textContent.includes('Stopped after turn')", timeout=300_000)
    status = page.request.get(f"{BASE}/api/tokenomics/status").json()
    check("Run notification · it follows you across pages, and its Stop run ends the run after the turn in progress",
          status["state"] == "stopped" and not status["running"], status)
    page.evaluate("location.hash = '#/tokenomics'")
    page.wait_for_selector("#tk-run:not([disabled])", timeout=30_000)
    measured = len(page.request.get(f"{BASE}/api/tokenomics").json()["turns"]) - before
    page.evaluate("location.hash = '#/4'")
    page.wait_for_timeout(500)
    check("Run notification · the page keeps the stopped run's turns, and the notification stays hidden once seen",
          measured in (3, 6, 9) and page.locator(".run-toast[hidden]").count() == 1, measured)

    # Context window · from an answer: both agents' calls, section by section
    page.goto(f"{BASE}/#/2")
    page.wait_for_selector("#reply-memorizz a.cw-link", timeout=60_000)
    check("Context window · each answer and the Model context rail link to the turn's context window",
          page.locator("#reply-scratch a.cw-link").count() == 1 and page.locator("#ctxrail a.cw-rail-link").count() == 1)
    rail = lambda: page.evaluate("document.querySelector('#ctxrail-shell').getBoundingClientRect().width")
    wide = rail()
    page.locator("#ctxrail-toggle").click()
    page.wait_for_timeout(500)
    narrow = rail()
    page.locator("#ctxrail-mini").click()
    page.wait_for_timeout(500)
    check("Model context rail · collapses to a strip at the side and expands again from it",
          wide > 300 and narrow < 60 and rail() > 300 and page.locator("#ctxrail a.cw-rail-link").count() == 1,
          (wide, narrow, rail()))
    page.locator("#reply-memorizz a.cw-link").click()
    page.wait_for_selector("#cw-memorizz .cw-section", timeout=30_000)
    kinds = {side: page.eval_on_selector_all(f"#cw-{side} .cw-section .cw-kind", "els => els.map(e => e.textContent)")
             for side in ("scratch", "memorizz")}
    check("Context window · both agents' requests in reading order: instructions, tools, then the messages",
          kinds["scratch"][:1] == ["Instructions"] and "This turn's message" in kinds["scratch"]
          and kinds["memorizz"][:1] == ["Instructions"] and "This turn's message" in kinds["memorizz"], kinds)
    check("Context window · each call shows OpenAI's counts and a bar of its sections",
          page.locator("#cw-memorizz .cw-bar span").count() >= 3
          and "input tokens" in page.locator("#cw-memorizz .cw-metrics").inner_text())
    page.locator("#cw-memorizz .cw-section summary").first.click()
    check("Context window · a section opens to the exact text sent",
          "MemAgent" in page.locator("#cw-memorizz .cw-section details[open] .cw-pre").first.inner_text())
    page.screenshot(path=str(ARTIFACTS / "context-window.png"), full_page=True)
    page.locator("#cw-next").click()
    page.wait_for_function("document.querySelector('#cw-question')?.textContent.includes('Who are you')", timeout=30_000)
    check("Context window · the turn picker steps to the next turn", page.locator("#cw-turn option").count() >= 2)

    # Part 3 · persona evolution (no model call on either side)
    page.goto(f"{BASE}/#/3")
    page.wait_for_selector("form[data-action='evolve']")
    check("Part 3 · persona evolves on both sides", run_action(page, "evolve", "dl"))

    # Part 5 · knowledge search
    page.goto(f"{BASE}/#/5")
    page.wait_for_selector("form[data-action='search']")
    check("Part 5 · search shows distances and MemoRizz scores", run_action(page, "search", "table"))
    page.screenshot(path=str(ARTIFACTS / "part-05-search.png"), full_page=True)

    # Part 6 · tool selection preview
    page.goto(f"{BASE}/#/6")
    page.wait_for_selector("form[data-action='preview']")
    check("Part 6 · tool preview from both sides", run_action(page, "preview", "table"))

    # Part 15 · Jev routing
    page.goto(f"{BASE}/#/15")
    page.wait_for_selector("form[data-action='route']")
    check("Part 15 · routing table with Jev probabilities", run_action(page, "route", ".prob-bars"))
    page.screenshot(path=str(ARTIFACTS / "part-15-routing.png"), full_page=True)

    # Part 16 · operational evidence
    page.goto(f"{BASE}/#/16")
    page.wait_for_selector("form[data-action='observability']")
    check("Part 16 · operational evidence", run_action(page, "observability", "dl"))

    # Data Explorer
    page.locator("#explorer-toggle").click()
    page.wait_for_selector("[data-explorer-table='scratch_conversation']", timeout=60_000)
    page.locator("[data-explorer-table='scratch_conversation']").click()
    page.wait_for_selector("#explorer-grid table", timeout=30_000)
    check("Data Explorer lists scratch and MemoRizz tables and reads rows",
          page.locator("[data-explorer-table='conversation_memory']").count() == 1)
    page.locator("#explorer-scope").click()
    page.wait_for_selector("#explorer-grid table", timeout=30_000)
    page.screenshot(path=str(ARTIFACTS / "data-explorer.png"))
    page.locator("#explorer-toggle").click()

    # Theme toggle
    before = page.evaluate("document.documentElement.getAttribute('data-theme')")
    page.locator("#theme-toggle").click()
    after = page.evaluate("document.documentElement.getAttribute('data-theme')")
    check("theme toggles", before != after, (before, after))

    # Phone width: no sideways scroll, menu opens
    phone = browser.new_page(viewport={"width": 390, "height": 844})
    watch(phone)
    for route in ("#/", "#/2", "#/15", "#/tokenomics", "#/context"):
        phone.goto(f"{BASE}/{route}")
        phone.wait_for_selector(".view")
        phone.wait_for_timeout(800)
        width = phone.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        check(f"phone {route} has no sideways scroll", width[0] <= width[1] + 1, width)
    phone.locator(".menu-btn").click()
    check("phone menu opens the sidebar", phone.evaluate("document.querySelector('#sidebar').classList.contains('open')"))
    phone.screenshot(path=str(ARTIFACTS / "phone.png"))
    browser.close()

check("no console or page errors", not problems, problems)
print(f"\n{'FAILED' if failures else 'PASSED'}: {len(failures)} failing check(s) · {time.perf_counter() - started:.0f}s")
sys.exit(1 if failures else 0)

"""Verify the theme toggle button actually flips the theme (and persists)."""

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1280, "height": 860}, color_scheme="light")
    page = ctx.new_page()
    page.goto("http://127.0.0.1:5001/", wait_until="networkidle", timeout=60000)
    before = page.get_attribute("html", "data-theme")
    page.click("[data-theme-toggle]")
    page.wait_for_timeout(700)
    after = page.get_attribute("html", "data-theme")
    stored = page.evaluate("() => localStorage.getItem('pt-theme')")
    page.screenshot(path="docs/screenshots/dash-toggled.png", full_page=True)
    print(f"before={before} after={after} stored={stored}")
    browser.close()

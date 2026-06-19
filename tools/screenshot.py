"""Headless screenshot helper for visual verification.

Usage:
    python tools/screenshot.py <url> <out.png> [width] [height]

Launches headless Chromium, waits for network idle + a short settle for charts,
and writes a full-page screenshot. Used to visually verify the frontend each
build iteration without depending on the Playwright MCP browser bridge.
"""

from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright


def shot(url: str, out: str, width: int = 1440, height: int = 900, color_scheme: str = "light") -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": width, "height": height},
            color_scheme=color_scheme,  # drives theme.js default (no stored choice)
        )
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)  # let Chart.js animations settle
        page.screenshot(path=out, full_page=True)
        browser.close()


if __name__ == "__main__":
    url, out = sys.argv[1], sys.argv[2]
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 1440
    height = int(sys.argv[4]) if len(sys.argv) > 4 else 900
    color_scheme = sys.argv[5] if len(sys.argv) > 5 else "light"
    shot(url, out, width, height, color_scheme)
    print(f"saved {out}")

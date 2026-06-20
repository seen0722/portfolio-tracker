"""Responsive verification harness — checks EVERY page at desktop + mobile.

Catches the class of bug that ad-hoc, single-page checks miss:
  - horizontal overflow on any page at any breakpoint
  - content that vanishes on mobile (e.g. a shared .table-wrap hidden by a
    rule meant only for the dashboard → /transactions goes blank)

Run this after ANY global CSS or shared-class change — not just on the page you
were editing. Exits non-zero on any failure and writes one screenshot per
route × breakpoint to docs/screenshots/verify/ for visual review.

CANNOT catch stale-browser-cache regressions: every context starts cache-empty,
so it always loads the latest CSS. That class of bug is handled at the source by
cache-busting static URLs (?v=<hash>, see app/__init__.py). Treat real-device
reports as ground truth over this synthetic harness.

Usage: python tools/verify_pages.py [base_url]   # default http://127.0.0.1:5001
"""

from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5001"
BREAKPOINTS = {"mobile": 390, "desktop": 1340}

# route -> selectors that must be visible AND non-empty at every breakpoint.
# A comma-joined selector passes if ANY match is visible (e.g. table OR cards).
ROUTES = {
    "/": [".hero", "table.holdings-table, .holdings-cards, .holdings-tw table"],
    "/transactions": [".table-wrap"],
    "/macro": [".regime-banner"],
    "/report": [],  # overflow check only
}

_VISIBLE_JS = """(sel) => [...document.querySelectorAll(sel)].some(e => {
    const s = getComputedStyle(e);
    return s.display !== 'none' && s.visibility !== 'hidden' && e.offsetHeight > 0;
})"""


def main() -> int:
    out_dir = os.path.join(os.path.dirname(__file__), "..", "docs", "screenshots", "verify")
    os.makedirs(out_dir, exist_ok=True)
    failures: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for label, width in BREAKPOINTS.items():
            ctx = browser.new_context(
                viewport={"width": width, "height": 900}, reduced_motion="reduce"
            )
            page = ctx.new_page()
            for route, selectors in ROUTES.items():
                page.goto(BASE + route, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(2500)  # let async tables (heatmap/correlation) render
                # neutralise reveal animations so off-screen content is measurable
                page.add_style_tag(content=".reveal{opacity:1!important;transform:none!important;animation:none!important}")
                page.wait_for_timeout(200)

                overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
                if overflow > 2:
                    failures.append(f"[{label} {width}px] {route}: horizontal overflow +{overflow}px")

                for sel in selectors:
                    if not page.evaluate(_VISIBLE_JS, sel):
                        failures.append(f"[{label} {width}px] {route}: '{sel}' not visible / empty")

                name = (route.strip("/") or "dashboard").replace("/", "_")
                page.screenshot(path=os.path.join(out_dir, f"{name}-{label}.png"), full_page=True)
            ctx.close()
        browser.close()

    if failures:
        print("VERIFY FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print(f"VERIFY OK — {len(ROUTES)} routes × {len(BREAKPOINTS)} breakpoints: "
          "no overflow, key content visible. Screenshots in docs/screenshots/verify/")
    return 0


if __name__ == "__main__":
    sys.exit(main())

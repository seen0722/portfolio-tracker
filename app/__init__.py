"""Flask application factory.

The Flask import is deliberately kept inside ``create_app`` so that importing
``app.domain.*`` / ``app.infrastructure.*`` (pure layers) does not require Flask.
This keeps domain unit tests independent of the web framework.
"""

from __future__ import annotations

import os


def _asset_version(static_folder: str) -> str:
    """Short content hash of the cache-sensitive static assets (CSS/JS)."""
    import hashlib

    digest = hashlib.sha256()
    for rel in ("css/app.css", "js/theme.js"):
        try:
            with open(os.path.join(static_folder, rel), "rb") as handle:
                digest.update(handle.read())
        except OSError:
            pass
    return digest.hexdigest()[:10]


def create_app():
    from flask import Flask

    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )

    # CSRF protection for state-changing forms. Set a real SECRET_KEY in prod.
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or "dev-insecure-change-me"
    from flask_wtf.csrf import CSRFProtect

    CSRFProtect(app)

    # Cache-bust static assets: every url_for('static', ...) gets ?v=<hash>, so a
    # deploy that changes CSS/JS invalidates stale browser caches (phones cache
    # CSS aggressively — a new ?v= URL bypasses the old cached entry immediately).
    asset_ver = _asset_version(app.static_folder)

    @app.url_defaults
    def _add_asset_version(endpoint, values):
        if endpoint == "static" and "v" not in values:
            values["v"] = asset_ver

    from app.web.routes import bp

    app.register_blueprint(bp)

    # Daily report scheduler (in-process). Disable with ENABLE_SCHEDULER=0.
    if os.environ.get("ENABLE_SCHEDULER", "1") == "1":
        from app.dependencies import container
        from app.infrastructure.scheduler import start_scheduler

        start_scheduler(container.report_service)

    return app

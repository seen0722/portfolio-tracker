"""Flask application factory.

The Flask import is deliberately kept inside ``create_app`` so that importing
``app.domain.*`` / ``app.infrastructure.*`` (pure layers) does not require Flask.
This keeps domain unit tests independent of the web framework.
"""

from __future__ import annotations

import os


def create_app():
    from flask import Flask

    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )

    from app.web.routes import bp

    app.register_blueprint(bp)

    # Daily report scheduler (in-process). Disable with ENABLE_SCHEDULER=0.
    if os.environ.get("ENABLE_SCHEDULER", "1") == "1":
        from app.dependencies import container
        from app.infrastructure.scheduler import start_scheduler

        start_scheduler(container.report_service)

    return app

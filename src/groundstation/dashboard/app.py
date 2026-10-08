from __future__ import annotations

from pathlib import Path

from flask import Flask

from .routes import dashboard_bp


def create_app(config: dict | None = None) -> Flask:
    """Create the OrbitWatch Mission Control Flask application."""
    dashboard_dir = Path(__file__).resolve().parent

    app = Flask(
        __name__,
        template_folder=str(dashboard_dir / "templates"),
        static_folder=str(dashboard_dir / "static"),
    )

    app.config.update(
        SECRET_KEY="orbitwatch-development",
        JSON_SORT_KEYS=False,
    )

    if config:
        app.config.update(config)

    app.register_blueprint(dashboard_bp)

    return app


def run_dashboard(
    host: str = "127.0.0.1",
    port: int = 5000,
    debug: bool = False,
) -> None:
    """Run the OrbitWatch Mission Control dashboard."""
    app = create_app()
    app.run(host=host, port=port, debug=debug)

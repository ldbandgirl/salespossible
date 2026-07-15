"""Reachy Mini Apps entry point: Hermes Agent as the robot's brain."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from reachy_mini import ReachyMini, ReachyMiniApp

from hermes_mini.config import Config, load_config, save_overrides
from hermes_mini.pipeline import VoicePipeline
from hermes_mini.state import AppState

logger = logging.getLogger("hermes_mini")


class HermesMini(ReachyMiniApp):
    """Voice bridge between the robot and a self-hosted Hermes Agent.

    Note: the class name must stay `HermesMini` — the app assistant's `check`
    derives it from the package name (hermes_mini -> HermesMini).
    """

    custom_app_url = "http://0.0.0.0:7860/"
    dont_start_webserver = False

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event) -> None:
        logging.basicConfig(level=logging.INFO)
        instance_path = self._get_instance_path().parent

        cfg = load_config(instance_path)
        state = AppState()

        if self.settings_app is not None:
            register_api_routes(self.settings_app, cfg, state, instance_path)

        pipeline = VoicePipeline(reachy_mini, cfg, state, stop_event)
        pipeline.run()


def register_api_routes(app, cfg: Config, state: AppState, instance_path: Path) -> None:
    """Attach status/config endpoints to the app's FastAPI settings server."""
    from fastapi import Body

    @app.get("/api/status")
    async def get_status() -> dict:
        return state.to_dict()

    @app.get("/api/config")
    async def get_config() -> dict:
        return cfg.to_public_dict()

    @app.post("/api/config")
    async def set_config(overrides: dict = Body(...)) -> dict:
        # Masked secrets come back from the form unchanged; don't store those.
        cleaned = {
            k: v
            for k, v in overrides.items()
            if not (isinstance(v, str) and v.strip("*") == "" and v != "")
        }
        applied = cfg.apply_overrides(cleaned)
        if applied:
            save_overrides(instance_path, {k: getattr(cfg, k) for k in applied})
        return {"applied": applied, "config": cfg.to_public_dict()}

    @app.post("/api/pause")
    async def toggle_pause() -> dict:
        state.paused = not state.paused
        logger.info("Paused" if state.paused else "Resumed")
        return {"paused": state.paused}


def main() -> None:
    """Run standalone (outside the dashboard): `python -m hermes_mini.main`."""
    app = HermesMini()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()


if __name__ == "__main__":
    main()

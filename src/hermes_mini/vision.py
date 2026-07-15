"""Capture a camera frame and turn it into a data URL for Hermes.

Hermes' API accepts inline images (base64 `data:` URLs). The robot owns the
camera, so the app grabs a JPEG frame and hands it to Hermes alongside the
text — that's how Hermes gets to "see" through the Reachy Mini.
"""

from __future__ import annotations

import base64
import logging

from hermes_mini.config import Config

logger = logging.getLogger("hermes_mini.vision")


def wants_vision(cfg: Config, text: str) -> bool:
    """Decide whether this turn should include a camera frame."""
    mode = (cfg.vision_mode or "auto").lower()
    if mode == "always":
        return True
    if mode == "off":
        return False
    low = text.lower()
    return any(
        word.strip() and word.strip() in low
        for word in cfg.vision_trigger_words.split(",")
    )


def capture_jpeg(media) -> bytes | None:
    """Return the current camera frame as JPEG bytes, or None if unavailable."""
    getter = getattr(media, "get_frame_jpeg", None)
    if getter is None:
        return None
    try:
        return getter()
    except Exception as e:
        logger.warning("Camera capture failed: %s", e)
        return None


def capture_image_url(media) -> str | None:
    """Return the current camera frame as a base64 `data:` URL, or None."""
    jpeg = capture_jpeg(media)
    if not jpeg:
        return None
    encoded = base64.b64encode(jpeg).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"

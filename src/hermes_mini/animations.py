"""Small expressive motions so the robot shows what it's doing.

All motion goes through goto_target with short durations and is wrapped in
try/except: a motion hiccup must never take down the voice pipeline. Speech
head-wobble itself is handled by the SDK's wobbler (enable_wobbling), driven
by the audio we push to the speaker.
"""

from __future__ import annotations

import logging
import random
import threading

import numpy as np

logger = logging.getLogger("hermes_mini.animations")


def _head_pose(roll: float = 0.0, pitch: float = 0.0, yaw: float = 0.0, z_mm: float = 0.0):
    from reachy_mini.utils import create_head_pose

    return create_head_pose(z=z_mm, roll=roll, pitch=pitch, yaw=yaw, mm=True, degrees=True)


class AnimationPlayer:
    """Owns a background thread for the 'thinking' loop plus one-shot gestures."""

    def __init__(self, mini):
        self.mini = mini
        self._thinking_stop = threading.Event()
        self._thinking_thread: threading.Thread | None = None

    # ------------------------------------------------------------ one-shots

    def greeting(self) -> None:
        """Perk up and wiggle the antennas on startup."""
        try:
            self.mini.goto_target(
                head=_head_pose(pitch=-10, z_mm=5),
                antennas=np.deg2rad([30, -30]),
                duration=0.6,
            )
            self.mini.goto_target(antennas=np.deg2rad([-20, 20]), duration=0.3)
            self.mini.goto_target(antennas=np.deg2rad([20, -20]), duration=0.3)
            self.neutral(duration=0.6)
        except Exception as e:
            logger.debug("Greeting animation failed: %s", e)

    def listening_perk(self) -> None:
        """Quick antenna raise when an utterance opens."""
        try:
            self.mini.goto_target(antennas=np.deg2rad([25, -25]), duration=0.25)
        except Exception as e:
            logger.debug("Listening perk failed: %s", e)

    def error_shrug(self) -> None:
        """Droop antennas + small head shake when something goes wrong."""
        try:
            self.mini.goto_target(
                head=_head_pose(roll=8, pitch=8),
                antennas=np.deg2rad([-40, 40]),
                duration=0.5,
            )
            self.mini.goto_target(head=_head_pose(roll=-8, pitch=8), duration=0.4)
            self.neutral(duration=0.6)
        except Exception as e:
            logger.debug("Error shrug failed: %s", e)

    def neutral(self, duration: float = 0.5) -> None:
        try:
            self.mini.goto_target(
                head=_head_pose(), antennas=[0.0, 0.0], duration=duration
            )
        except Exception as e:
            logger.debug("Neutral pose failed: %s", e)

    # -------------------------------------------------------- thinking loop

    def start_thinking(self) -> None:
        if self._thinking_thread is not None and self._thinking_thread.is_alive():
            return
        self._thinking_stop.clear()
        self._thinking_thread = threading.Thread(
            target=self._thinking_loop, name="thinking-anim", daemon=True
        )
        self._thinking_thread.start()

    def stop_thinking(self, return_to_neutral: bool = True) -> None:
        self._thinking_stop.set()
        if self._thinking_thread is not None:
            self._thinking_thread.join(timeout=2.0)
            self._thinking_thread = None
        if return_to_neutral:
            self.neutral(duration=0.4)

    def _thinking_loop(self) -> None:
        """Slow pondering sway: gentle head tilts + asymmetric antenna drift."""
        while not self._thinking_stop.is_set():
            try:
                roll = random.uniform(-8, 8)
                pitch = random.uniform(-4, 10)
                yaw = random.uniform(-12, 12)
                right = random.uniform(-15, 35)
                left = random.uniform(-35, 15)
                self.mini.goto_target(
                    head=_head_pose(roll=roll, pitch=pitch, yaw=yaw),
                    antennas=np.deg2rad([right, left]),
                    duration=random.uniform(0.8, 1.4),
                    method="ease_in_out",
                )
            except Exception as e:
                logger.debug("Thinking loop motion failed: %s", e)
                if self._thinking_stop.wait(1.0):
                    break

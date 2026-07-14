"""Always-on utterance capture with voice activity detection.

Strategy: an adaptive energy gate (noise floor tracked continuously, speech
threshold = floor * multiplier), OR-combined with the ReSpeaker mic array's
own speech flag exposed through `media.get_DoA()`. A pre-roll ring buffer
keeps the audio from just before the gate opened so the first syllable of an
utterance isn't clipped.

All segmentation runs on the audio timeline (seconds of samples consumed),
not wall-clock time, so bursty chunk delivery doesn't skew the VAD.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable

import numpy as np
import numpy.typing as npt

from hermes_mini.audio_utils import rms, to_mono
from hermes_mini.config import Config
from hermes_mini.state import AppState

logger = logging.getLogger("hermes_mini.listener")

POLL_INTERVAL_S = 0.02
# Gaps shorter than this between speechy chunks still count as one speech run.
SPEECH_GAP_TOLERANCE_S = 0.3


class UtteranceListener:
    """Pulls mic chunks from a media source and segments them into utterances.

    `media` needs `get_audio_sample()` returning float32 arrays (or None) and
    optionally `get_DoA()` returning (angle, speech_detected).
    """

    def __init__(self, media, cfg: Config, state: AppState, sample_rate: int):
        self.media = media
        self.cfg = cfg
        self.state = state
        self.sample_rate = sample_rate
        self._noise_floor: float | None = None

    def drain(self) -> None:
        """Discard any buffered mic audio (used while the robot is speaking)."""
        while self.media.get_audio_sample() is not None:
            pass

    def capture_utterance(
        self,
        should_abort: Callable[[], bool],
        sleep: Callable[[float], None] = time.sleep,
    ) -> npt.NDArray[np.float32] | None:
        """Block until one utterance is captured; None if aborted.

        `should_abort` is polled between chunks (stop event / pause).
        """
        cfg = self.cfg
        t = 0.0  # audio-timeline clock, seconds of mic audio consumed
        pre_roll: deque[tuple[float, np.ndarray]] = deque()
        recording: list[np.ndarray] = []
        recording_started_t: float | None = None
        speech_run_s = 0.0
        last_speech_t: float | None = None

        while True:
            if should_abort():
                return None

            chunk = self.media.get_audio_sample()
            if chunk is None:
                sleep(POLL_INTERVAL_S)
                continue

            mono = to_mono(chunk)
            if mono.size == 0:
                continue
            chunk_s = mono.size / self.sample_rate
            t += chunk_s
            level = rms(mono)
            self.state.mic_level = min(1.0, level * 20.0)

            is_speech = self._classify(level)

            if recording_started_t is None:
                # WAITING: keep a pre-roll buffer, accumulate speech evidence.
                pre_roll.append((t, mono))
                horizon = t - cfg.vad_pre_roll_s
                while pre_roll and pre_roll[0][0] < horizon:
                    pre_roll.popleft()

                if is_speech:
                    if (
                        last_speech_t is not None
                        and t - last_speech_t > SPEECH_GAP_TOLERANCE_S + chunk_s
                    ):
                        speech_run_s = 0.0
                    speech_run_s += chunk_s
                    last_speech_t = t
                    if speech_run_s >= cfg.vad_min_speech_s:
                        recording = [c for _, c in pre_roll]
                        recording_started_t = t
                        self.state.phase = "listening (speech)"
                        logger.debug("Utterance opened (level=%.4f)", level)
            else:
                # RECORDING: collect until sustained silence or max length.
                recording.append(mono)
                if is_speech:
                    last_speech_t = t

                too_long = t - recording_started_t >= cfg.vad_max_utterance_s
                silence_s = t - (last_speech_t or recording_started_t)
                if silence_s >= cfg.vad_end_silence_s or too_long:
                    utterance = np.concatenate(recording)
                    duration = utterance.size / self.sample_rate
                    self.state.phase = "listening"
                    logger.info("Captured utterance: %.2fs", duration)
                    return utterance

    def _classify(self, level: float) -> bool:
        """Decide whether a chunk contains speech; updates the noise floor."""
        cfg = self.cfg
        if self._noise_floor is None:
            self._noise_floor = max(level, 1e-4)
        elif level < self._noise_floor:
            self._noise_floor = 0.7 * self._noise_floor + 0.3 * level  # fast down
        else:
            self._noise_floor = min(self._noise_floor * 1.005, level)  # slow up
        threshold = max(cfg.vad_min_rms, self._noise_floor * cfg.vad_threshold_mult)

        energetic = level >= threshold
        array_flag = False
        get_doa = getattr(self.media, "get_DoA", None)
        if get_doa is not None:
            try:
                doa = get_doa()
                if doa is not None:
                    _, array_flag = doa
            except Exception:  # never let a DoA hiccup kill the mic loop
                array_flag = False

        # The mic-array flag alone can trigger on the robot's own fans/servos;
        # require at least some energy along with it.
        return energetic or (array_flag and level >= threshold * 0.5)

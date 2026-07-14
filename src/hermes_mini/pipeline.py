"""The main listen → transcribe → Hermes → speak loop."""

from __future__ import annotations

import logging
import time

import numpy as np
import numpy.typing as npt

from hermes_mini.animations import AnimationPlayer
from hermes_mini.audio_utils import resample_linear
from hermes_mini.config import Config
from hermes_mini.hermes_client import HermesClient, HermesError
from hermes_mini.listener import UtteranceListener
from hermes_mini.speech import SpeechError, SttClient, TtsClient
from hermes_mini.state import AppState
from hermes_mini.text_utils import clamp_for_speech, strip_markdown

logger = logging.getLogger("hermes_mini.pipeline")

FALLBACK_RATE = 16000
PLAYBACK_CHUNK_S = 0.5


class VoicePipeline:
    """Runs on the app's main thread until stop_event is set."""

    def __init__(self, mini, cfg: Config, state: AppState, stop_event):
        self.mini = mini
        self.cfg = cfg
        self.state = state
        self.stop_event = stop_event

        in_rate = mini.media.get_input_audio_samplerate()
        self.in_rate = in_rate if in_rate and in_rate > 0 else FALLBACK_RATE
        out_rate = mini.media.get_output_audio_samplerate()
        self.out_rate = out_rate if out_rate and out_rate > 0 else FALLBACK_RATE

        self.listener = UtteranceListener(mini.media, cfg, state, self.in_rate)
        self.hermes = HermesClient(cfg)
        self.stt = SttClient(cfg)
        self.tts = TtsClient(cfg)
        self.animations = AnimationPlayer(mini)

    # ---------------------------------------------------------------- setup

    def run(self) -> None:
        logger.info(
            "Voice pipeline starting (mic %d Hz, speaker %d Hz)",
            self.in_rate,
            self.out_rate,
        )
        self.mini.media.start_recording()
        self.mini.media.start_playing()
        try:
            self.mini.enable_wobbling()  # audio-reactive head motion during speech
        except Exception as e:
            logger.debug("Could not enable wobbling: %s", e)

        self.animations.greeting()
        if self.cfg.greeting:
            self._try_speak(self.cfg.greeting)

        self.state.phase = "listening"
        try:
            while not self.stop_event.is_set():
                self._one_turn()
        finally:
            self._shutdown()

    def _shutdown(self) -> None:
        self.state.phase = "stopping"
        self.animations.stop_thinking(return_to_neutral=False)
        for closer in (
            lambda: self.mini.disable_wobbling(),
            lambda: self.mini.media.stop_recording(),
            lambda: self.mini.media.stop_playing(),
            self.hermes.close,
            self.stt.close,
            self.tts.close,
        ):
            try:
                closer()
            except Exception as e:
                logger.debug("Shutdown step failed: %s", e)
        logger.info("Voice pipeline stopped.")

    # ------------------------------------------------------------ main loop

    def _one_turn(self) -> None:
        if self.state.paused:
            self.listener.drain()
            self.stop_event.wait(0.2)
            return

        self.state.phase = "listening"
        utterance = self.listener.capture_utterance(
            should_abort=lambda: self.stop_event.is_set() or self.state.paused
        )
        if utterance is None:
            return

        self.animations.listening_perk()
        self.state.phase = "thinking"
        self.animations.start_thinking()
        try:
            heard = self.stt.transcribe(utterance, self.in_rate)
            if not heard:
                logger.info("Empty transcription, back to listening.")
                return
            self.state.last_heard = heard
            logger.info("Heard: %s", heard)

            reply = self.hermes.send(heard)
            self.state.hermes_mode_in_use = self.hermes.mode_in_use
            self.state.last_reply = reply
            self.state.turns += 1
            logger.info("Hermes: %s", reply[:200])
        except (HermesError, SpeechError) as e:
            self._handle_error(str(e))
            return
        except Exception as e:
            self._handle_error(f"{type(e).__name__}: {e}")
            return
        finally:
            self.animations.stop_thinking()

        speakable = clamp_for_speech(strip_markdown(reply))
        if speakable:
            self.state.phase = "speaking"
            self._try_speak(speakable)
        self.state.last_error = ""

    def _handle_error(self, message: str) -> None:
        logger.error("Turn failed: %s", message)
        self.state.last_error = message
        self.animations.stop_thinking()
        self.animations.error_shrug()
        # Don't hot-loop on a persistent failure (e.g. VPS down).
        self.stop_event.wait(1.0)

    # -------------------------------------------------------------- speaking

    def _try_speak(self, text: str) -> None:
        try:
            samples, rate = self.tts.synthesize(text)
            self._play(samples, rate)
        except SpeechError as e:
            self._handle_error(str(e))
        except Exception as e:
            self._handle_error(f"TTS/playback failed: {type(e).__name__}: {e}")

    def _play(self, samples: npt.NDArray[np.float32], rate: int) -> None:
        """Push audio to the speaker and wait it out, discarding mic input."""
        out = resample_linear(samples, rate, self.out_rate)
        duration = out.size / self.out_rate
        chunk = max(1, int(PLAYBACK_CHUNK_S * self.out_rate))
        started = time.monotonic()

        for i in range(0, out.size, chunk):
            if self.stop_event.is_set():
                return
            self.mini.media.push_audio_sample(out[i : i + chunk])
            self.listener.drain()

        # Wait for playback to finish (we only know the nominal duration).
        while time.monotonic() - started < duration + 0.3:
            if self.stop_event.wait(0.05):
                return
            self.listener.drain()
        # A last drain so the robot doesn't transcribe its own tail end.
        time.sleep(0.2)
        self.listener.drain()

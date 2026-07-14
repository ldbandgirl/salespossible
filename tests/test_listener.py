import numpy as np

from hermes_mini.config import Config
from hermes_mini.listener import UtteranceListener
from hermes_mini.state import AppState

RATE = 16000
CHUNK = 320  # 20 ms


class FakeMedia:
    """Feeds a pre-built list of 20 ms chunks to the listener."""

    def __init__(self, chunks):
        self.chunks = list(chunks)

    def get_audio_sample(self):
        if self.chunks:
            return self.chunks.pop(0)
        return None

    def get_DoA(self):
        return (0.0, False)


def seconds_of(level: float, seconds: float, freq: float = 300.0):
    n_chunks = int(seconds * RATE / CHUNK)
    out = []
    for i in range(n_chunks):
        t = (np.arange(CHUNK) + i * CHUNK) / RATE
        out.append((level * np.sin(2 * np.pi * freq * t)).astype(np.float32))
    return out


def make_listener(chunks):
    cfg = Config()
    cfg.vad_min_rms = 0.02
    state = AppState()
    media = FakeMedia(chunks)
    return UtteranceListener(media, cfg, state, RATE), media


def test_captures_speech_between_silence():
    chunks = (
        seconds_of(0.001, 1.0)  # quiet room
        + seconds_of(0.3, 1.5)  # speech
        + seconds_of(0.001, 2.0)  # silence closes the utterance
    )
    listener, media = make_listener(chunks)

    utterance = listener.capture_utterance(
        should_abort=lambda: not media.chunks, sleep=lambda s: None
    )
    assert utterance is not None
    duration = utterance.size / RATE
    # Should contain roughly the speech plus pre-roll, not the trailing silence.
    assert 1.2 < duration < 3.2


def test_ignores_pure_silence():
    listener, media = make_listener(seconds_of(0.001, 3.0))
    utterance = listener.capture_utterance(
        should_abort=lambda: not media.chunks, sleep=lambda s: None
    )
    assert utterance is None  # aborted once chunks ran out, nothing captured


def test_short_blip_does_not_open_utterance():
    chunks = (
        seconds_of(0.001, 0.5)
        + seconds_of(0.3, 0.1)  # 100 ms pop — below vad_min_speech_s
        + seconds_of(0.001, 2.0)
    )
    listener, media = make_listener(chunks)
    utterance = listener.capture_utterance(
        should_abort=lambda: not media.chunks, sleep=lambda s: None
    )
    assert utterance is None


def test_abort_returns_none():
    listener, _ = make_listener([])
    assert listener.capture_utterance(should_abort=lambda: True) is None

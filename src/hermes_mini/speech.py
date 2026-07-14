"""Speech-to-text and text-to-speech providers.

Hermes' HTTP API is text-only (its voice mode lives in the Hermes CLI and
Discord integrations), so the robot handles audio conversion itself:

  STT: OpenAI (`whisper-1` by default) or Groq (`whisper-large-v3-turbo`)
  TTS: OpenAI (`gpt-4o-mini-tts`, WAV out) or ElevenLabs (raw PCM 16 kHz out)
"""

from __future__ import annotations

import logging

import httpx
import numpy as np
import numpy.typing as npt

from hermes_mini.audio_utils import decode_pcm16, decode_wav, encode_wav16
from hermes_mini.config import Config

logger = logging.getLogger("hermes_mini.speech")

OPENAI_BASE = "https://api.openai.com/v1"
GROQ_BASE = "https://api.groq.com/openai/v1"
ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"

DEFAULT_STT_MODELS = {
    "openai": "whisper-1",
    "groq": "whisper-large-v3-turbo",
}


class SpeechError(RuntimeError):
    """Raised when an STT/TTS provider call fails."""


class SttClient:
    """Transcribe recorded utterances via an OpenAI-compatible audio API."""

    def __init__(self, cfg: Config, transport: httpx.BaseTransport | None = None):
        self.cfg = cfg
        self._client = httpx.Client(
            timeout=httpx.Timeout(60.0, connect=10.0), transport=transport
        )

    def close(self) -> None:
        self._client.close()

    def transcribe(self, samples: npt.NDArray[np.float32], rate: int) -> str:
        provider = (self.cfg.stt_provider or "openai").lower()
        if provider == "groq":
            base, key = GROQ_BASE, self.cfg.groq_api_key
        elif provider == "openai":
            base, key = OPENAI_BASE, self.cfg.openai_api_key
        else:
            raise SpeechError(f"Unknown STT provider: {provider}")
        if not key:
            raise SpeechError(
                f"No API key configured for STT provider '{provider}'. "
                "Set OPENAI_API_KEY or GROQ_API_KEY."
            )

        model = self.cfg.stt_model or DEFAULT_STT_MODELS[provider]
        wav = encode_wav16(samples, rate)
        data = {"model": model}
        if self.cfg.language:
            data["language"] = self.cfg.language

        try:
            resp = self._client.post(
                f"{base}/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                data=data,
                files={"file": ("speech.wav", wav, "audio/wav")},
            )
        except httpx.HTTPError as e:
            raise SpeechError(f"STT request failed: {e}") from e
        if resp.status_code >= 400:
            raise SpeechError(f"STT error {resp.status_code}: {resp.text[:300]}")
        return (resp.json().get("text") or "").strip()


class TtsClient:
    """Synthesize reply audio. Returns (mono float32 samples, sample rate)."""

    def __init__(self, cfg: Config, transport: httpx.BaseTransport | None = None):
        self.cfg = cfg
        self._client = httpx.Client(
            timeout=httpx.Timeout(60.0, connect=10.0), transport=transport
        )

    def close(self) -> None:
        self._client.close()

    def synthesize(self, text: str) -> tuple[npt.NDArray[np.float32], int]:
        provider = (self.cfg.tts_provider or "openai").lower()
        if provider == "elevenlabs":
            return self._elevenlabs(text)
        if provider == "openai":
            return self._openai(text)
        raise SpeechError(f"Unknown TTS provider: {provider}")

    def _openai(self, text: str) -> tuple[npt.NDArray[np.float32], int]:
        if not self.cfg.openai_api_key:
            raise SpeechError("OPENAI_API_KEY is required for OpenAI TTS.")
        try:
            resp = self._client.post(
                f"{OPENAI_BASE}/audio/speech",
                headers={"Authorization": f"Bearer {self.cfg.openai_api_key}"},
                json={
                    "model": self.cfg.tts_model or "gpt-4o-mini-tts",
                    "voice": self.cfg.tts_voice or "alloy",
                    "input": text,
                    "response_format": "wav",
                },
            )
        except httpx.HTTPError as e:
            raise SpeechError(f"TTS request failed: {e}") from e
        if resp.status_code >= 400:
            raise SpeechError(f"TTS error {resp.status_code}: {resp.text[:300]}")
        return decode_wav(resp.content)

    def _elevenlabs(self, text: str) -> tuple[npt.NDArray[np.float32], int]:
        if not self.cfg.elevenlabs_api_key:
            raise SpeechError("ELEVENLABS_API_KEY is required for ElevenLabs TTS.")
        if not self.cfg.elevenlabs_voice_id:
            raise SpeechError("ELEVENLABS_VOICE_ID is required for ElevenLabs TTS.")
        url = (
            f"{ELEVENLABS_BASE}/text-to-speech/{self.cfg.elevenlabs_voice_id}"
            "?output_format=pcm_16000"
        )
        try:
            resp = self._client.post(
                url,
                headers={"xi-api-key": self.cfg.elevenlabs_api_key},
                json={
                    "text": text,
                    "model_id": self.cfg.elevenlabs_model or "eleven_flash_v2_5",
                },
            )
        except httpx.HTTPError as e:
            raise SpeechError(f"TTS request failed: {e}") from e
        if resp.status_code >= 400:
            raise SpeechError(f"TTS error {resp.status_code}: {resp.text[:300]}")
        return decode_pcm16(resp.content), 16000

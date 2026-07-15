"""Speech-to-text and text-to-speech providers.

Hermes' HTTP API is text-only (its voice mode lives in the Hermes CLI and
Discord integrations), so the robot handles audio conversion itself:

  STT: Groq (`whisper-large-v3-turbo`, free tier — default), OpenAI
       (`whisper-1`), or MiniMax (experimental, OpenAI-compatible
       `/v1/audio/transcriptions`; MiniMax has no officially documented ASR
       endpoint, so it may not work with every account)
  TTS: MiniMax (`t2a_v2`, hex-encoded PCM 16 kHz — default), ElevenLabs
       (raw PCM 16 kHz out), or OpenAI (`gpt-4o-mini-tts`, WAV out)

MiniMax's Token Plan key covers text-to-speech but NOT a reliable
speech-to-text API, which is why hearing defaults to Groq's free tier.
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
MINIMAX_BASE = "https://api.minimax.io/v1"

DEFAULT_STT_MODELS = {
    "openai": "whisper-1",
    "groq": "whisper-large-v3-turbo",
    "minimax": "whisper-large-v3",
}

# Provider -> (base URL, config attribute holding the API key)
STT_PROVIDERS = {
    "groq": (GROQ_BASE, "groq_api_key"),
    "openai": (OPENAI_BASE, "openai_api_key"),
    "minimax": (MINIMAX_BASE, "minimax_api_key"),
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
        provider = (self.cfg.stt_provider or "groq").lower()
        if provider not in STT_PROVIDERS:
            raise SpeechError(f"Unknown STT provider: {provider}")
        base, key_attr = STT_PROVIDERS[provider]
        key = getattr(self.cfg, key_attr)
        if not key:
            hint = {
                "groq": "Set a free Groq key at console.groq.com.",
                "minimax": "Set your MiniMax API key.",
                "openai": "Set your OpenAI key.",
            }[provider]
            raise SpeechError(
                f"No API key configured for STT provider '{provider}'. {hint}"
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
        if provider == "minimax":
            return self._minimax(text)
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

    def _minimax(self, text: str) -> tuple[npt.NDArray[np.float32], int]:
        """MiniMax t2a_v2: JSON in, hex-encoded PCM (s16le mono) out."""
        if not self.cfg.minimax_api_key:
            raise SpeechError("MINIMAX_API_KEY is required for MiniMax TTS.")
        url = f"{MINIMAX_BASE}/t2a_v2"
        if self.cfg.minimax_group_id:
            url += f"?GroupId={self.cfg.minimax_group_id}"
        payload = {
            "model": self.cfg.minimax_tts_model or "speech-02-turbo",
            "text": text,
            "stream": False,
            "output_format": "hex",
            "voice_setting": {
                "voice_id": self.cfg.minimax_voice_id or "Wise_Woman",
                "speed": 1.0,
                "vol": 1.0,
                "pitch": 0,
            },
            "audio_setting": {"sample_rate": 16000, "format": "pcm", "channel": 1},
        }
        try:
            resp = self._client.post(
                url,
                headers={"Authorization": f"Bearer {self.cfg.minimax_api_key}"},
                json=payload,
            )
        except httpx.HTTPError as e:
            raise SpeechError(f"TTS request failed: {e}") from e
        if resp.status_code >= 400:
            raise SpeechError(f"TTS error {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        base_resp = data.get("base_resp") or {}
        if base_resp.get("status_code", 0) != 0:
            raise SpeechError(
                f"MiniMax TTS error {base_resp.get('status_code')}: "
                f"{base_resp.get('status_msg', 'unknown')}"
            )
        audio_hex = (data.get("data") or {}).get("audio")
        if not audio_hex:
            raise SpeechError("MiniMax TTS returned no audio.")
        try:
            pcm = bytes.fromhex(audio_hex)
        except ValueError as e:
            raise SpeechError(f"MiniMax TTS returned invalid hex audio: {e}") from e
        rate = int((data.get("extra_info") or {}).get("audio_sample_rate", 16000))
        return decode_pcm16(pcm), rate

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

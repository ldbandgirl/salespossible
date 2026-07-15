"""Configuration loading and persistence for the hermes_mini app.

Precedence (lowest to highest):
  1. dataclass defaults
  2. environment variables (including a `.env` file in the app instance dir)
  3. `settings.json` overrides saved from the web UI
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

logger = logging.getLogger("hermes_mini.config")

SETTINGS_FILENAME = "settings.json"

DEFAULT_SYSTEM_PROMPT = (
    "You are Hermes, and you are physically embodied in a small expressive desktop "
    "robot called Reachy Mini, sitting on your user's desk. You hear them through the "
    "robot's microphone and answer through its speaker. Speak naturally and keep "
    "replies short — one to three sentences — unless the user clearly asks for more. "
    "Your replies are read aloud by text-to-speech: use plain speakable prose, no "
    "markdown, no bullet lists, no code blocks, no emojis, no URLs unless asked."
)

# Environment variable name for each config field. Fields not listed here are
# tunables only settable via settings.json / the web UI.
ENV_MAP = {
    "hermes_base_url": "HERMES_BASE_URL",
    "hermes_api_key": "HERMES_API_KEY",
    "hermes_model": "HERMES_MODEL",
    "hermes_mode": "HERMES_MODE",
    "hermes_conversation": "HERMES_CONVERSATION",
    "system_prompt": "HERMES_SYSTEM_PROMPT",
    "stt_provider": "STT_PROVIDER",
    "stt_model": "STT_MODEL",
    "openai_api_key": "OPENAI_API_KEY",
    "groq_api_key": "GROQ_API_KEY",
    "language": "STT_LANGUAGE",
    "tts_provider": "TTS_PROVIDER",
    "tts_model": "TTS_MODEL",
    "tts_voice": "TTS_VOICE",
    "elevenlabs_api_key": "ELEVENLABS_API_KEY",
    "elevenlabs_voice_id": "ELEVENLABS_VOICE_ID",
    "elevenlabs_model": "ELEVENLABS_MODEL",
    "minimax_api_key": "MINIMAX_API_KEY",
    "minimax_group_id": "MINIMAX_GROUP_ID",
    "minimax_tts_model": "MINIMAX_TTS_MODEL",
    "minimax_voice_id": "MINIMAX_VOICE_ID",
    "greeting": "HERMES_MINI_GREETING",
    "vision_mode": "VISION_MODE",
}

# Fields hidden (masked) when serving config to the web UI.
SECRET_FIELDS = {
    "hermes_api_key",
    "openai_api_key",
    "groq_api_key",
    "elevenlabs_api_key",
    "minimax_api_key",
}


@dataclass
class Config:
    """Runtime configuration. Mutable: the pipeline reads attributes live."""

    # Hermes Agent
    hermes_base_url: str = ""
    hermes_api_key: str = ""
    hermes_model: str = "hermes-agent"
    hermes_mode: str = "auto"  # auto | responses | chat
    hermes_conversation: str = "reachy-mini"
    hermes_timeout_s: float = 180.0
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    history_max_turns: int = 12  # chat mode only
    streaming: bool = True  # speak each sentence as Hermes generates it
    tts_min_sentence_chars: int = 24  # don't synthesize tiny fragments alone

    # Speech to text (MiniMax has no reliable public ASR, so hearing
    # defaults to Groq's free tier; MiniMax STT is experimental)
    stt_provider: str = "groq"  # groq | minimax | openai
    stt_model: str = ""  # empty = provider default
    openai_api_key: str = ""
    groq_api_key: str = ""
    language: str = ""  # e.g. "en", empty = auto

    # Text to speech (MiniMax Token Plan key covers this)
    tts_provider: str = "minimax"  # minimax | elevenlabs | openai
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "alloy"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    elevenlabs_model: str = "eleven_flash_v2_5"
    minimax_api_key: str = ""
    minimax_group_id: str = ""
    minimax_tts_model: str = "speech-02-turbo"
    minimax_voice_id: str = "Wise_Woman"

    # Listening / voice activity detection
    vad_threshold_mult: float = 4.0  # speech threshold = noise floor * mult
    vad_min_rms: float = 0.010  # absolute floor for the speech threshold
    vad_min_speech_s: float = 0.30  # speech needed to open an utterance
    vad_end_silence_s: float = 0.7  # silence that closes an utterance
    vad_pre_roll_s: float = 0.5  # audio kept from before speech started
    vad_max_utterance_s: float = 30.0

    # Vision — attach a camera frame to the message so Hermes can "see".
    # off = never; auto = when the user says a trigger word; always = every turn.
    # (Requires the model behind Hermes to accept image input.)
    vision_mode: str = "auto"  # off | auto | always
    vision_trigger_words: str = (
        "see,look,vision,camera,eyes,watch,show you,in front of you,"
        "what is this,what am i,what do you,what's this,describe,what color,"
        "read this,holding,pointing,wearing"
    )

    # Behavior
    greeting: str = "Hermes online."

    def apply_env(self) -> None:
        """Overlay environment variables onto this config."""
        for field_name, env_name in ENV_MAP.items():
            value = os.environ.get(env_name)
            if value is not None and value != "":
                setattr(self, field_name, value)

    def apply_overrides(self, overrides: dict) -> list[str]:
        """Overlay a dict of overrides (from settings.json or the web UI).

        Unknown keys are ignored. Values are coerced to the field's current
        type. Returns the list of field names actually applied.
        """
        applied = []
        valid = {f.name: f for f in fields(self)}
        for key, value in overrides.items():
            if key not in valid or value is None:
                continue
            current = getattr(self, key)
            try:
                if isinstance(current, bool):
                    value = bool(value)
                elif isinstance(current, float):
                    value = float(value)
                elif isinstance(current, int):
                    value = int(value)
                else:
                    value = str(value)
            except (TypeError, ValueError):
                logger.warning("Ignoring bad value for config field %s: %r", key, value)
                continue
            setattr(self, key, value)
            applied.append(key)
        return applied

    def to_public_dict(self) -> dict:
        """Serialize for the web UI, masking secrets (empty string = unset)."""
        data = asdict(self)
        for key in SECRET_FIELDS:
            data[key] = "********" if data[key] else ""
        return data


def load_config(instance_path: Path | None) -> Config:
    """Build the config from defaults, .env / environment, and saved overrides."""
    if instance_path is not None:
        env_path = Path(instance_path) / ".env"
        if env_path.exists():
            try:
                from dotenv import load_dotenv

                load_dotenv(dotenv_path=str(env_path), override=True)
                logger.info("Loaded environment from %s", env_path)
            except Exception as e:
                logger.warning("Could not load %s: %s", env_path, e)

    cfg = Config()
    cfg.apply_env()

    if instance_path is not None:
        settings_path = Path(instance_path) / SETTINGS_FILENAME
        if settings_path.exists():
            try:
                overrides = json.loads(settings_path.read_text())
                cfg.apply_overrides(overrides)
                logger.info("Applied saved settings from %s", settings_path)
            except Exception as e:
                logger.warning("Could not read %s: %s", settings_path, e)

    return cfg


def save_overrides(instance_path: Path | None, overrides: dict) -> None:
    """Merge overrides into settings.json so they survive app restarts."""
    if instance_path is None:
        return
    settings_path = Path(instance_path) / SETTINGS_FILENAME
    existing: dict = {}
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text())
        except Exception:
            existing = {}
    existing.update(overrides)
    settings_path.write_text(json.dumps(existing, indent=2))
    logger.info("Saved settings to %s", settings_path)

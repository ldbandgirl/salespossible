"""`hermes-mini-check` — verify Hermes/STT/TTS setup from any machine.

Run this on your laptop (or the robot) before expecting the app to work:

    hermes-mini-check                 # connectivity + auth checks
    hermes-mini-check --say "hello"   # full round trip through Hermes

Reads the same environment variables / .env file as the app.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

from hermes_mini.config import load_config
from hermes_mini.hermes_client import HermesClient, HermesError

OK = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
SKIP = "\033[93m-\033[0m"


def _check(label: str, fn) -> bool:
    try:
        detail = fn()
        print(f"{OK} {label}" + (f" — {detail}" if detail else ""))
        return True
    except Exception as e:
        print(f"{FAIL} {label} — {e}")
        return False


def _skip(label: str, reason: str) -> None:
    print(f"{SKIP} {label} — skipped ({reason})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check hermes_mini configuration.")
    parser.add_argument("--say", metavar="TEXT", help="send TEXT to Hermes and print the reply")
    parser.add_argument(
        "--env-dir",
        type=Path,
        default=Path.cwd(),
        help="directory containing the .env file (default: current directory)",
    )
    args = parser.parse_args()

    cfg = load_config(args.env_dir)
    failures = 0

    print("— Hermes Agent —")
    if not cfg.hermes_base_url:
        print(f"{FAIL} HERMES_BASE_URL is not set")
        failures += 1
    else:
        hermes = HermesClient(cfg)
        if not _check(
            f"Reach Hermes at {cfg.hermes_base_url} (/v1/models)",
            lambda: "models: " + ", ".join(hermes.ping() or ["(none)"]),
        ):
            failures += 1
        elif args.say:
            def roundtrip() -> str:
                reply = hermes.send(args.say)
                return f"reply: {reply[:200]}"

            if not _check(f"Chat round trip ({cfg.hermes_mode} mode)", roundtrip):
                failures += 1
        hermes.close()

    print("\n— Speech to text —")
    provider = cfg.stt_provider.lower()
    if provider == "openai":
        failures += _key_ping(
            "OpenAI key",
            cfg.openai_api_key,
            "https://api.openai.com/v1/models",
            {"Authorization": f"Bearer {cfg.openai_api_key}"},
        )
    elif provider == "groq":
        failures += _key_ping(
            "Groq key",
            cfg.groq_api_key,
            "https://api.groq.com/openai/v1/models",
            {"Authorization": f"Bearer {cfg.groq_api_key}"},
        )
    else:
        print(f"{FAIL} Unknown STT_PROVIDER: {provider}")
        failures += 1

    print("\n— Text to speech —")
    provider = cfg.tts_provider.lower()
    if provider == "openai":
        failures += _key_ping(
            "OpenAI key",
            cfg.openai_api_key,
            "https://api.openai.com/v1/models",
            {"Authorization": f"Bearer {cfg.openai_api_key}"},
        )
    elif provider == "elevenlabs":
        if not cfg.elevenlabs_voice_id:
            print(f"{FAIL} ELEVENLABS_VOICE_ID is not set")
            failures += 1
        failures += _key_ping(
            "ElevenLabs key",
            cfg.elevenlabs_api_key,
            "https://api.elevenlabs.io/v1/user",
            {"xi-api-key": cfg.elevenlabs_api_key},
        )
    else:
        print(f"{FAIL} Unknown TTS_PROVIDER: {provider}")
        failures += 1

    print()
    if failures:
        print(f"{failures} check(s) failed.")
        sys.exit(1)
    print("All checks passed. Install the app on your Reachy Mini and talk to Hermes!")


def _key_ping(label: str, key: str, url: str, headers: dict) -> int:
    """Return 1 on failure, 0 on success (for failure counting)."""
    if not key:
        print(f"{FAIL} {label} is not set")
        return 1

    def ping() -> str:
        resp = httpx.get(url, headers=headers, timeout=15.0)
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:120]}")
        return "authenticated"

    return 0 if _check(label, ping) else 1


if __name__ == "__main__":
    main()

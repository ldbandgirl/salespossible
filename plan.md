# Plan: Hermes Agent on Reachy Mini ("hermes_mini")

## What the user wants

Use their self-hosted [Hermes Agent](https://github.com/NousResearch/hermes-agent)
(running on a Hostinger VPS) as the brain of their Reachy Mini Wireless robot,
sitting on their desk on home Wi-Fi. Talk to the robot, robot answers as Hermes.

## Answered questions

| Question | Answer |
|---|---|
| Hermes API surface | Hermes API server (`hermes gateway`), OpenAI-compatible: `/v1/chat/completions`, `/v1/responses` (server-side memory via named `conversation`), bearer auth with `API_SERVER_KEY` |
| Voice support in Hermes | Hermes voice mode is CLI/Discord-only; the HTTP API is **text-only** → this app does STT + TTS itself |
| Robot model | **Wireless** (standalone, daemon on the robot's CM4 at `reachy-mini.local:8000`) |
| Interaction | **Always listening** with voice-activity detection while the app runs |

## Architecture

```
 ┌──────────────────────── Reachy Mini (CM4, on Wi-Fi) ───────────────────────┐
 │  hermes_mini app (Python, installed via dashboard)                         │
 │                                                                            │
 │  mic (16 kHz) ─► VAD listener ─► STT (OpenAI/Groq) ─► HermesClient ─────────┼──► Hostinger VPS
 │                                                        │                   │    hermes gateway
 │  speaker ◄─ push_audio_sample ◄─ TTS (OpenAI/11Labs) ◄─┘  reply text       │    /v1/responses
 │      │                                                                     │    (bearer key,
 │  head wobble (SDK wobbler) + thinking/listening animations                 │     HTTPS)
 └────────────────────────────────────────────────────────────────────────────┘
```

Key point: the robot is behind home NAT, the VPS is public → the robot always
dials **out** to Hermes. Nothing on the home network needs port-forwarding.

## Design decisions

- **Python Reachy Mini app** (`ReachyMiniApp` subclass, `reachy_mini_apps`
  entry point) so the dashboard can install/start/stop it. Runs on the robot.
- **VAD**: energy-based with adaptive noise floor, OR-combined with the
  ReSpeaker mic array's built-in speech flag from `media.get_DoA()`.
  Pre-roll buffer so the first syllable isn't clipped.
- **STT/TTS are pluggable** (Hermes' HTTP API doesn't do audio):
  STT = OpenAI or Groq Whisper; TTS = OpenAI or ElevenLabs.
  One `OPENAI_API_KEY` covers both defaults.
- **Hermes modes**: `auto` tries `/v1/responses` with `store: true` and a named
  `conversation` (Hermes keeps memory server-side, surviving app restarts);
  falls back to `/v1/chat/completions` with a client-side rolling history.
- **Motion**: SDK `enable_wobbling()` gives audio-reactive head motion during
  speech for free; small `goto_target` loops for listening/thinking cues.
  Mic input is discarded while the robot speaks (no barge-in in v1) to avoid
  the robot hearing itself.
- **Settings/status web UI** served by the app base class's FastAPI server on
  port 7860 (`custom_app_url`), with `/api/status`, `/api/config`, `/api/pause`.
- **`hermes-mini-check` CLI** to verify Hermes/STT/TTS credentials from any
  machine before installing on the robot.

## Out of scope for v1 (roadmap)

- Barge-in (interrupting the robot mid-answer)
- Wake word
- Turning toward the speaker using the DoA angle
- Camera → Hermes image input (Hermes API accepts images; easy follow-up)
- Antenna-press mute toggle

---
title: Hermes on Reachy Mini
emoji: 🤖
colorFrom: yellow
colorTo: gray
sdk: static
pinned: false
short_description: Your self-hosted Hermes Agent as your robot's brain
tags:
 - reachy_mini
 - reachy_mini_python_app
---

# ☤ Hermes on Reachy Mini

Talk to your desk robot; your own [Hermes Agent](https://github.com/NousResearch/hermes-agent)
answers. This Reachy Mini app turns the robot into a voice body for a
self-hosted Hermes: the robot listens, sends what you said to your Hermes
server, speaks the reply through its speaker, and moves while it talks.
Because Hermes keeps its own persistent memory, skills, and tools, the robot
gets all of that for free.

```
 you speak ─► robot mic ─► voice activity detection ─► speech-to-text
                                                            │
        robot speaker ◄─ text-to-speech ◄─ Hermes Agent ◄───┘
        (+ head wobble, antenna/thinking animations)   (your VPS, over HTTPS)
```

The robot only ever dials **out** to your Hermes server, so nothing on your
home network needs port-forwarding.

## What you need

- A **Reachy Mini** (Wireless) on your Wi-Fi
- A **Hermes Agent** running on a VPS (Hostinger, or anywhere) with its API
  server enabled and reachable over HTTPS — setup below
- An **STT/TTS API key**: an OpenAI key covers both defaults
  (speech-to-text and text-to-speech; Hermes' HTTP API is text-only, its
  built-in voice mode only works in the Hermes CLI/Discord). Groq (STT) and
  ElevenLabs (TTS) are supported alternatives.

## 1. Expose Hermes on your VPS

On the VPS, enable Hermes' API server in `~/.hermes/.env`:

```bash
API_SERVER_ENABLED=true
API_SERVER_KEY=<generate something long and random>   # e.g. openssl rand -hex 32
# keep the default API_SERVER_HOST=127.0.0.1 and put a reverse proxy in front
```

and run the gateway (`hermes gateway`, ideally under systemd so it survives
reboots). The API listens on `127.0.0.1:8642`.

**Put HTTPS in front of it.** The API key grants Hermes' full toolset —
including terminal access on your VPS — so never expose port 8642 raw over
HTTP. The simplest reverse proxy is [Caddy](https://caddyserver.com), which
gets a Let's Encrypt certificate automatically. Point a DNS record (e.g.
`hermes.yourdomain.com`) at the VPS and use this `Caddyfile`:

```
hermes.yourdomain.com {
    reverse_proxy 127.0.0.1:8642
}
```

Sanity check from any machine:

```bash
curl https://hermes.yourdomain.com/v1/models \
  -H "Authorization: Bearer <your API_SERVER_KEY>"
```

## 2. Check your configuration (optional but recommended)

On your laptop:

```bash
pip install git+https://github.com/ldbandgirl/salespossible
cp .env.example .env          # fill in HERMES_BASE_URL, HERMES_API_KEY, OPENAI_API_KEY
hermes-mini-check             # connectivity + auth checks
hermes-mini-check --say "hi"  # full round trip through Hermes
```

## 3. Install on the robot

The robot's app marketplace installs from Hugging Face Spaces. This app is
published as the Space **`aiclawbots/hermes_mini`** — in the dashboard at
`http://reachy-mini.local:8000`, open the app store, search **hermes_mini**,
and hit Install.

To publish your own copy (e.g. after forking), use the official assistant
from a clone whose folder name is the app name:

```bash
pip install reachy-mini
git clone https://github.com/ldbandgirl/salespossible hermes_mini
cd hermes_mini
reachy-mini-app-assistant check .
reachy-mini-app-assistant publish . "Update" --public
```

Then open the app's settings page (the dashboard links to it once the app is
running, on port 7860) and fill in:

- **Hermes base URL** — `https://hermes.yourdomain.com`
- **Hermes API key** — your `API_SERVER_KEY`
- **OpenAI API key** — for speech-to-text and text-to-speech

Alternatively, put a `.env` file (see `.env.example`) in the installed app
folder on the robot before starting it.

## 4. Talk to it

Start the app from the dashboard. The robot perks up, says its greeting, and
listens continuously:

1. **Speak normally** — voice activity detection spots your sentence
   (antennas perk up when it hears you)
2. **Thinking** — the head sways while Hermes works; agent turns with tools
   can take a little while
3. **Answer** — the reply is spoken aloud with audio-reactive head wobble

The settings page (port 7860 on the robot) shows live status — what it heard,
what Hermes replied, mic level — and has a **Pause** button, listening
sensitivity, voices, and provider switches. Changes apply immediately.

## Configuration reference

| Setting / env var | Default | Meaning |
|---|---|---|
| `HERMES_BASE_URL` | — | Public HTTPS URL of your Hermes API server |
| `HERMES_API_KEY` | — | Bearer token (`API_SERVER_KEY` on the VPS) |
| `HERMES_MODE` | `auto` | `responses` = server-side memory via a named conversation; `chat` = stateless with local rolling history; `auto` tries responses, falls back to chat |
| `HERMES_CONVERSATION` | `reachy-mini` | Conversation name Hermes chains turns under (responses mode) |
| `HERMES_MODEL` | `hermes-agent` | Model name the API server advertises |
| `HERMES_SYSTEM_PROMPT` | built-in | Embodiment prompt (keep replies short & speakable) |
| `STT_PROVIDER` | `openai` | `openai` (whisper-1) or `groq` (whisper-large-v3-turbo, free tier) |
| `TTS_PROVIDER` | `openai` | `openai` (gpt-4o-mini-tts), `elevenlabs`, or `minimax` (t2a_v2) |
| `TTS_VOICE` | `alloy` | OpenAI voice name |
| `MINIMAX_API_KEY` | — | MiniMax platform API key for TTS (`MINIMAX_GROUP_ID`, `MINIMAX_VOICE_ID` optional) |
| `STT_LANGUAGE` | auto | Force a language code like `en` |

VAD tunables (`vad_threshold_mult`, `vad_end_silence_s`, …) are adjustable
from the settings page.

## Troubleshooting

- **Robot never reacts to speech** — watch the mic level bar on the settings
  page while talking. If it barely moves, lower the sensitivity multiplier.
  If it's pegged high in silence, raise it (noisy room / fan next to robot).
- **"Cannot reach Hermes"** — run `hermes-mini-check` from a laptop on the
  same network. Check the VPS: is `hermes gateway` running? Is the reverse
  proxy up? Does the curl sanity check above work?
- **401 from Hermes** — the key in the app doesn't match `API_SERVER_KEY`.
- **Replies are slow** — that's usually Hermes doing real agent work (tool
  calls). The robot plays its thinking animation for as long as it takes.
- **Robot answers itself** — it mutes its mic while speaking; if your volume
  is very high in a small room, add a beat of silence before replying to it.

## Security notes

- Your Hermes API key grants **full agent access, including a terminal on
  your VPS**. Use a long random key, HTTPS only, and rotate it if leaked.
- Keys entered on the settings page are stored in `settings.json` inside the
  app folder **on the robot** and masked in the UI.

## Development

```bash
pip install -e ".[dev]" # or: pip install -e . && pip install pytest
PYTHONPATH=src python -m pytest tests/
```

The package layout follows the standard Reachy Mini Python app structure
(`ReachyMiniApp` subclass exposed through the `reachy_mini_apps` entry
point). See `plan.md` for the architecture and design decisions.

Roadmap ideas: barge-in (interrupt the robot mid-answer), wake word, turning
toward the speaker using the mic array's direction-of-arrival, sending camera
frames to Hermes (its API accepts images), antenna-press pause toggle.

## License

Apache-2.0

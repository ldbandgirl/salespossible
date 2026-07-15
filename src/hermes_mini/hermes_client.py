"""HTTP client for a self-hosted Hermes Agent API server.

Hermes (github.com/NousResearch/hermes-agent) exposes an OpenAI-compatible
API when `API_SERVER_ENABLED=true` and `hermes gateway` is running:

  - POST /v1/responses          — server-side conversation persistence
                                  (named `conversation` for auto-chaining)
  - POST /v1/chat/completions   — stateless; client sends the history
  - GET  /v1/models             — discovery / connectivity check

All endpoints require `Authorization: Bearer <API_SERVER_KEY>`.

`mode` handling:
  - "responses": always use /v1/responses
  - "chat":      always use /v1/chat/completions with a rolling local history
  - "auto":      try /v1/responses first; on 404/405 permanently fall back
                 to chat mode for this process
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque

import httpx

from hermes_mini.config import Config

logger = logging.getLogger("hermes_mini.hermes")


class HermesError(RuntimeError):
    """Raised when Hermes cannot be reached or returns an error."""


class HermesClient:
    """Synchronous client; one instance per app run."""

    def __init__(self, cfg: Config, transport: httpx.BaseTransport | None = None):
        self.cfg = cfg
        self._responses_unsupported = False
        # maxlen counts messages; one turn = user + assistant.
        self._history: deque[dict] = deque(maxlen=max(2, cfg.history_max_turns * 2))
        # The voice loop and the web chat box both drive this client from
        # different threads; serialize turns so history/state don't race.
        self._lock = threading.RLock()
        self._client = httpx.Client(
            timeout=httpx.Timeout(cfg.hermes_timeout_s, connect=10.0),
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def _base(self) -> str:
        base = self.cfg.hermes_base_url.strip().rstrip("/")
        if not base:
            raise HermesError(
                "Hermes base URL is not configured. Set HERMES_BASE_URL or use the settings page."
            )
        return base

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.cfg.hermes_api_key:
            headers["Authorization"] = f"Bearer {self.cfg.hermes_api_key}"
        return headers

    @property
    def mode_in_use(self) -> str:
        """The transport mode requests are actually using right now."""
        mode = (self.cfg.hermes_mode or "auto").lower()
        if mode == "auto":
            return "chat" if self._responses_unsupported else "responses"
        return mode

    # ------------------------------------------------------------------ API

    def ping(self) -> list[str]:
        """Return the model names Hermes advertises (also validates auth)."""
        resp = self._request("GET", "/v1/models")
        data = resp.json()
        return [m.get("id", "?") for m in data.get("data", [])]

    def send(self, user_text: str) -> str:
        """Send one user utterance, return Hermes' reply text."""
        with self._lock:
            mode = (self.cfg.hermes_mode or "auto").lower()
            use_responses = mode == "responses" or (
                mode == "auto" and not self._responses_unsupported
            )
            if use_responses:
                try:
                    return self._send_responses(user_text)
                except HermesUnsupportedEndpoint:
                    if mode == "responses":
                        raise HermesError(
                            "Hermes rejected /v1/responses. Set HERMES_MODE=chat or upgrade Hermes."
                        )
                    logger.info("/v1/responses not available; falling back to chat mode.")
                    self._responses_unsupported = True
            return self._send_chat(user_text)

    def stream(self, user_text: str):
        """Yield reply text chunks as Hermes generates them.

        Same mode logic as send(). Falls back from responses to chat mode on
        404/405. The caller can fall back to send() if this yields nothing.
        """
        with self._lock:
            mode = (self.cfg.hermes_mode or "auto").lower()
            use_responses = mode == "responses" or (
                mode == "auto" and not self._responses_unsupported
            )
            if use_responses:
                try:
                    yield from self._stream_responses(user_text)
                    return
                except HermesUnsupportedEndpoint:
                    if mode == "responses":
                        raise HermesError(
                            "Hermes rejected /v1/responses. Set HERMES_MODE=chat or upgrade Hermes."
                        )
                    logger.info("/v1/responses not available; falling back to chat mode.")
                    self._responses_unsupported = True
            yield from self._stream_chat(user_text)

    # ------------------------------------------------------------ internals

    def _stream_responses(self, user_text: str):
        payload: dict = {
            "model": self.cfg.hermes_model,
            "input": user_text,
            "store": True,
            "stream": True,
        }
        if self.cfg.hermes_conversation:
            payload["conversation"] = self.cfg.hermes_conversation
        if self.cfg.system_prompt:
            payload["instructions"] = self.cfg.system_prompt
        yield from self._stream_request(
            "/v1/responses", payload, _delta_from_responses, allow_unsupported=True
        )

    def _stream_chat(self, user_text: str):
        messages = self._chat_messages(user_text)
        payload = {"model": self.cfg.hermes_model, "messages": messages, "stream": True}
        collected: list[str] = []
        for delta in self._stream_request(
            "/v1/chat/completions", payload, _delta_from_chat
        ):
            collected.append(delta)
            yield delta
        full = "".join(collected).strip()
        if full:
            self._history.append({"role": "user", "content": user_text})
            self._history.append({"role": "assistant", "content": full})

    def _stream_request(self, path, payload, extract, allow_unsupported=False):
        url = self._base() + path
        try:
            with self._client.stream(
                "POST", url, json=payload, headers=self._headers()
            ) as resp:
                if allow_unsupported and resp.status_code in (404, 405):
                    raise HermesUnsupportedEndpoint(path)
                if resp.status_code == 401:
                    raise HermesError("Hermes rejected the API key (401). Check the API key.")
                if resp.status_code >= 400:
                    resp.read()
                    raise HermesError(f"Hermes error {resp.status_code}: {resp.text[:300]}")
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except ValueError:
                        continue
                    delta = extract(obj)
                    if delta:
                        yield delta
        except httpx.HTTPError as e:
            raise HermesError(f"Cannot reach Hermes at {url}: {e}") from e

    def _chat_messages(self, user_text: str) -> list[dict]:
        messages: list[dict] = []
        if self.cfg.system_prompt:
            messages.append({"role": "system", "content": self.cfg.system_prompt})
        messages.extend(self._history)
        messages.append({"role": "user", "content": user_text})
        return messages

    def _send_responses(self, user_text: str) -> str:
        payload: dict = {
            "model": self.cfg.hermes_model,
            "input": user_text,
            "store": True,
        }
        if self.cfg.hermes_conversation:
            payload["conversation"] = self.cfg.hermes_conversation
        if self.cfg.system_prompt:
            payload["instructions"] = self.cfg.system_prompt

        resp = self._request("POST", "/v1/responses", json=payload, allow_unsupported=True)
        text = parse_responses_output(resp.json())
        if not text:
            raise HermesError("Hermes returned an empty response.")
        return text

    def _send_chat(self, user_text: str) -> str:
        payload = {
            "model": self.cfg.hermes_model,
            "messages": self._chat_messages(user_text),
            "stream": False,
        }
        resp = self._request("POST", "/v1/chat/completions", json=payload)
        text = parse_chat_output(resp.json())
        if not text:
            raise HermesError("Hermes returned an empty response.")

        self._history.append({"role": "user", "content": user_text})
        self._history.append({"role": "assistant", "content": text})
        return text

    def _request(
        self,
        method: str,
        path: str,
        json: dict | None = None,
        allow_unsupported: bool = False,
    ) -> httpx.Response:
        url = self._base() + path
        try:
            resp = self._client.request(method, url, json=json, headers=self._headers())
        except httpx.HTTPError as e:
            raise HermesError(f"Cannot reach Hermes at {url}: {e}") from e

        if allow_unsupported and resp.status_code in (404, 405):
            raise HermesUnsupportedEndpoint(path)
        if resp.status_code == 401:
            raise HermesError("Hermes rejected the API key (401). Check HERMES_API_KEY.")
        if resp.status_code >= 400:
            raise HermesError(f"Hermes error {resp.status_code}: {resp.text[:300]}")
        return resp


class HermesUnsupportedEndpoint(HermesError):
    """The Hermes build doesn't serve this endpoint (404/405)."""


def _delta_from_chat(obj: dict) -> str:
    """Extract the incremental text from one chat-completions SSE chunk."""
    try:
        content = (obj["choices"][0].get("delta") or {}).get("content")
    except (KeyError, IndexError, TypeError):
        return ""
    return content if isinstance(content, str) else ""


def _delta_from_responses(obj: dict) -> str:
    """Extract incremental text from one Responses-API SSE event.

    Tolerant of variants: `{type: response.output_text.delta, delta: "..."}`,
    a bare `{delta: "..."}`, or a chat-style chunk.
    """
    if not isinstance(obj, dict):
        return ""
    delta = obj.get("delta")
    event_type = obj.get("type", "") or ""
    if isinstance(delta, str) and (
        "output_text" in event_type or event_type.endswith(".delta") or not event_type
    ):
        return delta
    return _delta_from_chat(obj)


def parse_chat_output(data: dict) -> str:
    """Extract assistant text from an OpenAI chat-completions payload."""
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return ""
    if isinstance(content, list):  # multimodal-style content parts
        content = " ".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    return (content or "").strip()


def parse_responses_output(data: dict) -> str:
    """Extract assistant text from an OpenAI Responses-API payload."""
    # Some servers include the convenience aggregate directly.
    aggregate = data.get("output_text")
    if isinstance(aggregate, str) and aggregate.strip():
        return aggregate.strip()

    chunks: list[str] = []
    for item in data.get("output", []) or []:
        if not isinstance(item, dict) or item.get("type") not in (None, "message"):
            continue
        content = item.get("content", [])
        if isinstance(content, str):
            chunks.append(content)
            continue
        for part in content or []:
            if isinstance(part, dict) and part.get("type") in ("output_text", "text"):
                chunks.append(part.get("text", ""))
    return "\n".join(c for c in chunks if c).strip()

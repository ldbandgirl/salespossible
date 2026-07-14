import json

import httpx
import pytest

from hermes_mini.config import Config
from hermes_mini.hermes_client import (
    HermesClient,
    HermesError,
    parse_chat_output,
    parse_responses_output,
)


def make_client(handler, mode="auto"):
    cfg = Config()
    cfg.hermes_base_url = "https://hermes.test"
    cfg.hermes_api_key = "secret"
    cfg.hermes_mode = mode
    return HermesClient(cfg, transport=httpx.MockTransport(handler))


def chat_payload(text):
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def responses_payload(text):
    return {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": text}],
            }
        ]
    }


def test_responses_mode_used_first_in_auto():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        assert request.headers["authorization"] == "Bearer secret"
        if request.url.path == "/v1/responses":
            body = json.loads(request.content)
            assert body["conversation"] == "reachy-mini"
            assert body["store"] is True
            return httpx.Response(200, json=responses_payload("hi from responses"))
        raise AssertionError(f"unexpected path {request.url.path}")

    client = make_client(handler)
    assert client.send("hello") == "hi from responses"
    assert calls == ["/v1/responses"]


def test_auto_falls_back_to_chat_on_404():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/v1/responses":
            return httpx.Response(404, text="not found")
        body = json.loads(request.content)
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][-1] == {"role": "user", "content": "hello"}
        return httpx.Response(200, json=chat_payload("hi from chat"))

    client = make_client(handler)
    assert client.send("hello") == "hi from chat"
    # Fallback is sticky: second send goes straight to chat.
    assert client.send("hello") == "hi from chat"
    assert calls == ["/v1/responses", "/v1/chat/completions", "/v1/chat/completions"]


def test_chat_mode_keeps_history():
    seen_messages = []

    def handler(request):
        body = json.loads(request.content)
        seen_messages.append(body["messages"])
        return httpx.Response(200, json=chat_payload(f"reply {len(seen_messages)}"))

    client = make_client(handler, mode="chat")
    client.send("first")
    client.send("second")

    second_call = seen_messages[1]
    roles = [m["role"] for m in second_call]
    assert roles == ["system", "user", "assistant", "user"]
    assert second_call[1]["content"] == "first"
    assert second_call[2]["content"] == "reply 1"


def test_401_raises_helpful_error():
    def handler(request):
        return httpx.Response(401, text="unauthorized")

    client = make_client(handler, mode="chat")
    with pytest.raises(HermesError, match="API key"):
        client.send("hello")


def test_missing_base_url():
    cfg = Config()
    client = HermesClient(cfg)
    with pytest.raises(HermesError, match="base URL"):
        client.send("hello")


def test_parse_chat_output_variants():
    assert parse_chat_output(chat_payload("plain")) == "plain"
    multimodal = {
        "choices": [
            {"message": {"content": [{"type": "text", "text": "part1"}, {"type": "text", "text": "part2"}]}}
        ]
    }
    assert parse_chat_output(multimodal) == "part1 part2"
    assert parse_chat_output({}) == ""


def test_parse_responses_output_variants():
    assert parse_responses_output(responses_payload("hello")) == "hello"
    assert parse_responses_output({"output_text": "aggregate"}) == "aggregate"
    assert parse_responses_output({"output": [{"type": "message", "content": "raw string"}]}) == "raw string"
    assert parse_responses_output({}) == ""

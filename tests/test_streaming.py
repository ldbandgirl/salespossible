import httpx
import pytest

from hermes_mini.config import Config
from hermes_mini.hermes_client import (
    HermesClient,
    _delta_from_chat,
    _delta_from_responses,
)
from hermes_mini.text_utils import split_into_sentences


# ----------------------------------------------------------- sentence splitter


def test_split_emits_complete_sentences():
    sentences, rest = split_into_sentences("Hello there friend. How are ", min_chars=5)
    assert sentences == ["Hello there friend."]
    assert rest == "How are "


def test_split_merges_short_fragments():
    # "Hi." is shorter than min_chars, so it merges into the next sentence.
    sentences, rest = split_into_sentences("Hi. I am your robot assistant. ", min_chars=10)
    assert sentences == ["Hi. I am your robot assistant."]
    assert rest == ""


def test_split_no_boundary_keeps_everything():
    sentences, rest = split_into_sentences("still typing", min_chars=5)
    assert sentences == []
    assert rest == "still typing"


def test_split_on_newline():
    sentences, rest = split_into_sentences("First line here\nsecond", min_chars=5)
    assert sentences == ["First line here"]
    assert rest == "second"


# ----------------------------------------------------------- SSE delta parsers


def test_delta_from_chat():
    assert _delta_from_chat({"choices": [{"delta": {"content": "hi"}}]}) == "hi"
    assert _delta_from_chat({"choices": [{"delta": {}}]}) == ""
    assert _delta_from_chat({}) == ""


def test_delta_from_responses_variants():
    assert _delta_from_responses({"type": "response.output_text.delta", "delta": "a"}) == "a"
    assert _delta_from_responses({"delta": "b"}) == "b"  # bare delta
    assert _delta_from_responses({"type": "response.completed"}) == ""
    # chat-style fallback
    assert _delta_from_responses({"choices": [{"delta": {"content": "c"}}]}) == "c"


# ----------------------------------------------------------- client streaming


def sse(*chunks: str) -> bytes:
    body = ""
    for c in chunks:
        body += f"data: {c}\n\n"
    body += "data: [DONE]\n\n"
    return body.encode()


def test_stream_chat_yields_deltas():
    def handler(request):
        assert request.url.path == "/v1/chat/completions"
        import json

        assert json.loads(request.content)["stream"] is True
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=sse(
                '{"choices":[{"delta":{"content":"Hello "}}]}',
                '{"choices":[{"delta":{"content":"world."}}]}',
            ),
        )

    cfg = Config()
    cfg.hermes_base_url = "https://hermes.test"
    cfg.hermes_mode = "chat"
    client = HermesClient(cfg, transport=httpx.MockTransport(handler))
    assert "".join(client.stream("hi")) == "Hello world."


def test_stream_responses_then_chat_fallback():
    def handler(request):
        if request.url.path == "/v1/responses":
            return httpx.Response(404, content=b"nope")
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=sse('{"choices":[{"delta":{"content":"fallback"}}]}'),
        )

    cfg = Config()
    cfg.hermes_base_url = "https://hermes.test"
    cfg.hermes_mode = "auto"
    client = HermesClient(cfg, transport=httpx.MockTransport(handler))
    assert "".join(client.stream("hi")) == "fallback"


def test_stream_responses_output_text_events():
    def handler(request):
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=sse(
                '{"type":"response.output_text.delta","delta":"Part one. "}',
                '{"type":"response.output_text.delta","delta":"Part two."}',
                '{"type":"response.completed"}',
            ),
        )

    cfg = Config()
    cfg.hermes_base_url = "https://hermes.test"
    cfg.hermes_mode = "responses"
    client = HermesClient(cfg, transport=httpx.MockTransport(handler))
    assert "".join(client.stream("hi")) == "Part one. Part two."

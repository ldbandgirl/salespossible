import json

import httpx

from hermes_mini.config import Config
from hermes_mini.hermes_client import (
    HermesClient,
    _chat_user_content,
    _responses_input,
)
from hermes_mini.vision import capture_image_url, wants_vision

DATA_URL = "data:image/jpeg;base64,QUJD"


# ---------------------------------------------------------------- trigger


def test_wants_vision_auto_matches_keywords():
    cfg = Config()  # default mode auto, default trigger words
    assert wants_vision(cfg, "Hey, can you see what I'm holding?")
    assert wants_vision(cfg, "look at this")
    assert not wants_vision(cfg, "what time is it in Tokyo")


def test_wants_vision_modes():
    cfg = Config()
    cfg.vision_mode = "off"
    assert not wants_vision(cfg, "look at me")
    cfg.vision_mode = "always"
    assert wants_vision(cfg, "anything at all")


# --------------------------------------------------------- capture helper


class _Media:
    def __init__(self, jpeg):
        self._jpeg = jpeg

    def get_frame_jpeg(self):
        return self._jpeg


def test_capture_image_url_encodes_data_url():
    url = capture_image_url(_Media(b"ABC"))
    assert url == "data:image/jpeg;base64,QUJD"


def test_capture_image_url_none_when_no_frame():
    assert capture_image_url(_Media(None)) is None
    assert capture_image_url(object()) is None  # no get_frame_jpeg


# ---------------------------------------------------- payload construction


def test_chat_user_content_shapes():
    assert _chat_user_content("hi", None) == "hi"
    parts = _chat_user_content("what is this", DATA_URL)
    assert parts[0] == {"type": "text", "text": "what is this"}
    assert parts[1]["type"] == "image_url"
    assert parts[1]["image_url"]["url"] == DATA_URL


def test_responses_input_shapes():
    assert _responses_input("hi", None) == "hi"
    inp = _responses_input("look", DATA_URL)
    content = inp[0]["content"]
    assert content[0] == {"type": "input_text", "text": "look"}
    assert content[1] == {"type": "input_image", "image_url": DATA_URL}


def test_send_chat_includes_image_in_request():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "I see a cup"}}]}
        )

    cfg = Config()
    cfg.hermes_base_url = "https://hermes.test"
    cfg.hermes_mode = "chat"
    client = HermesClient(cfg, transport=httpx.MockTransport(handler))
    reply = client.send("what do you see", DATA_URL)
    assert reply == "I see a cup"

    content = captured["body"]["messages"][-1]["content"]
    assert any(p.get("type") == "image_url" for p in content)

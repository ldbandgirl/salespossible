import json

import httpx
import numpy as np
import pytest

from hermes_mini.config import Config
from hermes_mini.speech import SpeechError, TtsClient


def make_client(handler, **cfg_overrides):
    cfg = Config()
    cfg.tts_provider = "minimax"
    cfg.minimax_api_key = "mm-key"
    for k, v in cfg_overrides.items():
        setattr(cfg, k, v)
    return TtsClient(cfg, transport=httpx.MockTransport(handler))


def pcm_hex(samples_int16):
    return np.array(samples_int16, dtype="<i2").tobytes().hex()


def test_minimax_tts_decodes_hex_pcm():
    def handler(request):
        assert request.url.path == "/v1/t2a_v2"
        assert request.headers["authorization"] == "Bearer mm-key"
        body = json.loads(request.content)
        assert body["output_format"] == "hex"
        assert body["audio_setting"]["format"] == "pcm"
        assert body["voice_setting"]["voice_id"] == "Wise_Woman"
        return httpx.Response(
            200,
            json={
                "base_resp": {"status_code": 0, "status_msg": "success"},
                "data": {"audio": pcm_hex([0, 16384, -16384]), "status": 2},
                "extra_info": {"audio_sample_rate": 16000},
            },
        )

    samples, rate = make_client(handler).synthesize("hello")
    assert rate == 16000
    assert np.allclose(samples, [0.0, 0.5, -0.5], atol=1e-4)


def test_minimax_group_id_in_url():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "base_resp": {"status_code": 0},
                "data": {"audio": pcm_hex([0])},
                "extra_info": {},
            },
        )

    make_client(handler, minimax_group_id="1234567").synthesize("hi")
    assert "GroupId=1234567" in seen["url"]


def test_minimax_api_error_surfaces_message():
    def handler(request):
        return httpx.Response(
            200,
            json={"base_resp": {"status_code": 1004, "status_msg": "invalid api key"}},
        )

    with pytest.raises(SpeechError, match="1004.*invalid api key"):
        make_client(handler).synthesize("hi")


def test_minimax_missing_key():
    with pytest.raises(SpeechError, match="MINIMAX_API_KEY"):
        make_client(lambda r: httpx.Response(500), minimax_api_key="").synthesize("hi")

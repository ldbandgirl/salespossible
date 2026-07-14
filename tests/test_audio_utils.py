import numpy as np
import pytest

from hermes_mini.audio_utils import (
    decode_pcm16,
    decode_wav,
    encode_wav16,
    resample_linear,
    rms,
    to_mono,
)


def test_wav_roundtrip():
    rate = 16000
    t = np.linspace(0, 1, rate, endpoint=False)
    original = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

    data = encode_wav16(original, rate)
    decoded, decoded_rate = decode_wav(data)

    assert decoded_rate == rate
    assert decoded.shape == original.shape
    assert np.max(np.abs(decoded - original)) < 1e-3


def test_decode_wav_stereo_downmixes():
    rate = 8000
    left = np.full(100, 0.5, dtype=np.float32)
    right = np.full(100, -0.5, dtype=np.float32)
    interleaved = np.column_stack([left, right])

    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((interleaved * 32767).astype("<i2").tobytes())

    decoded, decoded_rate = decode_wav(buf.getvalue())
    assert decoded_rate == rate
    assert decoded.shape == (100,)
    assert np.max(np.abs(decoded)) < 1e-3  # L and R cancel out


def test_decode_pcm16():
    pcm = np.array([0, 16384, -16384], dtype="<i2").tobytes()
    decoded = decode_pcm16(pcm)
    assert np.allclose(decoded, [0.0, 0.5, -0.5], atol=1e-4)


def test_to_mono_shapes():
    n = 64
    mono = np.ones(n, dtype=np.float32)
    assert to_mono(mono).shape == (n,)
    assert to_mono(np.column_stack([mono, mono])).shape == (n,)  # (n, 2)
    assert to_mono(np.stack([mono, mono])).shape == (n,)  # (2, n)
    with pytest.raises(ValueError):
        to_mono(np.zeros((2, 2, 2)))


def test_resample_changes_length():
    x = np.sin(np.linspace(0, 10, 24000)).astype(np.float32)
    y = resample_linear(x, 24000, 16000)
    assert abs(y.size - 16000) <= 1
    assert y.dtype == np.float32
    # Identity when rates match
    assert resample_linear(x, 16000, 16000) is x or np.array_equal(
        resample_linear(x, 16000, 16000), x
    )


def test_rms():
    assert rms(np.zeros(10)) == 0.0
    assert abs(rms(np.ones(10)) - 1.0) < 1e-6
    assert rms(np.array([])) == 0.0

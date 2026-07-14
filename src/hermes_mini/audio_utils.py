"""Pure-numpy audio helpers: WAV encode/decode, resampling, channel mixing."""

from __future__ import annotations

import io
import wave

import numpy as np
import numpy.typing as npt


def to_mono(samples: npt.NDArray) -> npt.NDArray[np.float32]:
    """Downmix an audio array of shape (n,), (n, ch) or (ch, n) to mono float32."""
    x = np.asarray(samples, dtype=np.float32)
    if x.ndim == 1:
        return x
    if x.ndim != 2:
        raise ValueError(f"Expected 1D or 2D audio, got shape {x.shape}")
    # Channels are the smaller axis (mics/speakers have <= 8 channels).
    if x.shape[0] <= 8 and x.shape[0] < x.shape[1]:
        return x.mean(axis=0)
    return x.mean(axis=1)


def rms(samples: npt.NDArray) -> float:
    """Root-mean-square level of an audio chunk (0.0 for empty input)."""
    x = np.asarray(samples, dtype=np.float32)
    if x.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(x))))


def resample_linear(
    samples: npt.NDArray[np.float32], rate_from: int, rate_to: int
) -> npt.NDArray[np.float32]:
    """Resample mono float32 audio with linear interpolation."""
    if rate_from == rate_to or samples.size == 0:
        return samples.astype(np.float32, copy=False)
    n_out = max(1, int(round(samples.size * rate_to / rate_from)))
    t_in = np.linspace(0.0, 1.0, num=samples.size, endpoint=False)
    t_out = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    return np.interp(t_out, t_in, samples).astype(np.float32)


def encode_wav16(samples: npt.NDArray[np.float32], rate: int) -> bytes:
    """Encode mono float32 [-1, 1] samples as a 16-bit PCM WAV file."""
    mono = to_mono(samples)
    pcm = np.clip(mono, -1.0, 1.0)
    pcm16 = (pcm * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm16.tobytes())
    return buf.getvalue()


def decode_wav(data: bytes) -> tuple[npt.NDArray[np.float32], int]:
    """Decode a WAV file to (mono float32 samples, sample rate).

    Supports 16-bit, 24-bit and 32-bit PCM, mono or multi-channel.
    """
    with wave.open(io.BytesIO(data), "rb") as w:
        n_channels = w.getnchannels()
        sampwidth = w.getsampwidth()
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())

    if sampwidth == 2:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sampwidth == 4:
        x = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    elif sampwidth == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        as32 = (
            b[:, 0].astype(np.int32)
            | (b[:, 1].astype(np.int32) << 8)
            | (b[:, 2].astype(np.int32) << 16)
        )
        as32 = np.where(as32 & 0x800000, as32 - 0x1000000, as32)
        x = as32.astype(np.float32) / 8388608.0
    else:
        raise ValueError(f"Unsupported WAV sample width: {sampwidth} bytes")

    if n_channels > 1:
        x = x.reshape(-1, n_channels).mean(axis=1)
    return x.astype(np.float32), rate


def decode_pcm16(data: bytes) -> npt.NDArray[np.float32]:
    """Decode raw signed 16-bit little-endian PCM to mono float32."""
    return np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0

"""Turn Hermes' (potentially markdown) replies into speakable plain text."""

from __future__ import annotations

import re

_CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`]*)`")
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_EMPHASIS = re.compile(r"(\*\*|__|\*|_)(?=\S)(.+?)(?<=\S)\1")
_BULLET = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
_NUMBERED = re.compile(r"^\s*\d+[.)]\s+", re.MULTILINE)
_BLOCKQUOTE = re.compile(r"^\s*>\s?", re.MULTILINE)
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
_HORIZONTAL_RULE = re.compile(r"^\s*([-*_]\s*){3,}$", re.MULTILINE)
_MULTI_BLANK = re.compile(r"\n{3,}")


def strip_markdown(text: str) -> str:
    """Convert markdown to plain text suitable for text-to-speech."""
    out = text
    out = _CODE_BLOCK.sub(" (code omitted) ", out)
    out = _INLINE_CODE.sub(r"\1", out)
    out = _IMAGE.sub("", out)
    out = _LINK.sub(r"\1", out)
    out = _TABLE_ROW.sub("", out)
    out = _HEADING.sub("", out)
    out = _HORIZONTAL_RULE.sub("", out)
    out = _EMPHASIS.sub(r"\2", out)
    out = _EMPHASIS.sub(r"\2", out)  # second pass for nested bold+italic
    out = _BULLET.sub("", out)
    out = _NUMBERED.sub("", out)
    out = _BLOCKQUOTE.sub("", out)
    out = _MULTI_BLANK.sub("\n\n", out)
    return out.strip()


def clamp_for_speech(text: str, max_chars: int = 1200) -> str:
    """Cap very long replies so the robot doesn't monologue for minutes."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    # Break at the last sentence end if there is one reasonably close.
    for sep in (". ", "! ", "? "):
        idx = cut.rfind(sep)
        if idx > max_chars // 2:
            return cut[: idx + 1]
    return cut + "…"

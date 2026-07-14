from hermes_mini.text_utils import clamp_for_speech, strip_markdown


def test_strip_markdown_basics():
    md = (
        "# Title\n\n"
        "Here is **bold** and *italic* and `code`.\n\n"
        "- item one\n"
        "- item two\n\n"
        "1. first\n"
        "2) second\n\n"
        "> a quote\n\n"
        "[a link](https://example.com) and ![img](https://x.com/i.png)\n\n"
        "```python\nprint('hi')\n```\n"
    )
    out = strip_markdown(md)
    assert "**" not in out and "`" not in out and "#" not in out
    assert "bold" in out and "italic" in out and "code" in out
    assert "item one" in out
    assert "first" in out and "second" in out
    assert "a quote" in out
    assert "a link" in out and "example.com" not in out
    assert "print" not in out and "code omitted" in out


def test_strip_markdown_plain_text_untouched():
    plain = "Hello there. How are you today?"
    assert strip_markdown(plain) == plain


def test_clamp_for_speech():
    short = "Short reply."
    assert clamp_for_speech(short) == short

    long_text = ("This is a sentence. " * 200).strip()
    clamped = clamp_for_speech(long_text, max_chars=300)
    assert len(clamped) <= 301
    assert clamped.endswith(".")


def test_clamp_no_sentence_boundary():
    blob = "x" * 500
    clamped = clamp_for_speech(blob, max_chars=100)
    assert len(clamped) == 101
    assert clamped.endswith("…")

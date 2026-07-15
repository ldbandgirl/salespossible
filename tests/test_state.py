from hermes_mini.state import AppState


def test_transcript_records_voice_and_text():
    s = AppState()
    s.add_message("user", "hello", "voice")
    s.add_message("assistant", "hi there", "voice")
    s.add_message("user", "typed question", "text")
    s.add_message("assistant", "typed answer", "text")

    msgs = s.transcript()
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert [m["source"] for m in msgs] == ["voice", "voice", "text", "text"]
    assert [m["id"] for m in msgs] == [1, 2, 3, 4]  # monotonic ids for the UI


def test_transcript_is_a_copy():
    s = AppState()
    s.add_message("user", "x", "text")
    snap = s.transcript()
    s.add_message("assistant", "y", "text")
    assert len(snap) == 1  # earlier snapshot is not mutated


def test_transcript_bounded():
    s = AppState()
    for i in range(250):
        s.add_message("user", f"m{i}", "text")
    msgs = s.transcript()
    assert len(msgs) == 200  # deque maxlen
    assert msgs[-1]["text"] == "m249"

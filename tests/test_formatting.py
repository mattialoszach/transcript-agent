from __future__ import annotations

from transcript_agent.formatting import build_paragraphs, format_document, timestamp
from transcript_agent.models import TranscriptSnippet


def test_timestamp_formats_short_and_long_times() -> None:
    assert timestamp(0) == "00:00"
    assert timestamp(65.9) == "01:05"
    assert timestamp(3661) == "01:01:01"


def test_build_paragraphs_cleans_whitespace_and_adjacent_duplicates() -> None:
    snippets = [
        TranscriptSnippet("  hello\nworld  ", 1, 1),
        TranscriptSnippet("hello world", 2, 1),
        TranscriptSnippet("Next.", 3, 1),
    ]
    paragraphs = build_paragraphs(snippets, target_chars=1, max_chars=100)
    assert [paragraph.text for paragraph in paragraphs] == ["hello world Next."]
    assert paragraphs[0].start == 1


def test_markdown_has_metadata_and_clickable_timestamps(document) -> None:
    output = format_document(document, "md", include_timestamps=True)
    assert output.startswith('# A useful video: "notes"\n')
    assert "[Watch on YouTube]" in output
    assert "Creator-provided captions" in output
    assert "[00:00](https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=0s)" in output
    assert output.endswith("\n")


def test_plain_text_can_omit_timestamps(document) -> None:
    output = format_document(document, "txt", include_timestamps=False)
    assert "Source: https://www.youtube.com/watch?v=dQw4w9WgXcQ" in output
    assert "[00:00]" not in output
    assert "Hello from the first caption." in output


def test_format_rejects_unknown_format(document) -> None:
    try:
        format_document(document, "pdf")  # type: ignore[arg-type]
    except ValueError as error:
        assert "Unsupported output format" in str(error)
    else:
        raise AssertionError("Expected an unsupported format error")

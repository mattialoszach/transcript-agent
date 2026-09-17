from __future__ import annotations

from transcript_agent.storage import safe_filename, save_document, transcript_filename


def test_safe_filename_removes_cross_platform_reserved_characters() -> None:
    assert safe_filename(' A/B:C*D? "E". ', "fallback") == "A - B - CD E"
    assert safe_filename("...", "fallback") == "fallback"


def test_transcript_filename_uses_clean_title(document) -> None:
    name = transcript_filename(document, "md")
    assert name == "A useful video - notes.md"


def test_transcript_filename_accepts_a_custom_name(document) -> None:
    assert transcript_filename(document, "md", "Meeting notes.md") == "Meeting notes.md"
    assert transcript_filename(document, "txt", "Team / sync") == "Team - sync.txt"


def test_save_is_idempotent_for_identical_content(tmp_path, document) -> None:
    first = save_document(document, tmp_path, "md")
    second = save_document(document, tmp_path, "md")
    assert first.created is True
    assert second.created is False
    assert second.path == first.path
    assert len(list(tmp_path.iterdir())) == 1


def test_save_does_not_overwrite_existing_content(tmp_path, document) -> None:
    preferred = tmp_path / transcript_filename(document, "txt")
    preferred.write_text("someone else's file", encoding="utf-8")
    result = save_document(document, tmp_path, "txt")
    assert result.path.name.endswith("(2).txt")
    assert preferred.read_text(encoding="utf-8") == "someone else's file"


def test_save_creates_requested_directory(tmp_path, document) -> None:
    destination = tmp_path / "nested" / "transcripts"
    result = save_document(document, destination, "md")
    assert result.path.is_file()


def test_save_uses_custom_name(tmp_path, document) -> None:
    result = save_document(document, tmp_path, "md", name="My transcript")
    assert result.path.name == "My transcript.md"

from __future__ import annotations

from transcript_agent.storage import safe_filename, save_document, transcript_filename


def test_safe_filename_removes_cross_platform_reserved_characters() -> None:
    assert safe_filename(' A/B:C*D? "E". ', "fallback") == "A-B-C-D- -E"
    assert safe_filename("...", "fallback") == "fallback"


def test_transcript_filename_contains_id(document) -> None:
    name = transcript_filename(document, "md")
    assert name == "A useful video- -notes [dQw4w9WgXcQ].md"


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

"""Safe transcript file naming and persistence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from transcript_agent.formatting import OutputFormat, format_document
from transcript_agent.models import TranscriptDocument

INVALID_FILENAME = re.compile(r"[<>:\"/\\|?*\x00-\x1f]")


@dataclass(frozen=True, slots=True)
class SaveResult:
    path: Path
    created: bool


def default_output_directory() -> Path:
    downloads = Path.home() / "Downloads"
    return downloads if downloads.is_dir() else Path.home()


def safe_filename(title: str, fallback: str, max_length: int = 120) -> str:
    cleaned = INVALID_FILENAME.sub("-", title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-")
    cleaned = cleaned[:max_length].rstrip(" .-")
    return cleaned or fallback


def transcript_filename(
    document: TranscriptDocument, output_format: OutputFormat
) -> str:
    stem = safe_filename(document.title, f"YouTube transcript {document.video_id}")
    return f"{stem} [{document.video_id}].{output_format}"


def save_document(
    document: TranscriptDocument,
    directory: Path,
    output_format: OutputFormat = "md",
    include_timestamps: bool = True,
) -> SaveResult:
    """Save without overwriting unrelated content or duplicating identical saves."""
    directory = directory.expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    content = format_document(document, output_format, include_timestamps)
    preferred = directory / transcript_filename(document, output_format)

    candidate = preferred
    suffix = 2
    while candidate.exists():
        try:
            if candidate.read_text(encoding="utf-8") == content:
                return SaveResult(candidate, created=False)
        except OSError:
            pass
        candidate = preferred.with_stem(f"{preferred.stem} ({suffix})")
        suffix += 1

    try:
        with candidate.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except OSError as error:
        raise OSError(
            f"Could not save to {directory}: {error.strerror or error}"
        ) from error
    return SaveResult(candidate, created=True)

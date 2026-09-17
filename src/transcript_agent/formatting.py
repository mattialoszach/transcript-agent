"""Readable Markdown and plain-text transcript formatting."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from transcript_agent.models import TranscriptDocument, TranscriptSnippet

OutputFormat = Literal["md", "txt"]


@dataclass(frozen=True, slots=True)
class Paragraph:
    start: float
    text: str


def timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def build_paragraphs(
    snippets: Iterable[TranscriptSnippet], target_chars: int = 420, max_chars: int = 720
) -> list[Paragraph]:
    """Combine caption fragments into paragraphs that are pleasant to skim."""
    paragraphs: list[Paragraph] = []
    words: list[str] = []
    start = 0.0

    def flush() -> None:
        nonlocal words
        if words:
            paragraphs.append(Paragraph(start, " ".join(words)))
            words = []

    for snippet in snippets:
        text = _clean_text(snippet.text)
        if not text:
            continue
        if not words:
            start = snippet.start

        # Auto-captions occasionally repeat an entire adjacent cue.
        if words and text == words[-1]:
            continue
        words.append(text)
        length = sum(len(part) + 1 for part in words)
        sentence_end = bool(re.search(r"[.!?][\]\"')]*$", text))
        if length >= max_chars or (length >= target_chars and sentence_end):
            flush()
    flush()
    return paragraphs


def _caption_kind(document: TranscriptDocument) -> str:
    return (
        "Auto-generated captions"
        if document.is_generated
        else "Creator-provided captions"
    )


def format_document(
    document: TranscriptDocument,
    output_format: OutputFormat = "md",
    include_timestamps: bool = True,
) -> str:
    """Render a complete, portable transcript document."""
    paragraphs = build_paragraphs(document.snippets)
    if output_format == "md":
        metadata = (
            f"[Watch on YouTube]({document.source_url}) · "
            f"{document.language} (`{document.language_code}`) · {_caption_kind(document)}"
        )
        lines = [f"# {document.title}", "", metadata, "", "## Transcript", ""]
        for paragraph in paragraphs:
            if include_timestamps:
                second = int(paragraph.start)
                link = f"{document.source_url}&t={second}s"
                lines.append(f"[{timestamp(paragraph.start)}]({link})  ")
            lines.extend((paragraph.text, ""))
        return "\n".join(lines).rstrip() + "\n"

    if output_format != "txt":
        raise ValueError(f"Unsupported output format: {output_format}")

    lines = [
        document.title,
        f"Source: {document.source_url}",
        f"Language: {document.language} ({document.language_code})",
        f"Captions: {_caption_kind(document)}",
        "",
    ]
    for paragraph in paragraphs:
        prefix = f"[{timestamp(paragraph.start)}] " if include_timestamps else ""
        lines.extend((f"{prefix}{paragraph.text}", ""))
    return "\n".join(lines).rstrip() + "\n"

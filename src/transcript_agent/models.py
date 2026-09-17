"""Domain models shared by the fetcher, formatter, and user interface."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TranscriptSnippet:
    text: str
    start: float
    duration: float


@dataclass(frozen=True, slots=True)
class TranscriptDocument:
    video_id: str
    title: str
    source_url: str
    language: str
    language_code: str
    is_generated: bool
    snippets: tuple[TranscriptSnippet, ...]

    @property
    def duration(self) -> float:
        """Approximate duration covered by the captions, in seconds."""
        if not self.snippets:
            return 0.0
        final = self.snippets[-1]
        return final.start + final.duration

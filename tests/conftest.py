from __future__ import annotations

import pytest

from transcript_agent.models import TranscriptDocument, TranscriptSnippet


@pytest.fixture
def document() -> TranscriptDocument:
    return TranscriptDocument(
        video_id="dQw4w9WgXcQ",
        title='A useful video: "notes"',
        source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        language="English",
        language_code="en",
        is_generated=False,
        snippets=(
            TranscriptSnippet("Hello from the first caption.", 0.0, 2.0),
            TranscriptSnippet("This is the second caption!", 2.0, 3.0),
            TranscriptSnippet("And this is the final caption.", 65.0, 2.0),
        ),
    )

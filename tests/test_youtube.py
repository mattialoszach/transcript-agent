from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcript_agent.youtube import (
    InvalidYouTubeURL,
    TranscriptFetcher,
    TranscriptFetchError,
    canonical_url,
    choose_transcript,
    extract_video_id,
)

VIDEO_ID = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "source",
    [
        VIDEO_ID,
        f"https://www.youtube.com/watch?v={VIDEO_ID}&list=abc",
        f"youtube.com/watch?v={VIDEO_ID}",
        f"https://youtu.be/{VIDEO_ID}?si=test",
        f"https://www.youtube.com/shorts/{VIDEO_ID}",
        f"https://youtube.com/live/{VIDEO_ID}?feature=share",
        f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}",
        f"https://music.youtube.com/watch?v={VIDEO_ID}",
    ],
)
def test_extract_video_id_from_supported_sources(source: str) -> None:
    assert extract_video_id(source) == VIDEO_ID


@pytest.mark.parametrize(
    "source",
    [
        "",
        "not a url",
        "https://example.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=too-short",
        "https://youtube.com/channel/dQw4w9WgXcQ",
    ],
)
def test_extract_video_id_rejects_invalid_sources(source: str) -> None:
    with pytest.raises(InvalidYouTubeURL):
        extract_video_id(source)


def test_canonical_url() -> None:
    assert canonical_url(VIDEO_ID) == f"https://www.youtube.com/watch?v={VIDEO_ID}"


def _track(code: str, generated: bool) -> SimpleNamespace:
    return SimpleNamespace(language_code=code, is_generated=generated)


def test_choose_transcript_respects_language_then_manual_preference() -> None:
    tracks = [_track("en", False), _track("de", True), _track("de", False)]
    assert choose_transcript(tracks, ["de", "en"]) is tracks[2]


def test_choose_transcript_matches_language_region() -> None:
    tracks = [_track("en", False), _track("pt-BR", False)]
    assert choose_transcript(tracks, ["pt"]) is tracks[1]


def test_choose_transcript_falls_back_to_any_manual_track() -> None:
    tracks = [_track("ja", True), _track("fr", False)]
    assert choose_transcript(tracks, ["xx"]) is tracks[1]


def test_choose_transcript_rejects_empty_list() -> None:
    with pytest.raises(TranscriptFetchError, match="no available captions"):
        choose_transcript([], ["en"])


class FakeTrack:
    language = "Deutsch"
    language_code = "de"
    is_generated = True

    def fetch(self) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(text="Hallo &amp; willkommen", start=1, duration=2),
            SimpleNamespace(text="\u200b", start=3, duration=1),
        ]


class FakeApi:
    def list(self, video_id: str) -> list[FakeTrack]:
        assert video_id == VIDEO_ID
        return [FakeTrack()]


def test_fetcher_normalizes_api_result() -> None:
    fetcher = TranscriptFetcher(
        api_factory=FakeApi,
        title_resolver=lambda video_id: f"Title for {video_id}",
    )
    result = fetcher.fetch(VIDEO_ID, ["de"])
    assert result.title == f"Title for {VIDEO_ID}"
    assert result.language_code == "de"
    assert result.is_generated is True
    assert len(result.snippets) == 1
    assert result.snippets[0].text == "Hallo & willkommen"


def test_fetcher_converts_library_errors_to_user_facing_errors() -> None:
    class TranscriptsDisabled(Exception):
        pass

    class BrokenApi:
        def list(self, _video_id: str) -> list[object]:
            raise TranscriptsDisabled()

    fetcher = TranscriptFetcher(api_factory=BrokenApi)
    with pytest.raises(TranscriptFetchError, match="disabled"):
        fetcher.fetch(VIDEO_ID)

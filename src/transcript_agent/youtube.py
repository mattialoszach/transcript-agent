"""YouTube URL parsing and transcript retrieval."""

from __future__ import annotations

import json
import locale
import re
from collections.abc import Callable, Iterable, Sequence
from html import unescape
from typing import Any
from urllib.error import URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

from youtube_transcript_api import YouTubeTranscriptApi

from transcript_agent.models import TranscriptDocument, TranscriptSnippet

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}
SHORT_HOSTS = {"youtu.be", "www.youtu.be"}


class InvalidYouTubeURL(ValueError):
    """Raised when input does not contain a valid YouTube video ID."""


class TranscriptFetchError(RuntimeError):
    """A concise, user-facing transcript retrieval error."""


def extract_video_id(value: str) -> str:
    """Extract a video ID from common YouTube URLs or accept a bare ID."""
    candidate = value.strip()
    if VIDEO_ID_RE.fullmatch(candidate):
        return candidate
    if not candidate:
        raise InvalidYouTubeURL("Paste a YouTube URL to continue.")

    parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
    host = (parsed.hostname or "").lower().rstrip(".")
    video_id: str | None = None

    if host in SHORT_HOSTS:
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif host in YOUTUBE_HOSTS:
        parts = [part for part in parsed.path.split("/") if part]
        if parsed.path.rstrip("/") == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif len(parts) >= 2 and parts[0] in {"embed", "shorts", "live", "v"}:
            video_id = parts[1]

    if video_id and VIDEO_ID_RE.fullmatch(video_id):
        return video_id
    raise InvalidYouTubeURL(
        "That doesn't look like a YouTube video URL. Try a watch, Shorts, live, "
        "or youtu.be link."
    )


def canonical_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _system_languages() -> list[str]:
    """Return useful language codes without relying on deprecated locale APIs."""
    language, _encoding = locale.getlocale()
    if not language:
        return ["en"]
    normalized = language.replace("_", "-")
    codes = [normalized]
    base = normalized.split("-", 1)[0]
    if base != normalized:
        codes.append(base)
    if "en" not in codes:
        codes.append("en")
    return codes


def _language_matches(actual: str, requested: str) -> bool:
    actual = actual.casefold().replace("_", "-")
    requested = requested.casefold().replace("_", "-")
    return actual == requested or actual.split("-", 1)[0] == requested.split("-", 1)[0]


def choose_transcript(transcripts: Sequence[Any], languages: Sequence[str]) -> Any:
    """Select a caption track predictably, preferring human-created captions."""
    if not transcripts:
        raise TranscriptFetchError("This video has no available captions.")

    priorities = list(languages) or _system_languages()
    for requested in priorities:
        matches = [
            item
            for item in transcripts
            if _language_matches(str(item.language_code), requested)
        ]
        if matches:
            return min(matches, key=lambda item: bool(item.is_generated))

    return min(transcripts, key=lambda item: bool(item.is_generated))


def fetch_video_title(video_id: str, timeout: float = 5.0) -> str:
    """Resolve the public title through YouTube's no-key oEmbed endpoint."""
    page_url = quote(canonical_url(video_id), safe="")
    request = Request(
        f"https://www.youtube.com/oembed?url={page_url}&format=json",
        headers={"User-Agent": "transcript-agent/1.0"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
        title = str(payload.get("title", "")).strip()
        return title or f"YouTube video {video_id}"
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return f"YouTube video {video_id}"


def _friendly_error(error: Exception) -> TranscriptFetchError:
    name = type(error).__name__
    messages = {
        "TranscriptsDisabled": "Captions are disabled for this video.",
        "NoTranscriptFound": "No usable captions were found for this video.",
        "VideoUnavailable": "This video is unavailable or private.",
        "AgeRestricted": "This video is age-restricted and can't be read anonymously.",
        "RequestBlocked": "YouTube blocked this request. Wait a moment, then retry.",
        "IpBlocked": "YouTube blocked requests from this network. Try another network.",
        "PoTokenRequired": "YouTube requires browser verification for this caption track.",
        "YouTubeRequestFailed": "YouTube couldn't serve this transcript right now.",
    }
    return TranscriptFetchError(
        messages.get(name, f"Could not fetch captions: {error}")
    )


class TranscriptFetcher:
    """Fetch caption tracks and normalize them into the app's domain model."""

    def __init__(
        self,
        api_factory: Callable[[], Any] = YouTubeTranscriptApi,
        title_resolver: Callable[[str], str] = fetch_video_title,
    ) -> None:
        self._api_factory = api_factory
        self._title_resolver = title_resolver

    def fetch(self, source: str, languages: Iterable[str] = ()) -> TranscriptDocument:
        video_id = extract_video_id(source)
        try:
            available = list(self._api_factory().list(video_id))
            selected = choose_transcript(available, tuple(languages))
            fetched = selected.fetch()
        except TranscriptFetchError:
            raise
        except Exception as error:
            raise _friendly_error(error) from error

        normalized: list[TranscriptSnippet] = []
        for snippet in fetched:
            text = unescape(str(snippet.text)).replace("\u200b", "").strip()
            if text:
                normalized.append(
                    TranscriptSnippet(
                        text=text,
                        start=float(snippet.start),
                        duration=float(snippet.duration),
                    )
                )
        snippets = tuple(normalized)
        if not snippets:
            raise TranscriptFetchError("The selected caption track is empty.")

        return TranscriptDocument(
            video_id=video_id,
            title=self._title_resolver(video_id),
            source_url=canonical_url(video_id),
            language=str(selected.language),
            language_code=str(selected.language_code),
            is_generated=bool(selected.is_generated),
            snippets=snippets,
        )

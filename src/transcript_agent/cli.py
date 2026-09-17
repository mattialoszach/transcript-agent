"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from transcript_agent import __version__
from transcript_agent.formatting import format_document
from transcript_agent.storage import default_output_directory, save_document
from transcript_agent.youtube import (
    InvalidYouTubeURL,
    TranscriptFetcher,
    TranscriptFetchError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="transcript-agent",
        description="Fetch, inspect, and save YouTube captions from the terminal.",
    )
    parser.add_argument("url", nargs="?", help="YouTube URL or 11-character video ID")
    parser.add_argument(
        "-l",
        "--language",
        action="append",
        default=[],
        metavar="CODE",
        help="preferred language code; repeat for fallback order",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=("md", "txt"),
        default="md",
        dest="output_format",
        help="save format (default: md)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="save folder (default: ~/Downloads)",
    )
    parser.add_argument(
        "--no-timestamps",
        action="store_true",
        help="omit paragraph timestamps from the saved transcript",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--no-ui",
        action="store_true",
        help="fetch and save immediately without the TUI",
    )
    mode.add_argument(
        "--stdout", action="store_true", help="write the formatted transcript to stdout"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def run_headless(args: argparse.Namespace) -> int:
    if not args.url:
        print(
            "transcript-agent: a YouTube URL is required in headless mode",
            file=sys.stderr,
        )
        return 2
    try:
        document = TranscriptFetcher().fetch(args.url, args.language)
        timestamps = not args.no_timestamps
        if args.stdout:
            sys.stdout.write(format_document(document, args.output_format, timestamps))
            return 0
        result = save_document(
            document,
            args.output_dir or default_output_directory(),
            args.output_format,
            timestamps,
        )
    except (InvalidYouTubeURL, TranscriptFetchError, OSError) as error:
        print(f"transcript-agent: {error}", file=sys.stderr)
        return 1

    verb = "Saved" if result.created else "Already saved"
    print(f"{verb}: {result.path}")
    return 0


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.no_ui or args.stdout:
        raise SystemExit(run_headless(args))

    from transcript_agent.app import TranscriptAgentApp

    app = TranscriptAgentApp(
        initial_url=args.url,
        languages=args.language,
        output_directory=args.output_dir or default_output_directory(),
        output_format=args.output_format,
        include_timestamps=not args.no_timestamps,
    )
    app.run()


if __name__ == "__main__":
    main()

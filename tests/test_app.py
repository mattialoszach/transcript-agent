from __future__ import annotations

import asyncio

from transcript_agent.app import (
    HelpScreen,
    HomeScreen,
    NamePicker,
    TranscriptAgentApp,
    ViewerScreen,
)


def test_home_screen_mounts() -> None:
    async def scenario() -> None:
        app = TranscriptAgentApp()
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, HomeScreen)
            assert app.screen.query_one("#url-input").has_focus

    asyncio.run(scenario())


def test_viewer_shortcuts_toggle_options_and_save(tmp_path, document) -> None:
    async def scenario() -> None:
        app = TranscriptAgentApp(output_directory=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.push_screen(ViewerScreen(document, document.source_url))
            await pilot.pause()
            assert isinstance(app.screen, ViewerScreen)

            await pilot.press("f", "t", "?")
            await pilot.pause()
            assert app.output_format == "txt"
            assert app.include_timestamps is False
            assert isinstance(app.screen, HelpScreen)

            await pilot.press("escape")
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()
            assert len(list(tmp_path.glob("*.txt"))) == 1

    asyncio.run(scenario())


def test_viewer_updates_text_when_timestamps_are_toggled(document) -> None:
    async def scenario() -> None:
        app = TranscriptAgentApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.push_screen(ViewerScreen(document, document.source_url))
            await pilot.pause()

            transcript = app.screen.query_one("#transcript")
            assert "00:00" in str(transcript.render())
            await pilot.press("t")
            await pilot.pause()
            assert "00:00" not in str(transcript.render())

    asyncio.run(scenario())


def test_viewer_allows_direct_naming(tmp_path, document) -> None:
    async def scenario() -> None:
        app = TranscriptAgentApp(output_directory=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.push_screen(ViewerScreen(document, document.source_url))
            await pilot.pause()

            await pilot.press("m")
            await pilot.pause()
            assert isinstance(app.screen, NamePicker)
            name_input = app.screen.query_one("#name-input")
            name_input.value = "Project interview"
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()
            assert (tmp_path / "Project interview.md").is_file()

    asyncio.run(scenario())


def test_initial_url_fetch_retry_and_new_flow(tmp_path, document) -> None:
    class FakeFetcher:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple[str, ...]]] = []

        def fetch(self, source: str, languages: tuple[str, ...]):
            self.calls.append((source, languages))
            return document

    async def scenario() -> None:
        fetcher = FakeFetcher()
        app = TranscriptAgentApp(
            initial_url=document.source_url,
            languages=("en",),
            output_directory=tmp_path,
            fetcher=fetcher,  # type: ignore[arg-type]
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert isinstance(app.screen, ViewerScreen)
            assert fetcher.calls == [(document.source_url, ("en",))]

            await pilot.press("r")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert isinstance(app.screen, ViewerScreen)
            assert len(fetcher.calls) == 2

            await pilot.press("n")
            await pilot.pause()
            assert isinstance(app.screen, HomeScreen)
            assert app.screen.query_one("#url-input").value == ""

    asyncio.run(scenario())

"""Keyboard-first Textual interface for Transcript Agent."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import cast

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    LoadingIndicator,
    Static,
)

from transcript_agent.formatting import OutputFormat, build_paragraphs, timestamp
from transcript_agent.models import TranscriptDocument
from transcript_agent.storage import SaveResult, save_document, transcript_filename
from transcript_agent.youtube import (
    InvalidYouTubeURL,
    TranscriptFetcher,
    TranscriptFetchError,
    extract_video_id,
)


class HomeScreen(Screen[None]):
    """URL entry and fetch-state screen."""

    BINDINGS = (
        Binding("ctrl+q", "app.quit", "Quit", show=False),
        Binding("escape", "app.quit", "Quit", show=False),
    )

    def __init__(self, initial_url: str | None = None) -> None:
        super().__init__()
        self.initial_url = initial_url

    def compose(self) -> ComposeResult:
        yield Header()
        with Center(id="home-center"), Vertical(id="home-card"):
            yield Static("YT", id="mark")
            yield Label("Transcript Agent", id="home-title")
            yield Static(
                "Paste a YouTube link. We'll find the best caption track.",
                id="home-subtitle",
            )
            yield Input(
                placeholder="https://youtube.com/watch?v=…",
                id="url-input",
            )
            with Horizontal(id="fetch-row"):
                yield Button("Fetch transcript", id="fetch", variant="primary")
                yield LoadingIndicator(id="loading")
            yield Static("", id="home-status")
            yield Static(
                "Watch links · Shorts · youtu.be · bare video IDs",
                id="url-hint",
            )
        yield Footer()

    def on_mount(self) -> None:
        loading = self.query_one("#loading", LoadingIndicator)
        loading.display = False
        field = self.query_one("#url-input", Input)
        field.focus()
        if self.initial_url:
            field.value = self.initial_url
            self.call_after_refresh(self.action_fetch)

    @on(Input.Submitted, "#url-input")
    def submit_url(self) -> None:
        self.action_fetch()

    @on(Button.Pressed, "#fetch")
    def press_fetch(self) -> None:
        self.action_fetch()

    def prepare(self, source: str = "") -> None:
        field = self.query_one("#url-input", Input)
        field.value = source
        self.query_one("#home-status", Static).update("")
        field.focus()

    def action_fetch(self) -> None:
        source = self.query_one("#url-input", Input).value.strip()
        try:
            extract_video_id(source)
        except InvalidYouTubeURL as error:
            self._finish_fetch(str(error), failed=True)
            return

        self.query_one("#home-status", Static).update("Reading captions from YouTube…")
        self.query_one("#loading", LoadingIndicator).display = True
        self.query_one("#fetch", Button).disabled = True
        self.query_one("#url-input", Input).disabled = True
        self.fetch_in_background(source)

    @work(thread=True, exclusive=True, group="youtube-fetch")
    def fetch_in_background(self, source: str) -> None:
        app = cast("TranscriptAgentApp", self.app)
        try:
            document = app.fetcher.fetch(source, app.languages)
        except (InvalidYouTubeURL, TranscriptFetchError, OSError) as error:
            self.app.call_from_thread(self._finish_fetch, str(error), True)
            return
        except Exception as error:  # noqa: BLE001 - keep the TUI recoverable
            self.app.call_from_thread(
                self._finish_fetch, f"Unexpected error: {error}", True
            )
            return
        self.app.call_from_thread(self._show_document, document, source)

    def _finish_fetch(self, message: str, failed: bool = False) -> None:
        status = self.query_one("#home-status", Static)
        status.update(Text(message, style="bold #ff6b6b" if failed else ""))
        self.query_one("#loading", LoadingIndicator).display = False
        self.query_one("#fetch", Button).disabled = False
        field = self.query_one("#url-input", Input)
        field.disabled = False
        field.focus()

    def _show_document(self, document: TranscriptDocument, source: str) -> None:
        self._finish_fetch("Ready")
        app = cast("TranscriptAgentApp", self.app)
        self.app.push_screen(ViewerScreen(document, source, app.output_name))


class TranscriptView(Static, can_focus=True):
    """Focusable transcript surface so Vim navigation always has a home."""


class ViewerScreen(Screen[None]):
    """Transcript inspection and save screen."""

    BINDINGS = (
        Binding("j", "line_down", "Down"),
        Binding("k", "line_up", "Up"),
        Binding("down", "line_down", "", show=False),
        Binding("up", "line_up", "", show=False),
        Binding("ctrl+d", "page_down", "Page down"),
        Binding("pagedown", "page_down", "", show=False),
        Binding("ctrl+u", "page_up", "Page up"),
        Binding("pageup", "page_up", "", show=False),
        Binding("g", "top", "Top", key_display="g"),
        Binding("G", "bottom", "Bottom", key_display="G"),
        Binding("s", "save", "Save"),
        Binding("m", "name", "Name"),
        Binding("o", "folder", "Folder"),
        Binding("f", "format", "Format"),
        Binding("t", "timestamps", "Timestamps"),
        Binding("r", "retry", "Retry"),
        Binding("n", "new", "New URL"),
        Binding("question_mark", "help", "Help"),
        Binding("q", "app.quit", "Quit"),
    )

    def __init__(
        self,
        document: TranscriptDocument,
        source: str,
        output_name: str | None = None,
    ) -> None:
        super().__init__()
        self.document = document
        self.source = source
        self.output_name = output_name

    def compose(self) -> ComposeResult:
        app = cast("TranscriptAgentApp", self.app)
        yield Header()
        with Vertical(id="reader-shell"):
            with Horizontal(id="metadata-bar"):
                yield Static(self.document.title, id="video-title")
                kind = "AUTO" if self.document.is_generated else "MANUAL"
                yield Static(
                    f"{self.document.language_code.upper()}  ·  {kind}",
                    id="track-badge",
                )
            with VerticalScroll(id="transcript-scroll"):
                yield TranscriptView(self._reader_text(), id="transcript")
            with Horizontal(id="toolbar"):
                yield Button("Save  S", id="save", variant="primary")
                yield Button("Name  M", id="name")
                yield Button("Folder  O", id="folder")
                yield Button(self._format_label(app.output_format), id="format")
                yield Button(
                    self._timestamp_label(app.include_timestamps), id="timestamps"
                )
                yield Button("Retry  R", id="retry")
                yield Button("New  N", id="new")
            yield Static(self._destination_text(), id="save-status")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#transcript", TranscriptView).focus()

    def _reader_text(self) -> Text:
        app = cast("TranscriptAgentApp", self.app)
        text = Text()
        for index, paragraph in enumerate(build_paragraphs(self.document.snippets)):
            if index:
                text.append("\n\n" if app.include_timestamps else " ")
            if app.include_timestamps:
                text.append(timestamp(paragraph.start), style="bold #5eead4")
                text.append("  ")
            text.append(paragraph.text, style="#e7edf4")
        return text

    @staticmethod
    def _format_label(output_format: OutputFormat) -> str:
        return f"{output_format.upper()}  F"

    @staticmethod
    def _timestamp_label(enabled: bool) -> str:
        return f"Times {'on' if enabled else 'off'}  T"

    def _destination_text(self) -> str:
        app = cast("TranscriptAgentApp", self.app)
        filename = transcript_filename(
            self.document, app.output_format, self.output_name
        )
        return f"Save to  {app.output_directory / filename}"

    def _restore_reader_focus(self) -> None:
        self.query_one("#transcript", TranscriptView).focus()

    def _scroll(self) -> VerticalScroll:
        return self.query_one("#transcript-scroll", VerticalScroll)

    def action_line_down(self) -> None:
        self._scroll().scroll_relative(y=2, animate=False)

    def action_line_up(self) -> None:
        self._scroll().scroll_relative(y=-2, animate=False)

    def action_page_down(self) -> None:
        self._scroll().scroll_page_down(animate=False)

    def action_page_up(self) -> None:
        self._scroll().scroll_page_up(animate=False)

    def action_top(self) -> None:
        self._scroll().scroll_home(animate=False)

    def action_bottom(self) -> None:
        self._scroll().scroll_end(animate=False)

    def action_save(self) -> None:
        app = cast("TranscriptAgentApp", self.app)
        status = self.query_one("#save-status", Static)
        try:
            result = save_document(
                self.document,
                app.output_directory,
                app.output_format,
                app.include_timestamps,
                self.output_name,
            )
        except OSError as error:
            status.update(Text(str(error), style="bold #ff6b6b"))
            self.notify(str(error), severity="error", timeout=5)
            return
        self._show_save_result(result)
        self._restore_reader_focus()

    def action_name(self) -> None:
        app = cast("TranscriptAgentApp", self.app)
        suggested = Path(
            transcript_filename(self.document, app.output_format, self.output_name)
        ).stem
        self.app.push_screen(NamePicker(suggested), self._name_selected)

    def _name_selected(self, name: str | None) -> None:
        if name is not None:
            self.output_name = name
            self.query_one("#save-status", Static).update(self._destination_text())
        self._restore_reader_focus()

    def _show_save_result(self, result: SaveResult) -> None:
        verb = "Saved" if result.created else "Already saved"
        self.query_one("#save-status", Static).update(
            Text(f"{verb}  {result.path}", style="bold #5eead4")
        )
        self.notify(f"{verb}: {result.path.name}", timeout=4)

    def action_folder(self) -> None:
        app = cast("TranscriptAgentApp", self.app)
        self.app.push_screen(FolderPicker(app.output_directory), self._folder_selected)

    def _folder_selected(self, directory: Path | None) -> None:
        if directory is not None:
            app = cast("TranscriptAgentApp", self.app)
            app.output_directory = directory
            self.query_one("#save-status", Static).update(self._destination_text())
        self._restore_reader_focus()

    def action_format(self) -> None:
        app = cast("TranscriptAgentApp", self.app)
        app.output_format = "txt" if app.output_format == "md" else "md"
        self.query_one("#format", Button).label = self._format_label(app.output_format)
        self.query_one("#save-status", Static).update(self._destination_text())
        self._restore_reader_focus()

    def action_timestamps(self) -> None:
        app = cast("TranscriptAgentApp", self.app)
        app.include_timestamps = not app.include_timestamps
        self.query_one("#timestamps", Button).label = self._timestamp_label(
            app.include_timestamps
        )
        self.query_one("#transcript", TranscriptView).update(self._reader_text())
        self._restore_reader_focus()

    def action_retry(self) -> None:
        app = cast("TranscriptAgentApp", self.app)
        self.app.pop_screen()
        app.home_screen.prepare(self.source)
        app.home_screen.call_after_refresh(app.home_screen.action_fetch)

    def action_new(self) -> None:
        app = cast("TranscriptAgentApp", self.app)
        self.app.pop_screen()
        app.home_screen.prepare()

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen(), lambda _: self._restore_reader_focus())

    @on(Button.Pressed)
    def button_pressed(self, event: Button.Pressed) -> None:
        actions = {
            "save": self.action_save,
            "name": self.action_name,
            "folder": self.action_folder,
            "format": self.action_format,
            "timestamps": self.action_timestamps,
            "retry": self.action_retry,
            "new": self.action_new,
        }
        action = actions.get(event.button.id or "")
        if action:
            action()


class FolderPicker(ModalScreen[Path | None]):
    """Small folder browser with a direct path fallback."""

    BINDINGS = (
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+enter", "choose", "Use folder"),
    )

    def __init__(self, current: Path) -> None:
        super().__init__()
        self.current = current.expanduser().resolve()
        self.selected = self.current

    def compose(self) -> ComposeResult:
        with Vertical(id="folder-dialog"):
            yield Label("Choose a save folder", id="dialog-title")
            yield Input(str(self.current), id="folder-path")
            yield DirectoryTree(str(Path.home()), id="folder-tree")
            yield Static("Enter opens folders · Ctrl+Enter confirms", id="folder-hint")
            with Horizontal(id="dialog-buttons"):
                yield Button("Cancel  Esc", id="cancel")
                yield Button("Use this folder", id="choose", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#folder-tree", DirectoryTree).focus()

    @on(DirectoryTree.DirectorySelected)
    def directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self.selected = event.path.resolve()
        self.query_one("#folder-path", Input).value = str(self.selected)

    @on(Input.Submitted, "#folder-path")
    def path_submitted(self) -> None:
        self.action_choose()

    @on(Button.Pressed)
    def dialog_button(self, event: Button.Pressed) -> None:
        if event.button.id == "choose":
            self.action_choose()
        elif event.button.id == "cancel":
            self.action_cancel()

    def action_choose(self) -> None:
        raw = self.query_one("#folder-path", Input).value.strip()
        path = Path(raw).expanduser()
        if not path.is_dir():
            self.query_one("#folder-hint", Static).update(
                Text("Choose an existing folder.", style="bold #ff6b6b")
            )
            return
        self.dismiss(path.resolve())

    def action_cancel(self) -> None:
        self.dismiss(None)


class NamePicker(ModalScreen[str | None]):
    """Prompt for the saved transcript's filename."""

    BINDINGS = (Binding("escape", "cancel", "Cancel"),)

    def __init__(self, suggested: str) -> None:
        super().__init__()
        self.suggested = suggested

    def compose(self) -> ComposeResult:
        with Vertical(id="name-dialog"):
            yield Label("Name the transcript", id="dialog-title")
            yield Input(self.suggested, id="name-input", select_on_focus=False)
            yield Static("The file extension is added automatically.", id="name-hint")
            with Horizontal(id="dialog-buttons"):
                yield Button("Cancel  Esc", id="cancel")
                yield Button("Use this name", id="choose", variant="primary")

    def on_mount(self) -> None:
        field = self.query_one("#name-input", Input)
        field.focus()
        field.action_end()

    @on(Input.Submitted, "#name-input")
    def name_submitted(self) -> None:
        self.action_choose()

    @on(Button.Pressed)
    def dialog_button(self, event: Button.Pressed) -> None:
        if event.button.id == "choose":
            self.action_choose()
        elif event.button.id == "cancel":
            self.action_cancel()

    def action_choose(self) -> None:
        name = self.query_one("#name-input", Input).value.strip()
        if not name:
            self.query_one("#name-hint", Static).update(
                Text("Enter a filename.", style="bold #ff6b6b")
            )
            return
        self.dismiss(name)

    def action_cancel(self) -> None:
        self.dismiss(None)


class HelpScreen(ModalScreen[None]):
    BINDINGS = (
        Binding("escape", "close", "Close"),
        Binding("question_mark", "close", "Close", show=False),
        Binding("q", "close", "Close", show=False),
    )

    def compose(self) -> ComposeResult:
        with Vertical(id="help-dialog"):
            yield Label("Keyboard shortcuts", id="dialog-title")
            yield Static(
                "j / k or ↑ / ↓   scroll\n"
                "Ctrl+d / Ctrl+u   page down / up\n"
                "g / G             top / bottom\n\n"
                "s   save           m   name file\n"
                "o   choose folder  f   MD / TXT\n"
                "t   timestamps     r   retry\n"
                "n   new URL\n"
                "q   quit           ?   close help",
                id="help-copy",
            )
            yield Button("Close", id="close", variant="primary")

    @on(Button.Pressed, "#close")
    def close_button(self) -> None:
        self.action_close()

    def action_close(self) -> None:
        self.dismiss(None)


class TranscriptAgentApp(App[None]):
    """Application state and visual theme."""

    TITLE = "Transcript Agent"
    SUB_TITLE = "YouTube captions, without the clutter"
    ENABLE_COMMAND_PALETTE = False
    CSS = """
    $ink: #e7edf4;
    $muted: #81909f;
    $surface: #111820;
    $panel: #17212b;
    $accent: #5eead4;
    $danger: #ff6b6b;

    Screen {
        background: #0b1016;
        color: $ink;
    }

    Header {
        background: #0b1016;
        color: $ink;
    }

    Footer {
        background: #111820;
        color: $muted;
    }

    Footer .footer-key--key {
        background: #263442;
        color: $accent;
    }

    #home-card {
        width: 72;
        max-width: 92%;
        height: auto;
        padding: 2 4;
        margin-top: 1;
        background: $surface;
        border: round #263442;
    }

    #home-center {
        height: 1fr;
    }

    #mark {
        width: 8;
        height: 3;
        padding: 0 1;
        background: $accent;
        color: #07110f;
        text-style: bold;
        content-align: center middle;
        margin-bottom: 1;
    }

    #home-title {
        height: 2;
        text-style: bold;
        color: $ink;
    }

    #home-subtitle, #url-hint {
        color: $muted;
        margin-bottom: 1;
    }

    #url-hint {
        margin-top: 1;
        margin-bottom: 0;
    }

    Input {
        border: tall #2a3947;
        background: #0d141b;
        color: $ink;
    }

    Input:focus {
        border: tall $accent;
    }

    #fetch-row {
        height: 3;
        margin-top: 1;
    }

    #fetch {
        width: 22;
    }

    #loading {
        width: 6;
        height: 3;
        color: $accent;
    }

    #home-status {
        min-height: 1;
        color: $muted;
    }

    Button {
        min-width: 10;
        height: 3;
        border: none;
        background: #24313e;
        color: $ink;
    }

    Button:hover, Button:focus {
        background: #344657;
        color: white;
        text-style: bold;
    }

    Button.-primary {
        background: #1c8f82;
        color: white;
    }

    #reader-shell {
        width: 100%;
        height: 100%;
        padding: 0 2;
    }

    #metadata-bar {
        height: 3;
        padding: 0 1;
        background: $surface;
        border-bottom: solid #263442;
    }

    #video-title {
        width: 1fr;
        height: 2;
        padding-top: 1;
        text-style: bold;
        text-overflow: ellipsis;
    }

    #track-badge {
        width: auto;
        height: 2;
        padding: 1 1 0 1;
        color: $accent;
        text-style: bold;
    }

    #transcript-scroll {
        height: 1fr;
        margin: 1 0;
        padding: 1 2;
        align-horizontal: center;
        background: $surface;
        border: round #263442;
        scrollbar-color: #314355;
        scrollbar-color-hover: $accent;
        scrollbar-background: $surface;
    }

    #transcript {
        width: 100%;
        height: auto;
        max-width: 110;
        color: $ink;
    }

    #transcript:focus {
        border: none;
    }

    #toolbar {
        height: 3;
    }

    #toolbar Button {
        margin-right: 1;
    }

    #save-status {
        height: 2;
        padding: 0 1;
        color: $muted;
        text-overflow: ellipsis;
    }

    FolderPicker, NamePicker, HelpScreen {
        align: center middle;
        background: #05080ca8;
    }

    #folder-dialog {
        width: 78;
        max-width: 94%;
        height: 80%;
        padding: 1 2;
        background: $panel;
        border: round #3a5064;
    }

    #name-dialog {
        width: 64;
        max-width: 92%;
        height: auto;
        padding: 1 2;
        background: $panel;
        border: round #3a5064;
    }

    #name-hint {
        height: 2;
        padding-top: 1;
        color: $muted;
    }

    #dialog-title {
        height: 2;
        text-style: bold;
        color: $ink;
    }

    #folder-tree {
        height: 1fr;
        margin-top: 1;
        background: #0d141b;
        border: round #2a3947;
    }

    #folder-hint {
        height: 2;
        padding-top: 1;
        color: $muted;
    }

    #dialog-buttons {
        height: 3;
        align-horizontal: right;
    }

    #dialog-buttons Button {
        margin-left: 1;
    }

    #help-dialog {
        width: 58;
        max-width: 90%;
        height: auto;
        padding: 2 3;
        background: $panel;
        border: round #3a5064;
    }

    #help-copy {
        height: auto;
        margin: 1 0 2 0;
        color: $ink;
    }

    #help-dialog Button {
        width: 14;
        align-horizontal: center;
    }
    """

    def __init__(
        self,
        initial_url: str | None = None,
        languages: Iterable[str] = (),
        output_directory: Path | None = None,
        output_format: OutputFormat = "md",
        include_timestamps: bool = True,
        output_name: str | None = None,
        fetcher: TranscriptFetcher | None = None,
    ) -> None:
        super().__init__()
        from transcript_agent.storage import default_output_directory

        self.initial_url = initial_url
        self.languages = tuple(languages)
        self.output_directory = output_directory or default_output_directory()
        self.output_format = output_format
        self.include_timestamps = include_timestamps
        self.output_name = output_name
        self.fetcher = fetcher or TranscriptFetcher()
        self.home_screen = HomeScreen(initial_url)

    def on_mount(self) -> None:
        self.push_screen(self.home_screen)

# Transcript Agent

A fast, keyboard-first terminal app for fetching, reading, and saving the captions that YouTube already provides. Paste a URL, skim the transcript in a clean reader, and press `s` to save it as Markdown or plain text.

No API key, browser automation, audio download, or speech-to-text service is required.

## Install

Python 3.10 or newer is required. From this repository, the cleanest installation is:

```bash
uv tool install .
```

Or with `pipx`:

```bash
pipx install .
```

Standard `pip` also works: `python -m pip install .`

Then run it from anywhere:

```bash
transcript-agent
```

The shorter `yt-transcript` command is installed as an alias.

## Use

Open the app and paste a link:

```bash
yt-transcript
```

Or skip the first screen:

```bash
yt-transcript "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

The reader shows all essential controls on screen. It also supports familiar Vim movement:

| Key | Action |
| --- | --- |
| `j` / `k`, `↓` / `↑` | Scroll down / up |
| `Ctrl+d` / `Ctrl+u` | Page down / up |
| `g` / `G` | Jump to top / bottom |
| `s` | Save |
| `o` | Choose a save folder |
| `f` | Switch Markdown / plain text |
| `t` | Toggle timestamps |
| `r` | Retry the current video |
| `n` | Enter a new URL |
| `?` | Show all shortcuts |
| `q` | Quit |

Transcripts save to `~/Downloads` by default (or the home folder if Downloads does not exist). Filenames contain the video title and ID. Existing files are never silently overwritten, and saving identical content twice reuses the existing file.

Supported inputs include regular watch links, `youtu.be` links, Shorts, live links, embed links, YouTube Music links, and bare 11-character video IDs.

## Fast non-interactive use

Fetch and save immediately:

```bash
yt-transcript VIDEO_URL --no-ui
```

Choose text output and a folder:

```bash
yt-transcript VIDEO_URL --no-ui --format txt --output-dir ./notes
```

Pipe a transcript into another command:

```bash
yt-transcript VIDEO_URL --stdout --no-timestamps > transcript.md
```

Prefer German, then English if German is unavailable:

```bash
yt-transcript VIDEO_URL --language de --language en
```

Run `yt-transcript --help` for the complete command reference.

## Output

Markdown output contains:

- The YouTube title
- A source link
- Caption language and whether the track is creator-provided or generated
- Readable paragraphs with timestamps linked to the matching moment in the video

Plain text contains the same metadata without Markdown syntax. Timestamps can be disabled in the UI or with `--no-timestamps`.

## How caption selection works

Transcript Agent tries explicitly requested languages first. Otherwise it tries the computer's language, its base language, and English. Within a language it prefers creator-provided captions over auto-generated captions. If none of those languages exist, it uses the best available caption track.

Only caption tracks available from YouTube can be fetched. Videos with disabled captions, private videos, age restrictions, network blocks, or YouTube browser-verification requirements may not work. The app reports these cases without crashing so a different URL or a retry can be used.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv build
```

The implementation is deliberately small:

- `youtube.py` parses URLs and selects/fetches caption tracks
- `formatting.py` turns caption fragments into readable documents
- `storage.py` handles safe names and non-destructive saving
- `app.py` contains the Textual terminal UI
- `cli.py` provides interactive and automation-friendly commands

## License

MIT

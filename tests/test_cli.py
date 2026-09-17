from __future__ import annotations

from transcript_agent import cli


class FakeFetcher:
    document = None

    def fetch(self, _source, _languages):
        assert self.document is not None
        return self.document


def test_headless_requires_url(capsys) -> None:
    args = cli.build_parser().parse_args(["--no-ui"])
    assert cli.run_headless(args) == 2
    assert "required" in capsys.readouterr().err


def test_stdout_mode_prints_document(monkeypatch, capsys, document) -> None:
    FakeFetcher.document = document
    monkeypatch.setattr(cli, "TranscriptFetcher", FakeFetcher)
    args = cli.build_parser().parse_args(["dQw4w9WgXcQ", "--stdout"])
    assert cli.run_headless(args) == 0
    assert "# A useful video" in capsys.readouterr().out


def test_no_ui_saves_document(monkeypatch, capsys, tmp_path, document) -> None:
    FakeFetcher.document = document
    monkeypatch.setattr(cli, "TranscriptFetcher", FakeFetcher)
    args = cli.build_parser().parse_args(
        ["dQw4w9WgXcQ", "--no-ui", "--output-dir", str(tmp_path), "--format", "txt"]
    )
    assert cli.run_headless(args) == 0
    assert "Saved:" in capsys.readouterr().out
    assert len(list(tmp_path.glob("*.txt"))) == 1

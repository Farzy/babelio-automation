import json

from click.testing import CliRunner

import main

CREDS = ["--username", "user@example.com", "--password", "secret"]


def test_mark_possessed_dry_run_lists_urls(tmp_path):
    urls_file = tmp_path / "urls.json"
    urls_file.write_text(json.dumps(["https://www.babelio.com/livres/A/1", {"url": "u2"}]))

    result = CliRunner().invoke(main.cli, ["mark-possessed", "--urls-file", str(urls_file), *CREDS])

    assert result.exit_code == 0
    assert "DRY RUN" in result.output
    assert "https://www.babelio.com/livres/A/1" in result.output
    assert "  - u2" in result.output


def test_mark_possessed_empty_file(tmp_path):
    urls_file = tmp_path / "urls.json"
    urls_file.write_text("[]")

    result = CliRunner().invoke(main.cli, ["mark-possessed", "--urls-file", str(urls_file), *CREDS])

    assert "No URLs found" in result.output


def test_mark_possessed_reports_results(tmp_path, monkeypatch):
    urls_file = tmp_path / "urls.json"
    urls_file.write_text('["a", "b", "c"]')

    class FakeBot:
        def __init__(self, *_args, **_kwargs):
            pass

        def mark_possessed(self, urls):
            assert urls == ["a", "b", "c"]
            return {"success": ["a"], "already": ["b"], "failed": [("c", "boom")]}

    monkeypatch.setattr(main, "BabelioBot", FakeBot)
    result = CliRunner().invoke(
        main.cli, ["mark-possessed", "--urls-file", str(urls_file), "--no-dry-run", *CREDS]
    )

    assert "Marked 'Possédé': 1" in result.output
    assert "Already 'Possédé': 1" in result.output
    assert "c: boom" in result.output


def test_books_json_output(monkeypatch):
    book = {"title": "T", "author": "A", "status": "Lu", "possessed": True, "url": "u"}

    class FakeBot:
        def __init__(self, *_args, **_kwargs):
            pass

        def fetch_library_books(self, **kwargs):
            assert kwargs["status_filter"] == "wishlist"
            return [book]

    monkeypatch.setattr(main, "BabelioBot", FakeBot)
    result = CliRunner().invoke(
        main.cli, ["books", "--status", "wishlist", "--json-output", *CREDS]
    )

    assert result.exit_code == 0
    assert json.loads(result.output[result.output.index("[") :]) == [book]


def test_books_rejects_removed_status():
    result = CliRunner().invoke(main.cli, ["books", "--status", "pense-bete", *CREDS])

    assert result.exit_code != 0

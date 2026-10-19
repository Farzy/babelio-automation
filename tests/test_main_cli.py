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
            assert kwargs["statuses"] == ["wishlist"]
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


def test_books_has_no_non_possedes_flag():
    result = CliRunner().invoke(main.cli, ["books", "--non-possedes", *CREDS])

    assert result.exit_code != 0
    assert "No such option" in result.output


def test_books_accepts_repeated_status_flags(monkeypatch):
    seen = {}

    class FakeBot:
        def __init__(self, *_args, **_kwargs):
            pass

        def fetch_library_books(self, **kwargs):
            seen.update(kwargs)
            return []

    monkeypatch.setattr(main, "BabelioBot", FakeBot)
    result = CliRunner().invoke(
        main.cli, ["books", "-s", "a-lire", "-s", "non-possedes", "--json-output", *CREDS]
    )

    assert result.exit_code == 0
    assert seen["statuses"] == ["a-lire", "non-possedes"]


def test_books_defaults_to_tous(monkeypatch):
    seen = {}

    class FakeBot:
        def __init__(self, *_args, **_kwargs):
            pass

        def fetch_library_books(self, **kwargs):
            seen.update(kwargs)
            return []

    monkeypatch.setattr(main, "BabelioBot", FakeBot)
    CliRunner().invoke(main.cli, ["books", "--json-output", *CREDS])

    assert seen["statuses"] == ["tous"]


def test_books_rejects_incompatible_statuses_before_scraping(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("must not reach Babelio")

    monkeypatch.setattr(main, "BabelioBot", boom)
    result = CliRunner().invoke(main.cli, ["books", "-s", "possedes", "-s", "non-possedes", *CREDS])

    assert result.exit_code == 2
    assert "Incompatible statuses" in result.output

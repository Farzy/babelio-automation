import json
import time

import config


def test_load_config_defaults(tmp_path, monkeypatch):
    test_cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_FILE", str(test_cfg_file))
    monkeypatch.setattr(config, "CONFIG_DIR", str(tmp_path))

    # Test defaults when file does not exist
    cfg = config.load_config()
    assert cfg["cache_ttl_seconds"] == 3600

    # Write a test config file
    test_data = {
        "babelio_username": "user@test.com",
        "babelio_password": "test_pass_value",  # noqa: S105 # pragma: allowlist secret
        "google_sheet_url": "https://docs.google.com/spreadsheets/d/test/edit",
        "cache_ttl_seconds": 1800,
    }
    with open(test_cfg_file, "w", encoding="utf-8") as f:
        json.dump(test_data, f)

    loaded = config.load_config()
    assert loaded["babelio_username"] == "user@test.com"
    assert loaded["babelio_password"] == "test_pass_value"  # noqa: S105 # pragma: allowlist secret
    assert loaded["cache_ttl_seconds"] == 1800


def test_books_cache_lifecycle(tmp_path, monkeypatch):
    test_cache_file = tmp_path / "books_cache.json"
    monkeypatch.setattr(config, "CACHE_FILE", str(test_cache_file))
    monkeypatch.setattr(config, "CONFIG_DIR", str(tmp_path))

    # Expect None when cache file does not exist
    assert config.load_books_cache(ttl_seconds=3600) is None

    # Save books to cache
    sample_books = [
        {
            "title": "La Route",
            "author": "Cormac McCarthy",
            "status": "Lu",
            "possessed": False,
            "url": "https://www.babelio.com/livres/McCarthy-La-Route/34709",
        }
    ]
    saved_path = config.save_books_cache(sample_books)
    assert saved_path == str(test_cache_file)

    # Load books back from cache
    loaded = config.load_books_cache(ttl_seconds=3600)
    assert loaded is not None
    assert len(loaded) == 1
    assert loaded[0]["title"] == "La Route"

    # Expect None when cache is expired (TTL = 0)
    time.sleep(0.01)
    assert config.load_books_cache(ttl_seconds=0) is None

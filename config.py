import contextlib
import json
import os
import time
from typing import Any

CONFIG_DIR = os.path.expanduser("~/.config/babelio-automation")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
CACHE_FILE = os.path.join(CONFIG_DIR, "books_cache.json")
STATE_FILE = os.path.join(CONFIG_DIR, "session_state.json")
DEFAULT_TTL_SECONDS = 3600  # 1 hour default


def ensure_config_dir() -> str:
    """Ensure configuration directory exists."""
    with contextlib.suppress(Exception):
        os.makedirs(CONFIG_DIR, exist_ok=True)
    return CONFIG_DIR


def get_state_file_path() -> str:
    """Get the absolute path for persistent session state storage."""
    ensure_config_dir()
    return STATE_FILE


def load_config() -> dict[str, Any]:
    """Load configuration with priority: config file -> .env / env vars -> defaults."""
    ensure_config_dir()
    config: dict[str, Any] = {}

    if os.path.exists(CONFIG_FILE):
        with contextlib.suppress(Exception), open(CONFIG_FILE, encoding="utf-8") as f:
            file_config = json.load(f)
            if isinstance(file_config, dict):
                config.update(file_config)

    config.setdefault("babelio_username", os.getenv("BABELIO_USERNAME", ""))
    config.setdefault("babelio_password", os.getenv("BABELIO_PASSWORD", ""))
    config.setdefault("google_sheet_url", os.getenv("GOOGLE_SHEET_URL", ""))
    config.setdefault("gog_account", os.getenv("GOG_ACCOUNT", None))

    ttl_val = config.get("cache_ttl_seconds")
    if ttl_val is None:
        ttl_val = os.getenv("BABELIO_CACHE_TTL", DEFAULT_TTL_SECONDS)
    try:
        config["cache_ttl_seconds"] = int(ttl_val)
    except (ValueError, TypeError):
        config["cache_ttl_seconds"] = DEFAULT_TTL_SECONDS

    return config


def create_user_config_file(
    username: str,
    password: str,
    sheet_url: str,
    gog_account: str | None = None,
    ttl: int = DEFAULT_TTL_SECONDS,
) -> str:
    """Create or update user's configuration file in ~/.config/babelio-automation/config.json."""
    ensure_config_dir()
    cfg_data = {
        "babelio_username": username,
        "babelio_password": password,
        "google_sheet_url": sheet_url,
        "gog_account": gog_account,
        "cache_ttl_seconds": ttl,
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg_data, f, indent=2, ensure_ascii=False)
    return CONFIG_FILE


def load_books_cache(ttl_seconds: int = DEFAULT_TTL_SECONDS) -> list[dict[str, Any]] | None:
    """Load books from local cache file if it exists and is unexpired."""
    if not os.path.exists(CACHE_FILE):
        return None

    with contextlib.suppress(Exception), open(CACHE_FILE, encoding="utf-8") as f:
        data = json.load(f)

        cached_time = data.get("timestamp", 0)
        age = time.time() - cached_time

        if age < ttl_seconds and isinstance(data.get("books"), list):
            return data["books"]

    return None


def save_books_cache(books: list[dict[str, Any]]) -> str:
    """Save books list to local cache file with current timestamp."""
    ensure_config_dir()
    data = {
        "timestamp": time.time(),
        "books": books,
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return CACHE_FILE

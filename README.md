# Babelio Automation (v0.2.0)

A CLI tool for synchronizing personal book libraries from Google Sheets to [Babelio](https://www.babelio.com/) and querying your Babelio library with advanced filtering options. Since Babelio does not offer a public API, this project uses **Playwright** browser automation alongside the **`gog` CLI** for Google Sheets API integration.

---

## Key Features

- **Automated Authentication**: Log in securely to Babelio with automated cookie consent (SFBX iframe) handling and session persistence (`~/.config/babelio-automation/session_state.json`).
- **Configuration Management**: Persistent JSON configuration file (`~/.config/babelio-automation/config.json`) for credentials, Google Sheet URLs, and cache settings.
- **Smart Book Caching**: Caches your complete Babelio book library locally (`~/.config/babelio-automation/books_cache.json`) for a configurable duration (default: **1 hour** / 3600 seconds), making list and filter queries instantaneous and protecting your Babelio account against rate limits or IP blocks.
- **Cache Bypass / Direct Query**: Includes `--no-cache` (`--bypass-cache` / `--force-refresh`) options to bypass local storage and query the Babelio website directly.
- **Google Sheets Integration via `gog`**: Uses the `gog` CLI (`/usr/local/bin/gog`) for reading and updating Google Sheets without requiring Google Service Account JSON keys.
- **Babelio Library Listing & Filtering**: View and search your Babelio books using built-in or custom status filters:
  - **`lus`**: Books on your Read shelf.
  - **`a-lire`**: Books on your To Read shelf.
  - **`en-cours`**: Books currently being read.
  - **`pense-bete`**: Books tagged as Pense-bête / Bookmarks.
  - **`abandonnes`**: Books marked as Abandoned.
  - **`possedes`**: Books marked as Possessed.
  - **`non-possedes`**: Books **NOT** marked as Possessed (client-side evaluation missing from web interface).
  - **`critiques` / `non-critiques`**: Filter by review status.
  - **`--non-possedes` flag**: Combine with any status (e.g. `--status a-lire --non-possedes` to find unowned books on your "To Read" shelf).

---

## Prerequisites

- **Python**: 3.12 or later
- **Package Manager**: [`uv`](https://docs.astral.sh/uv/)
- **Google CLI**: [`gog`](https://github.com/gogcli) installed and authenticated on your machine

---

## Quick Start & Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Farzy/babelio-automation.git
   cd babelio-automation
   ```

2. **Install dependencies and binary entrypoint**:
   ```bash
   uv sync
   ```

3. **Install Playwright Browsers**:
   ```bash
   uv run playwright install chromium
   ```

---

## Configuration

Configuration values are resolved in the following priority order:

1. **CLI Flag / Command Arguments**
2. **Configuration File**: `~/.config/babelio-automation/config.json`
3. **Environment Variables / `.env` file**

### Configuration File (`~/.config/babelio-automation/config.json`)

Create `~/.config/babelio-automation/config.json` (see [`config.example.json`](config.example.json) for reference):

```json
{
  "babelio_username": "your_email@example.com",
  "babelio_password": "<SECRET_KEY>",
  "google_sheet_url": "https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit",
  "gog_account": "your_google_account@example.com",
  "cache_ttl_seconds": 3600
}
```

### Environment Variables (`.env` Fallback)

Alternatively, copy `.env.example` to `.env`:

```env
GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit
BABELIO_USERNAME=your_email@example.com
BABELIO_PASSWORD=your_babelio_password
```

### Inspecting Active Configuration

View your active configuration paths and settings (with password masked):

```bash
uv run babelio-cli show-config
```

---

## CLI Usage (`babelio-cli`)

### 1. List & Filter Babelio Library Books (`books`)

Display books in your Babelio library instantly using local 1-hour cache or query directly:

```bash
# List books that are NOT possessed (instant local cache hit)
uv run babelio-cli books --status non-possedes --limit 20

# Query Babelio website directly (bypass local cache)
uv run babelio-cli books --status non-possedes --no-cache

# Force refresh library cache
uv run babelio-cli books --status non-possedes --force-refresh

# List unowned books on your "To Read" shelf
uv run babelio-cli books --status a-lire --non-possedes

# List books on your "Pense-bête" shelf
uv run babelio-cli books --status pense-bete

# List 5-star rated books with JSON output
uv run babelio-cli books --rating 5 --json-output
```

#### Cache Control Flags
- `--no-cache` / `--bypass-cache`: Bypass book cache and query Babelio website directly.
- `--force-refresh` / `-f`: Bypass local cache and force refresh/update the cache file.
- `--cache-ttl <SECONDS>`: Override cache time-to-live period (default: 3,600s / 1h).

#### Status Filter Options (`--status` / `-s`)
- `tous`: All library books (default)
- `lus`: Read books
- `a-lire`: Books to read
- `en-cours`: Currently reading
- `pense-bete`: Bookmarks / Pense-bête
- `abandonnes`: Abandoned books
- `possedes`: Possessed books
- `non-possedes`: Books not marked as possessed
- `critiques`: Reviewed books
- `non-critiques`: Unreviewed books

---

### 2. Synchronize Google Sheet to Babelio (`sync`)

#### Dry Run (Default / Safe Mode)
```bash
uv run babelio-cli sync --limit 5 --dry-run
```

#### Live Sync (Interactive Mode)
```bash
uv run babelio-cli sync --no-headless --no-dry-run
```

---

### 3. Read Google Sheet Data (`read-books`)

```bash
uv run babelio-cli read-books
```

---

## Global Tool Installation (Optional)

Install `babelio-cli` globally as a standalone command using `uv tool`:

```bash
# Standard installation
uv tool install .

# Editable installation
uv tool install --editable .
```

Invoke from anywhere:

```bash
babelio-cli books --status non-possedes --no-cache
```

---

## Running Unit Tests

Run the `pytest` test suite:

```bash
uv run pytest
```

---

## Development & Code Quality

```bash
uv run ruff check .
uv run pre-commit install
```

# Babelio Automation (v0.2.0)

A CLI tool for synchronizing personal book libraries from Google Sheets to [Babelio](https://www.babelio.com/) and querying your Babelio library with advanced filtering options. Since Babelio does not offer a public API, this project uses **Playwright** browser automation alongside the **`gog` CLI** for Google Sheets API integration.

---

## Key Features

- **Automated Authentication**: Log in securely to Babelio with automated cookie consent (SFBX iframe) handling and session persistence (`.babelio_state.json`).
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
- **Multi-Stage Book Search**: Intelligent fallback search strategy: `ISBN` $\rightarrow$ `Title + Author` $\rightarrow$ `Title + Publisher` $\rightarrow$ `Title`.
- **Safe Execution Options**: Full support for `--dry-run`, `--headless` / `--no-headless`, `--json-output`, and `--limit`.

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

### Environment Variables (`.env`)

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Google Sheet URL or ID
GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit

# Babelio Credentials
BABELIO_USERNAME=your_email@example.com
BABELIO_PASSWORD=your_babelio_password
```

---

## CLI Usage (`babelio-cli`)

### 1. List & Filter Babelio Library Books (`babelio-books`)

Display books in your Babelio library filtered by shelf status, possession, or rating:

```bash
# List books that are NOT possessed (custom client-side filter)
uv run babelio-cli babelio-books --status non-possedes --limit 20

# List unowned books on your "To Read" shelf
uv run babelio-cli babelio-books --status a-lire --non-possedes

# List books on your "Pense-bête" shelf
uv run babelio-cli babelio-books --status pense-bete

# List 5-star rated books with JSON output
uv run babelio-cli babelio-books --rating 5 --json-output
```

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
babelio-cli babelio-books --status non-possedes
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

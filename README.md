# Babelio Automation

A CLI tool for synchronizing personal book libraries from Google Sheets to [Babelio](https://www.babelio.com/). Since Babelio does not offer a public API, this project uses **Playwright** browser automation alongside the **`gog` CLI** for Google Sheets API integration.

---

## Key Features

- **Automated Authentication**: Log in securely to Babelio with automated cookie consent (SFBX iframe) handling and session persistence (`.babelio_state.json`).
- **Google Sheets Integration via `gog`**: Uses the `gog` CLI (`/usr/local/bin/gog`) for reading and updating Google Sheets without requiring Google Service Account JSON keys.
- **Multi-Stage Book Search**: Intelligent fallback search strategy: `ISBN` $\rightarrow$ `Title + Author` $\rightarrow$ `Title + Publisher` $\rightarrow$ `Title`.
- **Status & Shelf Mapping**:
  - `Read` / `Lu` $\rightarrow$ Babelio Shelf **Lu** (`1`)
  - `To Read` / `À lire` / `Wish List` $\rightarrow$ Babelio Shelf **À lire** (`2`)
  - `Currently Reading` / `En cours` $\rightarrow$ Babelio Shelf **En cours** (`3`)
- **Duplication Prevention**: Skips books already present in your Babelio library.
- **Interactive Match Confirmation**: Prompts the user to confirm matches when running interactively.
- **Google Sheet Sync Update**: Automatically updates the `Babelio` column in your Google Sheet to `OUI` or `Maybe` after processing.
- **Safe Execution Options**: Full support for `--dry-run`, `--headless` / `--no-headless`, and `--limit`.

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

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Install Playwright Browsers**:
   ```bash
   uv run playwright install chromium
   ```

---

## Configuration

### 1. Environment Variables (`.env`)

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

### 2. Google CLI (`gog`) Authentication

Make sure `gog` is authenticated for Google Drive & Sheets on your system:

```bash
# Add your Google Account to gog
gog auth add your_google_account@example.com
```

To verify auth status:
```bash
gog auth list
```

---

## Google Sheet Expected Structure

The tool expects the Google Sheet (`Sheet1`) to contain headers on the first row with the following column structure:

| Row Index | Column Name | Description |
|---|---|---|
| `0` | `Title` | Book title |
| `5` | `Author` | Author name |
| `7` | `Publisher` | Publisher name |
| `8` | `Status` | Reading status (`Read`, `Lu`, `To Read`, `À lire`, `En cours`) |
| `9` | `ISBN` | Book ISBN-10 or ISBN-13 |
| `11` | `Babelio` | Sync status (`OUI`, `MAYBE`, or blank) |

*Rows where the `Babelio` column is already `OUI` or `MAYBE` will be skipped automatically.*

---

## CLI Usage

### Read & Preview Google Sheet Data
Test Google Sheets connection via `gog` and inspect the first few rows:

```bash
uv run python main.py read-books
```

### Synchronize Books to Babelio

#### Dry Run (Default / Safe Mode)
Simulates sync operations without making modifications to your Babelio account or Google Sheet:

```bash
uv run python main.py sync --limit 5 --dry-run
```

#### Live Sync (Interactive Mode)
Runs live automation with visible browser window so you can confirm book matches:

```bash
uv run python main.py sync --no-headless --no-dry-run
```

#### Headless Execution
Runs in the background without opening a browser window:

```bash
uv run python main.py sync --headless --no-dry-run
```

#### Command Options Reference

```bash
uv run python main.py sync --help
```

- `--sheet-url TEXT`: Overrides `GOOGLE_SHEET_URL` environment variable.
- `--account TEXT`: Specifies Google account email for `gog` CLI.
- `--username TEXT`: Overrides `BABELIO_USERNAME` environment variable.
- `--password TEXT`: Overrides `BABELIO_PASSWORD` environment variable.
- `--headless / --no-headless`: Run browser in headless mode (default: `--no-headless`).
- `--dry-run / --no-dry-run`: Enable/disable dry run mode (default: `--dry-run`).
- `--limit INTEGER`: Limit number of books to process in one run.

---

## Running Unit Tests

Run the `pytest` test suite:

```bash
uv run pytest
```

---

## Development & Code Quality

### Code Formatting & Linting
Code quality is enforced using `ruff`:

```bash
uv run ruff check .
```

### Pre-commit Hooks
Set up pre-commit hooks before committing:

```bash
uv run pre-commit install
```

---

## Project Structure

```
babelio-automation/
├── main.py                 # Click CLI commands entrypoint
├── babelio_api.py          # Playwright automation & Babelio sync bot
├── gog_client.py           # GogSheetsClient wrapper for gog CLI
├── tests/                  # Pytest unit test suite
│   ├── test_gog_client.py
│   └── test_babelio_api.py
├── pyproject.toml          # Dependencies and project config (uv)
├── uv.lock                 # Locked dependency tree
├── .env.example            # Template for environment variables
├── .pre-commit-config.yaml # Pre-commit linting configuration
└── README.md               # Project documentation
```

import json

import click
from dotenv import load_dotenv

from babelio_api import BabelioBot
from config import DEFAULT_TTL_SECONDS, load_config
from gog_client import GogSheetsClient

load_dotenv()
CFG = load_config()

STATUS_CHOICES = [
    "tous",
    "lus",
    "a-lire",
    "en-cours",
    "wishlist",
    "abandonnes",
    "possedes",
    "non-possedes",
    "critiques",
    "non-critiques",
]


@click.group()
def cli():
    """Babelio Automation Tool using gog CLI and Playwright."""
    pass


@cli.command()
@click.option(
    "--sheet-url",
    default=CFG.get("google_sheet_url") or None,
    help="URL or ID of the Google Sheet",
)
@click.option(
    "--account",
    default=CFG.get("gog_account") or None,
    help="Google Account email for gog CLI",
)
def read_books(sheet_url, account):
    """Read books list from Google Sheets via gog CLI"""
    if not sheet_url:
        click.echo(
            "Error: GOOGLE_SHEET_URL not set in config file, environment, or command line.",
            err=True,
        )
        return

    try:
        gog_client = GogSheetsClient(account=account)
        click.echo(f"Fetching data from sheet via gog CLI: {sheet_url}")
        values = gog_client.get_all_values(sheet_url)

        if not values:
            click.echo("Sheet is empty.")
            return

        click.echo(f"\nHeaders: {values[0]}")
        click.echo("\nFirst 5 rows:")
        for i, row in enumerate(values[1:6], 1):
            click.echo(f"Row {i}: {row}")

        click.echo(f"\nTotal rows found: {len(values) - 1}")

    except Exception as e:
        click.echo(f"An error occurred: {e}", err=True)


@cli.command()
@click.option(
    "--sheet-url",
    default=CFG.get("google_sheet_url") or None,
    help="URL or ID of the Google Sheet",
)
@click.option(
    "--account",
    default=CFG.get("gog_account") or None,
    help="Google Account email for gog CLI",
)
@click.option(
    "--username",
    default=CFG.get("babelio_username") or None,
    help="Babelio Username",
    required=True,
)
@click.option(
    "--password",
    default=CFG.get("babelio_password") or None,
    help="Babelio Password",
    required=True,
)
@click.option("--headless/--no-headless", default=False, help="Run browser in headless mode")
@click.option("--dry-run/--no-dry-run", default=True, help="Dry run (do not add to library)")
@click.option("--limit", type=int, default=None, help="Limit number of books to process")
def sync(sheet_url, account, username, password, headless, dry_run, limit):
    """Sync books from Google Sheets to Babelio"""
    if not sheet_url:
        click.echo("Error: GOOGLE_SHEET_URL not set in config file or environment.", err=True)
        return

    try:
        gog_client = GogSheetsClient(account=account)
        click.echo(f"Fetching sheet data via gog CLI: {sheet_url}")
        values = gog_client.get_all_values(sheet_url)

        if len(values) <= 1:
            click.echo("Sheet is empty or has only headers.")
            return

        books_data = values[1:]  # Skip header

        bot = BabelioBot(username, password, headless=headless)
        results = bot.run(books_data, sheet_url, gog_client, dry_run=dry_run, limit=limit)

        # Print Summary
        click.echo("\n" + "=" * 40)
        click.echo("EXECUTION SUMMARY")
        click.echo("=" * 40)

        click.echo(f"\nSuccessfully Added: {len(results['success'])}")
        for isbn, title in results["success"]:
            click.echo(f"  - {title} (ISBN: {isbn})")

        click.echo(f"\nSkipped (Already in Library): {len(results['skipped'])}")
        for isbn, title in results["skipped"]:
            click.echo(f"  - {title} (ISBN: {isbn})")

        click.echo(f"\nFailed / Not Found: {len(results['failed'])}")
        for item in results["failed"]:
            if len(item) == 3:
                isbn, title, reason = item
                click.echo(f"  - {title} (ISBN: {isbn}): {reason}")
            else:
                title, reason = item
                click.echo(f"  - {title}: {reason}")

        click.echo("=" * 40)

    except Exception as e:
        click.echo(f"An error occurred: {e}", err=True)


@cli.command("books")
@click.option(
    "--status",
    "-s",
    type=click.Choice(STATUS_CHOICES, case_sensitive=False),
    default="tous",
    help="Filter books by status (e.g. lus, a-lire, non-possedes, wishlist)",
)
@click.option(
    "--rating",
    "-r",
    type=click.IntRange(1, 5),
    default=None,
    help="Filter books by star rating (1 to 5)",
)
@click.option(
    "--limit",
    "-l",
    type=int,
    default=50,
    help="Maximum number of books to display (default: 50)",
)
@click.option(
    "--force-refresh",
    "-f",
    is_flag=True,
    default=False,
    help="Bypass local cache and force refresh from Babelio website",
)
@click.option(
    "--no-cache",
    "--bypass-cache",
    "no_cache",
    is_flag=True,
    default=False,
    help="Bypass book cache and query Babelio website directly",
)
@click.option(
    "--cache-ttl",
    type=int,
    default=CFG.get("cache_ttl_seconds", DEFAULT_TTL_SECONDS),
    help="Book cache time-to-live in seconds (default: 3600)",
)
@click.option(
    "--json-output",
    is_flag=True,
    default=False,
    help="Output results as JSON",
)
@click.option(
    "--username",
    default=CFG.get("babelio_username") or None,
    help="Babelio Username",
    required=True,
)
@click.option(
    "--password",
    default=CFG.get("babelio_password") or None,
    help="Babelio Password",
    required=True,
)
@click.option("--headless/--no-headless", default=True, help="Run browser in headless mode")
def books(
    status,
    rating,
    limit,
    force_refresh,
    no_cache,
    cache_ttl,
    json_output,
    username,
    password,
    headless,
):
    """List and filter books from your Babelio library (uses 1-hour local cache)"""
    try:
        bypass = force_refresh or no_cache
        bot = BabelioBot(username, password, headless=headless)
        if not json_output:
            click.echo(
                f"Fetching Babelio books (status='{status}', rating={rating}, "
                f"bypass_cache={bypass})..."
            )
        book_list = bot.fetch_library_books(
            status_filter=status,
            rating=rating,
            limit=limit,
            force_refresh=bypass,
            cache_ttl_seconds=cache_ttl,
        )

        if json_output:
            click.echo(json.dumps(book_list, indent=2, ensure_ascii=False))
            return

        click.echo("\n" + "=" * 60)
        click.echo(f"BABELIO BOOKS LIST ({len(book_list)} found)")
        click.echo("=" * 60)

        if not book_list:
            click.echo("No books match the specified filters.")
            return

        for idx, book in enumerate(book_list, 1):
            pos_str = "Possédé" if book["possessed"] else "Non possédé"
            click.echo(f"{idx:3d}. {book['title']} - {book['author']}")
            click.echo(f"     Status: {book['status']} | Possession: {pos_str}")
            click.echo(f"     URL: {book['url']}\n")

        click.echo("=" * 60)

    except Exception as e:
        click.echo(f"An error occurred: {e}", err=True)


@cli.command("mark-possessed")
@click.option(
    "--urls-file",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="Path to a JSON file containing a list of Babelio book URLs (or a list of "
    "objects with a 'url' field) to tag as 'Possédé'.",
)
@click.option("--dry-run/--no-dry-run", default=True, help="List URLs without modifying Babelio")
@click.option(
    "--username",
    default=CFG.get("babelio_username") or None,
    help="Babelio Username",
    required=True,
)
@click.option(
    "--password",
    default=CFG.get("babelio_password") or None,
    help="Babelio Password",
    required=True,
)
@click.option("--headless/--no-headless", default=True, help="Run browser in headless mode")
def mark_possessed(urls_file, dry_run, username, password, headless):
    """Add the 'Possédé' tag to books already in your Babelio library."""
    with open(urls_file, encoding="utf-8") as f:
        raw = json.load(f)

    urls = [item["url"] if isinstance(item, dict) else item for item in raw]

    if not urls:
        click.echo("No URLs found in file.")
        return

    click.echo(f"Loaded {len(urls)} book URL(s) from {urls_file}.")

    if dry_run:
        click.echo("DRY RUN: would mark the following URLs as 'Possédé':")
        for url in urls:
            click.echo(f"  - {url}")
        return

    bot = BabelioBot(username, password, headless=headless)
    results = bot.mark_possessed(urls)

    click.echo("\n" + "=" * 40)
    click.echo("MARK POSSESSED SUMMARY")
    click.echo("=" * 40)
    click.echo(f"\nMarked 'Possédé': {len(results['success'])}")
    for url in results["success"]:
        click.echo(f"  - {url}")
    click.echo(f"\nAlready 'Possédé': {len(results['already'])}")
    for url in results["already"]:
        click.echo(f"  - {url}")
    click.echo(f"\nFailed: {len(results['failed'])}")
    for url, reason in results["failed"]:
        click.echo(f"  - {url}: {reason}")
    click.echo("=" * 40)


@cli.command("show-config")
def show_config():
    """Show active configuration file values and paths."""
    cfg = load_config()
    click.echo("\n" + "=" * 50)
    click.echo("BABELIO AUTOMATION CONFIGURATION")
    click.echo("=" * 50)

    pass_val = cfg.get("babelio_password", "")
    masked_pass = "*" * len(pass_val) if pass_val else "<NOT SET>"

    click.echo("Config Directory:  ~/.config/babelio-automation/")
    click.echo("Config File:       ~/.config/babelio-automation/config.json")
    click.echo("Cache File:        ~/.config/babelio-automation/books_cache.json")
    click.echo("Session State:     ~/.config/babelio-automation/session_state.json")
    click.echo("-" * 50)
    click.echo(f"Babelio Username:  {cfg.get('babelio_username') or '<NOT SET>'}")
    click.echo(f"Babelio Password:  {masked_pass}")
    click.echo(f"Google Sheet URL:  {cfg.get('google_sheet_url') or '<NOT SET>'}")
    click.echo(f"Gog Account:       {cfg.get('gog_account') or '<DEFAULT>'}")
    ttl = cfg.get("cache_ttl_seconds", DEFAULT_TTL_SECONDS)
    click.echo(f"Cache TTL Seconds: {ttl} seconds ({ttl // 60} mins)")
    click.echo("=" * 50)


if __name__ == "__main__":
    cli()

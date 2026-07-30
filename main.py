import json

import click
from dotenv import load_dotenv

from babelio_api import BabelioBot
from gog_client import GogSheetsClient

load_dotenv()

STATUS_CHOICES = [
    "tous",
    "lus",
    "a-lire",
    "en-cours",
    "pense-bete",
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
@click.option("--sheet-url", envvar="GOOGLE_SHEET_URL", help="URL or ID of the Google Sheet")
@click.option(
    "--account", envvar="GOG_ACCOUNT", help="Google Account email for gog CLI", default=None
)
def read_books(sheet_url, account):
    """Read books list from Google Sheets via gog CLI"""
    if not sheet_url:
        click.echo("Error: GOOGLE_SHEET_URL not set in environment or command line.", err=True)
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
@click.option("--sheet-url", envvar="GOOGLE_SHEET_URL", help="URL or ID of the Google Sheet")
@click.option(
    "--account", envvar="GOG_ACCOUNT", help="Google Account email for gog CLI", default=None
)
@click.option("--username", envvar="BABELIO_USERNAME", help="Babelio Username", required=True)
@click.option("--password", envvar="BABELIO_PASSWORD", help="Babelio Password", required=True)
@click.option("--headless/--no-headless", default=False, help="Run browser in headless mode")
@click.option("--dry-run/--no-dry-run", default=True, help="Dry run (do not add to library)")
@click.option("--limit", type=int, default=None, help="Limit number of books to process")
def sync(sheet_url, account, username, password, headless, dry_run, limit):
    """Sync books from Google Sheets to Babelio"""
    if not sheet_url:
        click.echo("Error: GOOGLE_SHEET_URL not set.", err=True)
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
    help="Filter books by status (e.g. lus, a-lire, non-possedes, pense-bete)",
)
@click.option(
    "--non-possedes",
    is_flag=True,
    default=False,
    help="Filter out books marked as possessed (can be combined with any status)",
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
    "--json-output",
    is_flag=True,
    default=False,
    help="Output results as JSON",
)
@click.option("--username", envvar="BABELIO_USERNAME", help="Babelio Username", required=True)
@click.option("--password", envvar="BABELIO_PASSWORD", help="Babelio Password", required=True)
@click.option("--headless/--no-headless", default=True, help="Run browser in headless mode")
def books(status, non_possedes, rating, limit, json_output, username, password, headless):
    """List and filter books from your Babelio library"""
    try:
        bot = BabelioBot(username, password, headless=headless)
        click.echo(
            f"Fetching Babelio books (status='{status}', rating={rating}, "
            f"non_possedes={non_possedes})..."
        )
        book_list = bot.fetch_library_books(
            status_filter=status,
            rating=rating,
            limit=limit,
            non_possedes_only=non_possedes,
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


if __name__ == "__main__":
    cli()

import click
import gspread
from dotenv import load_dotenv

from babelio_api import BabelioBot

load_dotenv()


@click.group()
def cli():
    """Babelio Automation Tool"""
    pass


@cli.command()
@click.option("--sheet-url", envvar="GOOGLE_SHEET_URL", help="URL of the Google Sheet")
def read_books(sheet_url):
    """Read books list from Google Sheets"""
    if not sheet_url:
        click.echo("Error: GOOGLE_SHEET_URL not set in environment or command line.", err=True)
        return

    try:
        # Assuming you will set up a service account and download the JSON key
        # Default behavior of gspread looks for ~/.config/gspread/service_account.json
        # Information: https://docs.gspread.org/en/latest/oauth2.html#for-bots-using-service-account
        gc = gspread.service_account()
        click.echo(f"Opening sheet: {sheet_url}")
        sh = gc.open_by_url(sheet_url)
        worksheet = sh.sheet1

        # Read the first few rows just to test
        click.echo("Fetching data...")
        values = worksheet.get_all_values()

        if not values:
            click.echo("Sheet is empty.")
            return

        # Print headers
        click.echo(f"\nHeaders: {values[0]}")

        # Print first few rows
        click.echo("\nFirst 5 rows:")
        for i, row in enumerate(values[1:6], 1):
            click.echo(f"Row {i}: {row}")

        click.echo(f"\nTotal rows found: {len(values) - 1}")  # exclude header

    except Exception as e:
        click.echo(f"An error occurred: {e}", err=True)


@cli.command()
@click.option("--sheet-url", envvar="GOOGLE_SHEET_URL", help="URL of the Google Sheet")
@click.option("--username", envvar="BABELIO_USERNAME", help="Babelio Username", required=True)
@click.option("--password", envvar="BABELIO_PASSWORD", help="Babelio Password", required=True)
@click.option("--headless/--no-headless", default=False, help="Run browser in headless mode")
@click.option("--dry-run/--no-dry-run", default=True, help="Dry run (do not add to library)")
@click.option("--limit", type=int, default=None, help="Limit number of books to process")
def sync(sheet_url, username, password, headless, dry_run, limit):
    """Sync books from Google Sheets to Babelio"""
    if not sheet_url:
        click.echo("Error: GOOGLE_SHEET_URL not set.", err=True)
        return

    try:
        gc = gspread.service_account()
        click.echo(f"Opening sheet: {sheet_url}")
        sh = gc.open_by_url(sheet_url)
        worksheet = sh.sheet1

        click.echo("Fetching data...")
        values = worksheet.get_all_values()

        if len(values) <= 1:
            click.echo("Sheet is empty or has only headers.")
            return

        books_data = values[1:]  # Skip header

        bot = BabelioBot(username, password, headless=headless)
        results = bot.run(books_data, worksheet, dry_run=dry_run, limit=limit)

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
            # Not all items might have isbn if they failed early
            if len(item) == 3:
                isbn, title, reason = item
                click.echo(f"  - {title} (ISBN: {isbn}): {reason}")
            else:
                title, reason = item
                click.echo(f"  - {title}: {reason}")

        click.echo("=" * 40)

    except Exception as e:
        click.echo(f"An error occurred: {e}", err=True)


if __name__ == "__main__":
    cli()

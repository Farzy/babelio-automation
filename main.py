import os
import click
import gspread
from dotenv import load_dotenv

load_dotenv()

@click.group()
def cli():
    """Babelio Automation Tool"""
    pass

@cli.command()
@click.option('--sheet-url', envvar='GOOGLE_SHEET_URL', help='URL of the Google Sheet')
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
             
        click.echo(f"\nTotal rows found: {len(values) - 1}") # exclude header
        
    except Exception as e:
        click.echo(f"An error occurred: {e}", err=True)

if __name__ == '__main__':
    cli()

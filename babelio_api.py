import html
import os
import time

import click
from playwright.sync_api import TimeoutError, sync_playwright

from gog_client import GogSheetsClient

STATE_FILE = ".babelio_state.json"


class BabelioBot:
    def __init__(self, username: str, password: str, headless: bool = False):
        self.username = username
        self.password = password
        self.headless = headless

    def run(
        self,
        books_data: list[list[str]],
        sheet_url: str,
        gog_client: GogSheetsClient,
        dry_run: bool = True,
        limit: int | None = None,
    ) -> dict[str, list]:
        """Run Babelio synchronization for books data extracted from Google Sheets."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            user_agent = (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )

            context_options = {
                "user_agent": user_agent,
                "locale": "fr-FR",
                "timezone_id": "Europe/Paris",
            }
            if os.path.exists(STATE_FILE):
                context_options["storage_state"] = STATE_FILE

            context = browser.new_context(**context_options)
            page = context.new_page()

            click.echo("Logging into Babelio...")
            self._login(context, page)

            count = 0
            results: dict[str, list] = {"success": [], "skipped": [], "failed": []}

            for index, row in enumerate(books_data):
                if limit and count >= limit:
                    break

                try:
                    title = html.unescape(row[0])
                    author = html.unescape(row[5]) if len(row) > 5 else ""
                    publisher = html.unescape(row[7]) if len(row) > 7 else ""
                    status_raw = row[8] if len(row) > 8 else ""
                    isbn = row[9] if len(row) > 9 else ""
                    babelio_synced = row[11].strip().upper() if len(row) > 11 else ""
                except IndexError:
                    continue

                if title.lower() == "title" and isbn.lower() == "isbn":
                    continue

                sheet_row_num = index + 2

                if babelio_synced in ["OUI", "MAYBE"]:
                    continue

                click.echo(f"\nProcessing: {title} (ISBN: {isbn})")

                try:
                    success, reason = self._process_book(
                        page, isbn, title, author, publisher, status_raw, dry_run
                    )
                    if success:
                        if reason == "Already in library":
                            results["skipped"].append((isbn, title))
                            if not dry_run and gog_client:
                                self._update_sheet(gog_client, sheet_url, sheet_row_num, "OUI")
                        else:
                            results["success"].append((isbn, title))
                            if not dry_run and gog_client:
                                self._update_sheet(gog_client, sheet_url, sheet_row_num, "Maybe")
                    else:
                        results["failed"].append((isbn, title, reason))
                except Exception as e:
                    click.echo(f"[{title}] Error processing: {e}")
                    results["failed"].append((isbn, title, str(e)))

                count += 1
                time.sleep(2)

            browser.close()
            return results

    def _update_sheet(
        self, gog_client: GogSheetsClient, sheet_url: str, row_num: int, value: str
    ) -> None:
        """Update column 'L' (index 12) in Google Sheet using gog CLI."""
        gog_client.update_cell(sheet_url, row_num, 12, value)

    def _login(self, context, page) -> None:
        """Check session validity or authenticate with Babelio."""
        click.echo("Checking session validity...")
        page.goto("https://www.babelio.com/actualites.php", wait_until="domcontentloaded")

        if ("actualites.php" in page.url or "monprofil.php" in page.url) and page.locator(
            "a[href*='mes_livres.php']"
        ).first.is_visible():
            click.echo("Already logged in via saved session state.")
            return

        click.echo("Session expired or missing. Logging in...")
        page.goto("https://www.babelio.com/connection.php")

        try:
            click.echo("Waiting for potential cookies banner...")
            btn_selectors = (
                'button.app-agree-button, button:has-text("Tout Accepter"), '
                'button:has-text("Tout accepter"), button:has-text("Accepter tout")'
            )
            iframe_selector = (
                'iframe[title="Consent Manager"], '
                'iframe[title="Consent window"], '
                'iframe[title="Fenêtre de consentement"], '
                'iframe[src*="sfbx"]'
            )

            consent_frame = page.frame_locator(iframe_selector)
            accept_btn = consent_frame.locator(btn_selectors).first
            accept_btn.click(force=True, timeout=10000)
            click.echo("Cookies banner accepted.")
            time.sleep(2)
        except Exception:
            click.echo("No cookies banner found or timed out. Proceeding to login.")

        page.wait_for_selector("input[name='Login' i]", state="visible", timeout=10000)
        page.fill("input[name='Login' i]", self.username)
        page.fill("input[name='Password' i]", self.password)
        page.click("input[name='sub_btn'], input[type='submit'][value*='onnexion' i]")

        try:
            page.wait_for_function("window.location.pathname !== '/connection.php'", timeout=10000)
            page.wait_for_load_state("domcontentloaded")
            click.echo("Successfully logged in.")
            context.storage_state(path=STATE_FILE)
            click.echo("Session state saved.")
        except TimeoutError as err:
            page.screenshot(path="login_timeout.png")
            err_msg = "Failed to login to Babelio. Check credentials or CAPTCHA presence."
            raise Exception(err_msg) from err

    def _process_book(
        self,
        page,
        isbn: str,
        title: str,
        author: str,
        publisher: str,
        status_raw: str,
        dry_run: bool,
    ) -> tuple[bool, str]:
        """Search and add book to Babelio library."""
        search_queries = []
        if isbn:
            search_queries.append(isbn)
        if title and author:
            search_queries.append(f"{title} {author}")
        if title and publisher and not publisher.strip().isdigit():
            search_queries.append(f"{title} {publisher}")
        if title:
            search_queries.append(title)

        seen = set()
        search_queries = [q for q in search_queries if not (q in seen or seen.add(q))]

        found = False
        for query in search_queries:
            page.goto("https://www.babelio.com/", wait_until="domcontentloaded")
            search_selector = "input#searchbox, input#recherche_general"

            page.wait_for_selector(search_selector, state="visible", timeout=10000)
            page.fill(search_selector, query)
            page.press(search_selector, "Enter")

            try:
                page.wait_for_selector(".livre_top, .list_livre", timeout=8000)
                if "/resrecherche.php" in page.url:
                    links = page.locator(".list_livre a.titre_v2").all()
                    if not links:
                        continue
                    links[0].click()
                    page.wait_for_selector(".livre_top", timeout=8000)

                found = True
                break
            except TimeoutError:
                continue

        if not found:
            click.echo(f"[{title}] Not found on Babelio after trying queries: {search_queries}")
            return False, "Not Found"

        try:
            b_title_loc = page.locator('h1[itemprop="name"]')
            babelio_title = (
                b_title_loc.inner_text(timeout=2000).strip()
                if b_title_loc.is_visible()
                else "Unknown Title"
            )

            b_author_loc = page.locator('span[itemprop="author"]')
            babelio_author = (
                b_author_loc.inner_text(timeout=2000).strip()
                if b_author_loc.is_visible()
                else "Unknown Author"
            )
        except Exception:
            babelio_title, babelio_author = "Unknown Title", "Unknown Author"

        click.echo("\n--- Found Match on Babelio ---")
        click.echo(f"Original: {title} (ISBN: {isbn}) by {author}")
        click.echo(f"Found:    {babelio_title} by {babelio_author}")
        click.echo(f"URL:      {page.url}")
        click.echo("------------------------------")

        if not click.confirm(f"Add '{babelio_title}' to your library?", default=True):
            click.echo(f"[{title}] Skipped by user.")
            return False, "User skipped"

        add_btn = page.locator("#btn_ajout_biblio, .btn_ajout_biblio")
        if not add_btn.is_visible():
            add_btn = page.locator("a[href*='mes_livres']")

        if add_btn.is_visible():
            add_btn_text = add_btn.inner_text().strip()
            if "Lu" in add_btn_text or "lire" in add_btn_text or "En cours" in add_btn_text:
                click.echo(f"[{title}] Already in library ({add_btn_text}). Skipping.")
                return True, "Already in library"

        shelf = self._map_status(status_raw)

        if dry_run:
            click.echo(f"[{title}] DRY RUN: Would add to library with status '{shelf}'.")
            return True, "Added (Dry Run)"

        add_btn.click()
        try:
            page.wait_for_selector("#id_status", timeout=5000)
        except TimeoutError:
            click.echo(f"[{title}] Could not open add to library modal. Skipping.")
            return False, "Modal Error"

        status_val = (
            "1"
            if shelf == "Lu"
            else "2"
            if shelf == "À lire"
            else "3"
            if shelf == "En cours"
            else "1"
        )
        page.select_option("#id_status", status_val)
        page.click("#btn_ajout_livre_valider")
        time.sleep(1)
        click.echo(f"[{title}] Added to library with status '{shelf}'.")
        return True, "Added"

    def _map_status(self, status: str) -> str:
        """Map Google Sheet status string to Babelio shelf name."""
        status = status.strip().lower()
        if status in ["read", "lu"]:
            return "Lu"
        elif status in ["to read", "à lire", "wish list"]:
            return "À lire"
        elif status in ["currently reading", "en cours"]:
            return "En cours"
        return "Lu"

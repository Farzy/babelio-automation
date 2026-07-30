import html
import os
import time

import click
from playwright.sync_api import TimeoutError, sync_playwright

from gog_client import GogSheetsClient


def get_state_file_path() -> str:
    """Get the absolute path for persistent session state storage."""
    try:
        config_dir = os.path.expanduser("~/.config/babelio-automation")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "session_state.json")
    except Exception:
        return ".babelio_state.json"


class BabelioBot:
    def __init__(self, username: str, password: str, headless: bool = False):
        self.username = username
        self.password = password
        self.headless = headless
        self.state_file = get_state_file_path()

    def _build_library_url(self, status: str, rating: int | None = None) -> str:
        """Build the mabibliotheque.php URL based on status and rating filters."""
        base_url = "https://www.babelio.com/mabibliotheque.php"
        params = []

        status_norm = status.strip().lower().replace("_", "-").replace(" ", "-")

        if status_norm in ["lus", "lu", "read"]:
            params.append("s1=1")
        elif status_norm in ["a-lire", "à-lire", "to-read"]:
            params.append("s1=2")
        elif status_norm in ["en-cours", "currently-reading"]:
            params.append("s1=0")
        elif status_norm in ["pense-bete", "pense-bête", "bookmark"]:
            params.append("s1=3")
        elif status_norm in ["abandonnes", "abandonnés", "abandoned"]:
            params.append("s1=4")
        elif status_norm in ["possedes", "possédés", "owned"]:
            params.append("s1=5")
        elif status_norm in ["critiques", "critiqués", "reviewed"]:
            params.append("s3=10")
        elif status_norm in ["non-critiques", "non-critiqués", "unreviewed"]:
            params.append("s3=11")

        if rating in [1, 2, 3, 4, 5]:
            params.append(f"note={rating}")

        if params:
            return f"{base_url}?{'&'.join(params)}"
        return base_url

    def fetch_library_books(
        self,
        status_filter: str = "tous",
        rating: int | None = None,
        limit: int = 50,
        non_possedes_only: bool = False,
    ) -> list[dict[str, str | bool]]:
        """Fetch user library books from Babelio with status/possession filters."""
        base_url = self._build_library_url(status_filter, rating)
        books: list[dict[str, str | bool]] = []
        filter_non_possedes = non_possedes_only or (
            status_filter.strip().lower().replace("_", "-") == "non-possedes"
        )

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
            if os.path.exists(self.state_file):
                context_options["storage_state"] = self.state_file

            context = browser.new_context(**context_options)
            page = context.new_page()

            self._login(context, page)

            page_num = 1
            max_pages = 100

            while len(books) < limit and page_num <= max_pages:
                sep = "&" if "?" in base_url else "?"
                page_url = f"{base_url}{sep}pageN={page_num}"
                click.echo(f"Fetching Babelio library page {page_num}...")
                page.goto(page_url, wait_until="domcontentloaded")
                time.sleep(1.5)

                rows = page.locator("tr:has(a[href*='/livres/'])").all()
                if not rows:
                    rows = page.locator(
                        "tr[id*='ligne_'], tr[id*='livre_'], table.mes_livres_table tr"
                    ).all()

                if not rows:
                    break

                for row in rows:
                    if len(books) >= limit:
                        break

                    row_text = row.inner_text().strip()
                    if not row_text or "TITRE | PARU EN" in row_text:
                        continue

                    title_links = row.locator("a[href*='/livres/']").all()
                    title = ""
                    book_url = ""
                    for t_link in title_links:
                        txt = t_link.inner_text().strip()
                        if (
                            txt
                            and not txt.startswith("http")
                            and "critique" not in txt.lower()
                            and "citation" not in txt.lower()
                        ):
                            title = txt
                            book_url = t_link.get_attribute("href") or ""
                            break

                    if not title:
                        continue

                    if book_url.startswith("/"):
                        book_url = f"https://www.babelio.com{book_url}"

                    author_link = row.locator("a[href*='/auteur/']").first
                    author = author_link.inner_text().strip() if author_link.count() > 0 else ""

                    is_possessed = "Possédé" in row_text or "possede" in row_text.lower()

                    if filter_non_possedes and is_possessed:
                        continue

                    reading_status = "Inconnu"
                    for st in ["Lu", "À lire", "En cours", "Pense-bête", "Abandonné"]:
                        if st in row_text:
                            reading_status = st
                            break

                    books.append(
                        {
                            "title": title,
                            "author": author,
                            "status": reading_status,
                            "possessed": is_possessed,
                            "url": book_url,
                        }
                    )

                next_page_link = page.locator(f"a[href*='pageN={page_num + 1}']").first
                if next_page_link.count() == 0:
                    break

                page_num += 1

            browser.close()
            return books

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
            if os.path.exists(self.state_file):
                context_options["storage_state"] = self.state_file

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

        if "connection.php" not in page.url and (
            page.locator("input#hid_user").count() > 0
            or page.locator("a[href*='closeSession=1']").count() > 0
        ):
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
        page.click("input[name='sub_btn'], input[type='submit'][value*='onnexion' i]", force=True)

        try:
            page.wait_for_function("window.location.pathname !== '/connection.php'", timeout=10000)
            page.wait_for_load_state("domcontentloaded")
            click.echo("Successfully logged in.")
            context.storage_state(path=self.state_file)
            click.echo(f"Session state saved to {self.state_file}.")
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

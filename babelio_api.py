import html
import os
import time
from typing import Any

import click
from playwright.sync_api import Browser, BrowserContext, TimeoutError, sync_playwright

from babelio_parsers import (
    has_next_library_page,
    parse_book_header,
    parse_library_page,
    parse_search_results,
)
from config import DEFAULT_TTL_SECONDS, get_state_file_path, load_books_cache, save_books_cache
from gog_client import GogSheetsClient

#: User agent sent by every browser context.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

#: Label of the book page button while the book is not yet in the user's library.
ADD_TO_LIBRARY_LABEL = "Ajouter à mes livres"


class BabelioBot:
    def __init__(self, username: str, password: str, headless: bool = False):
        self.username = username
        self.password = password
        self.headless = headless
        self.state_file = get_state_file_path()

    def _new_context(self, browser: Browser) -> BrowserContext:
        """Create a French-locale browser context, reusing the saved session if any."""
        return browser.new_context(
            user_agent=USER_AGENT,
            locale="fr-FR",
            timezone_id="Europe/Paris",
            storage_state=self.state_file if os.path.exists(self.state_file) else None,
        )

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
        elif status_norm in ["wishlist"]:
            params.append("s1=3")
        elif status_norm in ["abandonnes", "abandonnés", "abandoned"]:
            params.append("s1=4")
        elif status_norm in ["possedes", "possédés", "owned"]:
            params.append("possede=1")
        elif status_norm in ["critiques", "critiqués", "reviewed"]:
            params.append("critique=reviewed")
        elif status_norm in ["non-critiques", "non-critiqués", "unreviewed"]:
            params.append("critique=notreviewed")

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
        force_refresh: bool = False,
        cache_ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> list[dict[str, Any]]:
        """Fetch user library books with local caching and status/possession filters."""
        all_books: list[dict[str, Any]] | None = None

        if not force_refresh:
            all_books = load_books_cache(cache_ttl_seconds)
            if all_books is not None:
                click.echo(
                    f"[Cache HIT] Loaded {len(all_books)} books from local cache. "
                    "Use --force-refresh to update."
                )

        if all_books is None:
            click.echo("[Cache MISS/Refresh] Fetching book library from Babelio...")
            all_books = self._scrape_all_library_books()
            save_books_cache(all_books)
            click.echo(f"Cached {len(all_books)} books to local cache.")

        # Apply in-memory filtering
        status_norm = status_filter.strip().lower().replace("_", "-").replace(" ", "-")

        filtered_books = []
        for book in all_books:
            b_status = str(book.get("status", "")).strip()
            is_pos = bool(book.get("possessed", False))
            b_rating = book.get("rating")

            # Filter by rating if specified
            if rating in [1, 2, 3, 4, 5] and b_rating != rating:
                continue

            # Filter by reading status / shelf
            if status_norm in ["lus", "lu", "read"] and b_status != "Lu":
                continue
            if status_norm in ["a-lire", "à-lire", "to-read"] and b_status != "À lire":
                continue
            if status_norm in ["en-cours", "currently-reading"] and b_status != "En cours":
                continue
            if status_norm in ["wishlist"] and b_status != "Wishlist":
                continue
            if status_norm in ["abandonnes", "abandonnés", "abandoned"] and b_status != "Abandonné":
                continue
            if status_norm in ["possedes", "possédés", "owned"] and not is_pos:
                continue

            if status_norm in ["critiques", "critiqués", "reviewed"] and not book.get("reviewed"):
                continue
            if status_norm in ["non-critiques", "non-critiqués", "unreviewed"] and book.get(
                "reviewed"
            ):
                continue

            # "non-possedes" means books I could own but do not: wishlist
            # entries are not mine yet, so they are excluded as well.
            if status_norm == "non-possedes" and (is_pos or b_status == "Wishlist"):
                continue

            filtered_books.append(book)

        return filtered_books[:limit]

    def _scrape_all_library_books(self) -> list[dict[str, Any]]:
        """Scrape all pages of user library from Babelio."""
        base_url = "https://www.babelio.com/mabibliotheque.php"
        all_books: list[dict[str, Any]] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = self._new_context(browser)
            page = context.new_page()

            self._login(context, page)

            max_pages = 200

            # The unfiltered view ("Tous") leaves out the Wishlist shelf, so scrape it too.
            for shelf_query in ("", "s1=3&"):
                page_num = 1
                while page_num <= max_pages:
                    page_url = f"{base_url}?{shelf_query}pageN={page_num}"
                    click.echo(f"Scraping Babelio library page {page_num} ({page_url})...")
                    page.goto(page_url, wait_until="domcontentloaded")
                    time.sleep(1.5)

                    html_content = page.content()
                    page_books = parse_library_page(html_content)
                    if not page_books:
                        break
                    all_books.extend(page_books)

                    if not has_next_library_page(html_content):
                        break

                    page_num += 1

            browser.close()
            return all_books

    def mark_possessed(self, urls: list[str]) -> dict[str, list]:
        """Add the 'Possédé' tag to each book at the given Babelio URLs.

        Each URL must be a book already present in the user's library (the
        'Possédé' checkbox only exists in the per-book status dropdown once
        a book has been added to a shelf). Books already tagged 'Possédé'
        are reported under 'already' rather than re-clicked.
        """
        results: dict[str, list] = {"success": [], "already": [], "failed": []}

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = self._new_context(browser)
            page = context.new_page()
            self._login(context, page)

            for url in urls:
                try:
                    page.goto(url, wait_until="domcontentloaded")
                    # The "Gérer ce livre" panel is loaded asynchronously (htmx).
                    page.wait_for_selector("#ma-lecture .lib-edit-form", timeout=10000)

                    # Lazy locator: it re-queries the panel after htmx refreshes it.
                    possede_chk = page.locator("#lib-f-flags label", has_text="Possédé").locator(
                        "input[type='checkbox']"
                    )
                    if possede_chk.is_checked():
                        click.echo(f"[{url}] Already marked 'Possédé'. Skipping.")
                        results["already"].append(url)
                        continue

                    with page.expect_response(
                        lambda r: "mabibliotheque.php" in r.url and r.request.method == "POST",
                        timeout=10000,
                    ):
                        possede_chk.check(no_wait_after=True)
                    page.wait_for_selector("#ma-lecture .lib-edit-form", timeout=5000)

                    if possede_chk.is_checked():
                        click.echo(f"[{url}] Marked 'Possédé'.")
                        results["success"].append(url)
                    else:
                        click.echo(f"[{url}] Checkbox did not update as expected.")
                        results["failed"].append((url, "Checkbox state did not update"))
                except Exception as e:
                    click.echo(f"[{url}] Error: {e}")
                    results["failed"].append((url, str(e)))

                time.sleep(1.5)

            browser.close()
            return results

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
            context = self._new_context(browser)
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
        page.click("form.auth-form button[name='sub_btn']", force=True)

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

        search_queries = list(dict.fromkeys(search_queries))

        found = False
        for query in search_queries:
            page.goto("https://www.babelio.com/", wait_until="domcontentloaded")
            search_selector = "#header-search-input"

            page.wait_for_selector(search_selector, state="visible", timeout=10000)
            page.fill(search_selector, query)
            page.press(search_selector, "Enter")

            try:
                page.wait_for_url("**/recherche.php*", timeout=8000)
                page.wait_for_selector(".rs-section", timeout=8000)
                results = parse_search_results(page.content())
                if not results:
                    continue
                page.goto(str(results[0]["url"]), wait_until="domcontentloaded")
                page.wait_for_selector("h1.book-title", timeout=8000)

                found = True
                break
            except TimeoutError:
                continue

        if not found:
            click.echo(f"[{title}] Not found on Babelio after trying queries: {search_queries}")
            return False, "Not Found"

        babelio_title, babelio_author = parse_book_header(page.content())
        babelio_title = babelio_title or "Unknown Title"
        babelio_author = babelio_author or "Unknown Author"

        click.echo("\n--- Found Match on Babelio ---")
        click.echo(f"Original: {title} (ISBN: {isbn}) by {author}")
        click.echo(f"Found:    {babelio_title} by {babelio_author}")
        click.echo(f"URL:      {page.url}")
        click.echo("------------------------------")

        if not click.confirm(f"Add '{babelio_title}' to your library?", default=True):
            click.echo(f"[{title}] Skipped by user.")
            return False, "User skipped"

        library_label = page.locator("#hcta-library-label").inner_text().strip()
        if library_label != ADD_TO_LIBRARY_LABEL:
            click.echo(f"[{title}] Already in library ({library_label}). Skipping.")
            return True, "Already in library"

        shelf = self._map_status(status_raw)

        if dry_run:
            click.echo(f"[{title}] DRY RUN: Would add to library with status '{shelf}'.")
            return True, "Added (Dry Run)"

        page.click("#hcta-library-btn")
        try:
            with page.expect_response(
                lambda r: "mabibliotheque.php" in r.url and r.request.method == "POST",
                timeout=10000,
            ):
                page.locator("#hcta-library-menu button.hcta-menu-item").get_by_text(
                    shelf, exact=True
                ).click()
            page.wait_for_selector("#ma-lecture .lib-edit-form", timeout=5000)
        except TimeoutError:
            click.echo(f"[{title}] Could not add the book to the library. Skipping.")
            return False, "Add Error"

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

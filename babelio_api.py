import time

import click
from playwright.sync_api import TimeoutError, sync_playwright


class BabelioBot:
    def __init__(self, username, password, headless=False):
        self.username = username
        self.password = password
        self.headless = headless

    def run(self, books_data, worksheet, dry_run=True, limit=None):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            user_agent = (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
            context = browser.new_context(
                user_agent=user_agent, locale="fr-FR", timezone_id="Europe/Paris"
            )
            page = context.new_page()

            click.echo("Logging into Babelio...")
            self._login(page)

            count = 0
            results = {"success": [], "skipped": [], "failed": []}

            for index, row in enumerate(books_data):
                if limit and count >= limit:
                    break

                # Assuming row format based on headers print:
                # [0] Title, [5] Author, [7] Publisher, [8] Status, [9] ISBN, [11] Babelio
                try:
                    title = row[0]
                    author = row[5] if len(row) > 5 else ""
                    publisher = row[7] if len(row) > 7 else ""
                    status_raw = row[8]
                    isbn = row[9]
                    babelio_synced = row[11].strip().upper()
                except IndexError:
                    continue  # Malformed row

                # Skip header row if present
                if title.lower() == "title" and isbn.lower() == "isbn":
                    continue

                sheet_row_num = index + 2  # Google Sheet rows are 1-based, and +1 for header

                if babelio_synced in ["OUI", "MAYBE"]:
                    continue  # Already synced or marked as maybe

                click.echo(f"\nProcessing: {title} (ISBN: {isbn})")

                try:
                    success, reason = self._process_book(
                        page, isbn, title, author, publisher, status_raw, dry_run
                    )
                    if success:
                        if reason == "Already in library":
                            results["skipped"].append((isbn, title))
                            # Update Google Sheet anyway so we don't process it again
                            if not dry_run:
                                self._update_sheet(worksheet, sheet_row_num, "OUI")
                        else:
                            results["success"].append((isbn, title))
                            if not dry_run:
                                self._update_sheet(worksheet, sheet_row_num, "Maybe")
                    else:
                        results["failed"].append((isbn, title, reason))
                except Exception as e:
                    click.echo(f"[{title}] Error processing: {e}")
                    results["failed"].append((isbn, title, str(e)))

                count += 1
                time.sleep(2)  # Grace period

            browser.close()
            return results

    def _update_sheet(self, worksheet, row_num, value):
        # Column 'L' is index 12 in 1-based (Babelio column)
        worksheet.update_cell(row_num, 12, value)

    def _login(self, page):
        page.goto("https://www.babelio.com/connection.php")

        # Handle Cookies Banner (SFBX Consent Manager iframe)
        try:
            click.echo("Waiting for potential cookies banner...")
            # Button text can vary slightly depending on the exact version of the banner
            btn_selectors = (
                'button.app-agree-button, button:has-text("Tout Accepter"), '
                'button:has-text("Tout accepter"), button:has-text("Accepter tout")'
            )

            # The iframe title can change based on locale or SFBX updates
            iframe_selector = (
                'iframe[title="Consent Manager"], '
                'iframe[title="Consent window"], '
                'iframe[title="Fenêtre de consentement"], '
                'iframe[src*="sfbx"]'
            )

            consent_frame = page.frame_locator(iframe_selector)
            accept_btn = consent_frame.locator(btn_selectors).first

            # Use force=True because visibility check sometimes fails for this banner
            accept_btn.click(force=True, timeout=10000)

            click.echo("Cookies banner accepted.")
            time.sleep(2)  # delay for banner to disappear and DOM to settle
        except Exception:
            click.echo("No cookies banner found or timed out. Proceeding to login.")

        # Wait for the login input to be visible and interactable before filling
        page.wait_for_selector("input[name='Login' i]", state="visible", timeout=10000)
        page.fill("input[name='Login' i]", self.username)
        page.fill("input[name='Password' i]", self.password)
        page.click("input[name='sub_btn'], input[type='submit'][value*='onnexion' i]")

        try:
            # Wait for the browser to redirect away from the login page
            page.wait_for_function("window.location.pathname !== '/connection.php'", timeout=10000)
            page.wait_for_load_state("domcontentloaded")
            click.echo("Successfully logged in.")
        except TimeoutError as err:
            page.screenshot(path="login_timeout.png")
            click.echo(f"Current page URL: {page.url}")
            click.echo(f"Page title: {page.title()}")
            click.echo(f"Body text snippet: {page.inner_text('body')[:500]}")
            raise Exception(
                "Failed to login to Babelio. Check credentials or CAPTCHA presence."
            ) from err

    def _process_book(self, page, isbn, title, author, publisher, status_raw, dry_run):
        # 1. Build Search Queries
        search_queries = []
        if isbn:
            search_queries.append(isbn)
        if title and author:
            search_queries.append(f"{title} {author}")
        if title and publisher and not publisher.strip().isdigit():
            search_queries.append(f"{title} {publisher}")
        if title:
            search_queries.append(title)

        # Ensure unique queries while maintaining order
        seen = set()
        search_queries = [q for q in search_queries if not (q in seen or seen.add(q))]

        found = False
        for query in search_queries:
            page.goto("https://www.babelio.com/", wait_until="domcontentloaded")

            # When logged in, the search bar ID is often 'searchbox'
            search_selector = "input#searchbox, input#recherche_general"

            page.wait_for_selector(search_selector, state="visible", timeout=10000)
            page.fill(search_selector, query)
            page.press(search_selector, "Enter")

            # Wait for either the book page (redirect) or search results
            try:
                page.wait_for_selector(".livre_top, .list_livre", timeout=8000)

                # If it's a search result page, click the first book
                if "/resrecherche.php" in page.url:
                    links = page.locator(".list_livre a.titre_v2").all()
                    if not links:
                        continue  # Try next query
                    links[0].click()
                    page.wait_for_selector(".livre_top", timeout=8000)

                found = True
                break  # Successfully found a book page
            except TimeoutError:
                continue  # Try next query

        if not found:
            click.echo(f"[{title}] Not found on Babelio after trying queries: {search_queries}")
            return False, "Not Found"

        # 2. Extract and display metadata for confirmation
        # Using locators with short timeouts as the page should already be loaded
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

        # 3. Duplication check: Is it already in the library?
        # On a book page, the "Ajouter à mes livres" button changes if we already have it.
        # It usually shows the shelf name (e.g. "Lu", "A lire")
        add_btn = page.locator("#btn_ajout_biblio, .btn_ajout_biblio")
        if not add_btn.is_visible():
            add_btn = page.locator("a[href*='mes_livres']")

        if add_btn.is_visible():
            add_btn_text = add_btn.inner_text().strip()
            if "Lu" in add_btn_text or "lire" in add_btn_text or "En cours" in add_btn_text:
                click.echo(f"[{title}] Already in library ({add_btn_text}). Skipping.")
                return True, "Already in library"

        # 3. Execution (Add to library)
        shelf = self._map_status(status_raw)

        if dry_run:
            click.echo(f"[{title}] DRY RUN: Would add to library with status '{shelf}'.")
            return True, "Added (Dry Run)"

        # Click the 'Ajouter' button (this opens a modal usually)
        add_btn.click()
        try:
            page.wait_for_selector("#id_status", timeout=5000)  # Wait for the dropdown in the modal
        except TimeoutError:
            click.echo(f"[{title}] Could not open add to library modal. Skipping.")
            return False, "Modal Error"

        # Select the status
        # Babelio status values: 1=Lu, 2=A lire, 3=En cours
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

        # Save
        page.click("#btn_ajout_livre_valider")

        # Wait for modal to close or toast to appear
        time.sleep(1)
        click.echo(f"[{title}] Added to library with status '{shelf}'.")
        return True, "Added"

    def _map_status(self, status):
        """Map Google Sheet status to Babelio shelves"""
        status = status.strip().lower()
        if status in ["read", "lu"]:
            return "Lu"
        elif status in ["to read", "à lire", "wish list"]:
            return "À lire"
        elif status in ["currently reading", "en cours"]:
            return "En cours"
        return "Lu"  # Default

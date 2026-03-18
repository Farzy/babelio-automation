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
            context = browser.new_context(user_agent=user_agent)
            page = context.new_page()

            click.echo("Logging into Babelio...")
            self._login(page)

            count = 0
            results = {"success": [], "skipped": [], "failed": []}

            for index, row in enumerate(books_data):
                if limit and count >= limit:
                    break

                # Assuming row format based on headers print:
                # [0] Title, [5] Author, [8] Status, [9] ISBN, [11] Babelio
                try:
                    title = row[0]
                    status_raw = row[8]
                    isbn = row[9]
                    babelio_synced = row[11].strip().upper()
                except IndexError:
                    continue  # Malformed row

                sheet_row_num = index + 2  # Google Sheet rows are 1-based, and +1 for header

                if babelio_synced == "OUI":
                    continue  # Already synced

                if not isbn:
                    click.echo(f"[{title}] Skipped: No ISBN provided.")
                    results["failed"].append((title, "No ISBN"))
                    continue

                click.echo(f"\nProcessing: {title} (ISBN: {isbn})")

                try:
                    success, reason = self._process_book(page, isbn, title, status_raw, dry_run)
                    if success:
                        if reason == "Already in library":
                            results["skipped"].append((isbn, title))
                            # Update Google Sheet anyway so we don't process it again
                            if not dry_run:
                                self._update_sheet(worksheet, sheet_row_num, "OUI")
                        else:
                            results["success"].append((isbn, title))
                            if not dry_run:
                                self._update_sheet(worksheet, sheet_row_num, "OUI")
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
            # iframe title is "Consent Manager" or "Consent window"
            btn_selectors = (
                'button.app-agree-button, button:has-text("Tout Accepter"), '
                'button:has-text("Tout accepter"), button:has-text("Accept all")'
            )

            # Create locators for both possible iframes
            f1 = page.frame_locator('iframe[title="Consent Manager"]')
            f2 = page.frame_locator('iframe[title="Consent window"]')

            # Wait for any frame to have the accept button
            accept_btn = f1.locator(btn_selectors).first.or_(f2.locator(btn_selectors).first)

            # Use force=True because visibility check sometimes fails for this banner
            accept_btn.click(force=True, timeout=10000)

            click.echo("Cookies banner accepted.")
            time.sleep(2)  # delay for banner to disappear and DOM to settle
        except Exception:
            click.echo("No cookies banner found or timed out. Proceeding to login.")

        # Wait for the login input to be visible and interactable before filling
        page.wait_for_selector("input[name='login']", state="visible", timeout=10000)
        page.fill("input[name='login']", self.username)
        page.fill("input[name='password']", self.password)
        page.click("button[type='submit']")

        try:
            # Wait for an element that only appears when logged in
            page.wait_for_selector(".header_user_menu", timeout=10000)
            click.echo("Successfully logged in.")
        except TimeoutError as err:
            raise Exception(
                "Failed to login to Babelio. Check credentials or CAPTCHA presence."
            ) from err

    def _process_book(self, page, isbn, title, status_raw, dry_run):
        # 1. Search by ISBN
        page.goto("https://www.babelio.com/")
        page.fill("input#recherche_general", isbn)
        page.press("input#recherche_general", "Enter")

        # Wait for either the book page (redirect) or search results
        try:
            page.wait_for_selector(".livre_top, .list_livre", timeout=8000)
        except TimeoutError:
            click.echo(f"[{title}] Not found on Babelio.")
            return False, "Not Found"

        # If it's a search result page, click the first book
        if "/resrecherche.php" in page.url:
            links = page.locator(".list_livre a.titre_v2").all()
            if not links:
                click.echo(f"[{title}] No search results found.")
                return False, "No Results"
            links[0].click()
            page.wait_for_selector(".livre_top")

        # 2. Duplication check: Is it already in the library?
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

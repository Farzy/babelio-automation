"""Pure HTML parsers for the (2026 redesign of the) Babelio website.

Every function here takes raw HTML and returns plain Python data, so the
scraping logic can be unit-tested against saved fixtures without a browser.
"""

import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

BASE_URL = "https://www.babelio.com"

#: Babelio ``statut`` code (``s1`` URL parameter, ``lib-status--N`` CSS class,
#: ``statut`` form value) mapped to the French label displayed on the site.
STATUS_LABELS: dict[int, str] = {
    0: "En cours",
    1: "Lu",
    2: "À lire",
    3: "Wishlist",
    4: "Abandonné",
}

_RATING_RE = re.compile(r"(\d)\s+sur\s+5")


def _text(node: Tag | None) -> str:
    """Return the stripped text of a node, or an empty string for ``None``."""
    return node.get_text(" ", strip=True) if node else ""


def _href(node: Tag | None) -> str:
    """Return the absolute URL of an anchor, or an empty string for ``None``."""
    if node is None:
        return ""
    return urljoin(BASE_URL, str(node.get("href") or ""))


def parse_library_page(html: str) -> list[dict[str, Any]]:
    """Parse one ``mabibliotheque.php`` page into book dictionaries.

    Each dictionary has the keys ``title``, ``author``, ``status``,
    ``possessed``, ``rating`` (``int`` 1-5 or ``None``), ``reviewed`` and ``url``.
    """
    soup = BeautifulSoup(html, "html.parser")
    books: list[dict[str, Any]] = []

    for item in soup.select("ul.lib-books > li.lib-book"):
        title_link = item.select_one(".lib-book-title a")
        title = _text(title_link)
        if not title:
            continue

        authors = [_text(a) for a in item.select(".lib-book-author a")]
        stars = item.select_one(".lib-stars")
        rating_match = _RATING_RE.search(str(stars.get("aria-label") or "")) if stars else None

        books.append(
            {
                "title": title,
                "author": ", ".join(a for a in authors if a),
                "status": _text(item.select_one(".lib-status")) or "Inconnu",
                "possessed": any(
                    _text(flag) == "Possédé" for flag in item.select(".lib-flags .lib-flag")
                ),
                "rating": int(rating_match.group(1)) if rating_match else None,
                "reviewed": item.select_one(".lib-flag--review") is not None,
                "url": _href(title_link),
            }
        )

    return books


def has_next_library_page(html: str) -> bool:
    """Tell whether the library pagination offers a "next page" link."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.select_one("nav.reviews-pagination a[rel='next']") is not None


def parse_search_results(html: str) -> list[dict[str, str | None]]:
    """Parse the book section of a ``recherche.php`` results page.

    Each dictionary has the keys ``title``, ``author``, ``url`` and ``status``
    (the user's shelf label, or ``None`` when the book is not in the library).
    """
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str | None]] = []

    for item in soup.select(".lv-grid .lv-item"):
        title_link = item.select_one(".lv-title a")
        if title_link is None:
            continue
        results.append(
            {
                "title": _text(title_link),
                "author": _text(item.select_one(".lv-author a")),
                "url": _href(title_link),
                "status": _text(item.select_one(".lv-status-chip")) or None,
            }
        )

    return results


def parse_book_header(html: str) -> tuple[str, str]:
    """Return ``(title, author)`` from a book page, ``("", "")`` when absent."""
    soup = BeautifulSoup(html, "html.parser")
    title = _text(soup.select_one("h1.book-title"))
    author = ", ".join(_text(a) for a in soup.select("a.book-author-link"))
    return title, author

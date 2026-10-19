from pathlib import Path

from babelio_parsers import (
    has_next_library_page,
    parse_book_header,
    parse_library_page,
    parse_search_results,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_library_page_full_entry():
    books = parse_library_page(load("library_page.html"))

    assert len(books) == 3
    assert books[0] == {
        "title": "L'Étranger",
        "author": "Albert Camus",
        "status": "Lu",
        "possessed": True,
        "rating": 4,
        "reviewed": True,
        "url": "https://www.babelio.com/livres/Camus-Ltranger/3874",
    }


def test_parse_library_page_minimal_entries():
    _, multi_author, wishlist = parse_library_page(load("library_page.html"))

    assert multi_author["author"] == "Neil Gaiman, Terry Pratchett"
    assert multi_author["status"] == "À lire"
    assert multi_author["possessed"] is False
    assert multi_author["rating"] is None
    assert multi_author["reviewed"] is False

    # Other flags (pin, "À échanger") must not be mistaken for possession.
    assert wishlist["status"] == "Wishlist"
    assert wishlist["possessed"] is False
    assert wishlist["author"] == ""


def test_parse_library_page_ignores_unrelated_html():
    assert parse_library_page("<html><body><h1>Connexion</h1></body></html>") == []


def test_has_next_library_page():
    assert has_next_library_page(load("library_page.html")) is True
    assert has_next_library_page(load("library_last_page.html")) is False


def test_parse_last_page_status():
    assert parse_library_page(load("library_last_page.html"))[0]["status"] == "Abandonné"


def test_parse_search_results():
    results = parse_search_results(load("search_results.html"))

    assert results == [
        {
            "title": "L'Étranger",
            "author": "Albert Camus",
            "url": "https://www.babelio.com/livres/Camus-Ltranger/3874",
            "status": "Lu",
        },
        {
            "title": "La Peste",
            "author": "Albert Camus",
            "url": "https://www.babelio.com/livres/Camus-La-Peste/4000",
            "status": None,
        },
    ]


def test_parse_search_results_empty():
    assert parse_search_results("<main><section class='rs-section'></section></main>") == []


def test_parse_book_header():
    assert parse_book_header(load("book_page.html")) == (
        "Parle-moi de chez nous",
        "Jeanine Cummins",
    )
    assert parse_book_header("<html></html>") == ("", "")

import pytest

from babelio_api import BabelioBot, validate_statuses


def test_map_status():
    bot = BabelioBot("dummy@user.com", "dummypass")

    assert bot._map_status("Read") == "Lu"
    assert bot._map_status("lu") == "Lu"
    assert bot._map_status("To Read") == "À lire"
    assert bot._map_status("à lire") == "À lire"
    assert bot._map_status("wish list") == "À lire"
    assert bot._map_status("Currently Reading") == "En cours"
    assert bot._map_status("en cours") == "En cours"
    assert bot._map_status("unknown status") == "Lu"


def _fetch(bot, monkeypatch, books, **kwargs):
    monkeypatch.setattr("babelio_api.load_books_cache", lambda _ttl: books)
    return bot.fetch_library_books(**kwargs)


BOOKS = [
    {"title": "A", "status": "Lu", "possessed": True, "rating": 5, "reviewed": True},
    {"title": "B", "status": "Wishlist", "possessed": False, "rating": None, "reviewed": False},
    {"title": "C", "status": "Lu", "possessed": False, "rating": 3, "reviewed": False},
    {"title": "D", "status": "À lire", "possessed": False, "rating": None, "reviewed": False},
    {"title": "E", "status": "À lire", "possessed": True, "rating": None, "reviewed": True},
    {"title": "F", "status": "Abandonné", "possessed": True, "rating": 2, "reviewed": False},
]


def _titles(bot, monkeypatch, statuses, **kw):
    return [b["title"] for b in _fetch(bot, monkeypatch, BOOKS, statuses=statuses, **kw)]


def test_fetch_single_status_filters(monkeypatch):
    bot = BabelioBot("dummy@user.com", "dummypass")

    assert _titles(bot, monkeypatch, ["tous"]) == list("ABCDEF")
    assert _titles(bot, monkeypatch, ["wishlist"]) == ["B"]
    assert _titles(bot, monkeypatch, ["lus"]) == ["A", "C"]
    assert _titles(bot, monkeypatch, ["possedes"]) == ["A", "E", "F"]
    # Wishlist entries are never "non-possedes".
    assert _titles(bot, monkeypatch, ["non-possedes"]) == ["C", "D"]
    assert _titles(bot, monkeypatch, ["critiques"]) == ["A", "E"]
    assert _titles(bot, monkeypatch, ["non-critiques"]) == ["B", "C", "D", "F"]
    assert _titles(bot, monkeypatch, ["tous"], rating=3) == ["C"]


def test_fetch_defaults_to_every_book(monkeypatch):
    bot = BabelioBot("dummy@user.com", "dummypass")

    assert [b["title"] for b in _fetch(bot, monkeypatch, BOOKS)] == list("ABCDEF")


def test_fetch_multiple_shelves_match_any(monkeypatch):
    bot = BabelioBot("dummy@user.com", "dummypass")

    assert _titles(bot, monkeypatch, ["lus", "a-lire"]) == ["A", "C", "D", "E"]
    assert _titles(bot, monkeypatch, ["wishlist", "abandonnes"]) == ["B", "F"]


def test_fetch_combines_shelf_possession_and_review_filters(monkeypatch):
    bot = BabelioBot("dummy@user.com", "dummypass")

    assert _titles(bot, monkeypatch, ["a-lire", "non-possedes"]) == ["D"]
    assert _titles(bot, monkeypatch, ["lus", "a-lire", "possedes"]) == ["A", "E"]
    assert _titles(bot, monkeypatch, ["possedes", "non-critiques"]) == ["F"]
    assert _titles(bot, monkeypatch, ["possedes", "critiques"], rating=5) == ["A"]
    assert _titles(bot, monkeypatch, ["lus", "non-possedes", "non-critiques"]) == ["C"]


def test_validate_statuses_normalizes():
    assert validate_statuses([]) == ["tous"]
    assert validate_statuses(["Lus", "a_lire", "LUS"]) == ["lus", "a-lire"]
    assert validate_statuses(["lus", "possedes", "critiques"]) == ["lus", "possedes", "critiques"]


@pytest.mark.parametrize(
    ("statuses", "message"),
    [
        (["possedes", "non-possedes"], "owned"),
        (["critiques", "non-critiques"], "reviewed"),
        (["non-possedes", "wishlist"], "Wishlist"),
        (["non-possedes", "lus", "wishlist"], "Wishlist"),
        (["tous", "lus"], "'tous'"),
        (["lus", "tous"], "'tous'"),
        (["nope"], "Unknown status: nope"),
    ],
)
def test_validate_statuses_rejects_bad_combinations(statuses, message):
    with pytest.raises(ValueError, match=message):
        validate_statuses(statuses)


def test_fetch_rejects_incompatible_statuses(monkeypatch):
    bot = BabelioBot("dummy@user.com", "dummypass")

    with pytest.raises(ValueError, match="Incompatible"):
        _fetch(bot, monkeypatch, BOOKS, statuses=["possedes", "non-possedes"])

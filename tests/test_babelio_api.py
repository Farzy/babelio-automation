from babelio_api import BabelioBot


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


def test_build_library_url():
    bot = BabelioBot("dummy@user.com", "dummypass")

    assert "s1=1" in bot._build_library_url("lus")
    assert "s1=2" in bot._build_library_url("a-lire")
    assert "s1=0" in bot._build_library_url("en-cours")
    assert "s1=3" in bot._build_library_url("wishlist")
    assert "s1=4" in bot._build_library_url("abandonnes")
    assert "possede=1" in bot._build_library_url("possedes")
    assert "critique=reviewed" in bot._build_library_url("critiques")
    assert "critique=notreviewed" in bot._build_library_url("non-critiques")
    assert bot._build_library_url("tous") == "https://www.babelio.com/mabibliotheque.php"
    assert bot._build_library_url("non-possedes") == "https://www.babelio.com/mabibliotheque.php"
    assert "note=5" in bot._build_library_url("lus", rating=5)


def test_build_library_url_redesigned_filters():
    bot = BabelioBot("dummy@user.com", "dummypass")

    assert bot._build_library_url("wishlist").endswith("?s1=3")
    assert bot._build_library_url("possedes").endswith("?possede=1")
    assert bot._build_library_url("critiques").endswith("?critique=reviewed")
    assert bot._build_library_url("non-critiques").endswith("?critique=notreviewed")


def _fetch(bot, monkeypatch, books, **kwargs):
    monkeypatch.setattr("babelio_api.load_books_cache", lambda _ttl: books)
    return bot.fetch_library_books(**kwargs)


def test_fetch_library_books_filters(monkeypatch):
    bot = BabelioBot("dummy@user.com", "dummypass")
    books = [
        {"title": "A", "status": "Lu", "possessed": True, "rating": 5, "reviewed": True},
        {"title": "B", "status": "Wishlist", "possessed": False, "rating": None, "reviewed": False},
        {"title": "C", "status": "Lu", "possessed": False, "rating": 3, "reviewed": False},
    ]

    def titles(**kw):
        return [b["title"] for b in _fetch(bot, monkeypatch, books, **kw)]

    assert titles(status_filter="wishlist") == ["B"]
    assert titles(status_filter="lus") == ["A", "C"]
    assert titles(status_filter="possedes") == ["A"]
    assert titles(status_filter="non-possedes") == ["B", "C"]
    assert titles(status_filter="critiques") == ["A"]
    assert titles(status_filter="non-critiques") == ["B", "C"]
    assert titles(rating=3) == ["C"]

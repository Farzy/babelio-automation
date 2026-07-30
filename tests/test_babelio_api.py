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
    assert "s1=3" in bot._build_library_url("pense-bete")
    assert "s1=4" in bot._build_library_url("abandonnes")
    assert "s1=5" in bot._build_library_url("possedes")
    assert "s3=10" in bot._build_library_url("critiques")
    assert "s3=11" in bot._build_library_url("non-critiques")
    assert "action=toute" in bot._build_library_url("tous")
    assert "action=toute" in bot._build_library_url("non-possedes")
    assert "note=5" in bot._build_library_url("lus", rating=5)

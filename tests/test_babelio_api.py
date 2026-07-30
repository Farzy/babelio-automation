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

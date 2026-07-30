import json
from unittest.mock import MagicMock, patch

import pytest

from gog_client import GogSheetsClient, col_to_letter

TEST_SHEET_ID = "1uCwsAjpwOhwKjgWVtg-7EXdKKy9UN9S0GnxBQ5NDpXE"


def test_col_to_letter():
    assert col_to_letter(1) == "A"
    assert col_to_letter(2) == "B"
    assert col_to_letter(12) == "L"
    assert col_to_letter(26) == "Z"
    assert col_to_letter(27) == "AA"
    assert col_to_letter(28) == "AB"


def test_extract_spreadsheet_id_valid():
    url = f"https://docs.google.com/spreadsheets/d/{TEST_SHEET_ID}/edit"
    assert GogSheetsClient.extract_spreadsheet_id(url) == TEST_SHEET_ID
    assert GogSheetsClient.extract_spreadsheet_id(TEST_SHEET_ID) == TEST_SHEET_ID


def test_extract_spreadsheet_id_invalid():
    with pytest.raises(ValueError, match="Spreadsheet URL or ID cannot be empty"):
        GogSheetsClient.extract_spreadsheet_id("")

    with pytest.raises(ValueError, match="Could not parse valid Spreadsheet ID"):
        GogSheetsClient.extract_spreadsheet_id("http://invalid-url.com/something")


@patch("subprocess.run")
def test_get_all_values(mock_run):
    mock_response = MagicMock()
    mock_response.stdout = json.dumps(
        {
            "values": [
                ["Title", "Author", "ISBN"],
                ["Test Book", "Test Author", "9781234567890"],
            ]
        }
    )
    mock_run.return_value = mock_response

    client = GogSheetsClient()
    rows = client.get_all_values(TEST_SHEET_ID)

    assert len(rows) == 2
    assert rows[0] == ["Title", "Author", "ISBN"]
    assert rows[1][0] == "Test Book"

    mock_run.assert_called_once_with(
        ["gog", "sheets", "get", TEST_SHEET_ID, "A1:Z1000", "--json"],
        capture_output=True,
        text=True,
        check=True,
    )


@patch("subprocess.run")
def test_update_cell(mock_run):
    mock_run.return_value = MagicMock()

    client = GogSheetsClient()
    client.update_cell(TEST_SHEET_ID, row=2, col=12, value="OUI")

    mock_run.assert_called_once_with(
        ["gog", "sheets", "update", TEST_SHEET_ID, "Sheet1!L2", "OUI"],
        capture_output=True,
        text=True,
        check=True,
    )

import json
import re
import subprocess  # nosec B404


def col_to_letter(col: int) -> str:
    """Convert 1-based column index to Excel column letter (e.g. 1 -> A, 12 -> L, 27 -> AA)."""
    result = ""
    while col > 0:
        col, remainder = divmod(col - 1, 26)
        result = chr(65 + remainder) + result
    return result


class GogSheetsClient:
    """Python client wrapper for gog CLI to interface with Google Sheets."""

    def __init__(self, account: str | None = None):
        self.account = account

    @staticmethod
    def extract_spreadsheet_id(url_or_id: str) -> str:
        """Extract Google Spreadsheet ID from a URL or raw ID string."""
        if not url_or_id:
            raise ValueError("Spreadsheet URL or ID cannot be empty.")
        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url_or_id)
        if match:
            return match.group(1)
        if re.match(r"^[a-zA-Z0-9-_]+$", url_or_id):
            return url_or_id
        raise ValueError(f"Could not parse valid Spreadsheet ID from: {url_or_id}")

    def get_all_values(self, sheet_url_or_id: str, range_name: str = "A1:Z1000") -> list[list[str]]:
        """Fetch values from a Google Sheet range using gog sheets get."""
        spreadsheet_id = self.extract_spreadsheet_id(sheet_url_or_id)
        cmd = ["gog", "sheets", "get", spreadsheet_id, range_name, "--json"]
        if self.account:
            cmd.extend(["--account", self.account])

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        try:
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                return data.get("values", [])
            elif isinstance(data, list):
                return data
            return []
        except json.JSONDecodeError as e:
            err_msg = f"Failed to parse gog sheets JSON output: {e}\nOutput: {result.stdout}"
            raise RuntimeError(err_msg) from e

    def update_cell(
        self, sheet_url_or_id: str, row: int, col: int, value: str, tab: str = "Sheet1"
    ) -> None:
        """Update a single cell value using gog sheets update."""
        spreadsheet_id = self.extract_spreadsheet_id(sheet_url_or_id)
        col_letter = col_to_letter(col)
        cell_range = f"{tab}!{col_letter}{row}" if tab else f"{col_letter}{row}"

        cmd = ["gog", "sheets", "update", spreadsheet_id, cell_range, value]
        if self.account:
            cmd.extend(["--account", self.account])

        subprocess.run(cmd, capture_output=True, text=True, check=True)

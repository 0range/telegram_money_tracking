from unittest.mock import MagicMock, patch
from bot import get_user_sheet, get_budgets_sheet

@patch('gspread.authorize')
def test_sheet_creation(mock_auth):
    mock_spreadsheet = MagicMock()
    mock_auth.return_value.open_by_url().worksheet.side_effect = Exception("Not found")
    
    sheet = get_user_sheet(123)
    mock_auth.return_value.open_by_url().add_worksheet.assert_called_once_with(
        title="123", rows=100, cols=11
    )

from unittest.mock import MagicMock, patch
import gspread
from bot import get_user_sheet

@patch('gspread.authorize')
def test_sheet_creation(mock_auth):
    mock_spreadsheet = MagicMock()
    mock_auth.return_value.open_by_url.return_value = mock_spreadsheet
    
    # Эмулируем отсутствие листа
    mock_spreadsheet.worksheet.side_effect = gspread.WorksheetNotFound
    
    get_user_sheet(123)
    
    mock_spreadsheet.add_worksheet.assert_called_once_with(
        title="123", rows=100, cols=11
    )

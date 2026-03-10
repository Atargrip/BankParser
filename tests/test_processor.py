import pytest
from unittest.mock import MagicMock, patch
from processor import StatementProcessor
from models import ParseResult, ParseError

def test_processor_file_not_found():
    processor = StatementProcessor()
    with patch("os.path.exists", return_value=False):
        result = processor.process_file("nonexistent.pdf")
        assert len(result.errors) == 1
        assert result.errors[0].message == "Файл не найден"

def test_processor_unrecognized_bank(mock_pdfplumber):
    processor = StatementProcessor()
    # Mock open(file, "rb")
    with patch("builtins.open", MagicMock()):
        with patch("os.path.exists", return_value=True):
            # All can_parse return False
            for p in processor.parsers:
                p.can_parse = MagicMock(return_value=False)
            
            result = processor.process_file("some.pdf")
            assert len(result.errors) == 1
            assert result.errors[0].message == "Банк не распознан"

def test_processor_routing(mock_pdfplumber):
    processor = StatementProcessor()
    with patch("builtins.open", MagicMock()):
        with patch("os.path.exists", return_value=True):
            # Let's say Halyk matches
            for p in processor.parsers:
                p.can_parse = MagicMock(return_value=False)
            
            from parsers.halyk import HalykParser
            halyk_parser = next(p for p in processor.parsers if isinstance(p, HalykParser))
            halyk_parser.can_parse = MagicMock(return_value=True)
            halyk_parser.parse = MagicMock(return_value=ParseResult(payments=[MagicMock()]))
            
            result = processor.process_file("halyk.pdf")
            assert len(result.payments) == 1
            halyk_parser.parse.assert_called_once()

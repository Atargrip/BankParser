import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch
import io

from parsers.base import Parser
from parsers.halyk import HalykParser
from parsers.otbasy import OtbasyParser
from parsers.alataucity import AlatauCityParser
from parsers.bcc import BccPdfParser
from parsers.eurasian import EurasianParser
from parsers.forte import ForteParser
from parsers.freedom import FreedomParser
from parsers.nurbank import NurbankPdfParser
from parsers.rbk import RBKParser
from models import Payment, ParseError

# --- Tests for Parser.clean_amount ---

@pytest.mark.parametrize("input_str, expected", [
    ("1 234,56", Decimal("1234.56")),
    ("1,234.56", Decimal("1234.56")),
    ("100 000 \xa0 ₸", Decimal("100000")),
    ("-500.00", Decimal("-500.00")),
    ("abc", Decimal("0")),
    ("", Decimal("0")),
    (None, Decimal("0")),
    ("12.34\n", Decimal("12.34")),
])
def test_clean_amount(input_str, expected):
    assert Parser.clean_amount(input_str) == expected

# --- Tests for can_parse ---

def test_halyk_can_parse_success(mock_pdfplumber):
    parser = HalykParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    # Halyk looks for specific image dimensions
    mock_page.images = [{"width": 96.0, "height": 35.0}]
    
    assert parser.can_parse(b"dummy pdf content") is True

def test_halyk_can_parse_failure(mock_pdfplumber):
    parser = HalykParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_page.images = [{"width": 10.0, "height": 10.0}]
    
    assert parser.can_parse(b"dummy pdf content") is False

def test_otbasy_can_parse_success(mock_pdfplumber):
    parser = OtbasyParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_page.images = [{"width": 230.0, "height": 81.5}]
    
    assert parser.can_parse(b"dummy pdf content") is True

def test_alatau_can_parse_success(mock_pdfplumber):
    parser = AlatauCityParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_page.extract_text.return_value = "Alatau City Bank Выписка"
    
    assert parser.can_parse(b"dummy pdf content") is True

def test_bcc_can_parse_success(mock_pdfplumber):
    parser = BccPdfParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_page.extract_text.return_value = "Банк ЦентрКредит"
    
    assert parser.can_parse(b"dummy pdf content") is True

def test_eurasian_can_parse_success(mock_pdfplumber):
    parser = EurasianParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_page.extract_text.return_value = "Евразийский банк"
    
    assert parser.can_parse(b"dummy pdf content") is True

def test_forte_can_parse_success(mock_pdfplumber):
    parser = ForteParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_page.extract_text.return_value = "ForteBank Выписка по лицевому счету"
    
    assert parser.can_parse(b"dummy pdf content") is True

def test_freedom_can_parse_success(mock_pdfplumber):
    parser = FreedomParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_page.extract_text.return_value = "Freedom Bank"
    
    assert parser.can_parse(b"dummy pdf content") is True

def test_nurbank_can_parse_success(mock_pdfplumber):
    parser = NurbankPdfParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_page.extract_text.return_value = "Нурбанк Выписка"
    
    assert parser.can_parse(b"dummy pdf content") is True

def test_rbk_can_parse_success(mock_pdfplumber):
    parser = RBKParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_page.extract_text.return_value = "Bank RBK Выписка по лицевому счету"
    
    assert parser.can_parse(b"dummy pdf content") is True

# --- Tests for parse methods ---

def test_halyk_parse_success(mock_pdfplumber):
    parser = HalykParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    
    # Halyk table: date (0), empty (1), desc (2), amount (3), currency (4)
    mock_page.extract_tables.return_value = [[
        ["01.01.2024", "", "Test Payment", "-1000", "KZT"],
        ["02.01.2024", "", "Salary", "500000", "KZT"]
    ]]
    
    result = parser.parse(b"dummy content")
    
    assert len(result.payments) == 2
    assert result.payments[0].date == date(2024, 1, 1)
    assert result.payments[0].amount == 1000.0
    assert result.payments[0].type == "expense"
    assert result.payments[1].date == date(2024, 1, 2)
    assert result.payments[1].type == "income"
    assert len(result.errors) == 0

def test_otbasy_parse_success(mock_pdfplumber):
    parser = OtbasyParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    
    # Otbasy table: 0: No, 1: Date, 3: IIN, 7: Corr, 8: Debit, 9: Credit, 10: Desc
    row1 = ["1", "03.11.25", "doc1", "123456789012", "bik", "bank", "acc", "Corr Name", "1000", "0", "Description"]
    mock_page.extract_tables.return_value = [[row1]]
    
    result = parser.parse(b"dummy content")
    
    assert len(result.payments) == 1
    p = result.payments[0]
    assert p.date == date(2025, 11, 3)
    assert p.amount == 1000.0
    assert p.type == "expense"

def test_otbasy_parse_year_bug_fix(mock_pdfplumber):
    parser = OtbasyParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    
    # Случай с ошибкой "2100" (когда к "21" приклеились нули)
    row1 = ["1", "03.11.2100", "doc1", "123456789012", "bik", "bank", "acc", "Corr Name", "1000", "0", "Description"]
    # Случай с нормальным длинным годом "2024"
    row2 = ["2", "15.05.2024", "doc2", "123456789012", "bik", "bank", "acc", "Corr Name", "0", "500", "Description"]
    # Случай с коротким годом "25"
    row3 = ["3", "20.12.25", "doc3", "123456789012", "bik", "bank", "acc", "Corr Name", "200", "0", "Description"]
    
    mock_page.extract_tables.return_value = [[row1, row2, row3]]
    
    result = parser.parse(b"dummy")
    
    assert result.payments[0].date == date(2021, 11, 3)
    assert result.payments[1].date == date(2024, 5, 15)
    assert result.payments[2].date == date(2025, 12, 20)

def test_parser_error_handling(mock_pdfplumber):
    parser = HalykParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    
    # Row with invalid amount
    mock_page.extract_tables.return_value = [[
        ["01.01.2024", "", "Error Row", "NOT_A_NUMBER", "KZT"]
    ]]
    
    result = parser.parse(b"dummy content")
    assert len(result.payments) == 0 # Halyk clean_amount returns 0 on error, then skips
    assert len(result.errors) == 0
    
    # If something else fails, e.g. currency access (out of range)
    mock_page.extract_tables.return_value = [[
        ["01.01.2024", "", "Error Row", "100"] # missing index 4 (currency)
    ]]
    result = parser.parse(b"dummy content")
    assert len(result.errors) > 0

def test_alatau_parse_success(mock_pdfplumber):
    parser = AlatauCityParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    
    # 0: Date, 3: Debit, 4: Credit, 8: Desc, 9: Corr, 10: IIN
    row = ["01.01.2024", "", "", "1000", "0", "", "", "", "Description", "Corr Name", "123456789012", "", ""]
    mock_page.extract_tables.return_value = [[row]]
    
    result = parser.parse(b"dummy content")
    assert len(result.payments) == 1
    assert result.payments[0].amount == 1000.0
    assert result.payments[0].type == "expense"

def test_bcc_parse_success(mock_pdfplumber):
    parser = BccPdfParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    
    # BCC uses regex matching on text
    mock_page.extract_text.return_value = "2024-01-01\nLine 1\nSalary Payment\nLine 3\n500.00 KZT\n"
    
    result = parser.parse(b"dummy content")
    assert len(result.payments) == 1
    assert result.payments[0].date == date(2024, 1, 1)
    assert result.payments[0].amount == 500.0
    assert result.payments[0].type == "income"

def test_eurasian_parse_success(mock_pdfplumber):
    parser = EurasianParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    
    # 0: Date, 4: IIN, 5: Corr, 6: Debit, 7: Credit, 8: Desc
    row = ["01.01.2024", "doc", "bik", "acc", "123456789012", "Corr Name", "0", "1500", "Eurasian Info"]
    mock_page.extract_tables.return_value = [[row]]
    
    result = parser.parse(b"dummy content")
    assert len(result.payments) == 1
    assert result.payments[0].date == date(2024, 1, 1)
    assert result.payments[0].amount == 1500.0
    assert result.payments[0].type == "income"

def test_forte_parse_success(mock_pdfplumber):
    parser = ForteParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    
    mock_page.extract_text.return_value = "Валюта: USD"
    # Row: 0: No, 1: Date, 3: Sender, 4: Receiver, 5: Debit, 6: Credit, 7: Desc
    row = ["1", "01.01.2024", "", "Sender Name", "Receiver Name", "100.50", "0", "Forte Test"]
    mock_page.extract_tables.return_value = [[row]]
    
    result = parser.parse(b"dummy content")
    assert len(result.payments) == 1
    assert result.payments[0].date == date(2024, 1, 1)
    assert result.payments[0].amount == 100.50
    assert result.payments[0].currency == "USD"
    assert result.payments[0].type == "expense"

def test_freedom_parse_success(mock_pdfplumber):
    parser = FreedomParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    
    # 1: Date, 5: Corr, 8: Debit, 9: Credit, 10: Desc
    row = ["", "01.01.2024", "", "", "", "Freedom Corr", "", "", "0", "2000", "Freedom Desc"]
    mock_page.extract_tables.return_value = [[row]]
    
    result = parser.parse(b"dummy content")
    assert len(result.payments) == 1
    assert result.payments[0].date == date(2024, 1, 1)
    assert result.payments[0].amount == 2000.0
    assert result.payments[0].type == "income"

def test_nurbank_parse_success(mock_pdfplumber):
    parser = NurbankPdfParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    
    # 0: Date, 2: Debit, 3: Credit, 4: Corr\nIIN, 5: Desc
    row = ["01.01.2024", "doc", "3000", "0", "Nurbank Corr\n123456789012", "Nurbank Desc"]
    mock_page.extract_table.return_value = [row] # Nurbank uses extract_table (singular)
    
    result = parser.parse(b"dummy content")
    assert len(result.payments) == 1
    assert result.payments[0].date == date(2024, 1, 1)
    assert result.payments[0].amount == 3000.0
    assert result.payments[0].type == "expense"

def test_rbk_parse_success(mock_pdfplumber):
    parser = RBKParser()
    mock_pdf = mock_pdfplumber.return_value.__enter__.return_value
    mock_page = MagicMock()
    mock_pdf.pages = [mock_page]
    
    mock_page.extract_text.return_value = "Валюта : KZT"
    # 0: No, 1: Date, 3: Sender, 4: Receiver, 5: Debit, 6: Credit, 7: Desc
    row = ["1", "01.01.2024", "", "Sender RBK", "Receiver RBK", "0", "4000", "RBK Desc"]
    mock_page.extract_tables.return_value = [[row]]
    
    result = parser.parse(b"dummy content")
    assert len(result.payments) == 1
    assert result.payments[0].date == date(2024, 1, 1)
    assert result.payments[0].amount == 4000.0
    assert result.payments[0].type == "income"

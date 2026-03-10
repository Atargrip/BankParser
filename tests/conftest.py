import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_pdfplumber():
    with patch("pdfplumber.open") as mock_open:
        yield mock_open

@pytest.fixture
def mock_page():
    page = MagicMock()
    # Default return values to avoid errors if not explicitly set in test
    page.images = []
    page.extract_text.return_value = ""
    page.extract_tables.return_value = []
    return page

@pytest.fixture
def mock_pdf(mock_page):
    pdf = MagicMock()
    pdf.pages = [mock_page]
    pdf.__enter__.return_value = pdf
    return pdf

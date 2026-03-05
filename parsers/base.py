from abc import ABC, abstractmethod
from decimal import Decimal
from .models import ParseResult

class Parser(ABC):
    @staticmethod
    def clean_amount(amount_str) -> Decimal:
        if not amount_str:
            return Decimal(0)
        # Удаляем пробелы, неразрывные пробелы (\xa0), валюту и переносы
        clean = str(amount_str).replace(" ", "").replace("\xa0", "").replace("\n", "").replace("₸", "")
        clean = clean.replace(",", ".")
        try:
            return Decimal(clean)
        except:
            return Decimal(0)

    @abstractmethod
    def can_parse(self, file_bytes: bytes) -> bool:
        """Проверяет, подходит ли данный парсер для файла"""
        pass

    @abstractmethod
    def parse(self, file_bytes: bytes) -> ParseResult:
        """Основной метод парсинга документа"""
        pass

from abc import ABC, abstractmethod
from decimal import Decimal
from models import ParseResult

class Parser(ABC):
    @staticmethod
    def clean_amount(amount_str) -> Decimal:
        if not amount_str:
            return Decimal(0)
        # Удаляем пробелы, неразрывные пробелы (\xa0), валюту и переносы
        clean = str(amount_str).replace(" ", "").replace("\xa0", "").replace("\n", "").replace("₸", "")
        
        # Если есть и запятая, и точка - удаляем первый разделитель (тысячные) и оставляем второй как decimal
        if "," in clean and "." in clean:
            if clean.find(",") < clean.find("."):
                clean = clean.replace(",", "")
            else:
                clean = clean.replace(".", "").replace(",", ".")
        else:
            # Если только запятая - превращаем в точку
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

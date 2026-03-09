import os
from typing import List
from .models import ParseResult, ParseError
from .parsers.base import Parser
from .parsers.otbasy import OtbasyParser
from .parsers.forte import ForteParser
from .parsers.rbk import RBKParser
from .parsers.halyk import HalykParser
from .parsers.nurbank import NurbankPdfParser
from .parsers.alataucity import AlatauCityParser

class StatementProcessor:
    def __init__(self):
        self.parsers: List[Parser] = [
            OtbasyParser(),
            ForteParser(),
            RBKParser(),
            HalykParser(),
            NurbankPdfParser(),
            AlatauCityParser(),
        ]

    def process_file(self, file_path: str) -> ParseResult:
        if not os.path.exists(file_path):
            result = ParseResult()
            result.errors.append(ParseError(row=0, column=0, message="Файл не найден", rawValue=file_path))
            return result

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        # Определяем нужный парсер
        for parser in self.parsers:
            if parser.can_parse(file_bytes):
                return parser.parse(file_bytes)

        # Если ни один парсер не подошел
        result = ParseResult()
        result.errors.append(ParseError(row=0, column=0, message="Банк не распознан", rawValue=""))
        return result

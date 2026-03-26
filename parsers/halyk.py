import pdfplumber
import io
import re
from parsers.base import Parser
from models import Payment, ParseError, ParseResult

class HalykParser(Parser):
    def can_parse(self, file_bytes: bytes) -> bool:
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                if not pdf.pages:
                    return False

                page = pdf.pages[0]

                TARGET_WIDTH = 96.0
                TARGET_HEIGHT = 35.0
                TOLERANCE = 0.5

                if hasattr(page, 'images'):
                    for img in page.images:
                        try:
                            w = float(img.get('width', 0))
                            h = float(img.get('height', 0))

                            # проверка с погрешностью
                            w_ok = abs(w - TARGET_WIDTH) <= TOLERANCE
                            h_ok = abs(h - TARGET_HEIGHT) <= TOLERANCE

                            if w_ok and h_ok:
                                return True
                        except (ValueError, TypeError):
                            continue

                return False
        except Exception:
            return False

    def parse(self, file_bytes: bytes) -> ParseResult:
        result = ParseResult()

        table_settings = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 4,
            "text_x_tolerance": 2,
            "text_y_tolerance": 2,
        }

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables(table_settings)
                for table in tables:
                    for row_idx, row in enumerate(table):
                        # Сразу очищаем все ячейки от лишних пробелов и переносов
                        clean_row = [str(cell).strip() if cell else "" for cell in row]

                        # Требуем минимум 4 колонки
                        if len(clean_row) < 4:
                            continue

                        col_date = clean_row[0].replace("\n", " ")
                        col_desc = " ".join(clean_row[2].split())
                        col_amount = clean_row[3]

                        # Фильтруем ТОЛЬКО явные заголовки таблицы или пустые строки
                        if "Дата" in col_date or "Всего" in col_date or (not col_date and not col_amount):
                            continue

                        try:
                            # ПРАВИЛО 1: Если дата не нашлась — это ошибка парсинга, а не пропуск строки!
                            date_match = re.search(r'(\d{2})[./-](\d{2})[./-](\d{2,4})', col_date)
                            if not date_match:
                                raise ValueError(f"Не удалось найти корректную дату в ячейке: '{col_date}'")

                            # ПРАВИЛО 2: Если сумма 0 — это ошибка (недопарсили), отправляем в errors
                            amount = float(self.clean_amount(col_amount))
                            if amount == 0:
                                raise ValueError(f"Не удалось распознать сумму (или она равна 0): '{col_amount}'")

                            t_type = "expense" if amount < 0 else "income"

                            # ПРАВИЛО 3: Правильное решение "Ошибки 2100 года"
                            d, m, y = date_match.groups()
                            if len(y) == 4 and not (y.startswith("20") or y.startswith("19")):
                                y = f"20{y[:2]}"  # 2100 -> 2021, 2610 -> 2026
                            elif len(y) == 2:
                                y = f"20{y}"  # 26 -> 2026
                            safe_date_str = f"{d}.{m}.{y}"

                            # ПРАВИЛО 4: Безопасное обращение к валюте (защита от IndexError)
                            currency_str = clean_row[4] if len(clean_row) > 4 else "KZT"
                            if not currency_str:
                                currency_str = "KZT"

                            payment = Payment(
                                date=self.parse_date(safe_date_str),
                                merchant=col_desc,
                                amount=abs(amount),
                                currency=currency_str,
                                type=t_type,
                                bank="Halyk Bank"
                            )
                            result.payments.append(payment)

                        except Exception as e:
                            # Теперь все проблемные строки (без даты или с кривой суммой) будут учтены тут
                            result.errors.append(ParseError(
                                row=row_idx,
                                column=-1,
                                message=str(e),
                                rawValue=str(clean_row)
                            ))

        return result

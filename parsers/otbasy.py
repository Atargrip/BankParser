import pdfplumber
import io
import re
from parsers.base import Parser
from models import Payment, ParseError, ParseResult

class OtbasyParser(Parser):
    def can_parse(self, file_bytes: bytes) -> bool:
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                if not pdf.pages:
                    return False

                page = pdf.pages[0]

                # text = page.extract_text()
                # if text:
                #     text_upper = text.upper()
                #     if 'НАРОДНЫЙ БАНК КАЗАХСТАНА' in text_upper or 'HSBKKZKX' in text_upper:
                #         return True

                TARGET_WIDTH = 230.0
                TARGET_HEIGHT = 81.5
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
        }

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables(table_settings)
                for table in tables:
                    for row_idx, row in enumerate(table):
                        # Сразу очищаем от мусора
                        clean_row =[str(cell).strip() if cell else "" for cell in row]

                        if len(clean_row) < 11:
                            continue

                        # Отличный фильтр заголовков от автора (оставляем его)
                        # Если 1-я колонка содержит только цифры (номер по порядку), то это транзакция
                        if not re.match(r'^\d+$', clean_row[0]):
                            continue

                        try:
                            date_str = clean_row[1].replace("\n", " ")
                            iin_bin = clean_row[3].replace("\n", "")
                            correspondent = clean_row[7].replace("\n", " ")
                            debit_str = clean_row[8]  # Расход
                            credit_str = clean_row[9]  # Приход
                            description = clean_row[10].replace("\n", " ")

                            debit_amount = float(self.clean_amount(debit_str))
                            credit_amount = float(self.clean_amount(credit_str))

                            amount = 0.0
                            t_type = ""

                            if debit_amount > 0:
                                amount = debit_amount
                                t_type = "expense"
                            elif credit_amount > 0:
                                amount = credit_amount
                                t_type = "income"
                            else:
                                # ПРАВИЛО 2: Было continue, теперь raise ValueError.
                                # Если у нас есть номер транзакции, но суммы не спарсились - это ошибка!
                                raise ValueError(f"Обе суммы равны нулю или не распознаны. Расход: '{debit_str}', Приход: '{credit_str}'")

                            # ПРАВИЛО 1 и 3: Безопасный парсинг даты и "Ошибки 2100"
                            date_match = re.search(r'(\d{2})[./-](\d{2})[./-](\d{2,4})', date_str)
                            if not date_match:
                                raise ValueError(f"Не удалось найти корректную дату в ячейке: '{date_str}'")

                            d, m, y = date_match.groups()
                            if len(y) == 4 and not (y.startswith("20") or y.startswith("19")):
                                y = f"20{y[:2]}"  # 2100 -> 2021, 2610 -> 2026
                            elif len(y) == 2:
                                y = f"20{y}"      # 26 -> 2026
                            safe_date_str = f"{d}.{m}.{y}"

                            payment = Payment(
                                date=self.parse_date(safe_date_str),
                                amount=amount,
                                currency="KZT",  # Валюта в Отбасы всегда KZT
                                type=t_type,
                                merchant=description,
                                bank="Otbasy Bank",
                                correspondent=correspondent,
                                iin_bin=iin_bin
                            )
                            result.payments.append(payment)

                        except Exception as e:
                            # Ошибки дат и сумм аккуратно попадают сюда для логирования
                            result.errors.append(ParseError(
                                row=row_idx,
                                column=-1,
                                message=str(e),
                                rawValue=str(clean_row)
                            ))

        return result

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

        # Настройки для извлечения таблицы с явными границами (как в PDF Отбасы)
        table_settings = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
        }

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables(table_settings)
                for table in tables:
                    for row_idx, row in enumerate(table):
                        # Очищаем ячейки от None
                        clean_row = [str(cell).strip() if cell else "" for cell in row]

                        # В таблице Отбасы банка 11 колонок. Пропускаем короткие строки
                        if len(clean_row) < 11:
                            continue

                        # Проверяем, что первая колонка - это порядковый номер (цифры), чтобы отсеять шапку
                        if not re.match(r'^\d+$', clean_row[0]):
                            continue

                        try:
                            # Маппинг колонок (на основе предоставленного PDF):
                            # 0: №, 1: Дата, 2: № док, 3: БИН/ИИН, 4: БИК, 5: Банк корр.,
                            # 6: Счет корр., 7: Корреспондент, 8: Дебет, 9: Кредит, 10: Назначение платежа

                            date_str = clean_row[1].replace("\n", "")
                            iin_bin = clean_row[3].replace("\n", "")
                            correspondent = clean_row[7].replace("\n", " ")
                            debit_str = clean_row[8]  # Расход
                            credit_str = clean_row[9]  # Приход
                            description = clean_row[10].replace("\n", " ")

                            debit_amount = float(self.clean_amount(debit_str))
                            credit_amount = float(self.clean_amount(credit_str))

                            amount = 0.0
                            t_type = ""

                            # Определяем тип операции
                            if debit_amount > 0:
                                amount = debit_amount
                                t_type = "expense"
                            elif credit_amount > 0:
                                amount = credit_amount
                                t_type = "income"
                            else:
                                continue  # Если везде нули

                            # Форматируем дату. Ожидаем DD.MM.YY или DD.MM.YYYY
                            # Используем regex, так как иногда в ячейку попадают лишние цифры (например, "2100")
                            date_raw = clean_row[1].replace("\n", "").strip()
                            match = re.search(r'(\d{2})\.(\d{2})\.(\d{2,4})', date_raw)
                            payment_date = None
                            if match:
                                d, m, y = match.groups()
                                if not (len(y) == 4 and y.startswith("20")):
                                    # Исправит "2100" -> "2021", "25" -> "2025"
                                    y = f"20{y[:2]}"
                                payment_date = self.parse_date(f"{d}.{m}.{y}")
                            else:
                                payment_date = self.parse_date(date_raw)

                            payment = Payment(
                                date=payment_date,
                                amount=amount,
                                currency="KZT",  # Валюта в шапке документа KZT
                                type=t_type,
                                merchant=description,
                                bank="Otbasy Bank",
                                correspondent=correspondent,
                                iin_bin=iin_bin
                            )
                            result.payments.append(payment)

                        except Exception as e:
                            # Записываем ошибку, если строка сломалась, но продолжаем парсить
                            result.errors.append(ParseError(
                                row=row_idx,
                                column=-1,
                                message=str(e),
                                rawValue=str(clean_row)
                            ))

        return result

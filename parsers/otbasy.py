import pdfplumber
import io
import re
from .base import Parser
from ..models import Payment, ParseError, ParseResult

class OtbasyParser(Parser):
    def can_parse(self, file_bytes: bytes) -> bool:
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                if len(pdf.pages) == 0:
                    return False
                text = pdf.pages[0].extract_text()
                # Ищем характерные маркеры Отбасы банка
                return text and ("ОТБАСЫ БАНК" in text.upper() or "OTBASY" in text.upper())
        except:
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

                            # Форматируем дату из '03.11.25' в '03.11.2025'
                            if len(date_str) == 8:
                                day, month, year = date_str.split('.')
                                date_str = f"{day}.{month}.20{year}"

                            payment = Payment(
                                date=date_str,
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

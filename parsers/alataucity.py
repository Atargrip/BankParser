import pdfplumber
import io
import re

from .base import Parser
from ..models import Payment, ParseError, ParseResult


class AlatauCityParser(Parser):
    def can_parse(self, file_bytes: bytes) -> bool:
        #проверка  на принадлежность к Alatau City
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                if len(pdf.pages) == 0:
                    return False

                first_page_text = pdf.pages[0].extract_text()
                if not first_page_text:
                    return False

                text_lower = first_page_text.lower()
                # Ищем упоминание банка и слово "выписка"
                has_bank = 'alatau city bank' in text_lower
                has_statement = 'выписка' in text_lower

                return has_bank and has_statement
        except:
            return False

    def parse(self, file_bytes: bytes) -> ParseResult:
        result = ParseResult()

        # таблица с линиями
        # используем настройки извлечения по сетке
        table_settings = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
        }

        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page_num, page in enumerate(pdf.pages):

                    # Извлекаем все таблицы на странице
                    tables = page.extract_tables(table_settings)

                    for table in tables:
                        for row_idx, row in enumerate(table):
                            # Очищаем ячейки от пустых значений (None)
                            clean_row = [str(cell).strip() if cell else "" for cell in row]

                            # В таблице Alatau City Bank 13 колонок + Защита от коротких/пустых строк
                            if len(clean_row) < 12:
                                continue

                            # Пропускаем шапку таблицы (если в первой колонке слово "Дата")
                            if 'дата' in clean_row[0].lower() or 'итого' in clean_row[0].lower():
                                continue

                            try:
                                # Дата идет с временем , берем только первую часть
                                date_raw = clean_row[0].split('\n')[0].strip()

                                #прoвоерка. Если дата не похожа на ДД.ММ.ГГГГ, это не строка с транзакцией
                                if not re.match(r'\d{2}\.\d{2}\.\d{4}', date_raw):
                                    continue

                                # Заменяем опечатки 'О' на '0' перед парсингом сумм
                                debit_raw = clean_row[3].replace('О', '0').replace('O', '0')
                                credit_raw = clean_row[4].replace('О', '0').replace('O', '0')

                                merchant_desc = clean_row[8].replace('\n', ' ').strip()
                                correspondent = clean_row[9].replace('\n', ' ').strip()
                                iin_bin_str = clean_row[10].replace('\n', ' ').strip()


                                debit = float(self.clean_amount(debit_raw))
                                credit = float(self.clean_amount(credit_raw))

                                amount = 0.0
                                t_type = ""


                                if debit > 0:
                                    amount = debit
                                    t_type = "expense"
                                elif credit > 0:
                                    amount = credit
                                    t_type = "income"
                                else:
                                    continue  # Пропускаем строки с нулевыми оборотами

                                # Склеиваем корреспондента и назначение платежа в поле merchant
                                merchant_text = f"{correspondent} | {merchant_desc}".strip(" |")

                                payment = Payment(
                                    date=date_raw,
                                    amount=amount,
                                    currency="KZT",
                                    type=t_type,
                                    merchant=merchant_text,
                                    bank="Alatau City Bank",
                                    correspondent=correspondent,
                                    iin_bin=iin_bin_str
                                )
                                result.payments.append(payment)

                            except Exception as e:
                                result.errors.append(ParseError(
                                    row=row_idx,
                                    column=-1,
                                    message=f"Страница {page_num + 1}. Ошибка парсинга: {e}",
                                    rawValue=str(clean_row)
                                ))

        except Exception as e:
            result.errors.append(ParseError(row=0, column=0, message=f"Критическая ошибка: {e}", rawValue=""))

        return result
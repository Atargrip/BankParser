import pdfplumber
import io
import re

from parsers.base import Parser
from models import Payment, ParseError, ParseResult



class NurbankPdfParser(Parser):
    def can_parse(self, file_bytes: bytes) -> bool:
        #Проверка ищет слова 'Нурбанк' и 'Выписка'
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                if len(pdf.pages) == 0:
                    return False

                first_page_text = pdf.pages[0].extract_text()
                if not first_page_text:
                    return False

                text_lower = first_page_text.lower()
                return 'нурбанк' in text_lower and 'выписка' in text_lower
        except:
            return False


    def parse(self, file_bytes: bytes) -> ParseResult:
        result = ParseResult()



        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page_num, page in enumerate(pdf.pages):

                    table = page.extract_table()

                    if not table:
                        continue

                    for row_index, row in enumerate(table):
                        # Очищаем ячейки от None
                        clean_row = [str(cell) if cell else "" for cell in row]

                        # Пропуск заголовков или пустых строк
                        if not clean_row or not clean_row[0] or 'дата' in clean_row[0].lower():
                            continue

                        try:
                            # Защита от коротких строк
                            if len(clean_row) < 6:
                                continue

                            date_str = clean_row[0].strip()
                            doc_num = clean_row[1].strip()

                            # Предварительно меняем букву 'О' на цифру '0' для защиты от ошибок
                            debit_raw = clean_row[2].replace('О', '0').replace('O', '0')
                            credit_raw = clean_row[3].replace('О', '0').replace('O', '0')

                            counterparty_raw = clean_row[4]
                            details_str = clean_row[5].strip()

                            # Если дата пустая или не похожа на дату, пропускаем
                            if not re.match(r'\d{2}\.\d{2}\.\d{4}', date_str):
                                continue

                            # Контрагент и ИИН/БИН склеены переносом строки (\n)
                            counterparty_parts = counterparty_raw.split('\n')
                            counterparty_name = counterparty_parts[0].strip() if len(counterparty_parts) > 0 else ""
                            iin_bin_str = counterparty_parts[1].strip() if len(counterparty_parts) > 1 else ""

                            debit = float(self.clean_amount(debit_raw))
                            credit = float(self.clean_amount(credit_raw))

                            amount = 0.0
                            t_type = ""

                            #  тип транзакции (Расход =expense, Приход = income)
                            if debit > 0:
                                amount = debit
                                t_type = "expense"
                            elif credit > 0:
                                amount = credit
                                t_type = "income"
                            else:
                                continue  # Если везде нули, скип

                            # Если нужен номер документа
                            # merchant_text = f"{counterparty_name} (Док №{doc_num}) | {details_str}"
                            merchant_text = f"{counterparty_name} | {details_str}"

                            payment = Payment(
                                date=self.parse_date(date_str),
                                amount=amount,
                                currency="KZT",
                                type=t_type,
                                merchant=merchant_text.strip(" |"),
                                bank="Nurbank",
                                correspondent=counterparty_name,
                                iin_bin=iin_bin_str
                            )
                            result.payments.append(payment)

                        except Exception as e:
                            result.errors.append(ParseError(
                                row=row_index,
                                column=-1,
                                message=f"Страница {page_num + 1}. Ошибка парсинга: {e}",
                                rawValue=str(clean_row)
                            ))

        except Exception as e:
            result.errors.append(
                ParseError(row=0, column=0, message=f"Критическая ошибка чтения PDF: {e}", rawValue=""))

        return result
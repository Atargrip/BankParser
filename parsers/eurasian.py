import pdfplumber
import io
import re
from parsers.base import Parser
from models import Payment, ParseError, ParseResult


class EurasianParser(Parser):

    def can_parse(self, file_bytes: bytes) -> bool:
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                if len(pdf.pages) == 0:
                    return False

                text = pdf.pages[0].extract_text()

                # Проверяем маркеры Евразийского банка
                return text and (
                    "ЕВРАЗИЙСКИЙ БАНК" in text.upper()
                    or "EURASIAN BANK" in text.upper()
                )

        except:
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

                        clean_row = [
                            str(cell).strip() if cell else "" for cell in row
                        ]

                        if len(clean_row) < 9:
                            continue

                        if not re.match(r"\d{2}\.\d{2}\.\d{4}", clean_row[0]):
                            continue

                        try:

                            # Маппинг колонок из твоего PDF
                            # 0: Дата
                            # 1: № документа
                            # 2: БИК
                            # 3: Счет
                            # 4: ИИН/БИН
                            # 5: Банк корреспондент
                            # 6: Дебет
                            # 7: Кредит
                            # 8: Назначение платежа

                            date_str = clean_row[0]
                            doc_number = clean_row[1]
                            iin_bin = clean_row[4]

                            correspondent = clean_row[5].replace("\n", " ")

                            debit_str = clean_row[6]
                            credit_str = clean_row[7]

                            description = clean_row[8].replace("\n", " ")

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
                                continue

                            payment = Payment(
                                date=date_str,
                                amount=amount,
                                currency="KZT",
                                type=t_type,
                                merchant=description,
                                bank="Eurasian Bank",
                                correspondent=correspondent,
                                iin_bin=iin_bin
                            )

                            result.payments.append(payment)

                        except Exception as e:

                            result.errors.append(
                                ParseError(
                                    row=row_idx,
                                    column=-1,
                                    message=str(e),
                                    rawValue=str(clean_row)
                                )
                            )

        return result
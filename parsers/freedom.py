import pdfplumber
import io
import re

from parsers.base import Parser
from models import Payment, ParseError, ParseResult

class FreedomParser(Parser):
    def can_parse(self, file_bytes: bytes) -> bool:
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                if len(pdf.pages) == 0:
                    return False

                first_page_text = pdf.pages[0].extract_text()
                if not first_page_text:
                    return False

                text = first_page_text.lower()
                return "freedom bank" in text or "фридом банк" in text
        except Exception:
            return False

    def parse(self, file_bytes: bytes) -> ParseResult:
        result = ParseResult()

        table_settings = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
        }

        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    tables = page.extract_tables(table_settings)

                    for table in tables:
                        for row_idx, row in enumerate(table):
                            clean_row = [str(cell).strip() if cell else "" for cell in row]

                            if len(clean_row) < 11:
                                continue

                            if "дата" in clean_row[1].lower():
                                continue

                            try:
                                date_raw = clean_row[1]

                                # Исправлено: год может состоять из 2 или 4 цифр
                                if not re.match(r"\d{2}\.\d{2}\.\d{2,4}", date_raw):
                                    continue

                                correspondent = clean_row[5]
                                iin_bin = clean_row[6]
                                debit_raw = clean_row[8]
                                credit_raw = clean_row[9]
                                merchant_desc = clean_row[10]

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
                                    continue

                                merchant_text = f"{correspondent} | {merchant_desc}".strip(" |")

                                payment = Payment(
                                    date=date_raw,
                                    amount=amount,
                                    currency="KZT",
                                    type=t_type,
                                    merchant=merchant_text,
                                    bank="Freedom Bank",
                                    correspondent=correspondent,
                                    iin_bin=iin_bin
                                )
                                result.payments.append(payment)

                            except Exception as e:
                                result.errors.append(
                                    ParseError(
                                        row=row_idx,
                                        column=-1,
                                        message=f"Страница {page_num+1}: {e}",
                                        rawValue=str(clean_row)
                                    )
                                )

        except Exception as e:
            result.errors.append(
                ParseError(
                    row=0,
                    column=0,
                    message=f"Critical error: {e}",
                    rawValue=""
                )
            )

        return result
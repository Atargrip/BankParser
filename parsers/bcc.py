import pdfplumber
import io
import re
import pandas as pd

from parsers.base import Parser
from models import Payment, ParseError, ParseResult


class BccPdfParser(Parser):

    def can_parse(self, file_bytes: bytes) -> bool:
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                text = pdf.pages[0].extract_text().lower()

                return "центркредит" in text or "bcc" in text
        except:
            return False


    def parse(self, file_bytes: bytes) -> ParseResult:

        result = ParseResult()

        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:

                for page in pdf.pages:

                    table = page.extract_table()

                    if not table:
                        continue

                    for row in table:

                        if not row or len(row) < 9:
                            continue

                        try:

                            date_match = re.search(r'\d{2}\.\d{2}\.\d{4}', str(row[1]))
                            if not date_match:
                                continue

                            d, m, y = date_match.group(0).split('.')
                            formatted_date = f"{y}-{m}-{d}"

                            debit_raw = str(row[7]).replace(',', '.')
                            credit_raw = str(row[8]).replace(',', '.')

                            debit = float(re.sub(r'[^\d.]', '', debit_raw) or 0)
                            credit = float(re.sub(r'[^\d.]', '', credit_raw) or 0)

                            if debit > 0:
                                amount = debit
                                t_type = "expense"
                            elif credit > 0:
                                amount = credit
                                t_type = "income"
                            else:
                                continue

                            merchant = str(row[5]).replace("\n", " ")

                            payment = Payment(
                                date=formatted_date,
                                amount=amount,
                                currency="KZT",
                                type=t_type,
                                merchant=merchant,
                                bank="BCC"
                            )

                            result.payments.append(payment)

                        except:
                            continue

        except Exception as e:

            result.errors.append(
                ParseError(
                    row=0,
                    column=0,
                    message=str(e),
                    rawValue=""
                )
            )

        return result



class BccExcelParser(Parser):

    def can_parse(self, file_bytes: bytes) -> bool:
        try:
            pd.read_excel(io.BytesIO(file_bytes))
            return True
        except:
            return False


    def parse(self, file_bytes: bytes) -> ParseResult:

        result = ParseResult()

        try:

            df = pd.read_excel(io.BytesIO(file_bytes))

            for _, row in df.iterrows():

                try:

                    date_match = re.search(r'\d{2}\.\d{2}\.\d{4}', str(row[1]))
                    if not date_match:
                        continue

                    d, m, y = date_match.group(0).split('.')
                    formatted_date = f"{y}-{m}-{d}"

                    debit = float(str(row[7]).replace(',', '.')) if str(row[7]) != "nan" else 0
                    credit = float(str(row[8]).replace(',', '.')) if str(row[8]) != "nan" else 0

                    if debit > 0:
                        amount = debit
                        t_type = "expense"
                    elif credit > 0:
                        amount = credit
                        t_type = "income"
                    else:
                        continue

                    merchant = str(row[5])

                    payment = Payment(
                        date=formatted_date,
                        amount=amount,
                        currency="KZT",
                        type=t_type,
                        merchant=merchant,
                        bank="BCC"
                    )

                    result.payments.append(payment)

                except:
                    continue

        except Exception as e:

            result.errors.append(
                ParseError(
                    row=0,
                    column=0,
                    message=str(e),
                    rawValue=""
                )
            )

        return result

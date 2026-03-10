import pdfplumber
import io
import re

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

                text = ""

                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text += "\n" + t

                # операция строкаларын іздеу
                pattern = r'(\d{4}-\d{2}-\d{2}).*?\n.*?\n(.*?)\n.*?(-?\d[\d\s]+\.\d{2})\s*KZT'

                matches = re.findall(pattern, text, re.DOTALL)

                for m in matches:

                    date = m[0]
                    description = m[1].strip()

                    amount_raw = m[2].replace(" ", "")
                    amount = float(amount_raw)

                    t_type = "income"

                    if amount < 0:
                        t_type = "expense"
                        amount = abs(amount)

                    payment = Payment(
                        date=date,
                        amount=amount,
                        currency="KZT",
                        type=t_type,
                        merchant=description,
                        bank="BCC"
                    )

                    result.payments.append(payment)

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
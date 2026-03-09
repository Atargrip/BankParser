import io
import re

import pdfplumber

from .base import Parser
from ..models import Payment, ParseError, ParseResult


class RBKParser(Parser):
    def can_parse(self, file_bytes: bytes) -> bool:
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                if len(pdf.pages) == 0:
                    return False
                first_page_text = (pdf.pages[0].extract_text() or "").upper()
                return "BANK RBK" in first_page_text and "ВЫПИСКА ПО ЛИЦЕВОМУ СЧЕТУ" in first_page_text
        except Exception:
            return False

    def parse(self, file_bytes: bytes) -> ParseResult:
        result = ParseResult()

        table_settings = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
        }

        currency = "KZT"
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            if len(pdf.pages) > 0:
                first_page_text = pdf.pages[0].extract_text() or ""
                currency_match = re.search(r"Валюта\s*:\s*([A-Z]{3})", first_page_text, flags=re.IGNORECASE)
                if currency_match:
                    currency = currency_match.group(1).upper()

            for page in pdf.pages:
                tables = page.extract_tables(table_settings)
                for table in tables:
                    for row_idx, row in enumerate(table):
                        clean_row = [str(cell).strip() if cell else "" for cell in row]

                        if len(clean_row) < 8:
                            continue
                        if not re.match(r"^\d+$", clean_row[0]):
                            continue

                        try:
                            date_value = clean_row[1].split()[0] if clean_row[1] else ""
                            sender_cell = clean_row[3]
                            receiver_cell = clean_row[4]
                            debit_str = clean_row[5]
                            credit_str = clean_row[6]
                            description = clean_row[7].replace("\n", " ").strip()

                            debit_amount = float(self.clean_amount(debit_str))
                            credit_amount = float(self.clean_amount(credit_str))

                            if debit_amount > 0:
                                amount = debit_amount
                                payment_type = "expense"
                                correspondent_cell = receiver_cell
                            elif credit_amount > 0:
                                amount = credit_amount
                                payment_type = "income"
                                correspondent_cell = sender_cell
                            else:
                                continue

                            correspondent_lines = [line.strip() for line in correspondent_cell.split("\n") if line.strip()]
                            correspondent = correspondent_lines[0] if correspondent_lines else None

                            iin_bin_match = re.search(r"(?:БИН|ИИН)\s*:\s*([0-9]{12})", correspondent_cell)
                            iin_bin = iin_bin_match.group(1) if iin_bin_match else None

                            payment = Payment(
                                date=date_value,
                                amount=amount,
                                currency=currency,
                                type=payment_type,
                                merchant=description,
                                bank="Bank RBK",
                                correspondent=correspondent,
                                iin_bin=iin_bin,
                            )
                            result.payments.append(payment)
                        except Exception as e:
                            result.errors.append(
                                ParseError(
                                    row=row_idx,
                                    column=-1,
                                    message=str(e),
                                    rawValue=str(clean_row),
                                )
                            )

        return result

import io
import re

import pdfplumber
import xlrd

from parsers.base import Parser
from models import Payment, ParseError, ParseResult

# OLE2 compound document magic bytes (used by .xls BIFF format)
_XLS_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"


class RBKParser(Parser):
    def can_parse(self, file_bytes: bytes) -> bool:
        if file_bytes[:8] == _XLS_MAGIC:
            return self._can_parse_xls(file_bytes)
        return self._can_parse_pdf(file_bytes)

    def _can_parse_pdf(self, file_bytes: bytes) -> bool:
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                if len(pdf.pages) == 0:
                    return False
                first_page_text = (pdf.pages[0].extract_text() or "").upper()
                return "BANK RBK" in first_page_text and "ВЫПИСКА ПО ЛИЦЕВОМУ СЧЕТУ" in first_page_text
        except Exception:
            return False

    def _can_parse_xls(self, file_bytes: bytes) -> bool:
        try:
            wb = xlrd.open_workbook(file_contents=file_bytes)
            sh = wb.sheet_by_index(0)
            return (
                sh.name == "report_acc_statement"
                and "ВЫПИСКА ПО ЛИЦЕВОМУ СЧЕТУ" in str(sh.cell_value(1, 0)).upper()
            )
        except Exception:
            return False

    def parse(self, file_bytes: bytes) -> ParseResult:
        if file_bytes[:8] == _XLS_MAGIC:
            return self._parse_xls(file_bytes)
        return self._parse_pdf(file_bytes)

    def _parse_xls(self, file_bytes: bytes) -> ParseResult:
        result = ParseResult()
        wb = xlrd.open_workbook(file_contents=file_bytes)
        sh = wb.sheet_by_index(0)

        currency = "KZT"
        for r in range(sh.nrows):
            currency_match = re.search(r"Валюта\s*:\s*([A-Z]{3})", str(sh.cell_value(r, 0)), re.IGNORECASE)
            if currency_match:
                currency = currency_match.group(1).upper()
                break

        # Find header row (contains "№" in col 0)
        data_start = 0
        for r in range(sh.nrows):
            if str(sh.cell_value(r, 0)).strip() == "№":
                data_start = r + 1
                break

        for row_idx in range(data_start, sh.nrows):
            try:
                num_val = sh.cell_value(row_idx, 0)
                if not num_val:
                    continue

                date_value = str(sh.cell_value(row_idx, 1)).strip()
                sender_cell = str(sh.cell_value(row_idx, 3))
                receiver_cell = str(sh.cell_value(row_idx, 4))
                debit_amount = float(sh.cell_value(row_idx, 5) or 0)
                credit_amount = float(sh.cell_value(row_idx, 6) or 0)
                description = str(sh.cell_value(row_idx, 7)).replace("\n", " ").strip()

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

                result.payments.append(Payment(
                    date=self.parse_date(date_value),
                    amount=amount,
                    currency=currency,
                    type=payment_type,
                    merchant=description,
                    bank="Bank RBK",
                    correspondent=correspondent,
                    iin_bin=iin_bin,
                ))
            except Exception as e:
                result.errors.append(ParseError(
                    row=row_idx,
                    column=-1,
                    message=str(e),
                    rawValue=str([sh.cell_value(row_idx, c) for c in range(sh.ncols)]),
                ))

        return result

    def _parse_pdf(self, file_bytes: bytes) -> ParseResult:
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
                                date=self.parse_date(date_value),
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

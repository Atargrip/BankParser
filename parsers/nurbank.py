import pandas as pd
import pdfplumber
import io
import re

from .base import Parser
from ..models import Payment, ParseResult, ParseError

# Магические байты для определения формата файла
_PDF_MAGIC = b"%PDF"
_XLS_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
_XLSX_MAGIC = b"PK\x03\x04"


def clean_float(val) -> float:
    """Очищает строку и превращает её в float."""
    if pd.isna(val) or str(val).strip() == '':
        return 0.0

    cleaned = str(val).replace(' ', '').replace('\xa0', '').replace(',', '.')
    cleaned = cleaned.replace('O', '0').replace('o', '0').replace('О', '0').replace('о', '0')

    try:
        return float(cleaned)
    except ValueError as e:
        raise ValueError(f"Невозможно преобразовать значение '{val}' в число.") from e


class NurbankParser(Parser):
    def can_parse(self, file_bytes: bytes) -> bool:
        """Определяет формат и направляет в нужный обработчик."""
        if file_bytes.startswith(_PDF_MAGIC):
            return self._can_parse_pdf(file_bytes)
        elif file_bytes.startswith(_XLS_MAGIC) or file_bytes.startswith(_XLSX_MAGIC):
            return self._can_parse_excel(file_bytes)
        return False

    def parse(self, file_bytes: bytes) -> ParseResult:
        """Запускает парсинг в зависимости от формата."""
        if file_bytes.startswith(_PDF_MAGIC):
            return self._parse_pdf(file_bytes)
        elif file_bytes.startswith(_XLS_MAGIC) or file_bytes.startswith(_XLSX_MAGIC):
            return self._parse_excel(file_bytes)

        result = ParseResult()
        result.errors.append(ParseError(row=0, column=0, message="Неподдерживаемый формат файла", rawValue=""))
        return result

    # ==========================================
    #               ЛОГИКА ДЛЯ PDF
    # ==========================================
    def _can_parse_pdf(self, file_bytes: bytes) -> bool:
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                if len(pdf.pages) == 0:
                    return False
                first_page_text = pdf.pages[0].extract_text()
                if not first_page_text:
                    return False
                text_lower = first_page_text.lower()
                return 'нурбанк' in text_lower and 'выписка' in text_lower
        except Exception:
            return False

    def _parse_pdf(self, file_bytes: bytes) -> ParseResult:
        result = ParseResult()
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    table = page.extract_table()
                    if not table:
                        continue

                    for row_index, row in enumerate(table):
                        clean_row = [str(cell) if cell else "" for cell in row]

                        if not clean_row or not clean_row[0] or 'дата' in clean_row[0].lower():
                            continue

                        try:
                            if len(clean_row) < 6:
                                continue

                            date_str = clean_row[0].strip()
                            debit_raw = clean_row[2].replace('О', '0').replace('O', '0')
                            credit_raw = clean_row[3].replace('О', '0').replace('O', '0')
                            counterparty_raw = clean_row[4]
                            details_str = clean_row[5].strip()

                            if not re.match(r'\d{2}\.\d{2}\.\d{4}', date_str):
                                continue

                            counterparty_parts = counterparty_raw.split('\n')
                            counterparty_name = counterparty_parts[0].strip() if len(counterparty_parts) > 0 else ""
                            iin_bin_str = counterparty_parts[1].strip() if len(counterparty_parts) > 1 else ""

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

                            merchant_text = f"{counterparty_name} | {details_str}".strip(" |")

                            payment = Payment(
                                date=date_str,
                                amount=amount,
                                currency="KZT",
                                type=t_type,
                                merchant=merchant_text,
                                bank="Nurbank",
                                correspondent=counterparty_name,
                                iin_bin=iin_bin_str
                            )
                            result.payments.append(payment)

                        except Exception as e:
                            result.errors.append(
                                ParseError(row=row_index, column=-1, message=f"Ошибка: {e}", rawValue=str(clean_row)))
        except Exception as e:
            result.errors.append(
                ParseError(row=0, column=0, message=f"Критическая ошибка чтения PDF: {e}", rawValue=""))

        return result

    # ==========================================
    #               ЛОГИКА ДЛЯ EXCEL
    # ==========================================
    def _get_excel_engine(self, file_bytes: bytes) -> str:
        """Возвращает нужный движок pandas в зависимости от формата Excel."""
        if file_bytes.startswith(_XLSX_MAGIC):
            return "openpyxl"
        return "xlrd"

    def _can_parse_excel(self, file_bytes: bytes) -> bool:
        engine = self._get_excel_engine(file_bytes)
        try:
            df = pd.read_excel(io.BytesIO(file_bytes), header=None, nrows=50, engine=engine)
        except Exception as e:
            print(f"[CanParse] Ошибка чтения Excel файла Нурбанка: {e}")
            return False

        bank_found = False
        table_found = False

        for _, row in df.iterrows():
            row_text = ' '.join([str(val).lower().replace('\n', ' ') for val in row.values if pd.notna(val)])
            if 'наименование банка' in row_text and 'нурбанк' in row_text:
                bank_found = True
            if 'дата' in row_text and 'дебет' in row_text and 'кредит' in row_text and 'кнп' in row_text:
                table_found = True
            if bank_found and table_found:
                return True
        return False

    def _parse_excel(self, file_bytes: bytes) -> ParseResult:
        result = ParseResult()
        engine = self._get_excel_engine(file_bytes)
        try:
            df_raw = pd.read_excel(io.BytesIO(file_bytes), header=None, engine=engine)
            table_start_index = -1

            for index, row in df_raw.iterrows():
                row_text = ' '.join([str(val).lower() for val in row.values if pd.notna(val)])
                if 'дата' in row_text and 'дебет' in row_text and 'кредит' in row_text:
                    table_start_index = index
                    break

            if table_start_index == -1:
                result.errors.append(ParseError(row=0, column=0, message="Не найдена шапка таблицы.", rawValue=""))
                return result

            df = df_raw.iloc[table_start_index + 1:].copy()
            headers = df_raw.iloc[table_start_index].copy()
            df.columns = [' '.join(str(c).split()) for c in headers]

            for index, row in df.iterrows():
                excel_row = table_start_index + index + 2
                no_pp_str = str(row.get('№ п.п.', '')).strip()
                if no_pp_str.endswith('.0'):
                    no_pp_str = no_pp_str[:-2]
                if not no_pp_str.isdigit() or no_pp_str == '':
                    continue

                try:
                    debit = clean_float(row.get('Дебет'))
                    credit = clean_float(row.get('Кредит'))
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

                    correspondent = str(row.get('Контрагент', '')).strip()
                    details = str(row.get('Детали операции', '')).strip()
                    merchant_text = f"{correspondent} | {details}".strip(" |")

                    payment = Payment(
                        date=str(row.get('Дата', '')).strip(),  # Желательно пропустить через self.parse_date()
                        amount=amount,
                        currency="KZT",
                        type=t_type,
                        merchant=merchant_text,
                        bank="Nurbank",
                        correspondent=correspondent,
                        iin_bin=str(row.get('ИИН/БИН', '')).strip()
                    )
                    result.payments.append(payment)

                except ValueError as ve:
                    result.errors.append(ParseError(row=excel_row, column=-1, message=f"Ошибка суммы: {ve}",
                                                    rawValue=str(row.to_dict())))
                except Exception as e:
                    result.errors.append(ParseError(row=excel_row, column=-1, message=f"Ошибка строки: {e}",
                                                    rawValue=str(row.to_dict())))

        except Exception as e:
            result.errors.append(
                ParseError(row=0, column=0, message=f"Критическая ошибка извлечения Excel: {e}", rawValue=""))

        return result
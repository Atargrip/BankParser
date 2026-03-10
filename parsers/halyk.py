import pdfplumber
import io
import re
from .base import Parser
from ..models import Payment, ParseError, ParseResult

class HalykParser(Parser):
    def can_parse(self, file_bytes: bytes) -> bool:
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                if not pdf.pages:
                    return False

                page = pdf.pages[0]

                TARGET_WIDTH = 96.0
                TARGET_HEIGHT = 35.0
                TOLERANCE = 0.5

                if hasattr(page, 'images'):
                    for img in page.images:
                        try:
                            w = float(img.get('width', 0))
                            h = float(img.get('height', 0))

                            # проверка с погрешностью
                            w_ok = abs(w - TARGET_WIDTH) <= TOLERANCE
                            h_ok = abs(h - TARGET_HEIGHT) <= TOLERANCE

                            if w_ok and h_ok:
                                return True
                        except (ValueError, TypeError):
                            continue

                return False
        except Exception:
            return False

    def parse(self, file_bytes: bytes) -> ParseResult:
        result = ParseResult()

        table_settings = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 4,
            "text_x_tolerance": 2,
            "text_y_tolerance": 2,
        }

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables(table_settings)
                for table in tables:
                    for row_idx, row in enumerate(table):
                        clean_row = [str(cell) if cell else "" for cell in row]
                        if len(clean_row) < 4: continue

                        col_date = clean_row[0].replace("\n", " ")
                        col_desc = " ".join(clean_row[2].split())
                        col_amount = clean_row[3]

                        # Фильтры заголовков
                        if "Дата" in col_date or "Всего" in col_date or not re.search(r'\d{2}\.\d{2}\.\d{4}', col_date):
                            continue

                        try:
                            # Используем метод clean_amount из базового класса
                            amount = float(self.clean_amount(col_amount))
                            if amount == 0: continue

                            t_type = "expense" if amount < 0 else "income"

                            # Вместо словаря создаем объект Payment (как требует ТЗ)
                            payment = Payment(
                                date=col_date.split()[0],  # 02.12.2025
                                merchant=col_desc.strip(),
                                amount=abs(amount),
                                currency=clean_row[4].replace("\n", ""),
                                type=t_type,
                                bank="Halyk Bank"
                            )
                            result.payments.append(payment)

                        except Exception as e:
                            # Если что-то пошло не так, логируем ошибку в массив errors
                            result.errors.append(ParseError(
                                row=row_idx,
                                column=-1,
                                message=str(e),
                                rawValue=str(clean_row)
                            ))

        return result

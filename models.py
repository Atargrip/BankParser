from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Payment:
    date: str
    amount: float
    currency: str
    type: str  # "income" или "expense"
    merchant: str  # Назначение платежа или имя корреспондента
    bank: str
    # Дополнительные поля, которые есть в выписке Отбасы банка
    correspondent: Optional[str] = None
    iin_bin: Optional[str] = None


@dataclass
class ParseError:
    row: int
    column: int
    message: str
    rawValue: str


@dataclass
class ParseResult:
    payments: List[Payment] = field(default_factory=list)
    errors: List[ParseError] = field(default_factory=list)

import sys
import os
from processor import StatementProcessor

def main():
    if len(sys.argv) < 2:
        print("Использование: python main.py <путь_к_pdf_файлу>")
        return

    file_path = sys.argv[1]
    processor = StatementProcessor()
    
    print(f"Обработка файла: {file_path}...")
    result = processor.process_file(file_path)

    if result.payments:
        print(f"\nНайдено платежей: {len(result.payments)}")
        for i, payment in enumerate(result.payments[:], 1):
            print(f"{i}. {payment.date} | {payment.amount} {payment.currency} | {payment.type} | {payment.bank}")
            print(f"   Мерчант: {payment.merchant[:50]}...")
        #
        # if len(result.payments) > 5:
        #     print(f"... и еще {len(result.payments) - 5} платежей")
    else:
        print("\nПлатежи не найдены.")

    if result.errors:
        print(f"\nОшибки при парсинге ({len(result.errors)}):")
        for error in result.errors:
            print(f"Ошибка в строке {error.row}: {error.message}")

if __name__ == "__main__":
    main()


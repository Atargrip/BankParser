from processor import StatementProcessor

processor = StatementProcessor()

result = processor.process_file("documents/bcc.pdf")

print("PAYMENTS:")
for p in result.payments:
    print(p)

print("\nERRORS:")
for e in result.errors:
    print(e)
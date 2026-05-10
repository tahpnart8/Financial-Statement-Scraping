"""Debug script to test if pdfplumber can read uploaded PDFs."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import pdfplumber
import os
import tempfile

# Test with the actual DMC PDF
pdf_path = r'c:\Users\User\Downloads\DMC_Baocaotaichinh_2024_Kiemtoan_29042025155940.pdf'

if not os.path.exists(pdf_path):
    print(f"ERROR: File not found: {pdf_path}")
    # List available PDFs
    for f in os.listdir(r'c:\Users\User\Downloads'):
        if f.lower().endswith('.pdf') and 'DMC' in f.upper():
            print(f"  Found: {f}")
    sys.exit(1)

print(f"Testing PDF: {pdf_path}")
print(f"File size: {os.path.getsize(pdf_path)} bytes")

with pdfplumber.open(pdf_path) as pdf:
    print(f"Total pages: {len(pdf.pages)}")
    
    for i in range(min(5, len(pdf.pages))):
        page = pdf.pages[i]
        text = page.extract_text()
        layout = page.extract_text(layout=True)
        
        print(f"\n--- Page {i+1} ---")
        print(f"  extract_text(): {len(text) if text else 0} chars | None={text is None}")
        print(f"  extract_text(layout=True): {len(layout) if layout else 0} chars | None={layout is None}")
        
        if text:
            print(f"  Preview: {text[:150]}...")

# Now test what the extract function would return
print("\n\n=== Testing extract_financial_tables_from_pdf() ===")
from app.services.pdf_extractor import extract_financial_tables_from_pdf
result = extract_financial_tables_from_pdf(pdf_path)
if result:
    print(f"SUCCESS: Got {len(result)} chars of output")
    print(f"First 500 chars:\n{result[:500]}")
else:
    print("FAILURE: Function returned None!")

# Also test with a temp file (simulating upload)
print("\n\n=== Testing with temp file (simulating upload) ===")
with open(pdf_path, 'rb') as f:
    content = f.read()

with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
    tmp.write(content)
    tmp_path = tmp.name

print(f"Temp path: {tmp_path}")
print(f"Temp size: {os.path.getsize(tmp_path)} bytes")

result2 = extract_financial_tables_from_pdf(tmp_path)
if result2:
    print(f"SUCCESS: Got {len(result2)} chars from temp file")
else:
    print("FAILURE: Function returned None from temp file!")

os.remove(tmp_path)

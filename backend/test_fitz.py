"""Test pymupdf (fitz) on the scanned PDF."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import fitz  # pymupdf

pdf_path = r'c:\Users\User\Downloads\DMC_Baocaotaichinh_2024_Kiemtoan_29042025155940.pdf'

doc = fitz.open(pdf_path)
print(f"Total pages: {len(doc)}")

for i in range(min(5, len(doc))):
    page = doc[i]
    text = page.get_text()
    print(f"\n--- Page {i+1} ---")
    print(f"  Text length: {len(text)} chars")
    if text.strip():
        print(f"  Preview: {text[:300]}...")
    else:
        print("  EMPTY - This is likely a scanned image page")
        # Check if there are images on this page
        images = page.get_images()
        print(f"  Number of images: {len(images)}")

doc.close()

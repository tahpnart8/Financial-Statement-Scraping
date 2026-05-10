"""Quick test: Can Groq Vision read a scanned PDF page?"""
import sys, os, base64, io, json
sys.stdout.reconfigure(encoding='utf-8')

import fitz  # pymupdf
from groq import Groq

pdf_path = r'c:\Users\User\Downloads\DMC_Baocaotaichinh_2024_Kiemtoan_29042025155940.pdf'

# 1. Extract page 5 as image (likely a financial table page)
doc = fitz.open(pdf_path)
page = doc[4]  # 0-indexed, page 5

# Render page to PNG image at 150 DPI (good quality, reasonable size)
pix = page.get_pixmap(dpi=150)
img_bytes = pix.tobytes("png")
img_base64 = base64.b64encode(img_bytes).decode('utf-8')

print(f"Image size: {len(img_bytes)} bytes")
print(f"Base64 length: {len(img_base64)} chars")

# 2. Send to Groq Vision
client = Groq()

response = client.chat.completions.create(
    model="llama-3.2-90b-vision-preview",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text", 
                    "text": "Đây là 1 trang trong Báo cáo tài chính. Hãy đọc toàn bộ nội dung text và số liệu trên trang này. Trả về nguyên văn text bạn đọc được."
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_base64}"
                    }
                }
            ]
        }
    ],
    max_tokens=4096,
    temperature=0.1
)

result = response.choices[0].message.content
print(f"\n=== GROQ VISION OUTPUT (page 5) ===")
print(result[:2000])

doc.close()

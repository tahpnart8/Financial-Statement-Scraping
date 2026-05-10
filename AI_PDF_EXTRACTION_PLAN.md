# Kế Hoạch Nâng Cấp Hệ Thống: Trích Xuất BCTC Từ File PDF Bằng AI (Phiên bản Cloud/Serverless)

Tài liệu này trình bày kiến trúc và logic nâng cấp hệ thống cào dữ liệu BCTC, được tinh chỉnh đặc biệt để **triển khai trên các nền tảng Cloud miễn phí (Render cho Backend, Vercel cho Frontend, Supabase làm Database/Storage)** phục vụ quy mô nội bộ. Mục tiêu là dùng AI (Groq Llama) và OCR để lấp đầy 100% dữ liệu lịch sử.

## 1. Kiến Trúc Hệ Thống Cloud-Native (Architecture)

Vì hệ thống chạy trên **Render (Free Tier)** (có giới hạn nghiêm ngặt về RAM và dung lượng đĩa) và **Supabase**, kiến trúc phải đảm bảo tính **Stateless (Không lưu trạng thái)** và **Ephemeral (Phù du - dùng xong xóa ngay)**.

```mermaid
[Vercel FE] -> [Render BE] -> [Download PDF to /tmp or Supabase] -> [Cloud OCR / Lightweight Parser] -> [Groq Llama API] -> [Excel Writer] -> [Return Excel & Cleanup]
```

### 1.1. Giải pháp Lưu trữ PDF ngắn hạn (Ephemeral Storage)
Render có thư mục `/tmp` nhưng dung lượng rất hạn chế. Để an toàn và chuyên nghiệp:
*   **Phương án 1 (Stream In-Memory):** Tải file PDF dưới dạng bytes (stream) vào RAM, đọc nội dung, gửi cho AI và giải phóng RAM ngay lập tức. (Không lưu file vật lý).
*   **Phương án 2 (Supabase Storage TTL):** Tải file lên Supabase Storage bucket (được cấp miễn phí). Chạy một cronjob hoặc trigger trên Supabase tự động xóa các file có `created_at` cũ hơn 10 phút.
*   **Phương án 3 (Render `/tmp` + Auto Cleanup):** Lưu file vào `/tmp` của Render. Ngay sau khi vòng lặp tạo ra file Excel hoàn tất (khoảng 1-2 phút), gọi hàm `os.remove()` để xóa sạch file PDF và giải phóng bộ nhớ. (Ưu tiên phương án này vì dễ code nhất, không phụ thuộc kết nối DB).

### 1.2. Giải pháp OCR trên Cloud
Trên local, ta có thể cài các thư viện nặng (Tesseract, Marker). Nhưng trên Render Free, việc cài đặt và chạy các model AI/OCR nội bộ sẽ làm sập server (Out of Memory).
*   **Xử lý PDF chuẩn (Text-based):** Sử dụng thư viện `pdfplumber` hoặc `PyMuPDF (fitz)`. Đây là các thư viện Python thuần túy, cực nhẹ, chạy hoàn toàn trơn tru trên Render Free. Hầu hết BCTC từ 2013 đến nay đều là dạng này.
*   **Xử lý PDF dạng ảnh scan (Scanned PDF):** Không chạy OCR trên Render. Ta sẽ sử dụng một **Cloud OCR API miễn phí**:
    *   *OCR.space API:* Cấp 25,000 request/tháng miễn phí. Quá đủ cho nhu cầu cá nhân.
    *   *Google Cloud Vision API:* Miễn phí 1000 trang đầu tiên mỗi tháng. Cực kỳ chính xác với tiếng Việt.

### 1.3. Trình xử lý LLM (Groq Llama)
Sử dụng `llama3-70b-8192` qua **Groq API**. Tốc độ siêu nhanh, hoàn toàn miễn phí hiện tại và không tốn tài nguyên của server Render.

## 2. Logic Hoạt Động Chi Tiết (Workflow)

### Bước 1: Tiếp nhận Request & Thu thập PDF
*   User nhập mã chứng khoán (VD: DMC) và dải năm (2015).
*   Backend (Render) quét link PDF kiểm toán từ trang CafeF hoặc UBCKNN.
*   Backend tải file PDF về thư mục `/tmp` của server Render.

### Bước 2: Phân Tích PDF & Trích Xuất Bảng (Lightweight)
*   Sử dụng `pdfplumber` (chạy trực tiếp trên Render) để tìm trang có chứa tiêu đề BCTC.
*   Nếu `pdfplumber` không trích xuất được chữ (tức là file scan), Backend gửi file đó lên **OCR.space API** (hoặc Google Vision API) để lấy text.
*   Chuyển đổi dữ liệu thô thành định dạng **Markdown tables**.

### Bước 3: Đẩy cho LLM xử lý (Groq API)
*   Gửi Markdown Table kèm Prompt hệ thống cho Groq API.
*   Groq API trả về chuỗi JSON chứa các chỉ tiêu tài chính đã được chuẩn hóa (map chuẩn với key của template).

### Bước 4: Hợp nhất Dữ liệu & Xuất Excel
*   Hợp nhất dữ liệu 8 năm từ API Vietcap và các năm cũ (từ Llama).
*   Ghi vào 1 sheet duy nhất là `BCTC du phong` bằng thư viện `openpyxl`.

### Bước 5: XÓA DỌN DẸP (Garbage Collection)
*   Đây là bước **bắt buộc** trước khi trả Request về cho Frontend.
*   Backend gọi lệnh xóa file PDF ở `/tmp`, xóa file Excel ở `/tmp` (sau khi đã upload hoặc stream trả về cho user).
*   Đảm bảo dung lượng đĩa của Render luôn trở về 0.

## 3. Các Giới Hạn Cần Lưu Ý
*   **Render Free Tier:** Sẽ bị "ngủ đông" (sleep) nếu không có ai truy cập trong 15 phút. Khi người dùng đầu tiên vào, sẽ mất 1-2 phút để server thức dậy.
*   **Timeout của Vercel/Render:** Các gói free thường có giới hạn timeout request (Render: ko giới hạn, nhưng Vercel Free: 10-60 giây). Vì quá trình tải PDF -> OCR -> LLM -> Excel có thể mất 2-3 phút, Frontend (Vercel) không thể chờ HTTP Request thông thường.
    *   *Giải pháp:* Backend sẽ trả về `job_id` ngay lập tức. Quá trình tải và xử lý PDF chạy ngầm (Background Task). Frontend dùng cơ chế **Polling** (gọi API 3 giây/lần) để hỏi Backend xem tiến trình đến đâu, khi nào xong thì lấy link tải Excel. (Hệ thống hiện tại đã có cơ chế Polling này).

# Benchmark Chung Nhóm — Lab 7

> Bộ benchmark thống nhất cho cả nhóm. Mọi thành viên dùng **cùng tập tài liệu**, **cùng 5 queries**, và **cùng gold answers** để so sánh strategy chunking / metadata một cách công bằng. Kết quả retrieval của mỗi người được đưa vào `report/REPORT.md` mục 6.

---

## 1. Domain

**Domain:** VinFast vehicle documentation (spec + warranty + first-responder guide)

**Lý do chọn:**
- Tài liệu có sẵn trong [data/processed/](data/processed/), không cần thu thập thêm.
- Nội dung **hỗn hợp song ngữ** (tiếng Việt + tiếng Anh), phù hợp để test embedder đa ngôn ngữ.
- Có nhiều **dạng nội dung khác nhau**: bảng thông số kỹ thuật (spec sheet), văn bản chính sách (warranty), hướng dẫn kỹ thuật (first responder guide) — đủ đa dạng để các chiến lược chunking bộc lộ điểm mạnh/yếu.
- Gold answer dễ xác minh vì là dữ kiện cụ thể (con số, thời hạn, quy trình).

---

## 2. Tập Tài Liệu Chung (5 files)

Cả nhóm chỉ load **đúng 5 file dưới đây** để bảo đảm so sánh công bằng. Không thêm, không bớt.

| # | File | Ngôn ngữ | Loại nội dung | Size (bytes) |
|---|------|----------|---------------|--------------|
| 1 | [data/processed/VF3_spec.txt](data/processed/VF3_spec.txt) | EN | Spec sheet dạng bảng | ~5 KB |
| 2 | [data/processed/vf3_vn_warranty.txt](data/processed/vf3_vn_warranty.txt) | VI | Chính sách bảo hành VF3 | ~24 KB |
| 3 | [data/processed/20230927_VF6_VN_VN_1_1706781000_Warranty.txt](data/processed/20230927_VF6_VN_VN_1_1706781000_Warranty.txt) | VI | Chính sách bảo hành VF6 | ~39 KB |
| 4 | [data/processed/VF9 US Vehicle Warranty Booklet.txt](data/processed/VF9%20US%20Vehicle%20Warranty%20Booklet.txt) | EN | Warranty booklet VF9 (US) | ~37 KB |
| 5 | [data/processed/VINFAST_VF8_First_Responder_Guide.txt](data/processed/VINFAST_VF8_First_Responder_Guide.txt) | EN | First responder guide VF8 | ~18 KB |

---

## 3. Metadata Schema Chung

Mỗi chunk phải được gán các trường metadata sau khi add vào `EmbeddingStore`. Nhóm thống nhất schema này để `search_with_filter()` cho kết quả so sánh được.

| Trường | Kiểu | Giá trị hợp lệ | Ghi chú |
|--------|------|----------------|---------|
| `doc_id` | str | Tên file không đuôi | Khóa định danh tài liệu nguồn |
| `model` | str | `VF3`, `VF6`, `VF8`, `VF9` | Mẫu xe được nhắc đến |
| `doc_type` | str | `spec`, `warranty`, `first_responder` | Loại tài liệu |
| `language` | str | `vi`, `en` | Ngôn ngữ chính của chunk |
| `region` | str | `VN`, `US`, `global` | Thị trường áp dụng (warranty có phạm vi khác nhau) |

---

## 4. Benchmark Queries & Gold Answers

Tất cả thành viên chạy **đúng 5 queries dưới đây**, không paraphrase. Chạy qua cả `EmbeddingStore.search()` (top-k=3) và `KnowledgeBaseAgent.answer()`.

### Query 1 — Spec lookup (EN, trả về số cụ thể)

**Query:** `What is the battery capacity and range of the VinFast VF3?`

**Gold answer:**
- Battery type: LFP
- Battery capacity: **18.64 kWh**
- Range per full charge: **~210 km** (NEDC)

**Nguồn:** [VF3_spec.txt](data/processed/VF3_spec.txt) — phần "POWER TRAIN SYSTEM → Battery"

**Relevant nếu top-3 chứa:** chunk với các từ "Battery capacity", "18.64", "Range per full charge", "210"

---

### Query 2 — Warranty policy lookup (VI, dữ kiện chính sách)

**Query:** `Thời hạn bảo hành chung của xe VinFast VF3 là bao lâu?`

**Gold answer:**
- **7 năm** hoặc **160.000 km** tùy điều kiện nào đến trước (sử dụng thông thường)
- **3 năm** hoặc **100.000 km** nếu dùng cho mục đích thương mại (taxi, Grab, xe giao hàng...)
- Thời hạn tính từ **Ngày Kích Hoạt Bảo Hành**

**Nguồn:** [vf3_vn_warranty.txt](data/processed/vf3_vn_warranty.txt) — mục "5. THỜI HẠN BẢO HÀNH XE MỚI"

**Relevant nếu top-3 chứa:** chunk với "7 năm", "160.000 km", "Ngày Kích Hoạt Bảo Hành"

---

### Query 3 — Exclusion / negative case (VI, yêu cầu chunk liệt kê loại trừ)

**Query:** `Những hư hỏng nào không được VinFast bảo hành?`

**Gold answer (ít nhất 3 trong các mục sau):**
- Hư hỏng do sửa chữa/hoán cải trái phép, lắp phụ kiện không chính hãng
- Hư hỏng do sử dụng sai chức năng, lạm dụng xe (đua xe, chở quá tải, đường gồ ghề)
- Hư hỏng do thiên tai (hỏa hoạn, động đất, bão, sét, lũ lụt) hoặc động vật
- Hư hỏng do tai nạn, ngập nước, ngoại vật
- Hao mòn tự nhiên (má phanh, gạt mưa, bóng đèn, dầu mỡ, lọc…)
- Dùng pin / bộ sạc không chính hãng

**Nguồn:** [vf3_vn_warranty.txt](data/processed/vf3_vn_warranty.txt) — mục "9. NHỮNG HƯ HỎNG VÀ DỊCH VỤ KHÔNG THUỘC PHẠM VI BẢO HÀNH"

**Relevant nếu top-3 chứa:** chunk liệt kê các trường hợp loại trừ (từ khóa "không thuộc phạm vi bảo hành", "hao mòn", "phụ tùng không chính hãng")

---

### Query 4 — Safety procedure (EN, quy trình kỹ thuật)

**Query:** `How should first responders handle a VinFast VF8 high-voltage battery fire?`

**Gold answer:**
- Luôn giả định các bộ phận HV đang có điện, mang PPE đầy đủ
- Dập lửa bằng **lượng lớn nước**, ưu tiên lấy từ trụ cứu hỏa hoặc nguồn nước gần đó
- Pin lithium-ion có thể **tự bốc cháy lại** (reignite) nhiều giờ sau khi đã dập lửa
- Pin hư hỏng có thể thoát khí dễ cháy/độc → nguy cơ nổ
- Không dùng pin HV để nâng xe

**Nguồn:** [VINFAST_VF8_First_Responder_Guide.txt](data/processed/VINFAST_VF8_First_Responder_Guide.txt) — mục "Warnings" và "6. In Case of Fire"

**Relevant nếu top-3 chứa:** chunk với "HV battery", "water", "reignite"/"spontaneously self-ignite", "PPE"

---

### Query 5 — Cross-document / filter test (EN, cần metadata filter)

**Query:** `What is the battery warranty period for VinFast vehicles?`

**Gold answer (phân biệt theo mẫu xe và thị trường):**
- **VF3 (VN)**: pin mua theo xe mới được bảo hành **8 năm** hoặc **160.000 km** (nếu không dùng thương mại)
- **VF6 (VN)**: có chính sách tương tự, cần kiểm tra mục "PIN" trong warranty booklet
- **VF9 (US)**: theo US warranty booklet, có mục "High Voltage Battery Limited Warranty"

**Mục đích của query này:**
- Không filter → top-3 sẽ trộn lẫn VF3/VF6/VF9, khó có câu trả lời dứt khoát
- Filter `doc_type == "warranty"` và `model == "VF3"` → phải trả về đúng mục pin của VF3
- Test xem `search_with_filter()` có **thực sự cải thiện độ chính xác** không

**Nguồn:** nhiều file warranty

**Relevant nếu top-3 (với filter) chứa:** chunk với "pin", "8 năm", "160.000 km" của đúng mẫu xe được filter

---

## 5. Giao Thức Benchmark (mỗi thành viên chạy giống nhau)

1. **Load dữ liệu:** chỉ load đúng 5 file ở mục 2.
2. **Gán metadata:** theo schema mục 3.
3. **Chunk:** dùng strategy của riêng bạn (`FixedSizeChunker` / `SentenceChunker` / `RecursiveChunker` / custom) — đây là biến được so sánh.
4. **Embed + index** vào `EmbeddingStore`. Ghi lại backend đang dùng (mock / local / openai).
5. **Với mỗi query (1–5):**
   - Chạy `store.search(query, top_k=3)` — ghi lại top-1 chunk, score, relevant? (Y/N so với gold answer).
   - Chạy `agent.answer(query)` — ghi lại câu trả lời, kiểm tra có grounded vào retrieved context không.
6. **Với Query 5 bắt buộc chạy thêm** `store.search_with_filter(query, filter={"model": "VF3", "doc_type": "warranty"}, top_k=3)` và so sánh với bản không filter.
7. **Điền kết quả vào bảng mục 6 của `report/REPORT.md`.**

---

## 6. Cách Chấm Relevant (thống nhất)

Một query được tính là **"relevant in top-3"** nếu **ít nhất một** trong 3 chunk trả về chứa đủ **từ khóa cốt lõi** đã liệt kê ở dòng "Relevant nếu top-3 chứa" của query đó.

Thang điểm tóm tắt cho phần benchmark (5 queries × 2 điểm = 10):

| Tiêu chí | Điểm |
|----------|------|
| Top-3 chứa chunk relevant | 1 điểm/query |
| Agent answer grounded vào chunk đúng | 1 điểm/query |
| **Tổng** | **10 điểm** |

> Điểm này chính là phần **Results — Cá nhân (10 điểm)** ở mục 6 của `REPORT.md`.

---

## 7. Cần Lưu Ý Khi So Sánh Trong Nhóm

- Query 1 (spec, dạng bảng) — `FixedSizeChunker` thường cắt ngang bảng gây vỡ context; `RecursiveChunker` với separator `\n\n` có lợi thế.
- Query 2 & 3 (warranty VI) — `SentenceChunker` phải xử lý đúng dấu câu tiếng Việt; các bullet `•` có thể làm `SentenceChunker` regex đơn giản bị lỗi.
- Query 4 (safety EN) — test khả năng giữ nguyên khối cảnh báo (WARNING/DANGER/NOTE) của chunker.
- Query 5 (cross-doc) — đây là query **test metadata**, không phải test chunker. Thành viên nào gán metadata sơ sài sẽ thua ở câu này.

Khi họp nhóm so sánh, tập trung vào: *"Strategy nào thắng ở query nào, và tại sao?"* — không chỉ so tổng điểm.

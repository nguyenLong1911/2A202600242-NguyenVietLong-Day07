# Báo Cáo Lab 7: Embedding & Vector Store

**Họ tên:** Nguyễn Việt Long
**Nhóm:** X100
**Ngày:** 2026-04-10

---

## 1. Warm-up (5 điểm)

### Cosine Similarity (Ex 1.1)

**High cosine similarity nghĩa là gì?**
> Hai vector embedding chỉ cùng hướng trong không gian vector, tức là hai đoạn văn bản có ý nghĩa/ngữ cảnh gần nhau theo cách mà mô hình embedding đã học.

**Ví dụ HIGH similarity:**
- Sentence A: `The VinFast VF3 has a 18.64 kWh LFP battery.`
- Sentence B: `VF3 uses a lithium iron phosphate battery pack with 18.64 kWh capacity.`
- Tại sao tương đồng: cùng domain (spec xe điện), cùng chủ thể (VF3), cùng dữ kiện (18.64 kWh, LFP = lithium iron phosphate). Actual score = **0.810**.

**Ví dụ LOW similarity:**
- Sentence A: `How should I charge my electric vehicle?`
- Sentence B: `The boiling point of water is 100 degrees Celsius.`
- Tại sao khác: hai chủ đề không liên quan (EV charging vs vật lý đại cương), không chung keyword nào. Actual score = **-0.035**.

**Tại sao cosine similarity được ưu tiên hơn Euclidean distance cho text embeddings?**
> Cosine chỉ quan tâm tới *hướng* của vector nên không bị ảnh hưởng bởi độ dài chuỗi văn bản (câu dài có norm lớn hơn câu ngắn nhưng ý nghĩa vẫn có thể tương đương). Euclidean distance bị "phạt" ngay khi độ lớn khác nhau, cho dù hai vector chỉ về cùng một hướng ngữ nghĩa.

### Chunking Math (Ex 1.2)

**Document 10,000 ký tự, chunk_size=500, overlap=50. Bao nhiêu chunks?**
> step = chunk_size − overlap = 500 − 50 = 450
> số chunk ≈ ceil((10000 − 500) / 450) + 1 = ceil(9500 / 450) + 1 = 22 + 1 = **23 chunks** (chunk cuối chứa phần dư ngắn hơn 500).

**Nếu overlap tăng lên 100, chunk count thay đổi thế nào? Tại sao muốn overlap nhiều hơn?**
> step giảm còn 400 → số chunk tăng lên ≈ ceil(9500/400) + 1 = **25 chunks**. Tăng overlap giúp giữ context xuyên biên giới giữa các chunk, tránh cắt vỡ câu/ý ngay chỗ quan trọng, và tăng khả năng một chunk bất kỳ vẫn chứa đủ keyword để retrieval match được.

---

## 2. Document Selection — Nhóm (10 điểm)

### Domain & Lý Do Chọn

**Domain:** VinFast vehicle documentation (spec sheet + warranty policy + first responder guide)

**Tại sao nhóm chọn domain này?**
> Tài liệu song ngữ (EN + VI), đa dạng format (bảng spec, chính sách warranty, hướng dẫn kỹ thuật) nên bộc lộ điểm mạnh/yếu của từng chunking strategy rõ ràng. Gold answer là các dữ kiện cụ thể (con số, thời hạn, quy trình) nên chấm relevant được dứt khoát.

### Data Inventory

| # | Tên tài liệu | Nguồn | Số ký tự | Metadata đã gán |
|---|--------------|-------|----------|-----------------|
| 1 | [VF3_spec.txt](../data/processed/VF3_spec.txt) | VinFast | 4,881 | doc_id, model=VF3, doc_type=spec, language=en, region=global |
| 2 | [vf3_vn_warranty.txt](../data/processed/vf3_vn_warranty.txt) | VinFast VN | 18,125 | doc_id, model=VF3, doc_type=warranty, language=vi, region=VN |
| 3 | [20230927_VF6_VN_VN...Warranty.txt](../data/processed/20230927_VF6_VN_VN_1_1706781000_Warranty.txt) | VinFast VN | 30,472 | doc_id, model=VF6, doc_type=warranty, language=vi, region=VN |
| 4 | [VF9 US Vehicle Warranty Booklet.txt](../data/processed/VF9%20US%20Vehicle%20Warranty%20Booklet.txt) | VinFast US | 36,444 | doc_id, model=VF9, doc_type=warranty, language=en, region=US |
| 5 | [VINFAST_VF8_First_Responder_Guide.txt](../data/processed/VINFAST_VF8_First_Responder_Guide.txt) | VinFast | 17,695 | doc_id, model=VF8, doc_type=first_responder, language=en, region=global |

### Metadata Schema

| Trường metadata | Kiểu | Ví dụ giá trị | Tại sao hữu ích cho retrieval? |
|----------------|------|---------------|-------------------------------|
| `doc_id` | str | `vf3_vn_warranty` | Khoá định danh document nguồn, cần cho `delete_document` và debug top-k. |
| `model` | str | `VF3`, `VF6`, `VF8`, `VF9` | Cho phép filter theo mẫu xe. |
| `doc_type` | str | `spec`, `warranty`, `first_responder` | Cho phép chặn nhầm loại. |
| `language` | str | `vi`, `en` | Cho phép filter theo ngôn ngữ. |
| `region` | str | `VN`, `US`, `global` | Phân biệt chính sách warranty VN vs US. |

---

## 3. Chunking Strategy — Cá nhân chọn, nhóm so sánh (15 điểm)

### Baseline Analysis

| Tài liệu | Strategy | Chunk Count | Avg Length | Preserves Context? |
|-----------|----------|-------------|------------|-------------------|
| VF3_spec.txt | FixedSizeChunker | 10 | 488 | Không — cắt ngang bảng spec |
| VF3_spec.txt | SentenceChunker | 4 | 1,219 | Kém — regex không match được bảng |
| VF3_spec.txt | RecursiveChunker | 14 | 347 | Khá — tách theo `\n\n` |
| VF3_spec.txt | SectionAwareChunker | 12 | 448 | Tốt nhất — bám theo header |

### Strategy Của Tôi

**Loại:** `FixedSizeChunker` (chunk_size=1200, overlap=100)

**Mô tả cách hoạt động:**
> Chia tài liệu thành các đoạn có độ dài cố định là 1200 ký tự với phần gối đầu (overlap) 100 ký tự. Kích thước 1200 được chọn để bao quát được nhiều thông tin hơn trong một chunk, đặc biệt là các bảng thông số kỹ thuật dài.

**Tại sao tôi chọn strategy này cho domain nhóm?**
> Mục tiêu là xem fixed-size với kích thước lớn có cải thiện việc truy xuất các thông số kỹ thuật (spec) và các danh sách liệt kê (bullet points) trong tài liệu bảo hành so với cách chia nhỏ thông thường hay không.

### So Sánh: Strategy của tôi vs Baseline

| Tài liệu | Strategy | Chunk Count | Avg Length | Retrieval Quality?|
|-----------|----------|-------------|------------|--------------------|
| Toàn bộ 5 file | RecursiveChunker | 114 | ~400 | 3/5 relevant |
| Toàn bộ 5 file | **Fixed-size (1200)** | 92 | ~1100 | **4/5 relevant** |

### So Sánh Với Thành Viên Khác

| Thành viên | Strategy | Retrieval Score (/5) | Điểm mạnh | Điểm yếu |
|-----------|----------|----------------------|-----------|----------|
| Nguyễn Minh Hiếu | FixedSizeChunker (500/50) | 4/5 | Top-1 đúng ở 4/5 query, ổn định | Query 5 fail do nhiễu từ VF9 US |
| Nguyễn Quang Đăng | Recursive + metadata filter | 3/5 | Tốt cho query warranty theo model | Chưa ổn định với query spec |
| Nguyễn Việt Long | Fixed-size (1200) + metadata | 4/5 | Tốt hơn ở query spec và warranty rõ keyword | Query battery warranty cross-doc vẫn khó |
|Hà Huy Hoàng|Semantic Chunker + Hybrid Search (Vector + BM25)|4/5|Khắc phục được phần lớn lỗi ở Query 5 (cross-doc) nhờ cụm từ khóa (BM25) và ngữ nghĩa (Vector) bổ trợ nhau. Tránh được nhiễu từ tài liệu VF9 US.|Thời gian indexing chậm và tốn tài nguyên tính toán hơn. Chunk size động đôi khi làm trượt Top-1 ở các query hỏi về thông số spec quá ngắn gọn|
| Tống Tiến Mạnh| RecursiveChunker tùy chỉnh (chunk_size=500, overlap=100) | 8 | Giữ cấu trúc section markdown, chunk bao trọn điều khoản | Chunk đôi khi vẫn dài nếu section liên tục >500 ký tự |

**Strategy nào tốt nhất cho domain này? Tại sao?**
> Qua thực nghiệm, `FixedSizeChunker` với cấu hình phù hợp tỏ ra cân bằng nhất cho dataset hỗn hợp giữa bảng biểu và văn bản xuôi. Tuy nhiên, việc kết hợp thêm metadata filter là bắt buộc để xử lý các truy vấn đặc thù theo model xe.

---

## 4. My Approach — Cá nhân (10 điểm)

### Chunking Functions

**`SentenceChunker.chunk`** — approach:
> Sử dụng regex để split văn bản dựa trên các dấu kết thúc câu, sau đó gộp các câu lại cho tới khi đạt số lượng câu tối đa cho phép trong một chunk.

**`RecursiveChunker.chunk`** — approach:
> Tiếp cận theo kiểu chia để trị (divide and conquer), ưu tiên cắt ở các khoảng trống lớn như `\n\n`, sau đó đến `\n`, khoảng trắng, và cuối cùng là ký tự đơn lẻ nếu vẫn chưa đạt kích thước mục tiêu.

### EmbeddingStore

**`add_documents` + `search`** — approach:
> Thực hiện embedding nội dung văn bản cho mỗi document và lưu trữ kèm metadata. Khi search, query được embed và so sánh độ tương đồng cosine với các vector đã lưu để trả về kết quả tốt nhất.

**`search_with_filter` + `delete_document`** — approach:
> Filter metadata được áp dụng trước để thu hẹp không gian tìm kiếm, sau đó mới thực hiện so sánh vector. Việc xóa tài liệu dựa trên `doc_id` trong metadata.

### KnowledgeBaseAgent

**`answer`** — approach:
> Sử dụng kết quả truy xuất (top-k chunks) để tạo prompt cho LLM, yêu cầu LLM trả lời dựa tên ngữ cảnh được cung cấp.

---

## 5. Similarity Predictions — Cá nhân (5 điểm)

| Pair | Sentence A | Sentence B | Dự đoán | Actual Score | Đúng? |
|------|-----------|-----------|---------|--------------|-------|
| 1 | The VinFast VF3 has a 18.64 kWh LFP battery. | VF3 uses a lithium iron phosphate battery pack with 18.64 kWh capacity. | high | **0.810** | yes |
| 2 | Thời hạn bảo hành chung của xe VF3 là 7 năm. | VF3 general warranty lasts 7 years from the activation date. | high | **0.298** | **no** |
| 3 | How should I charge my electric vehicle? | The boiling point of water is 100 degrees Celsius. | low | **-0.035** | yes |
| 4 | High voltage battery fires require large amounts of water. | Pin cao áp bị cháy cần dùng nhiều nước để dập lửa. | high | **-0.021** | **no** |
| 5 | VinFast VF8 is a mid-size electric SUV. | The warranty excludes damage caused by floods and earthquakes. | low | **0.077** | yes |

**Kết quả nào bất ngờ nhất? Điều này nói gì về cách embeddings biểu diễn nghĩa?**
> Tương tự như quan sát của nhóm, mô hình `all-MiniLM-L6-v2` gặp khó khăn lớn với tiếng Việt. Nó không thể nhận diện được sự tương đồng xuyên ngôn ngữ (cross-lingual), dẫn đến điểm số rất thấp cho các cặp câu cùng nghĩa nhưng khác ngôn ngữ EN-VI.

---

## 6. Results — Cá nhân (10 điểm)

### Benchmark Queries & Gold Answers

| # | Query | Gold Answer |
|---|-------|-------------|
| 1 | What is the battery capacity and range of the VinFast VF3? | LFP, 18.64 kWh, ~210 km (NEDC) |
| 2 | Thời hạn bảo hành chung của xe VinFast VF3 là bao lâu? | 7 năm hoặc 160.000 km |
| 3 | Những hư hỏng nào không được VinFast bảo hành? | Sửa chữa trái phép, lạm dụng, thiên tai... |
| 4 | Fire handling for VF8 high-voltage battery? | Dùng nhiều nước, PPE đầy đủ... |
| 5 | Battery warranty period for VinFast vehicles? | VF3 VN: 8 năm hoặc 160.000 km |

### Kết Quả Của Tôi (FixedSize 1200)

| # | Query | Top-1 Retrieved Chunk (tóm tắt) | Score | Relevant? | Agent Answer (tóm tắt) |
|---|-------|--------------------------------|-------|-----------|------------------------|
| 1 | VF3 battery capacity/range | Top-1 từ VF3_spec và có thông số pin/range. | 0.6250 | Yes | Đúng 18.64 kWh và ~210 km. |
| 2 | Thời hạn bảo hành chung VF3 | Top-1 từ vf3_vn_warranty nói về thời hạn bảo hành. | 0.7288 | Yes | Đúng 7 năm/160.000 km. |
| 3 | Hư hỏng không được bảo hành | Top-1 từ vf3_vn_warranty có danh sách loại trừ. | 0.7657 | Yes | Liệt kê đúng các vi phạm bảo hành. |
| 4 | VF8 HV battery fire | Top-1 từ VF8 first responder guide về fire/HV warning. | 0.7066 | Yes | Nêu đúng quy trình dùng nước và PPE. |
| 5 | Battery warranty (cross-doc) | Sau filter top-1 vẫn chưa đủ keyword 8 năm. | 0.6332 | No | Context chưa nói rõ thời hạn mong muốn. |

**Bao nhiêu queries trả về chunk relevant trong top-3?** 4 / 5

---

## 7. What I Learned (5 điểm)

**Điều hay nhất tôi học được từ thành viên khác trong nhóm:**
> Metadata không chỉ để phân loại mà còn là "cứu cánh" khi embedding model không đủ mạnh để hiểu ngữ nghĩa phức tạp hoặc đa ngôn ngữ.

**Nếu làm lại, tôi sẽ thay đổi gì trong data strategy?**
> Tôi sẽ thực hiện tiền xử lý dữ liệu kỹ hơn (data cleaning), loại bỏ các khoảng trắng thừa từ quá trình parse PDF và thử nghiệm với các mô hình embedding đa ngôn ngữ mạnh hơn như `paraphrase-multilingual-MiniLM-L12-v2`.

---

## Tự Đánh Giá

| Tiêu chí | Loại | Điểm tự đánh giá |
|----------|------|-------------------|
| Warm-up | Cá nhân | 5 / 5 |
| Document selection | Nhóm | 9 / 10 |
| Chunking strategy | Nhóm | 14 / 15 |
| My approach | Cá nhân | 9 / 10 |
| Similarity predictions | Cá nhân | 5 / 5 |
| Results | Cá nhân | 8 / 10 |
| Core implementation (tests) | Cá nhân | 30 / 30 |
| Demo | Nhóm | 4 / 5 |
| **Tổng** | | **84 / 100** |

# Sơ đồ luồng dữ liệu — LUẬT GẦN BẢN v2

## 1. Luồng chính (lúc bà con dùng app)

```mermaid
flowchart TD
    A["🎙️ Bà con nói<br/>(Việt hoặc Mông)"] --> B{Ngôn ngữ?}

    B -->|Tiếng Việt| C1["STT: Gemini 2.5 Flash<br/>(audio → text tiếng Việt)<br/>~2-3s"]
    B -->|Tiếng Mông| C2["STT: Gemini<br/>+ dịch Mông→Việt<br/>~3-4s"]
    C1 --> D
    C2 --> D

    D["🧭 Tầng 1: phân loại NHÓM<br/>8 nhóm thủ tục<br/>gemini-2.5-flash · ~1s"]
    D --> E{"tin cậy<br/>≥ 55%?"}
    E -->|Không| Z["🙋 Chuyển cán bộ /<br/>hỏi lại 1 câu làm rõ"]
    E -->|Có| F["🎯 Tầng 2: chọn THỦ TỤC cụ thể<br/>(14 thủ tục chỉ riêng khai sinh)<br/>gemini-2.5-flash · ~1s"]

    F --> G{"tin cậy<br/>≥ 55%?"}
    G -->|Không| Z
    G -->|Có| H

    H{"Đã có câu trả lời<br/>trong cache?"}
    H -->|Có · 0s| J
    H -->|Chưa| I["📖 Đơn giản hoá<br/>gemini-2.5-pro + PDF gốc<br/>→ JSON có schema<br/>~4-8s"]
    I --> I2["💾 Lưu cache đĩa<br/>+ chờ cán bộ duyệt"]
    I2 --> J

    J["✅ Hiện NGAY thẻ trả lời tiếng Việt<br/>đi đâu · mang gì · bao lâu · bao nhiêu tiền"]

    J --> K["🔄 Dịch sang tiếng Mông (RPA)<br/>Gemini / hmn / mww · ~2s"]
    K --> L["🔤 Phiên âm RPA → chữ kiểu Việt<br/>core/hmong/rpa_vi.py · 0s, cục bộ"]
    L --> M{"Chuỗi dự phòng TTS"}

    M -->|Tầng 1| N1["🎙️ Giọng người Mông thu sẵn<br/>offline · 0 đồng · chính xác 100%"]
    M -->|Tầng 2| N2["🤖 Model neural cục bộ<br/>CosyVoice3 / F5-TTS"]
    M -->|Tầng 3| N3["🔊 TTS tiếng Việt đọc phiên âm<br/>gTTS · luôn chạy được"]
    N1 --> O
    N2 --> O
    N3 --> O

    O["🔉 Phát âm thanh + nhãn trung thực<br/>(giọng người / giọng máy)"]
    O --> P["🙋 Nút gọi cán bộ luôn hiển thị"]

    style J fill:#d4edda,stroke:#28a745
    style Z fill:#fff3cd,stroke:#ffc107
    style N1 fill:#d1ecf1,stroke:#0c5460
```

**Điểm then chốt về độ trễ:** ô `J` (thẻ trả lời tiếng Việt) được render **trước
khi** chạy bước dịch và TTS. Bà con đã có câu trả lời đọc được ở giây thứ 5-8,
trong lúc giọng Mông vẫn đang tạo. Đây là khác biệt lớn nhất so với bản v1 —
v1 bọc cả 4 lời gọi API trong **một** `st.spinner`, nên người dùng nhìn màn hình
trắng suốt 15-20 giây và tưởng app treo.

## 2. Luồng dữ liệu (lúc cán bộ cập nhật)

```mermaid
flowchart LR
    X1["📊 3 file Excel<br/>tải từ dichvucong.gov.vn<br/>(28 PDF NHÚNG bên trong)"]
    X1 -->|"tools/extract_tthc.py"| X2["📁 data/tthc/&lt;mã&gt;/<br/>thu_tuc.pdf<br/>raw.txt<br/>sections.json"]
    X2 --> X3["📋 data/manifest.json<br/>27 thủ tục"]
    X3 --> X4["core/kb.py<br/>(lớp truy vấn)"]
    X4 --> X5["app.py"]

    Y1["🛠️ Dashboard quản trị"] -->|upload xlsx / pdf| X1
    Y1 -->|"bấm Bóc tách lại"| X2
    Y1 -->|"sửa & DUYỆT câu trả lời"| Z1["data/cache/simplified/*.json<br/>_da_duyet = true"]
    Z1 --> X5
    Y1 -->|"chốt thuật ngữ"| Z2["data/glossary_hmong.csv"]
    Z2 --> X5
    Y1 -->|"upload mp3 người Mông đọc"| Z3["data/audio_bank/"]
    Z3 --> X5
```

## 3. Ngân sách độ trễ thực tế

| Bước | Lần đầu | Lần 2 (có cache) |
|---|---|---|
| STT tiếng Việt | 2–3 s | — |
| Phân loại nhóm | 0,8–1,5 s | 0 s |
| Chọn thủ tục | 0,8–1,5 s | 0 s |
| Đơn giản hoá (Pro + 9k ký tự) | 4–8 s | **0 s** |
| Dịch sang Mông | 1,5–3 s | 0 s |
| TTS | 1–2 s (gTTS) / 10–20 s (neural) | 0 s |
| **Tổng** | **11–19 s** | **2–3 s** |

Vì vậy phải **làm nóng cache trước buổi demo**: Dashboard → tab *Kho thủ tục* →
nút *🔥 Tạo sẵn câu trả lời*. Sau bước đó, mọi thủ tục trả lời trong 2-3 giây và
app chạy được cả khi wifi hội trường chập chờn.

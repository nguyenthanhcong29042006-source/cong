# LUẬT GẦN BẢN — MVP v2

> "Không để khoảng cách số trở thành khoảng cách công lý"
> Học viện Hành chính và Quản trị Công

Trợ lý pháp luật bằng giọng nói, giúp bà con dân tộc Mông làm thủ tục hành chính.

## Chạy lần đầu

```bash
pip install -r requirements.txt
python tools/extract_tthc.py      # BẮT BUỘC: bóc 28 PDF nhúng trong 3 file Excel
python tools/kiem_tra.py          # tự kiểm tra trước khi demo
streamlit run app.py
```

`.streamlit/secrets.toml` chỉ cần một dòng:
```toml
GEMINI_API_KEY = "..."
```

## Tài khoản

Bà con **không cần đăng nhập** — trang Hỏi đáp luôn mở. Đăng nhập ở thanh bên trái
chỉ để mở thêm trang *Quản trị kho*; riêng trang *Tài khoản & phân quyền* chỉ quản trị
viên thấy được.

Mật khẩu băm bằng PBKDF2-HMAC-SHA256 (200.000 vòng, muối riêng từng tài khoản).
Đây là mức đủ cho mạng nội bộ — **đổi mật khẩu mặc định** trước khi dùng thật, và
đừng đưa app lên Internet công khai với cơ chế này.

### 5 quyền

| Mã quyền | Cho phép làm gì |
|---|---|
| `kho_thu_tuc` | Xem và **sửa danh mục** thủ tục (tên, nhóm, cấp, ẩn/hiện), làm nóng câu trả lời |
| `cap_nhat_du_lieu` | Upload Excel/PDF, bấm bóc tách lại |
| `cau_tra_loi` | Sửa và ký duyệt câu trả lời AI |
| `tu_vung_giong` | Từ điển Việt–Mông, ngân hàng giọng đọc |
| `bo_nho_tam` | Xem và xoá cache |

## Trước buổi demo — 3 việc bắt buộc

1. Mở **Quan tri → Kho thủ tục → 🔥 Tạo sẵn câu trả lời**.
   Sau bước này mọi thủ tục trả lời trong 2-3 giây và app chạy được cả khi mất mạng.
2. Mở **Quan tri → Kiểm duyệt câu trả lời**, đọc lại 3-5 thủ tục sẽ demo, bấm **Duyệt**.
3. Chạy `python tools/kiem_tra.py`, bảo đảm không còn dòng `[!!]`.

## Cấu trúc

```
app.py                      Điểm vào: header, đăng nhập, điều hướng
giao_dien/
  cong_dan.py               Cổng người dân — một nút micro, tự xử lý
  quan_tri.py               Dashboard quản trị, tab hiện theo quyền
  tai_khoan.py              Tài khoản & phân quyền (chỉ admin)
core/
  auth.py                   Tài khoản, băm mật khẩu, kiểm tra quyền
  config.py                 Mọi hằng số, đường dẫn, công tắc bật-tắt
  kb.py                     Kho tri thức 27 thủ tục (đọc data/manifest.json)
  llm.py                    Lớp bọc Gemini: retry + cache đĩa
  router.py                 Phân loại ý định 2 tầng (nhóm → thủ tục cụ thể)
  simplify.py               ⭐ System prompt đơn giản hoá hướng dẫn pháp lý
  translate.py              Dịch Việt ↔ Mông (gemini / hmn / mww)
  stt.py                    Nhận diện giọng nói (Gemini, dự phòng SpeechRecognition)
  tts.py                    Giọng Mông, 4 tầng dự phòng
  hmong/rpa_vi.py           ⭐ Phiên âm RPA → chính tả kiểu Việt
tools/
  extract_tthc.py           Bóc PDF nhúng trong Excel → data/
  liet_ke_model.py          Xem tài khoản Gemini gọi được model nào
  tts_hmong_local.py        Khuôn mẫu chạy model TTS neural cục bộ
  kiem_tra.py               Tự kiểm tra hệ thống
data/
  manifest.json             Danh mục 27 thủ tục
  tthc/<mã>/                thu_tuc.pdf · raw.txt · sections.json
  cache/simplified/         Câu trả lời đã sinh (+ cờ _da_duyet)
  cache/audio/              Âm thanh đã tạo
  audio_bank/               Giọng người Mông thu sẵn (ưu tiên số 1)
  glossary_hmong.csv        Thuật ngữ Việt–Mông do người bản địa chốt
  kho_ghi_de.json           Phần danh mục cán bộ sửa tay (không bị mất khi bóc tách lại)
  users.json                Tài khoản (mật khẩu đã băm) — KHÔNG đưa lên Git
docs/
  DATAFLOW.md               Sơ đồ luồng dữ liệu + ngân sách độ trễ
  TTS_HMONG.md              Khảo sát dịch & TTS tiếng Mông, các phương án
```

## Công tắc cấu hình (biến môi trường)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `LGB_TTS_HMONG` | `auto` | `auto` / `audio_bank` / `local_neural` / `vi_phonetic` / `off` |
| `LGB_TRANSLATE` | `gemini` | `gemini` / `google_nmt` (hmn) / `azure` (mww) / `off` |
| `LGB_HMONG_ORTHO` | `vn` | Chữ Mông hiển thị: `vn` (kiểu Việt) hoặc `rpa` |
| `LGB_NGUONG_TU_TIN` | `0.55` | Dưới ngưỡng này thì chuyển cán bộ, không tự trả lời |
| `LGB_MODEL_QUALITY` | *(tự dò)* | Ép cứng model đọc PDF pháp lý, ví dụ `gemini-3.1-pro-preview` |
| `LGB_MODEL_FAST` | *(tự dò)* | Ép cứng model phân loại & dịch |

## Hai điều phải biết về dữ liệu

1. **PDF hướng dẫn không nằm trong `file_dichvucong/`.** Chúng là 28 đối tượng OLE
   nhúng bên trong 3 file Excel (`xl/embeddings/oleObject*.bin`). Cột "File" trong
   sheet luôn rỗng khi đọc bằng openpyxl. Phải chạy `tools/extract_tthc.py` trước.
2. **Thủ tục `2.000547` xuất hiện ở cả khai sinh và khai tử** — `core/kb.py` gộp
   thành 1 bản ghi thuộc 2 nhóm.
3. **Không ghi cứng tên model Gemini.** Google gỡ model khá thường xuyên
   (`gemini-2.5-pro` đã bị chặn với tài khoản mới). `core/llm.py` hỏi API xem tài
   khoản đang có gì, chọn theo danh sách ưu tiên trong `core/config.py`, và nếu gặp
   404 giữa chừng thì tự đổi sang model kế tiếp. Xem `python tools/liet_ke_model.py`.

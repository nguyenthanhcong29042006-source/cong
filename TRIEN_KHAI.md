# Đưa app lên mạng — Streamlit Community Cloud (miễn phí)

**Không cần mua hosting.** Streamlit Community Cloud miễn phí, chạy được app này,
có sẵn HTTPS (bắt buộc để dùng micro trên trình duyệt). Khoảng 15 phút.

---

## ⚠️ Cái bẫy phải biết trước

Streamlit Cloud **xoá sạch file mỗi lần app khởi động lại**. Nghĩa là:

- Câu trả lời sinh trên đó → **mất**
- Kiểm duyệt trên đó → **mất**
- File Excel / mp3 upload trên đó → **mất**
- Tài khoản đổi mật khẩu trên đó → **mất** (4 tài khoản mặc định thì tự tạo lại, vẫn đăng nhập được)

➡️ **Mọi thứ phải làm trên máy bạn trước, rồi mới đẩy lên GitHub.**
Trang Quản trị trên bản online chỉ nên dùng để *xem*.

---

## Thứ tự làm — làm đúng thứ tự này

### Bước 1 · Trên máy: tạo và duyệt toàn bộ câu trả lời

Cách nhanh nhất — chạy thẳng ở terminal, một lệnh làm hết 27 thủ tục:

```
cd D:\LuatGanBan_MVP
python tools/lam_nong.py --duyet "Họ tên — chức danh"
```

Lệnh này tự chờ khi gặp hạn mức, tự thử lại, in rõ từng thủ tục kèm độ tin cậy
và cảnh báo chỗ tài liệu không nêu rõ. Bỏ `--duyet` nếu muốn tự đọc rồi duyệt
trong giao diện.

Cách thứ hai — bấm nút trong app: `python -m streamlit run app.py` → đăng nhập
`admin_Minh` / `admin` → **Quản trị kho → Kho thủ tục → 🔥 Tạo sẵn câu trả lời**
→ **Kiểm duyệt câu trả lời → ⚡ Duyệt hàng loạt**.

Xong thì kiểm tra `data/cache/simplified/` có các file `tt_*.json`. **Đây là tài
sản quý nhất của bản demo** — có chúng thì app trả lời tức thì và gần như không
tốn lượt API nào khi ban giám khảo bấm thử.

### Bước 2 · Đưa code lên GitHub

Cài Git (git-scm.com) nếu chưa có, rồi:

```
cd D:\LuatGanBan_MVP
git init
git add .
git commit -m "Luat Gan Ban MVP"
git branch -M main
git remote add origin https://github.com/<tên-github>/luat-gan-ban.git
git push -u origin main
```

Tạo repo trống trên github.com trước (đừng tick "Add README").
Repo để **Private** cũng deploy được.

**Kiểm tra ngay sau khi push:** vào repo trên web, bảo đảm
- ✅ có thư mục `data/cache/simplified/` với các file `tt_*.json`
- ✅ có `data/tthc/` và `data/manifest.json`
- ❌ **không** có `.streamlit/secrets.toml` (khoá API của bạn!)

Nếu lỡ đẩy `secrets.toml` lên: vào Google AI Studio **huỷ khoá cũ, tạo khoá mới** ngay.

### Bước 3 · Deploy

1. Vào **share.streamlit.io** → đăng nhập bằng GitHub
2. **Create app** → chọn repo, nhánh `main`, file chính `app.py`
3. **Advanced settings**:
   - **Python version**: chọn **3.12** (3.14 chưa chắc có sẵn)
   - **Secrets**: dán vào

     ```toml
     GEMINI_API_KEY = "khoá của bạn"
     ```
4. **Deploy** — lần đầu mất 3-5 phút cài thư viện.

Bạn được một địa chỉ dạng `https://<tên>.streamlit.app` — dán vào hồ sơ dự thi.

---

## Phòng hờ cho ngày nộp

**Quay sẵn một video màn hình 2-3 phút** chạy thử trên máy bạn: nói vào micro →
ra kết quả → nghe tiếng Mông. Wifi hội trường hỏng, quota Gemini hết, Streamlit
Cloud bảo trì — có video là vẫn trình bày được. Đây là việc rẻ nhất mà cứu được
cả buổi.

**Nếu Streamlit Cloud không kịp:** app chạy trên máy bạn vẫn là một bản demo
hoàn chỉnh. Nộp kèm ảnh chụp màn hình + video, ghi rõ "bản chạy thử tại máy,
đang triển khai lên đám mây". Không ai trừ điểm vì chuyện đó.

---

## Sau khi deploy — cập nhật nội dung thế nào

Sửa trên máy → `git add . && git commit -m "cap nhat" && git push`
→ Streamlit Cloud tự build lại sau ~1 phút.

## Hạn mức Gemini khi nhiều người dùng

Gói miễn phí tính theo **cả dự án**, không phải theo người. Ban giám khảo bấm
nhiều có thể làm hết lượt. Hai lớp phòng thủ đã có sẵn:

1. Câu trả lời đã cache + đã duyệt → **không gọi API**, trả lời tức thì.
2. Hết lượt thì app báo bằng tiếng Việt tử tế và mời gọi cán bộ, không hiện lỗi đỏ.

Muốn chắc ăn hơn nữa: bật thanh toán cho dự án Google Cloud (dùng thật thì vẫn
gần như miễn phí ở mức này), hoặc trước buổi chấm đặt
`LGB_TRANSLATE=off` để bớt một lời gọi API mỗi câu.

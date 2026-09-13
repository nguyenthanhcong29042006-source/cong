# Tiếng Mông: dịch & giọng nói — kết quả khảo sát và cách làm

*Cập nhật: 11/09/2026*

## 1. Dịch máy Việt → Mông

| Dịch vụ | Hỗ trợ? | Mã ngôn ngữ | Ghi chú |
|---|---|---|---|
| **Google Cloud Translation** | ✅ Có | **`hmn`** | Chỉ ở tầng NMT. Danh sách của *Translation LLM* (tầng mới, chất lượng cao) **không** có tiếng Mông. `vi` → `hmn` chạy được. |
| **Azure AI Translator** | ✅ Có | **`mww`** | Ghi là *"Hmong Daw (Latin)"*. Có cả bản chạy trong container. |
| **AWS Translate** | ❌ Không | — | Không có trong danh sách ngôn ngữ. |
| **Gemini** | ⚠️ Gián tiếp | — | Dịch được nhưng chất lượng không ổn định, không cam kết. Bù lại: xử lý được hướng dẫn dài, giữ ngữ cảnh pháp lý, và ép được từ vựng qua glossary. |

### Cảnh báo quan trọng nhất của cả dự án

Tất cả các dịch vụ trên đều trả về **tiếng Mông Trắng (Hmong Daw)** viết bằng
**RPA** — hệ chữ do các nhà truyền giáo lập ở Lào năm 1951–53, thanh điệu ghi
bằng chữ cái cuối âm tiết (`nyob zoo`, `kuv`, `mus`).

Người Mông ở Việt Nam dùng **chữ Mông Latin hoá theo lối Việt** (ghi thanh
điệu bằng dấu như tiếng Việt). Hai hệ chữ **không đọc lẫn được**. Nghĩa là:

- Hiển thị RPA lên màn hình cho bà con ở Quảng Tân → gần như vô dụng.
- Nhưng **âm thanh thì vẫn hiểu được**, vì khác biệt là ở chữ viết, không phải
  ở tiếng nói (Hmong Daw và Mông ở Việt Nam thông hiểu nhau ở mức khá).

→ Kết luận kiến trúc: **dự án này là dự án ÂM THANH, không phải dự án chữ.**
Chữ chỉ để cán bộ đối chiếu. Đó là lý do `core/hmong/rpa_vi.py` tồn tại.

## 2. TTS tiếng Mông

### Không có dịch vụ thương mại nào hỗ trợ
Google Cloud TTS, Azure Speech, AWS Polly, ElevenLabs: **không có tiếng Mông**
(đã kiểm tra 09/2026). Không có đường đi nhanh bằng API trả tiền.

### Mã nguồn mở — trong đó có repo bạn tìm thấy

`YangNobody12/hmong-TTS`: dự án của nhóm **Local Voice (Thái Lan)**, huấn luyện
trên siêu máy tính LANTA (ThaiSC, GPU A100). Repo có 2 thư mục `F5TTS-model/`
và `unsloths-text-to-speech/`, giấy phép MIT **nhưng README ghi rõ dùng cho mục
đích thương mại phải xin phép trước**. Repo chỉ có 9 commit, **không kèm
checkpoint** và **không có hướng dẫn cài đặt/inference**.

→ Không tích hợp trực tiếp repo này được. Nhưng **checkpoint của chính nhóm đó
nằm trên Hugging Face**, và đó mới là thứ dùng được:

| Model | Kiến trúc | Dung lượng | Ghi chú |
|---|---|---|---|
| **`Xuajpaj2026/hmong-tts-weights`** | CosyVoice3-0.5B | ~1 GB, có ONNX | Mới nhất (08/09/2026). Có audio mẫu tiếng Mông. **Nên thử đầu tiên.** |
| `Pakorn2112/F5TTS-Hmong` | F5-TTS | 1,35 GB | 1 checkpoint + `vocab.txt`. Cùng nhóm với repo trên GitHub. Cần audio mẫu để clone giọng. |
| `Pakorn2112/Orpheus-TTS-hmong-3b` | Orpheus 3B (Llama) | ~6 GB | Có bản GGUF chạy CPU: `grimztha/Orpheus-3B-TTS-hmong-Q8_0-GGUF`. Chậm nhưng không cần GPU. |

Và các model liên quan khác đáng theo dõi:
- ASR: `Pakorn2112/whisper-model-large-hmong`, `kengher2004/hmong-whisper-small`,
  `Darejkal/mms-hmong-20260113` → Whisper **gốc không hỗ trợ tiếng Mông**, phải
  dùng bản fine-tune như trên.
- Dịch: `ThaiKami/Qwen2.5-0.5B-Instruct-VN-Hmong` ← **VN = Việt Nam**, đây là
  model duy nhất tìm được nhắm vào tiếng Mông ở Việt Nam.
- Dữ liệu: `ThaiKami/hmong-vn-audio` (278 mẫu audio Mông–Việt),
  `BachDo/hmong-tts-dataset` (30 file wav, tác giả Việt Nam),
  `Pakorn2112/hmong-dataset-audio-v1` (song song Mông–Thái).

**Đánh giá thẳng:** toàn bộ hệ sinh thái này mới, nhỏ (0 sao, vài trăm lượt tải),
gần như toàn bộ là tiếng Mông ở **Thái Lan/Lào**. Đặt cược bản demo vào nó là
rủi ro. Vì vậy `core/tts.py` thiết kế 4 tầng dự phòng thay vì phụ thuộc 1 model.

### Cách cài model neural (khi cần)

```bash
pip install huggingface_hub f5-tts
huggingface-cli download Pakorn2112/F5TTS-Hmong --local-dir models/f5tts-hmong
# đặt thêm 1 file models/f5tts-hmong/ref.wav (giọng mẫu) + sửa ref_text
# trong tools/tts_hmong_local.py
```
Rồi đặt biến môi trường: `set LGB_TTS_HMONG=local_neural`

## 3. Giải pháp thay thế — xếp theo mức nên dùng

**① Ngân hàng giọng thu sẵn (khuyến nghị mạnh nhất).**
28 thủ tục × 1 đoạn 40 giây = khoảng 20 phút thu âm. Một sinh viên người Mông,
một chiếc điện thoại, một buổi chiều. Kết quả: **giọng người thật, đúng phương
ngữ Quảng Tân, chạy offline, 0 đồng vận hành, không sai một chữ**. Dashboard đã
có sẵn tab upload (`🗣️ Từ vựng & giọng đọc`). Với một dự án hướng đến thi và
triển khai pilot, đây là phương án tốt hơn mọi model AI — và cũng là câu chuyện
"cộng đồng cùng làm" thuyết phục hơn khi trình bày.

**② Phiên âm RPA → chính tả kiểu Việt + TTS tiếng Việt (đang chạy trong code).**
Đây là "thủ thuật" bạn hỏi. Tiếng Mông và tiếng Việt đều là ngôn ngữ có thanh
điệu, bộ âm vị phủ nhau đáng kể. `core/hmong/rpa_vi.py` chuyển:

```
Nyob zoo, kuv xav ua ntawv pov thawj av
  →  Nhó rong, củ xả ua đẩu pỏ thẫu ả
```

rồi cho gTTS đọc bằng giọng `vi`. Kết quả là "người Việt đọc tiếng Mông" — dễ
hiểu hơn nhiều so với để máy đọc RPA theo lối tiếng Anh (`nyob` → "nai-ốp").
Bảng ánh xạ được lập từ bảng IPA của RPA; 8 thanh Mông ép vào 6 thanh Việt nên
**có mất mát** (thanh `s` và `g` hiện trùng nhau). **Bắt buộc cho một người Mông
bản địa nghe và hiệu đính bảng trong file đó trước khi dùng thật.**

**③ Ghép âm tiết (concatenative).** Thu sẵn ~150 âm tiết Mông thông dụng rồi
ghép. Chạy hoàn toàn offline, đọc được câu tự do. Nghe máy móc, cần 2-3 ngày
làm. Là phương án cho pilot nếu ① không phủ hết câu.

**④ Fine-tune MMS/VITS cho tiếng Mông Việt Nam.** MMS của Meta phủ 1.100+ ngôn
ngữ nhưng **không có tiếng Mông** (`mms-tts-hmn`, `mms-tts-mww`, `mms-tts-hnj`
đều không tồn tại). Phải tự huấn luyện: cần 3-5 giờ audio một giọng, chất lượng
ghi âm tốt, khoảng 1 tuần GPU. Đây là hạng mục xin ngân sách, không phải việc
làm trước hạn thi. Nếu làm, `ylacombe/finetune-hf-vits` là bộ công cụ phù hợp và
`ThaiKami/hmong-vn-audio` là dữ liệu khởi đầu.

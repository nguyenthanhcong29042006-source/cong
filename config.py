# -*- coding: utf-8 -*-
"""Cấu hình tập trung. Mọi hằng số / đường dẫn / công tắc bật-tắt nằm ở đây."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TTHC_DIR = DATA / "tthc"
MANIFEST = DATA / "manifest.json"
CACHE_SIMPLIFIED = DATA / "cache" / "simplified"
CACHE_AUDIO = DATA / "cache" / "audio"
AUDIO_BANK = DATA / "audio_bank"          # câu thu sẵn do người Mông đọc (nếu có)
RAW_EXCEL = DATA / "raw_excel"

for _p in (CACHE_SIMPLIFIED, CACHE_AUDIO, AUDIO_BANK, RAW_EXCEL, TTHC_DIR):
    _p.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ Models
# Google khai tử / đổi tên model khá thường xuyên (gemini-2.5-pro đã bị gỡ với
# tài khoản mới từ 2026). Vì vậy KHÔNG ghi cứng một tên model: mỗi vai trò có một
# DANH SÁCH ƯU TIÊN, core/llm.py sẽ hỏi API xem tài khoản của bạn đang có gì rồi
# chọn cái đầu tiên dùng được và nhớ lại (data/cache/models.json).
# Muốn ép cứng một model: đặt biến môi trường, ví dụ
#     set LGB_MODEL_QUALITY=gemini-3.1-pro-preview
UU_TIEN_QUALITY = [          # đọc PDF pháp lý -> dùng model mạnh nhất có thể
    # Đã bật thanh toán Google Cloud -> model Pro dùng được, và đây đúng là bước
    # cần độ chính xác nhất (đọc văn bản pháp luật, trích dẫn con số).
    "gemini-3.1-pro", "gemini-pro-latest", "gemini-2.5-pro",
    # Nếu Pro không gọi được (chưa bật thanh toán / hết hạn mức) -> tự tụt xuống Flash
    "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash",
    "gemini-flash-latest", "gemini-2.5-flash",
]
UU_TIEN_FAST = [             # phân loại ý định, dịch -> nhanh, rẻ, hạn mức cao
    "gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.1-flash-lite",
    "gemini-3.8-flash", "gemini-3.7-flash", "gemini-flash-latest",
    "gemini-2.5-flash-lite", "gemini-2.5-flash",
]
UU_TIEN_STT = [              # nghe audio -> cần model đa phương thức đầy đủ
    "gemini-3.8-flash", "gemini-3.7-flash", "gemini-flash-latest", "gemini-2.5-flash",
]

# Model KHÔNG dùng để sinh văn bản (ảnh, giọng nói, nhúng, robot, nhạc...).
# Lọc ra để cơ chế khớp-theo-tiền-tố không vô tình chọn nhầm
# (ví dụ "gemini-3.1-flash" sẽ khớp cả "gemini-3.1-flash-image").
LOAI_TRU_MODEL = (
    "image", "-tts", "embedding", "computer-use", "robotics", "lyria",
    "nano-banana", "deep-research", "transcribe", "customtools",
    "antigravity", "gemma", "veo", "imagen",
)

# Ghi đè bằng biến môi trường (nếu đặt thì bỏ qua cơ chế tự dò ở trên)
MODEL_FAST = os.getenv("LGB_MODEL_FAST", "")
MODEL_QUALITY = os.getenv("LGB_MODEL_QUALITY", "")
MODEL_STT = os.getenv("LGB_MODEL_STT", "")

CACHE_MODELS = DATA / "cache" / "models.json"

# ------------------------------------------------------------ Tiếng Mông
# 'auto'      : thử lần lượt audio_bank -> cosyvoice -> vi_phonetic
# 'audio_bank': chỉ dùng file thu sẵn (chính xác nhất, offline)
# 'cosyvoice' : model neural cục bộ (xem docs/TTS_HMONG.md)
# 'vi_phonetic': phiên âm Mông -> chính tả kiểu Việt rồi đọc bằng TTS tiếng Việt
# 'off'       : tắt hẳn giọng Mông (chỉ đọc tiếng Việt)
TTS_HMONG_PROVIDER = os.getenv("LGB_TTS_HMONG", "auto")

# 'gemini' | 'google_nmt' (mã hmn) | 'azure' (mã mww) | 'off'
TRANSLATE_PROVIDER = os.getenv("LGB_TRANSLATE", "gemini")

# Chính tả tiếng Mông dùng để HIỂN THỊ: 'rpa' (quốc tế) hoặc 'vn' (kiểu Việt Nam)
HMONG_ORTHOGRAPHY = os.getenv("LGB_HMONG_ORTHO", "vn")

# ---------------------------------------------------------------- Nhóm TTHC
DANH_MUC_THU_TUC = {
    "KHAI_SINH": "ĐĂNG KÝ KHAI SINH",
    "KET_HON": "ĐĂNG KÝ KẾT HÔN",
    "DOC_THAN": "XÁC NHẬN TÌNH TRẠNG HÔN NHÂN",
    "KHAI_TU": "ĐĂNG KÝ KHAI TỬ",
    "CHUNG_THUC": "SAO Y / CHỨNG THỰC",
    "DAT_DAI": "THỦ TỤC ĐẤT ĐAI",
    "TRO_CAP": "TRỢ CẤP XÃ HỘI",
    "KHAC": "VẤN ĐỀ KHÁC",
}

# Ngưỡng an toàn: dưới mức này thì KHÔNG tự tin trả lời, chuyển cán bộ.
NGUONG_TU_TIN = float(os.getenv("LGB_NGUONG_TU_TIN", "0.55"))

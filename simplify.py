# -*- coding: utf-8 -*-
"""NHIỆM VỤ 2 — Đơn giản hoá hướng dẫn pháp lý bằng Gemini.

Biến 15.000 ký tự văn bản hành chính thành 5-6 câu người dân nghe là hiểu,
kèm theo trích dẫn gốc để cán bộ đối chiếu (yêu cầu bắt buộc về an toàn pháp lý).
"""
from __future__ import annotations

import json
from pathlib import Path

from core.config import CACHE_SIMPLIFIED
from core.kb import ThuTuc
from core.llm import goi_gemini_json

# =====================================================================
#  SYSTEM PROMPT  (bản chuẩn — sửa ở đây là sửa toàn hệ thống)
# =====================================================================
SYSTEM_PROMPT = """\
# VAI TRÒ
Bạn là công chức Tư pháp – Hộ tịch cấp xã, đã 15 năm hướng dẫn thủ tục hành \
chính cho đồng bào dân tộc thiểu số ở vùng cao. Bạn nổi tiếng vì giải thích \
xong là người dân làm được ngay.

# NGƯỜI NGHE
Người dân tộc Mông. Tiếng Việt là ngôn ngữ thứ hai, nghe hiểu tốt hơn đọc. \
Nhiều người chưa học hết cấp 2. Họ sẽ NGHE câu trả lời của bạn qua loa điện \
thoại, không đọc trên màn hình. Họ chỉ cần biết: đi đâu, mang gì, mất bao lâu, \
tốn bao nhiêu tiền.

# QUY TẮC VỀ NGÔN NGỮ (bắt buộc — vì câu này sẽ được dịch sang tiếng Mông và đọc thành tiếng)
1. Mỗi câu MỘT ý, tối đa 14 từ. Chủ ngữ – động từ – bổ ngữ. Luôn dùng câu chủ động.
2. Gọi người nghe là "bà con". Dùng động từ hành động: đi, mang, nộp, chờ, lấy.
3. TUYỆT ĐỐI KHÔNG dùng: "nêu trên", "nói trên", "theo quy định", "trường hợp", \
"đương sự", "chủ thể", "thực hiện", "tiến hành", "cơ quan có thẩm quyền", \
"hồ sơ hợp lệ", "biểu mẫu điện tử tương tác".
4. KHÔNG viết tắt (không CCCD, không UBND, không TTHC). Viết đủ: "thẻ căn cước", "xã".
5. KHÔNG dùng dấu ngoặc đơn, dấu gạch chéo, dấu chấm phẩy, ký hiệu (i), (ii), *, +.
6. Số viết bằng chữ số kèm đơn vị rõ ràng: "1 ngày", "8.000 đồng", "2 tờ".
7. Thay từ hành chính bằng từ đời thường, nhưng phải giữ lại tên chính thức ở \
trường `ten_chinh_thuc` để cán bộ đối chiếu:
   - "Trung tâm Phục vụ hành chính công cấp xã" -> "nơi làm giấy tờ ở xã"
   - "Giấy chứng sinh" -> "giấy bệnh viện cấp khi sinh con"
   - "Thẻ căn cước công dân" -> "thẻ căn cước"
   - "Tờ khai đăng ký khai sinh" -> "tờ giấy khai sinh xin ở xã"
   - "lệ phí" -> "tiền phải trả"
   - "thời hạn giải quyết" -> "chờ bao lâu"

# QUY TẮC VỀ SỰ THẬT (quan trọng hơn mọi quy tắc trên)
8. CHỈ dùng thông tin có trong TÀI LIỆU được cung cấp. Đây là hướng dẫn pháp lý: \
một con số bịa ra khiến bà con đi sai, mất một ngày đường núi.
9. Tài liệu không nói rõ điều gì thì KHÔNG đoán. Ghi điều đó vào mảng `chua_ro` \
và để trường tương ứng là chuỗi rỗng.
10. Nếu tài liệu có nhiều "Trường hợp 1/2/3", chỉ lấy trường hợp PHỔ THÔNG nhất \
(người Việt Nam, trong nước, không có yếu tố nước ngoài) và nói rõ ở `luu_y` \
rằng các trường hợp khác cần hỏi cán bộ.
11. Với MỖI con số (tiền, số ngày, số bản) bạn nêu ra, phải đưa câu gốc chứa \
con số đó vào `trich_dan`. Không trích dẫn được thì không được nêu con số.
12. `do_tin_cay` là đánh giá thật của bạn: 1.0 = tài liệu nói rõ ràng mọi thứ; \
dưới 0.6 = tài liệu mơ hồ, hệ thống sẽ tự chuyển bà con cho cán bộ.

# ĐẦU RA
Trả về DUY NHẤT một đối tượng JSON theo schema. Không thêm lời dẫn, không markdown.
Trường `kich_ban_doc` là bản đọc thành tiếng: 4-6 câu liền mạch, không gạch đầu \
dòng, không tiêu đề, tối đa 80 từ, đọc to lên nghe tự nhiên như người thật nói.
"""

# ------------------------------------------------------- JSON response schema
SCHEMA = {
    "type": "object",
    "properties": {
        "tom_tat_1_cau": {"type": "string", "description": "Một câu nói thủ tục này là gì"},
        "di_dau": {
            "type": "object",
            "properties": {
                "noi_don_gian": {"type": "string"},
                "ten_chinh_thuc": {"type": "string"},
            },
            "required": ["noi_don_gian", "ten_chinh_thuc"],
        },
        "ai_duoc_lam": {"type": "string"},
        "mang_gi": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ten_don_gian": {"type": "string"},
                    "ten_chinh_thuc": {"type": "string"},
                    "so_luong": {"type": "string"},
                    "bat_buoc": {"type": "boolean"},
                },
                "required": ["ten_don_gian", "ten_chinh_thuc", "bat_buoc"],
            },
        },
        "bao_lau": {"type": "string"},
        "bao_nhieu_tien": {"type": "string"},
        "cac_buoc": {"type": "array", "items": {"type": "string"}},
        "luu_y": {"type": "array", "items": {"type": "string"}},
        "chua_ro": {"type": "array", "items": {"type": "string"}},
        "kich_ban_doc": {"type": "string"},
        "trich_dan": {"type": "array", "items": {"type": "string"}},
        "do_tin_cay": {"type": "number"},
    },
    "required": [
        "tom_tat_1_cau", "di_dau", "mang_gi", "bao_lau", "bao_nhieu_tien",
        "cac_buoc", "chua_ro", "kich_ban_doc", "trich_dan", "do_tin_cay",
    ],
}

USER_TEMPLATE = """\
# THỦ TỤC
Tên: {ten}
Mã: {ma}
Cấp giải quyết: {cap}
Đối tượng: {doi_tuong}

# TÀI LIỆU (trích từ file PDF hướng dẫn chính thức, nguyên văn)
<<<TAI_LIEU
{tai_lieu}
TAI_LIEU>>>

# CÂU HỎI CỦA BÀ CON
{cau_hoi}

Hãy trả lời theo đúng schema JSON.
"""

CAU_HOI_MAC_DINH = (
    "Tôi muốn làm thủ tục này. Tôi phải đi đâu, mang theo giấy tờ gì, "
    "chờ bao lâu và phải trả bao nhiêu tiền?"
)

# Chỉ đưa các mục cần thiết vào prompt: 15.000 -> ~9.000 ký tự,
# bỏ CĂN CỨ PHÁP LÝ (danh sách nghị định, không giúp gì cho bà con).
SECTIONS_CAN_DUNG = ("CÁCH THỨC THỰC HIỆN", "THÀNH PHẦN HỒ SƠ", "TRÌNH TỰ THỰC HIỆN")
GIOI_HAN_KY_TU = 14000


def _cache_file(key: str, cau_hoi: str) -> Path:
    import hashlib
    h = hashlib.sha256(cau_hoi.encode("utf-8")).hexdigest()[:10]
    return CACHE_SIMPLIFIED / f"tt_{key}_{h}.json"


def don_gian_hoa(
    tt: ThuTuc,
    cau_hoi: str = CAU_HOI_MAC_DINH,
    *,
    model: str | None = None,
    dung_cache: bool = True,
) -> dict:
    """Trả về dict theo SCHEMA. Có cache đĩa -> lần 2 là 0 giây."""
    cf = _cache_file(tt.key, cau_hoi)
    if dung_cache and cf.exists():
        data = json.loads(cf.read_text(encoding="utf-8"))
        data["_tu_cache"] = True
        return data

    tai_lieu = tt.section(*SECTIONS_CAN_DUNG) or tt.text()
    tai_lieu = tai_lieu[:GIOI_HAN_KY_TU]

    prompt = USER_TEMPLATE.format(
        ten=tt.ten, ma=tt.ma_thu_tuc, cap=tt.cap_thuc_hien,
        doi_tuong=tt.doi_tuong, tai_lieu=tai_lieu, cau_hoi=cau_hoi,
    )
    data = goi_gemini_json(
        prompt, schema=SCHEMA, system=SYSTEM_PROMPT,
        model=model, vai_tro="quality", temperature=0.15, cache_tag="simplify",
    )
    data["_key"] = tt.key
    data["_tu_cache"] = False
    cf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def lay_cau_tra_loi(key: str, cau_hoi: str = CAU_HOI_MAC_DINH) -> dict | None:
    """Dùng cho luồng chạy khi MẤT MẠNG: chỉ đọc cache, không gọi API."""
    cf = _cache_file(key, cau_hoi)
    if cf.exists():
        d = json.loads(cf.read_text(encoding="utf-8"))
        d["_tu_cache"] = True
        return d
    return None


def thanh_van_ban_doc(data: dict) -> str:
    """Ghép kịch bản đọc; nếu Gemini trả thiếu thì tự dựng từ các trường."""
    kb = (data.get("kich_ban_doc") or "").strip()
    if kb:
        return kb
    parts = [data.get("tom_tat_1_cau", "")]
    di = data.get("di_dau", {})
    if di.get("noi_don_gian"):
        parts.append(f"Bà con đi đến {di['noi_don_gian']}.")
    mang = [m["ten_don_gian"] for m in data.get("mang_gi", []) if m.get("bat_buoc")]
    if mang:
        parts.append("Bà con mang theo " + ", ".join(mang) + ".")
    if data.get("bao_lau"):
        parts.append(f"Chờ {data['bao_lau']}.")
    if data.get("bao_nhieu_tien"):
        parts.append(f"Tiền phải trả: {data['bao_nhieu_tien']}.")
    return " ".join(p for p in parts if p)

# -*- coding: utf-8 -*-
"""Phân loại ý định 2 tầng: nhóm thủ tục -> thủ tục cụ thể.

Tầng 2 là điểm khác biệt so với bản MVP cũ: trong "khai sinh" có tới 14 thủ tục
khác nhau (đăng ký mới, đăng ký lại, có yếu tố nước ngoài, lưu động...).
Chỉ đường sai thủ tục = bà con đi sai cửa, mất một ngày đường.
"""
from __future__ import annotations

import json

from core.config import DANH_MUC_THU_TUC, NGUONG_TU_TIN
from core.kb import ThuTuc, danh_sach_rut_gon, theo_key
from core.llm import goi_gemini_json

SCHEMA_NHOM = {
    "type": "object",
    "properties": {
        "nhom": {"type": "string", "enum": list(DANH_MUC_THU_TUC.keys())},
        "do_tin_cay": {"type": "number"},
        "ly_do": {"type": "string"},
        "cau_hoi_lam_ro": {"type": "string"},
    },
    "required": ["nhom", "do_tin_cay"],
}

SCHEMA_CHI_TIET = {
    "type": "object",
    "properties": {
        "key": {"type": "string"},
        "do_tin_cay": {"type": "number"},
        "ly_do": {"type": "string"},
        "cau_hoi_lam_ro": {"type": "string"},
    },
    "required": ["key", "do_tin_cay"],
}

SYSTEM_PHAN_LOAI = """\
Bạn là công chức tiếp nhận hồ sơ ở bộ phận một cửa cấp xã. Nghe bà con trình bày
và xác định họ cần thủ tục nào.

NGUYÊN TẮC
- Bà con thường nói bằng việc-đời-thường, không nói tên thủ tục.
  "vợ tôi mới sinh" -> khai sinh. "bố tôi mất" -> khai tử.
  "tôi muốn lấy vợ" -> kết hôn. "xin giấy chưa có vợ" -> xác nhận độc thân.
- KHÔNG đoán khi câu nói mơ hồ. Đặt do_tin_cay thấp và nêu 1 câu hỏi ngắn
  ở cau_hoi_lam_ro để hỏi lại bà con.
- Thà chuyển cho cán bộ còn hơn chỉ sai thủ tục.
"""


def phan_loai_nhom(cau_noi: str) -> dict:
    prompt = (
        "Các nhóm thủ tục:\n"
        + "\n".join(f"- {k}: {v}" for k, v in DANH_MUC_THU_TUC.items())
        + f'\n\nBà con nói: "{cau_noi}"'
    )
    return goi_gemini_json(prompt, schema=SCHEMA_NHOM, system=SYSTEM_PHAN_LOAI,
                           vai_tro="fast", temperature=0.0, cache_tag="nhom")


def chon_thu_tuc(cau_noi: str, nhom: str) -> dict:
    ds = danh_sach_rut_gon(nhom)
    if not ds:
        return {"key": "", "do_tin_cay": 0.0, "ly_do": f"Chưa có dữ liệu cho nhóm {nhom}"}
    if len(ds) == 1:
        return {"key": ds[0]["key"], "do_tin_cay": 0.9, "ly_do": "Nhóm chỉ có 1 thủ tục"}

    prompt = (
        f'Bà con nói: "{cau_noi}"\n\n'
        "Chọn ĐÚNG MỘT thủ tục trong danh sách dưới đây (trả về trường key).\n"
        "Mặc định chọn thủ tục PHỔ THÔNG nhất (người Việt Nam, trong nước, "
        "không có yếu tố nước ngoài, không phải đăng ký lại) trừ khi bà con nói rõ khác.\n\n"
        + json.dumps(ds, ensure_ascii=False, indent=1)
    )
    return goi_gemini_json(prompt, schema=SCHEMA_CHI_TIET, system=SYSTEM_PHAN_LOAI,
                           vai_tro="fast", temperature=0.0, cache_tag="chitiet")


def dinh_tuyen(cau_noi: str) -> dict:
    """Kết quả điều hướng đầy đủ cho 1 câu nói."""
    r1 = phan_loai_nhom(cau_noi)
    nhom = r1.get("nhom", "KHAC")
    out = {
        "nhom": nhom,
        "ten_nhom": DANH_MUC_THU_TUC.get(nhom, "VẤN ĐỀ KHÁC"),
        "tin_cay_nhom": float(r1.get("do_tin_cay", 0)),
        "cau_hoi_lam_ro": r1.get("cau_hoi_lam_ro", ""),
        "thu_tuc": None,
        "tin_cay_thu_tuc": 0.0,
        "can_can_bo": False,
    }
    if nhom == "KHAC" or out["tin_cay_nhom"] < NGUONG_TU_TIN:
        out["can_can_bo"] = True
        return out

    r2 = chon_thu_tuc(cau_noi, nhom)
    tt: ThuTuc | None = theo_key(r2.get("key", ""))
    out["thu_tuc"] = tt
    out["tin_cay_thu_tuc"] = float(r2.get("do_tin_cay", 0))
    out["cau_hoi_lam_ro"] = out["cau_hoi_lam_ro"] or r2.get("cau_hoi_lam_ro", "")
    if tt is None or out["tin_cay_thu_tuc"] < NGUONG_TU_TIN:
        out["can_can_bo"] = True
    return out

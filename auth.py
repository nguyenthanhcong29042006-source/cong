# -*- coding: utf-8 -*-
"""Tài khoản & phân quyền.

Lưu ở `data/users.json`. Mật khẩu KHÔNG lưu dạng chữ thường: băm bằng
PBKDF2-HMAC-SHA256 (200.000 vòng, mỗi tài khoản một muối riêng) — chỉ dùng thư
viện chuẩn của Python, không thêm phụ thuộc.

MỨC BẢO MẬT: đủ cho hệ thống nội bộ chạy trong mạng xã / máy cán bộ. Nếu sau này
đưa app lên Internet công khai thì phải thay bằng đăng nhập thật (OAuth, hoặc
`st.login` của Streamlit) và bắt buộc đổi mật khẩu mặc định.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime

from core.config import DATA

USERS_FILE = DATA / "users.json"
VONG_LAP = 200_000

# ------------------------------------------------------------------ Quyền
QUYEN = {
    "kho_thu_tuc":      "Kho thủ tục — xem, sửa danh mục, làm nóng câu trả lời",
    "cap_nhat_du_lieu": "Cập nhật dữ liệu — upload Excel/PDF, bóc tách lại",
    "cau_tra_loi":      "Kiểm duyệt câu trả lời — sửa và ký duyệt",
    "tu_vung_giong":    "Từ vựng & giọng đọc — từ điển Việt–Mông, ngân hàng giọng",
    "bo_nho_tam":       "Bộ nhớ tạm — xem và xoá cache",
}
QUYEN_ADMIN = "tai_khoan"          # riêng admin: quản lý tài khoản
TAT_CA_QUYEN = list(QUYEN.keys())

# Tài khoản khởi tạo lần đầu (mật khẩu sẽ được băm ngay, file gốc không lưu chữ thường)
MAC_DINH = [
    ("admin_Minh", "admin",        "admin",  "Minh — quản trị hệ thống"),
    ("APAG_han",   "123123",       "can_bo", "Cán bộ Hân"),
    ("APAG_thai",  "123123",       "can_bo", "Cán bộ Thái"),
    ("APAG_gv",    "giangvien123", "can_bo", "Giảng viên hướng dẫn"),
]


# ------------------------------------------------------------------ Băm
def bam(mat_khau: str, muoi: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", mat_khau.encode("utf-8"),
                               bytes.fromhex(muoi), VONG_LAP).hex()


def _tao_ban_ghi(ten: str, mat_khau: str, vai_tro: str, mo_ta: str,
                 quyen: list[str] | None = None) -> dict:
    muoi = secrets.token_hex(16)
    return {
        "ten_dang_nhap": ten,
        "mo_ta": mo_ta,
        "vai_tro": vai_tro,                       # 'admin' | 'can_bo'
        "quyen": TAT_CA_QUYEN if quyen is None else quyen,
        "muoi": muoi,
        "bam": bam(mat_khau, muoi),
        "kich_hoat": True,
        "tao_luc": datetime.now().isoformat(timespec="seconds"),
        "dang_nhap_cuoi": "",
        "phai_doi_mk": False,
    }


# ------------------------------------------------------------------ Đọc/ghi
def doc_users() -> dict[str, dict]:
    if not USERS_FILE.exists():
        khoi_tao_mac_dinh()
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def luu_users(users: dict[str, dict]) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = USERS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, USERS_FILE)


def khoi_tao_mac_dinh(ghi_de: bool = False) -> dict[str, dict]:
    if USERS_FILE.exists() and not ghi_de:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    users = {t: _tao_ban_ghi(t, mk, vt, mt) for t, mk, vt, mt in MAC_DINH}
    luu_users(users)
    return users


# ------------------------------------------------------------------ Nghiệp vụ
def kiem_tra_dang_nhap(ten: str, mat_khau: str) -> dict | None:
    users = doc_users()
    u = users.get((ten or "").strip())
    if not u or not u.get("kich_hoat", True):
        return None
    if not secrets.compare_digest(bam(mat_khau, u["muoi"]), u["bam"]):
        return None
    u["dang_nhap_cuoi"] = datetime.now().isoformat(timespec="seconds")
    users[u["ten_dang_nhap"]] = u
    luu_users(users)
    return u


def tao_user(ten: str, mat_khau: str, vai_tro: str = "can_bo",
             mo_ta: str = "", quyen: list[str] | None = None) -> tuple[bool, str]:
    ten = (ten or "").strip()
    if not ten:
        return False, "Tên đăng nhập không được để trống."
    if len(mat_khau or "") < 4:
        return False, "Mật khẩu phải từ 4 ký tự trở lên."
    users = doc_users()
    if ten in users:
        return False, f"Tên đăng nhập '{ten}' đã tồn tại."
    users[ten] = _tao_ban_ghi(ten, mat_khau, vai_tro, mo_ta, quyen)
    luu_users(users)
    return True, f"Đã tạo tài khoản '{ten}'."


def doi_mat_khau(ten: str, mat_khau_moi: str) -> tuple[bool, str]:
    if len(mat_khau_moi or "") < 4:
        return False, "Mật khẩu phải từ 4 ký tự trở lên."
    users = doc_users()
    if ten not in users:
        return False, "Không tìm thấy tài khoản."
    muoi = secrets.token_hex(16)
    users[ten].update({"muoi": muoi, "bam": bam(mat_khau_moi, muoi), "phai_doi_mk": False})
    luu_users(users)
    return True, f"Đã đổi mật khẩu cho '{ten}'."


def cap_nhat_quyen(ten: str, quyen: list[str], vai_tro: str | None = None,
                   mo_ta: str | None = None, kich_hoat: bool | None = None) -> tuple[bool, str]:
    users = doc_users()
    if ten not in users:
        return False, "Không tìm thấy tài khoản."
    users[ten]["quyen"] = [q for q in quyen if q in QUYEN]
    if vai_tro is not None:
        users[ten]["vai_tro"] = vai_tro
    if mo_ta is not None:
        users[ten]["mo_ta"] = mo_ta
    if kich_hoat is not None:
        users[ten]["kich_hoat"] = bool(kich_hoat)
    if _dem_admin(users) == 0:
        return False, "Phải còn ít nhất một tài khoản quản trị đang hoạt động."
    luu_users(users)
    return True, f"Đã cập nhật '{ten}'."


def xoa_user(ten: str) -> tuple[bool, str]:
    users = doc_users()
    if ten not in users:
        return False, "Không tìm thấy tài khoản."
    con_lai = {k: v for k, v in users.items() if k != ten}
    if _dem_admin(con_lai) == 0:
        return False, "Không thể xoá tài khoản quản trị cuối cùng."
    luu_users(con_lai)
    return True, f"Đã xoá '{ten}'."


def _dem_admin(users: dict[str, dict]) -> int:
    return sum(1 for u in users.values()
               if u.get("vai_tro") == "admin" and u.get("kich_hoat", True))


# ------------------------------------------------------------ Dùng trong app
def nguoi_dang_nhap():
    import streamlit as st
    return st.session_state.get("nguoi_dung")


def la_admin() -> bool:
    u = nguoi_dang_nhap()
    return bool(u and u.get("vai_tro") == "admin")


def co_quyen(quyen: str) -> bool:
    u = nguoi_dang_nhap()
    if not u:
        return False
    if u.get("vai_tro") == "admin":
        return True                       # admin có mọi quyền
    return quyen in (u.get("quyen") or [])


def quyen_cua(u: dict) -> list[str]:
    return TAT_CA_QUYEN if u.get("vai_tro") == "admin" else (u.get("quyen") or [])


def chan_neu_thieu_quyen(quyen: str) -> bool:
    """Trả True nếu ĐƯỢC phép; nếu không thì vẽ thông báo và trả False."""
    import streamlit as st
    if co_quyen(quyen):
        return True
    st.error(f"Tài khoản của bạn không có quyền: **{QUYEN.get(quyen, quyen)}**. "
             "Liên hệ quản trị viên để được cấp.")
    return False

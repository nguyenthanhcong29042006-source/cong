# -*- coding: utf-8 -*-
"""Tài khoản & phân quyền — CHỈ quản trị viên vào được."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core import auth

if not auth.la_admin():
    st.error("Trang này chỉ dành cho quản trị viên.")
    st.stop()

toi = auth.nguoi_dang_nhap()
st.title("👥 Tài khoản & phân quyền")
st.caption("Chỉ quản trị viên thấy trang này. Quản trị viên mặc định có đủ 5 quyền.")

users = auth.doc_users()

# Cảnh báo mật khẩu mặc định còn nguyên
con_mac_dinh = [t for t, mk, _, _ in auth.MAC_DINH
                if t in users and auth.bam(mk, users[t]["muoi"]) == users[t]["bam"]]
if con_mac_dinh:
    st.warning(
        "Các tài khoản sau vẫn dùng **mật khẩu khởi tạo**: "
        + ", ".join(f"`{t}`" for t in con_mac_dinh)
        + ". Đổi trước khi đưa máy ra khỏi phòng làm việc. "
          "Hệ thống này chỉ nên chạy trong mạng nội bộ của xã.", icon="🔑")

tab_ds, tab_them, tab_quyen = st.tabs(
    ["📋 Danh sách", "➕ Tạo tài khoản", "🔐 Bảng quyền"])

# ============================================================ DANH SÁCH
with tab_ds:
    rows = []
    for t, u in users.items():
        q = auth.quyen_cua(u)
        rows.append({
            "Tài khoản": t,
            "Mô tả": u.get("mo_ta", ""),
            "Vai trò": "Quản trị" if u["vai_tro"] == "admin" else "Cán bộ",
            "Số quyền": f"{len(q)}/{len(auth.QUYEN)}",
            "Hoạt động": "✅" if u.get("kich_hoat", True) else "⛔",
            "Đăng nhập cuối": (u.get("dang_nhap_cuoi") or "—").replace("T", " "),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Sửa một tài khoản")
    chon = st.selectbox("Chọn tài khoản", list(users.keys()),
                        format_func=lambda t: f"{t} — {users[t].get('mo_ta','')}")
    u = users[chon]
    la_chinh_minh = chon == toi["ten_dang_nhap"]

    with st.form("sua_tk"):
        mo_ta = st.text_input("Mô tả (họ tên, chức danh)", u.get("mo_ta", ""))
        c1, c2 = st.columns(2)
        vai_tro = c1.selectbox(
            "Vai trò", ["can_bo", "admin"],
            index=0 if u["vai_tro"] == "can_bo" else 1,
            format_func=lambda v: "Cán bộ" if v == "can_bo" else "Quản trị viên (toàn quyền)")
        kich_hoat = c2.checkbox("Cho phép đăng nhập", value=u.get("kich_hoat", True))

        st.markdown("**Quyền trên trang Quản trị kho**")
        if vai_tro == "admin":
            st.caption("Quản trị viên luôn có đủ 5 quyền, không cần tick.")
        chon_quyen = []
        for q, nhan in auth.QUYEN.items():
            if st.checkbox(nhan, value=q in (u.get("quyen") or []), key=f"q_{chon}_{q}"):
                chon_quyen.append(q)

        if st.form_submit_button("💾 Lưu", type="primary", use_container_width=True):
            if la_chinh_minh and (vai_tro != "admin" or not kich_hoat):
                st.error("Không thể tự hạ quyền hoặc tự khoá tài khoản đang đăng nhập.")
            else:
                ok, msg = auth.cap_nhat_quyen(chon, chon_quyen, vai_tro=vai_tro,
                                              mo_ta=mo_ta, kich_hoat=kich_hoat)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()

    st.markdown("**Đặt lại mật khẩu**")
    with st.form("doi_mk"):
        mk1 = st.text_input("Mật khẩu mới", type="password")
        mk2 = st.text_input("Nhập lại", type="password")
        if st.form_submit_button("🔑 Đổi mật khẩu", use_container_width=True):
            if mk1 != mk2:
                st.error("Hai ô mật khẩu không giống nhau.")
            else:
                ok, msg = auth.doi_mat_khau(chon, mk1)
                (st.success if ok else st.error)(msg)

    with st.expander("🗑️ Xoá tài khoản này"):
        st.caption("Không thể xoá tài khoản đang đăng nhập, cũng không thể xoá "
                   "quản trị viên cuối cùng.")
        xac_nhan = st.text_input(f"Gõ `{chon}` để xác nhận", key="xn_xoa")
        if st.button("Xoá vĩnh viễn", disabled=(xac_nhan != chon or la_chinh_minh)):
            ok, msg = auth.xoa_user(chon)
            (st.success if ok else st.error)(msg)
            if ok:
                st.rerun()

# ========================================================= TẠO TÀI KHOẢN
with tab_them:
    with st.form("tao_tk", clear_on_submit=True):
        c1, c2 = st.columns(2)
        ten_moi = c1.text_input("Tên đăng nhập", placeholder="APAG_ten")
        mk_moi = c2.text_input("Mật khẩu", type="password")
        mo_ta_moi = st.text_input("Mô tả (họ tên, chức danh)")
        vai_tro_moi = st.selectbox(
            "Vai trò", ["can_bo", "admin"],
            format_func=lambda v: "Cán bộ" if v == "can_bo" else "Quản trị viên")
        st.markdown("**Quyền** (mặc định cấp đủ 5 quyền)")
        q_moi = [q for q, nhan in auth.QUYEN.items()
                 if st.checkbox(nhan, value=True, key=f"new_{q}")]
        if st.form_submit_button("➕ Tạo tài khoản", type="primary",
                                 use_container_width=True):
            ok, msg = auth.tao_user(ten_moi, mk_moi, vai_tro_moi, mo_ta_moi, q_moi)
            (st.success if ok else st.error)(msg)
            if ok:
                st.rerun()

# =========================================================== BẢNG QUYỀN
with tab_quyen:
    st.caption("Ai đang có quyền gì. Sửa ở tab **Danh sách**.")
    bang = []
    for t, u in users.items():
        q = auth.quyen_cua(u)
        bang.append({"Tài khoản": t,
                     **{nhan: ("✅" if k in q else "—") for k, nhan in auth.QUYEN.items()}})
    st.dataframe(pd.DataFrame(bang), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**Ý nghĩa từng quyền**")
    for k, nhan in auth.QUYEN.items():
        st.markdown(f"- `{k}` — {nhan}")

    st.divider()
    st.caption("Mật khẩu được băm bằng PBKDF2-HMAC-SHA256, 200.000 vòng, muối riêng "
               "cho từng tài khoản. File `data/users.json` không chứa mật khẩu dạng "
               "chữ thường — nhưng vẫn nên để ngoài Git.")
    if st.button("⚠️ Khôi phục 4 tài khoản khởi tạo (ghi đè toàn bộ)"):
        auth.khoi_tao_mac_dinh(ghi_de=True)
        st.success("Đã khôi phục. Hãy đăng xuất rồi đăng nhập lại.")

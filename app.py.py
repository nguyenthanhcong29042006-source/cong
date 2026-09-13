# -*- coding: utf-8 -*-
"""LUẬT GẦN BẢN — điểm vào duy nhất của ứng dụng.
"Không để khoảng cách số trở thành khoảng cách công lý"

File này chỉ làm 3 việc: dựng header, xử lý đăng nhập, và quyết định
người đang dùng được vào những trang nào (st.navigation).

Chạy:  python -m streamlit run app.py
"""
from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from core import auth

ROOT = Path(__file__).resolve().parent

st.set_page_config(page_title="Luật Gần Bản", page_icon="⚖️",
                   layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
  .stApp, p, h1,h2,h3,h4,h5,h6, label, button, input, .stMarkdown, .stText, .stTextArea
      { font-family: 'Times New Roman', Times, serif !important; }
  [data-testid="stExpanderToggleIcon"], [data-testid="stIconMaterial"],
  [data-testid="stFileUploadDropzone"] span, .st-icon, .material-icons,
  .material-symbols-rounded
      { font-family: 'Material Symbols Rounded','Material Icons',sans-serif !important; }
  .the-tra-loi { font-size: 20px; line-height: 1.6; }
  .the-tra-loi b { color: #003366; }
  div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 10px; }
  /* nút micro to, dễ bấm cho người lớn tuổi */
  [data-testid="stAudioInput"] { transform: scale(1.15); transform-origin: left center; }

  /* Ẩn thanh công cụ mặc định để người dùng tập trung vào phần hỏi đáp. */
  [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"]
      { display: none !important; }
  [data-testid="stMainBlockContainer"], .block-container
      { padding-top: 0.6rem !important; }

  /* Giữ nhận diện dự án ở một hàng nhỏ gọn, không chiếm vùng tương tác. */
  .compact-project-header
      { display: flex; align-items: center; gap: 10px; min-height: 40px;
        margin: 0 0 10px; padding: 0 0 8px; border-bottom: 0.5px solid #ddd;
        white-space: nowrap; overflow: hidden; }
  .compact-project-name
      { color: #003366; font-size: 16px; font-weight: bold; flex-shrink: 0; }
  .compact-project-slogan
      { color: #444; font-size: 12px; font-style: italic; overflow: hidden;
        text-overflow: ellipsis; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _logo_b64() -> str:
    p = ROOT / "logo_hoc_vien.png"
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


def header() -> None:
    b64 = _logo_b64()
    # Ảnh logo có nhiều khoảng trắng quanh biểu tượng. Khung nhỏ này chỉ hiển thị
    # phần logo APAG, để header không còn chiếm nhiều chiều cao.
    img = (f'<img src="data:image/png;base64,{b64}" '
           'style="width:120px;height:34px;object-fit:cover;object-position:center;" '
           'alt="APAG">' if b64 else
           '<div style="width:120px;text-align:center;color:gray;">[APAG]</div>')
    st.markdown(f"""
    <div class="compact-project-header">
      <div style="flex:0 0 120px;">{img}</div>
      <div class="compact-project-name">DỰ ÁN LUẬT GẦN BẢN</div>
      <div style="color:#bbb;flex-shrink:0;">|</div>
      <div class="compact-project-slogan">
        "Không để khoảng cách số trở thành khoảng cách công lý"
      </div>
    </div>
    """, unsafe_allow_html=True)


header()

# ======================================================= ĐĂNG NHẬP (thanh bên)
auth.khoi_tao_mac_dinh()          # lần chạy đầu tiên: tạo 4 tài khoản mặc định

with st.sidebar:
    u = auth.nguoi_dang_nhap()
    if u:
        st.markdown(f"**{u.get('mo_ta') or u['ten_dang_nhap']}**")
        st.caption(f"`{u['ten_dang_nhap']}` · "
                   f"{'Quản trị viên' if u['vai_tro'] == 'admin' else 'Cán bộ'}")
        if u.get("phai_doi_mk"):
            st.warning("Bạn cần đổi mật khẩu.", icon="🔑")
        if st.button("Đăng xuất", use_container_width=True):
            del st.session_state["nguoi_dung"]
            st.rerun()
    else:
        st.markdown("### Đăng nhập cán bộ")
        st.caption("Bà con không cần đăng nhập — cứ dùng trang Hỏi đáp.")
        with st.form("dang_nhap", clear_on_submit=False):
            ten = st.text_input("Tên đăng nhập")
            mk = st.text_input("Mật khẩu", type="password")
            if st.form_submit_button("Đăng nhập", type="primary",
                                     use_container_width=True):
                nd = auth.kiem_tra_dang_nhap(ten, mk)
                if nd:
                    st.session_state["nguoi_dung"] = nd
                    st.rerun()
                else:
                    st.error("Sai tên đăng nhập hoặc mật khẩu.")

# ============================================================ ĐIỀU HƯỚNG
if not hasattr(st, "navigation") or not hasattr(st, "Page"):
    st.error(
        "Phiên bản Streamlit đang cài quá cũ (cần từ **1.36** trở lên).\n\n"
        "Mở terminal ở thư mục dự án và chạy:\n\n"
        "```\npip install -U streamlit\n```"
    )
    st.stop()

trang = [st.Page("giao_dien/cong_dan.py", title="Hỏi đáp thủ tục",
                 icon=":material/record_voice_over:", default=True)]

u = auth.nguoi_dang_nhap()
if u and (auth.la_admin() or auth.quyen_cua(u)):
    trang.append(st.Page("giao_dien/quan_tri.py", title="Quản trị kho",
                         icon=":material/settings:"))
if auth.la_admin():
    trang.append(st.Page("giao_dien/tai_khoan.py", title="Tài khoản & phân quyền",
                         icon=":material/manage_accounts:"))

st.navigation(trang, position="sidebar").run()

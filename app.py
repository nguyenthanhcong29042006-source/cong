# -*- coding: utf-8 -*-
"""LUẬT GẦN BẢN — điểm vào duy nhất của ứng dụng.

File này chỉ làm 3 việc: dựng header, xử lý đăng nhập, và quyết định
người đang dùng được vào những trang nào (st.navigation).
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
  div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; }
  
  /* Tối ưu nút micro nổi bật, to tròn ở giữa */
  [data-testid="stAudioInput"] { 
      display: flex;
      justify-content: center;
      margin: 15px auto;
  }
  [data-testid="stAudioInput"] > div {
      background: #f0f7ff;
      border: 2px dashed #003366;
      border-radius: 20px;
      padding: 10px;
  }

  /* Ẩn thanh công cụ Streamlit */
  [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"]
      { display: none !important; }
  [data-testid="stMainBlockContainer"], .block-container
      { padding-top: 0.4rem !important; max-width: 700px; }

  /* Header siêu gọn */
  .compact-project-header
      { display: flex; align-items: center; justify-content: space-between; min-height: 45px;
        margin: 0 0 8px; padding: 0 0 6px; border-bottom: 1px solid #e0e0e0; }
  .compact-project-name
      { color: #003366; font-size: 17px; font-weight: bold; }
  .compact-project-slogan
      { color: #d97706; font-size: 13px; font-weight: 600; font-style: italic; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _logo_b64() -> str:
    p = ROOT / "logo_hoc_vien.png"
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


def header() -> None:
    b64 = _logo_b64()
    img = (f'<img src="data:image/png;base64,{b64}" '
           'style="width:110px;height:32px;object-fit:cover;object-position:center;" '
           'alt="APAG">' if b64 else
           '<div style="width:100px;text-align:center;color:gray;">[APAG]</div>')
    st.markdown(f"""
    <div class="compact-project-header">
      <div style="display:flex; align-items:center; gap:10px;">
        {img}
        <div class="compact-project-name">LUẬT GẦN BẢN</div>
      </div>
      <div class="compact-project-slogan">
        "Đưa chính sách đến gần đồng bào"
      </div>
    </div>
    """, unsafe_allow_html=True)


header()

auth.khoi_tao_mac_dinh()

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

if not hasattr(st, "navigation") or not hasattr(st, "Page"):
    st.error("Phiên bản Streamlit quá cũ, cần từ 1.36 trở lên.")
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

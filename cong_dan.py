# -*- coding: utf-8 -*-
"""Cổng người dân — hỏi đáp thủ tục bằng giọng nói tối ưu Voice First."""
from __future__ import annotations

import hashlib
import time
from datetime import datetime

import streamlit as st

from core import kb
from core.config import (DANH_MUC_THU_TUC, HMONG_ORTHOGRAPHY, NGUONG_TU_TIN,
                         TTS_HMONG_PROVIDER)
from core.llm import LoiQuota
from core.router import dinh_tuyen
from core.simplify import CAU_HOI_MAC_DINH, don_gian_hoa, thanh_van_ban_doc
from core.stt import nghe
from core.translate import dich_sang_mong, dich_sang_viet
from core.tts import NHAN_TANG, phat_tieng_mong, tts_tieng_viet

ss = st.session_state
ss.setdefault("danh_sach_yeu_cau", [])
ss.setdefault("ket_qua", None)
ss.setdefault("cau_noi", "")
ss.setdefault("audio_da_xu_ly", "")

if not kb.load_kb():
    st.error(
        "**Kho dữ liệu trống.** Hãy chạy: `python tools/extract_tthc.py`"
    )
    st.stop()


@st.cache_data(ttl=3600, show_spinner=False)
def _dinh_tuyen(cau_noi: str) -> dict:
    r = dinh_tuyen(cau_noi)
    r["_key"] = r["thu_tuc"].key if r["thu_tuc"] else ""
    r.pop("thu_tuc", None)
    return r


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _don_gian_hoa(key: str, cau_hoi: str) -> dict:
    return don_gian_hoa(kb.theo_key(key), cau_hoi)


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _dich_mong(text: str) -> dict:
    return dich_sang_mong(text)


def _thong_diep_loi(e: Exception) -> str:
    if isinstance(e, LoiQuota):
        return ("Hệ thống đang bận do vượt quá lượt miễn phí tạm thời. "
                "Bà con vui lòng thử lại sau ít phút hoặc chọn nhanh thủ tục ở mục bên dưới.")
    return "Máy chưa nghe rõ, bà con bấm nói lại nhé."


def chay_pipeline(cau_noi: str, *, phat_giong_mong: bool = True) -> dict:
    t0 = time.perf_counter()
    kq: dict = {"cau_noi": cau_noi, "thoi_gian": {}}

    with st.status("Đang lắng nghe và tìm kiếm hướng dẫn…", expanded=True) as box:
        box.write("🧭 Đang tra cứu thủ tục cho bà con…")
        t = time.perf_counter()
        try:
            tuyen = _dinh_tuyen(cau_noi)
        except Exception as e:
            kq["loi"] = _thong_diep_loi(e)
            box.update(label="Chưa xử lý được", state="error", expanded=False)
            return kq
        kq["thoi_gian"]["dinh_tuyen"] = time.perf_counter() - t
        kq["tuyen"] = tuyen
        tt = kb.theo_key(tuyen["_key"]) if tuyen["_key"] else None
        kq["thu_tuc"] = tt

        if tuyen["can_can_bo"] or tt is None:
            box.update(label="Cần cán bộ hỗ trợ trực tiếp", state="complete", expanded=False)
            return kq
        box.write(f"   ↳ **{tt.ten}**")

        box.write("📖 Đang rút gọn nội dung hướng dẫn…")
        t = time.perf_counter()
        try:
            kq["don_gian"] = _don_gian_hoa(tt.key, CAU_HOI_MAC_DINH)
        except Exception as e:
            kq["loi"] = _thong_diep_loi(e)
            box.update(label="Chưa xử lý được", state="error", expanded=False)
            return kq
        kq["thoi_gian"]["don_gian_hoa"] = time.perf_counter() - t
        kq["kich_ban"] = thanh_van_ban_doc(kq["don_gian"])

        if phat_giong_mong:
            box.write("🔄 Đang chuyển sang tiếng Mông…")
            t = time.perf_counter()
            try:
                kq["mong"] = _dich_mong(kq["kich_ban"])
                kq["thoi_gian"]["dich"] = time.perf_counter() - t

                box.write("🔊 Đang tạo giọng đọc…")
                t = time.perf_counter()
                audio, tang = phat_tieng_mong(kq["mong"]["rpa"], key=tt.key)
                kq["thoi_gian"]["tts"] = time.perf_counter() - t
                kq["audio_mong"] = str(audio) if audio else ""
                kq["tang_tts"] = tang
            except Exception as e:
                kq["canh_bao"] = "Phần âm thanh tiếng Mông đang bận, đã hiển thị đầy đủ văn bản."
        
        kq["thoi_gian"]["tong"] = time.perf_counter() - t0
        box.update(label="Đã hoàn thành hướng dẫn!", state="complete", expanded=False)
    return kq


def xu_ly_cau_noi(van_ban: str) -> None:
    ss.cau_noi = van_ban
    ss.ket_qua = chay_pipeline(van_ban)


# ==========================================================================
# GIAO DIỆN CHÍNH: VOICE FIRST (MẶC ĐỊNH TIẾNG MÔNG)
# ==========================================================================
st.markdown("<h3 style='text-align: center; color: #003366; margin-bottom: 0px;'>🎙️ HỎI ĐÁP THỦ TỤC BẰNG GIỌNG NÓI</h3>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #555; font-size: 14px;'>Bấm vào biểu tượng micro bên dưới để nói yêu cầu của bà con</p>", unsafe_allow_html=True)

# Chọn ngôn ngữ (Mặc định Tiếng Mông)
col_l1, col_l2 = st.columns(2)
ngon_ngu = st.radio(
    "Chọn ngôn ngữ", 
    ["🔊 Tiếng Mông (Hmong)", "🔊 Tiếng Việt"],
    index=0, 
    horizontal=True, 
    label_visibility="collapsed"
)

audio_in = st.audio_input("Bấm vào đây để nói", label_visibility="collapsed")

if audio_in is not None:
    raw = audio_in.getvalue()
    van_tay = hashlib.sha256(raw).hexdigest()[:16]
    is_mong = ("Tiếng Mông" in ngon_ngu)
    if van_tay != ss.audio_da_xu_ly and len(raw) > 2000:
        ss.audio_da_xu_ly = van_tay
        with st.spinner("🎧 Máy đang lắng nghe…"):
            van_ban, _nguon = nghe(audio_in, tieng_mong=is_mong)
        if not van_ban:
            st.error("Máy chưa nghe rõ, bà con bấm nói lại nhé.")
        else:
            if is_mong:
                dong_vi = [l for l in van_ban.splitlines() if l.startswith("VI:")]
                van_ban = (dong_vi[0][3:].strip() if dong_vi
                           else dich_sang_viet(van_ban))
            xu_ly_cau_noi(van_ban)
    elif 0 < len(raw) <= 2000:
        st.warning("Bản ghi quá ngắn. Bà con bấm micro và nói lâu hơn một chút.")


# ==========================================================================
# KẾT QUẢ HIỂN THỊ THÂN THIỆN
# ==========================================================================
def nut_goi_can_bo(kq: dict) -> None:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🙋 CẦN CÁN BỘ / TÌNH NGUYỆN VIÊN HỖ TRỢ TRỰC TIẾP",
                 use_container_width=True):
        tt = kq.get("thu_tuc")
        ss.danh_sach_yeu_cau.append({
            "thoi_gian": datetime.now().strftime("%d/%m %H:%M:%S"),
            "van_de": tt.ten if tt else kq["tuyen"]["ten_nhom"],
            "ma": tt.ma_thu_tuc if tt else "",
            "chi_tiet": kq["cau_noi"],
            "trang_thai": "Mới",
        })
        st.success("✅ Đã gửi yêu cầu thành công. Cán bộ sẽ sớm liên hệ hỗ trợ bà con.")


def hien_ket_qua(kq: dict) -> None:
    if kq.get("loi"):
        st.error(f"⚠️ {kq['loi']}")
        nut_goi_can_bo(kq)
        return
    if kq.get("canh_bao"):
        st.warning(f"⚠️ {kq['canh_bao']}")

    tuyen, tt = kq["tuyen"], kq.get("thu_tuc")

    if tuyen["can_can_bo"] or tt is None:
        st.warning("🏷️ Nội dung này cần có sự hướng dẫn trực tiếp từ cán bộ xã.")
        nut_goi_can_bo(kq)
        return

    dg = kq["don_gian"]
    st.success(f"🏷️ **{tt.ten}**  ·  Mã thủ tục: {tt.ma_thu_tuc}")

    with st.container(border=True):
        st.markdown('<div class="the-tra-loi">', unsafe_allow_html=True)
        st.markdown(f"**{dg.get('tom_tat_1_cau','')}**")
        di = dg.get("di_dau", {})
        st.markdown(f"📍 **Đi đến:** {di.get('noi_don_gian','—')}")
        bb = [m for m in dg.get("mang_gi", []) if m.get("bat_buoc")]
        if bb:
            st.markdown("🎒 **Giấy tờ cần mang theo:**")
            for m in bb:
                sl = f" — {m['so_luong']}" if m.get("so_luong") else ""
                st.markdown(f"  • {m['ten_don_gian']}{sl}")
        c1, c2 = st.columns(2)
        c1.markdown(f"⏱️ **Thời gian chờ:** {dg.get('bao_lau','—')}")
        c2.markdown(f"💰 **Lệ phí:** {dg.get('bao_nhieu_tien','—')}")
        st.markdown("</div>", unsafe_allow_html=True)

    # Nút Loa phát âm thanh tiếng Việt nổi bật
    if st.button("🔊 Nghe hướng dẫn bằng Tiếng Việt", use_container_width=True, type="secondary"):
        p = tts_tieng_viet(kq["kich_ban"])
        if p:
            st.audio(str(p))
        else:
            st.warning("Đang chuẩn bị âm thanh, vui lòng thử lại.")

    # Hiển thị tiếng Mông kèm nút loa/audio nếu có
    if kq.get("mong"):
        with st.container(border=True):
            st.markdown(f"### 📖 Hướng dẫn bằng Tiếng Mông")
            st.markdown(f"**{kq['mong']['hien_thi']}**")
            if kq.get("audio_mong"):
                st.audio(kq["audio_mong"])
            with st.expander("Xem phiên âm phụ"):
                st.text(f"RPA: {kq['mong']['rpa']}")

    nut_goi_can_bo(kq)


if ss.ket_qua:
    st.write("---")
    hien_ket_qua(ss.ket_qua)


# ==========================================================================
# THU GỌN NHẬP LIỆU BÀN PHÍM / CHỌN DANH SÁCH Ở DƯỚI CÙNG
# ==========================================================================
st.markdown("<br><hr>", unsafe_allow_html=True)
with st.expander("⌨️ Cách khác: Gõ chữ hoặc chọn thủ tục từ danh sách"):
    t_go, t_chon = st.tabs(["Gõ câu hỏi", "Chọn từ danh sách"])

    with t_go:
        with st.form("form_go", clear_on_submit=False):
            txt = st.text_area(
                "Bà con cần hỏi việc gì?",
                placeholder="Ví dụ: Làm giấy khai sinh cho con ở đâu?",
                height=80)
            if st.form_submit_button("Gửi câu hỏi", type="primary",
                                     use_container_width=True) and txt.strip():
                xu_ly_cau_noi(txt.strip())

    with t_chon:
        nhom_chon = st.selectbox("Chọn nhóm việc:", list(DANH_MUC_THU_TUC.keys()),
                                 format_func=lambda k: DANH_MUC_THU_TUC[k])
        ds = kb.theo_nhom(nhom_chon)
        if ds:
            tt_chon = st.selectbox("Chọn thủ tục cụ thể:", ds, format_func=lambda t: t.ten)
            if st.button("Xem hướng dẫn ngay", type="primary", use_container_width=True):
                xu_ly_cau_noi(tt_chon.ten)

with st.sidebar:
    st.divider()
    st.markdown("### Trạng thái hệ thống")
    tk = kb.thong_ke()
    st.metric("Thủ tục trong kho", tk["so_thu_tuc"])
    if ss.danh_sach_yeu_cau:
        st.markdown("### Phiếu chờ cán bộ")
        for p in reversed(ss.danh_sach_yeu_cau[-5:]):
            st.caption(f"{p['thoi_gian']} — {p['van_de']}")

# -*- coding: utf-8 -*-
"""Cổng người dân — hỏi đáp thủ tục bằng giọng nói.

Nguyên tắc giao diện: MỘT nút. Bà con bấm micro, nói, bấm dừng — hệ thống tự
chạy hết chuỗi, không có nút "xử lý" thứ hai. Mọi thứ khác đẩy xuống dưới.
"""
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
        "**Kho dữ liệu trống.** Hãy chạy một lần:  `python tools/extract_tthc.py`\n\n"
        "Lệnh này bóc 28 file PDF hướng dẫn đang bị nhúng bên trong 3 file Excel "
        "ở `file_dichvucong/` ra thành `data/tthc/` + `data/manifest.json`."
    )
    st.stop()


# ==========================================================================
# HÀM CÓ CACHE (giảm độ trễ: lần 2 trở đi gần như tức thì)
# ==========================================================================
@st.cache_data(ttl=3600, show_spinner=False)
def _dinh_tuyen(cau_noi: str) -> dict:
    r = dinh_tuyen(cau_noi)
    r["_key"] = r["thu_tuc"].key if r["thu_tuc"] else ""   # ThuTuc không hash được
    r.pop("thu_tuc", None)
    return r


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _don_gian_hoa(key: str, cau_hoi: str) -> dict:
    return don_gian_hoa(kb.theo_key(key), cau_hoi)


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _dich_mong(text: str) -> dict:
    return dich_sang_mong(text)


# ==========================================================================
# PIPELINE — mỗi bước cập nhật ngay khi xong, không chờ cả chuỗi
# ==========================================================================
def _thong_diep_loi(e: Exception) -> str:
    """Đổi lỗi kỹ thuật thành câu người thường đọc được."""
    if isinstance(e, LoiQuota):
        return ("Tài khoản Gemini đã hết lượt gọi miễn phí trong phút/ngày này. "
                "Chờ vài phút rồi thử lại, hoặc chọn thủ tục ở mục **Cách khác** "
                "(những thủ tục đã tạo sẵn câu trả lời vẫn dùng được ngay).")
    s = str(e)
    if "GEMINI_API_KEY" in s:
        return "Chưa cấu hình khoá API Gemini trong `.streamlit/secrets.toml`."
    if "model" in s.lower() and ("404" in s or "not_found" in s.lower()):
        return ("Model AI đang dùng không còn khả dụng. Cán bộ vào trang Quản trị → "
                "Kho thủ tục → *Model Gemini đang dùng* để dò lại.")
    return f"Hệ thống đang bận. ({s[:140]})"


def chay_pipeline(cau_noi: str, *, phat_giong_mong: bool = True) -> dict:
    t0 = time.perf_counter()
    kq: dict = {"cau_noi": cau_noi, "thoi_gian": {}}

    with st.status("Đang xử lý…", expanded=True) as box:
        box.write("🧭 **Bước 1/4** — Tìm xem bà con cần thủ tục nào…")
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
            box.update(label="Cần cán bộ hỗ trợ", state="complete", expanded=False)
            return kq
        box.write(f"   ↳ **{tt.ten}** (mã {tt.ma_thu_tuc}) — "
                  f"độ tin cậy {tuyen['tin_cay_thu_tuc']:.0%}")

        box.write("📖 **Bước 2/4** — Đọc file hướng dẫn và rút ra câu ngắn gọn…")
        t = time.perf_counter()
        try:
            kq["don_gian"] = _don_gian_hoa(tt.key, CAU_HOI_MAC_DINH)
        except Exception as e:
            kq["loi"] = _thong_diep_loi(e)
            box.update(label="Chưa xử lý được", state="error", expanded=False)
            return kq
        kq["thoi_gian"]["don_gian_hoa"] = time.perf_counter() - t
        kq["kich_ban"] = thanh_van_ban_doc(kq["don_gian"])
        box.write(f"   ↳ xong ({kq['thoi_gian']['don_gian_hoa']:.1f}s"
                  f"{', lấy từ bộ nhớ' if kq['don_gian'].get('_tu_cache') else ''})")

        # Bước 3-4 KHÔNG sống còn: hỏng thì vẫn còn câu trả lời tiếng Việt.
        if phat_giong_mong:
            box.write("🔄 **Bước 3/4** — Dịch sang tiếng Mông…")
            t = time.perf_counter()
            try:
                kq["mong"] = _dich_mong(kq["kich_ban"])
                kq["thoi_gian"]["dich"] = time.perf_counter() - t
                box.write("   ↳ xong")

                box.write("🔊 **Bước 4/4** — Tạo giọng đọc tiếng Mông…")
                t = time.perf_counter()
                audio, tang = phat_tieng_mong(kq["mong"]["rpa"], key=tt.key)
                kq["thoi_gian"]["tts"] = time.perf_counter() - t
                kq["audio_mong"] = str(audio) if audio else ""
                kq["tang_tts"] = tang
                box.write(f"   ↳ {NHAN_TANG.get(tang, tang)}")
            except Exception as e:
                kq["canh_bao"] = f"Chưa dịch/đọc được tiếng Mông: {_thong_diep_loi(e)}"
                box.write("   ↳ ⚠️ bỏ qua phần tiếng Mông")
        else:
            box.write("⏭️ Bỏ qua bước dịch & giọng Mông (đang tắt)")

        kq["thoi_gian"]["tong"] = time.perf_counter() - t0
        box.update(label=f"Xong sau {kq['thoi_gian']['tong']:.1f} giây",
                   state="complete", expanded=False)
    return kq


def xu_ly_cau_noi(van_ban: str) -> None:
    ss.cau_noi = van_ban
    ss.ket_qua = chay_pipeline(van_ban)


# ==========================================================================
# MỘT NÚT DUY NHẤT
# ==========================================================================
st.markdown("### 🎙️ Bà con bấm vào micro rồi nói")
st.caption("Nói xong bấm dừng — máy tự làm hết, không phải bấm gì thêm.")

ngon_ngu = st.radio("Nói bằng tiếng gì?", ["Tiếng Việt", "Tiếng Mông (Hmong)"],
                    horizontal=True, label_visibility="collapsed")

audio_in = st.audio_input("Bấm micro:", label_visibility="collapsed")

# Tự xử lý ngay khi có bản ghi MỚI. Dấu vân tay nội dung để không chạy lại
# mỗi lần Streamlit vẽ lại trang.
if audio_in is not None:
    raw = audio_in.getvalue()
    van_tay = hashlib.sha256(raw).hexdigest()[:16]
    if van_tay != ss.audio_da_xu_ly and len(raw) > 2000:
        ss.audio_da_xu_ly = van_tay
        with st.spinner("🎧 Đang nghe bà con nói…"):
            van_ban, _nguon = nghe(audio_in, tieng_mong=(ngon_ngu != "Tiếng Việt"))
        if not van_ban:
            st.error("Máy chưa nghe rõ. Bà con nói lại gần micro hơn, "
                     "hoặc gõ câu hỏi ở phần **Cách khác** bên dưới.")
        else:
            if ngon_ngu != "Tiếng Việt":
                st.info(f"🗣️ Tiếng Mông: *{van_ban.splitlines()[0]}*")
                dong_vi = [l for l in van_ban.splitlines() if l.startswith("VI:")]
                van_ban = (dong_vi[0][3:].strip() if dong_vi
                           else dich_sang_viet(van_ban))
            st.success(f"🗣️ Bà con nói: *{van_ban}*")
            xu_ly_cau_noi(van_ban)
    elif 0 < len(raw) <= 2000:
        st.warning("Bản ghi quá ngắn. Bà con bấm micro và nói lâu hơn một chút.")

# ==========================================================================
# CÁCH KHÁC (gõ chữ / chọn danh sách) — thu gọn để không rối
# ==========================================================================
with st.expander("⌨️ Cách khác: gõ chữ hoặc chọn từ danh sách"):
    t_go, t_chon = st.tabs(["Gõ câu hỏi", "Chọn thủ tục"])

    with t_go:
        with st.form("form_go", clear_on_submit=False):
            txt = st.text_area(
                "Bà con cần hỏi việc gì?",
                placeholder="Ví dụ: Vợ tôi mới sinh con, tôi muốn làm giấy khai sinh",
                height=90)
            if st.form_submit_button("Gửi câu hỏi", type="primary",
                                     use_container_width=True) and txt.strip():
                xu_ly_cau_noi(txt.strip())

    with t_chon:
        st.caption("Chọn trực tiếp — không cần gọi AI, trả lời ngay. "
                   "Dùng khi phòng ồn hoặc mạng yếu.")
        nhom_chon = st.selectbox("Việc gì?", list(DANH_MUC_THU_TUC.keys()),
                                 format_func=lambda k: DANH_MUC_THU_TUC[k])
        ds = kb.theo_nhom(nhom_chon)
        if not ds:
            st.warning("Chưa có dữ liệu cho nhóm này. Nhóm đã có dữ liệu: "
                       + ", ".join(sorted({n for t in kb.load_kb() for n in t.nhom})))
        else:
            tt_chon = st.selectbox("Thủ tục cụ thể", ds, format_func=lambda t: t.ten)
            if st.button("Xem hướng dẫn", type="primary", use_container_width=True):
                xu_ly_cau_noi(tt_chon.ten)


# ==========================================================================
# KẾT QUẢ
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
            "tin_cay": kq["tuyen"].get("tin_cay_thu_tuc", 0),
            "trang_thai": "Mới",
        })
        st.success("✅ Đã gửi yêu cầu. Cán bộ sẽ liên hệ với bà con.")


def hien_ket_qua(kq: dict) -> None:
    if kq.get("loi"):
        st.error(f"⚠️ {kq['loi']}")
        st.info("Bà con vẫn có thể bấm nút dưới để cán bộ hỗ trợ trực tiếp.")
        kq.setdefault("tuyen", {"ten_nhom": "VẤN ĐỀ KHÁC", "tin_cay_thu_tuc": 0})
        nut_goi_can_bo(kq)
        return
    if kq.get("canh_bao"):
        st.warning(f"⚠️ {kq['canh_bao']}")

    tuyen, tt = kq["tuyen"], kq.get("thu_tuc")

    if tuyen["can_can_bo"] or tt is None:
        st.warning(f"🏷️ Hệ thống hiểu là: **{tuyen['ten_nhom']}** "
                   f"(chưa đủ chắc chắn — {tuyen['tin_cay_nhom']:.0%})")
        if tuyen.get("cau_hoi_lam_ro"):
            st.info(f"❓ {tuyen['cau_hoi_lam_ro']}")
        st.error("Việc này cần cán bộ trả lời trực tiếp. Bấm nút dưới để gửi yêu cầu.")
        nut_goi_can_bo(kq)
        return

    dg = kq["don_gian"]
    st.success(f"🏷️ **{tt.ten}**  ·  mã {tt.ma_thu_tuc}  ·  cấp {tt.cap_thuc_hien}")
    if dg.get("_da_duyet"):
        st.caption(f"✅ Nội dung đã được **{dg.get('_nguoi_duyet','cán bộ')}** duyệt.")

    with st.container(border=True):
        st.markdown('<div class="the-tra-loi">', unsafe_allow_html=True)
        st.markdown(f"**{dg.get('tom_tat_1_cau','')}**")
        di = dg.get("di_dau", {})
        st.markdown(f"📍 **Đi đâu:** {di.get('noi_don_gian','—')}")
        bb = [m for m in dg.get("mang_gi", []) if m.get("bat_buoc")]
        kbb = [m for m in dg.get("mang_gi", []) if not m.get("bat_buoc")]
        if bb:
            st.markdown("🎒 **Mang theo:**")
            for m in bb:
                sl = f" — {m['so_luong']}" if m.get("so_luong") else ""
                st.markdown(f"  • {m['ten_don_gian']}{sl}")
        c1, c2 = st.columns(2)
        c1.markdown(f"⏱️ **Chờ:** {dg.get('bao_lau','—')}")
        c2.markdown(f"💰 **Tiền:** {dg.get('bao_nhieu_tien','—')}")
        st.markdown("</div>", unsafe_allow_html=True)

    if st.button("🔊 Nghe bằng tiếng Việt", use_container_width=True):
        p = tts_tieng_viet(kq["kich_ban"])
        if p:
            st.audio(str(p))
        else:
            st.warning("Chưa tạo được giọng đọc (cần mạng + `pip install gTTS`).")

    if kq.get("mong"):
        with st.container(border=True):
            nhan_ortho = ("chữ Mông kiểu Việt Nam" if HMONG_ORTHOGRAPHY == "vn"
                          else "chữ Mông RPA")
            st.markdown(f"**📖 Tiếng Mông** ({nhan_ortho})")
            st.markdown(f"### {kq['mong']['hien_thi']}")
            with st.expander("Xem bản RPA / bản phiên âm"):
                st.text(f"RPA        : {kq['mong']['rpa']}")
                st.text(f"Phiên âm VN: {kq['mong']['vn']}")
            if kq.get("audio_mong"):
                st.audio(kq["audio_mong"])
                st.caption(NHAN_TANG.get(kq.get("tang_tts", ""), ""))
                if kq.get("tang_tts") == "vi_phonetic":
                    st.caption("⚠️ Đây là giọng máy đọc phiên âm, chưa phải giọng Mông "
                               "chuẩn. Bản chính thức sẽ dùng giọng người Mông thu sẵn.")
            else:
                st.caption(NHAN_TANG.get(kq.get("tang_tts", ""), ""))

    with st.expander("⚖️ Căn cứ & đối chiếu (dành cho cán bộ)"):
        st.metric("Độ tin cậy của bản tóm tắt", f"{dg.get('do_tin_cay', 0):.0%}")
        if dg.get("chua_ro"):
            st.warning("Tài liệu **không nêu rõ**: " + "; ".join(dg["chua_ro"]))
        for l in dg.get("luu_y", []):
            st.markdown(f"- {l}")
        if dg.get("cac_buoc"):
            st.markdown("**Các bước:**")
            for i, b in enumerate(dg["cac_buoc"], 1):
                st.markdown(f"{i}. {b}")
        if dg.get("trich_dan"):
            st.markdown("**Trích nguyên văn tài liệu gốc:**")
            for q in dg["trich_dan"]:
                st.markdown(f"> {q}")
        if kbb:
            st.markdown("**Giấy tờ không bắt buộc:** "
                        + ", ".join(m["ten_don_gian"] for m in kbb))
        if tt.pdf_path.exists():
            st.download_button("⬇️ Tải file hướng dẫn gốc (PDF)",
                               tt.pdf_path.read_bytes(),
                               file_name=f"{tt.ma_thu_tuc}.pdf", mime="application/pdf")
        tg = kq.get("thoi_gian", {})
        st.caption("Thời gian xử lý: "
                   + "  ·  ".join(f"{k} {v:.1f}s" for k, v in tg.items()))

    nut_goi_can_bo(kq)


if ss.ket_qua:
    st.write("---")
    hien_ket_qua(ss.ket_qua)

with st.sidebar:
    st.divider()
    st.markdown("### Trạng thái hệ thống")
    tk = kb.thong_ke()
    st.metric("Thủ tục trong kho", tk["so_thu_tuc"])
    st.caption(f"Nhóm có dữ liệu: {tk['so_nhom']}  ·  "
               f"{tk['tong_ky_tu']:,} ký tự văn bản gốc")
    st.caption(f"Giọng Mông: `{TTS_HMONG_PROVIDER}`  ·  "
               f"Ngưỡng tin cậy: {NGUONG_TU_TIN:.0%}")
    if tk["thieu_pdf"]:
        st.error(f"Thiếu PDF: {', '.join(tk['thieu_pdf'][:5])}")
    if ss.danh_sach_yeu_cau:
        st.markdown("### Phiếu chờ cán bộ")
        for p in reversed(ss.danh_sach_yeu_cau[-5:]):
            st.caption(f"{p['thoi_gian']} — {p['van_de']}")

# -*- coding: utf-8 -*-
"""Dashboard quản trị kho hướng dẫn.

Mỗi tab tương ứng một quyền trong core/auth.QUYEN. Cán bộ chỉ thấy tab mình
được cấp; quản trị viên thấy tất cả.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from core import auth, kb
from core.config import (AUDIO_BANK, CACHE_AUDIO, CACHE_SIMPLIFIED,
                         DANH_MUC_THU_TUC, ROOT)
from core.llm import (LoiQuota, danh_sach_model, ly_do_chan, model_dang_dung,
                      so_den, xoa_so_den)
from core.simplify import CAU_HOI_MAC_DINH, _cache_file, don_gian_hoa
from core.translate import GLOSSARY_FILE

EXCEL_DIR = ROOT / "file_dichvucong"

u = auth.nguoi_dang_nhap()
if not u:
    st.error("Bạn cần đăng nhập ở thanh bên trái.")
    st.stop()

st.title("🛠️ Quản trị kho hướng dẫn")
st.caption(f"Đang đăng nhập: **{u.get('mo_ta') or u['ten_dang_nhap']}** · "
           f"{'Quản trị viên (toàn quyền)' if auth.la_admin() else 'Cán bộ'}")
st.caption("⚠️ Nếu app đang chạy trên Streamlit Cloud, mọi thay đổi ở trang này sẽ "
           "**mất khi app khởi động lại**. Hãy làm trên máy rồi đẩy lên GitHub — "
           "xem `docs/TRIEN_KHAI.md`.")

# --------------------------------------------------- Dựng tab theo quyền
TAB_DEF = [
    ("kho_thu_tuc",      "📊 Kho thủ tục"),
    ("cap_nhat_du_lieu", "📥 Cập nhật dữ liệu"),
    ("cau_tra_loi",      "✅ Kiểm duyệt câu trả lời"),
    ("tu_vung_giong",    "🗣️ Từ vựng & giọng đọc"),
    ("bo_nho_tam",       "🧹 Bộ nhớ tạm"),
]
duoc_phep = [(q, nhan) for q, nhan in TAB_DEF if auth.co_quyen(q)]
if not duoc_phep:
    st.warning("Tài khoản của bạn chưa được cấp quyền nào trên trang này.")
    st.stop()

tabs = dict(zip([q for q, _ in duoc_phep], st.tabs([n for _, n in duoc_phep])))


# =========================================================== 1 · KHO THỦ TỤC
if "kho_thu_tuc" in tabs:
    with tabs["kho_thu_tuc"]:
        danh_sach = kb.load_kb()
        rows = []
        for t in danh_sach:
            cf = _cache_file(t.key, CAU_HOI_MAC_DINH)
            duyet = "— chưa tạo"
            if cf.exists():
                try:
                    d = json.loads(cf.read_text(encoding="utf-8"))
                    if not d.get("_da_duyet"):
                        duyet = "🟡 AI, chưa duyệt"
                    elif d.get("_duyet_hang_loat"):
                        duyet = "🔵 duyệt hàng loạt"
                    else:
                        duyet = "✅ đã đọc & duyệt"
                except Exception:
                    duyet = "⚠️ file lỗi"
            rows.append({
                "Mã": t.key, "Tên thủ tục": t.ten,
                "Nhóm": ", ".join(t.nhom), "Cấp": t.cap_thuc_hien,
                "Ẩn": t.an, "Ghi chú": t.ghi_chu,
                "PDF": "✔" if t.pdf_path.exists() else "✘",
                "Ký tự": t.so_ky_tu, "Câu trả lời": duyet,
            })
        df = pd.DataFrame(rows)
        tk = kb.thong_ke()

        c = st.columns(5)
        c[0].metric("Thủ tục", len(df))
        c[1].metric("Có PDF gốc", int((df["PDF"] == "✔").sum()))
        c[2].metric("Đã tạo câu trả lời", int((df["Câu trả lời"] != "— chưa tạo").sum()))
        c[3].metric("Đã duyệt",
                    int(df["Câu trả lời"].isin(["✅ đã đọc & duyệt",
                                                "🔵 duyệt hàng loạt"]).sum()))
        c[4].metric("Đang ẩn", tk["so_an"])

        st.divider()
        st.subheader("Sửa danh mục")
        st.caption("Sửa trực tiếp trong bảng: **Tên thủ tục**, **Nhóm** (viết hoa, cách "
                   "nhau bằng dấu phẩy), **Cấp**, **Ẩn**, **Ghi chú**. Bấm *Lưu thay đổi* "
                   "để áp dụng. Phần sửa lưu riêng ở `data/kho_ghi_de.json`, nên chạy lại "
                   "bóc tách cũng không mất.")
        st.caption("Mã nhóm dùng được: " + " · ".join(f"`{k}`" for k in DANH_MUC_THU_TUC))

        loc = st.multiselect("Lọc theo nhóm",
                             sorted({n for t in danh_sach for n in t.nhom}))
        df_hien = df[df["Nhóm"].apply(lambda s: any(x in s for x in loc))] if loc else df

        df_sua = st.data_editor(
            df_hien, use_container_width=True, hide_index=True, key="ed_kho",
            column_config={
                "Mã": st.column_config.TextColumn(disabled=True, width="small"),
                "Tên thủ tục": st.column_config.TextColumn(width="large"),
                "Nhóm": st.column_config.TextColumn(
                    help="Một hoặc nhiều mã nhóm, cách nhau bằng dấu phẩy"),
                "Ẩn": st.column_config.CheckboxColumn(
                    help="Ẩn khỏi danh sách bà con chọn (vẫn giữ dữ liệu)"),
                "PDF": st.column_config.TextColumn(disabled=True, width="small"),
                "Ký tự": st.column_config.NumberColumn(disabled=True),
                "Câu trả lời": st.column_config.TextColumn(disabled=True),
            },
        )

        c1, c2 = st.columns([1, 1])
        if c1.button("💾 Lưu thay đổi danh mục", type="primary",
                     use_container_width=True):
            goc = df_hien.set_index("Mã").to_dict("index")
            n = 0
            loi = []
            for _, r in df_sua.iterrows():
                key = r["Mã"]
                cu = goc.get(key, {})
                thay_doi = {}
                if str(r["Tên thủ tục"]).strip() != str(cu.get("Tên thủ tục", "")):
                    thay_doi["ten"] = str(r["Tên thủ tục"]).strip()
                if str(r["Nhóm"]) != str(cu.get("Nhóm", "")):
                    ds_nhom = [x.strip().upper() for x in str(r["Nhóm"]).split(",")
                               if x.strip()]
                    sai = [x for x in ds_nhom if x not in DANH_MUC_THU_TUC]
                    if sai:
                        loi.append(f"{key}: mã nhóm không hợp lệ {', '.join(sai)}")
                        continue
                    thay_doi["nhom"] = ds_nhom
                if str(r["Cấp"]).strip() != str(cu.get("Cấp", "")):
                    thay_doi["cap_thuc_hien"] = str(r["Cấp"]).strip()
                if bool(r["Ẩn"]) != bool(cu.get("Ẩn", False)):
                    thay_doi["an"] = bool(r["Ẩn"])
                if str(r["Ghi chú"] or "") != str(cu.get("Ghi chú", "") or ""):
                    thay_doi["ghi_chu"] = str(r["Ghi chú"] or "")
                if thay_doi:
                    kb.luu_ghi_de(key, **thay_doi)
                    n += 1
            st.cache_data.clear()
            if loi:
                st.error("Chưa lưu được một số dòng:\n\n" + "\n".join(f"- {x}" for x in loi))
            if n:
                st.success(f"Đã lưu {n} thủ tục.")
                st.rerun()
            elif not loi:
                st.info("Không có gì thay đổi.")

        if c2.button("↩️ Bỏ mọi sửa tay, quay về dữ liệu gốc",
                     use_container_width=True, disabled=tk["so_sua_tay"] == 0):
            kb.xoa_ghi_de()
            st.cache_data.clear()
            st.success("Đã quay về dữ liệu gốc.")
            st.rerun()

        st.download_button("⬇️ Xuất danh mục ra CSV",
                           df.to_csv(index=False).encode("utf-8-sig"),
                           "danh_muc_thu_tuc.csv", "text/csv")

        st.divider()
        st.subheader("Tạo sẵn câu trả lời (làm nóng bộ nhớ)")
        st.caption("Chạy trước buổi demo: mỗi thủ tục được Gemini xử lý 1 lần rồi lưu "
                   "đĩa. Sau đó app trả lời tức thì và **chạy được cả khi mất mạng**.")
        nhom_co = sorted({n for t in danh_sach for n in t.nhom})
        nhom_lam = st.multiselect("Chọn nhóm cần làm nóng", nhom_co, default=nhom_co)
        bo_qua = st.checkbox("Bỏ qua thủ tục đã có câu trả lời", value=True)
        if st.button("🔥 Tạo sẵn câu trả lời", type="primary"):
            can_lam = [t for t in danh_sach if any(n in nhom_lam for n in t.nhom)]
            if bo_qua:
                can_lam = [t for t in can_lam
                           if not _cache_file(t.key, CAU_HOI_MAC_DINH).exists()]
            if not can_lam:
                st.info("Không còn thủ tục nào cần làm.")
            else:
                bar = st.progress(0.0, "Bắt đầu…")
                loi, xong, het_quota = [], 0, False
                for i, t in enumerate(can_lam, 1):
                    bar.progress(i / len(can_lam), f"[{i}/{len(can_lam)}] {t.ten[:60]}")
                    try:
                        don_gian_hoa(t)
                        xong += 1
                    except LoiQuota as e:
                        het_quota = True
                        loi.append(f"{t.key}: {e}")
                        break          # hết lượt rồi, chạy tiếp chỉ tổ phí thời gian
                    except Exception as e:
                        loi.append(f"{t.key}: {str(e)[:160]}")
                bar.empty()
                st.success(f"Đã tạo xong {xong}/{len(can_lam)} thủ tục.")
                if het_quota:
                    st.warning("Dừng giữa chừng vì **hết lượt gọi Gemini miễn phí**. "
                               "Chờ ít phút rồi bấm lại — phần đã tạo được giữ nguyên, "
                               "hệ thống sẽ chạy tiếp từ chỗ còn thiếu.", icon="⏳")
                elif loi:
                    st.error("Một số thủ tục lỗi:\n" + "\n".join(f"- {x}" for x in loi))

        with st.expander("🔌 Model Gemini đang dùng"):
            st.caption("App tự dò model khả dụng của tài khoản bạn. Nếu Google gỡ một "
                       "model, app tự chuyển sang model kế tiếp — không phải sửa code.")
            try:
                st.json(model_dang_dung())
                ds_model = danh_sach_model()
                st.caption(f"Tài khoản này gọi được {len(ds_model)} model.")
                den = so_den()
                if den:
                    st.markdown("**Model đang bị bỏ qua** (tự động, nhớ 24 giờ):")
                    for m, ly_do in ly_do_chan().items():
                        st.markdown(f"- `{m}` — {ly_do[:120]}")
                    st.caption("Thường gặp: gói miễn phí có hạn mức **bằng 0** cho các "
                               "model Pro, nên chờ bao lâu cũng không gọi được. Hệ thống "
                               "tự chuyển sang model Flash.")
                c1, c2 = st.columns(2)
                if c1.button("🔄 Dò lại danh sách model"):
                    danh_sach_model(lam_moi=True)
                    st.rerun()
                if c2.button("🧹 Xoá danh sách bỏ qua", disabled=not den):
                    xoa_so_den()
                    st.rerun()
                st.code("\n".join(ds_model) or "(không lấy được danh sách)")
            except Exception as e:
                st.error(f"Không kết nối được Gemini: {e}")


# ====================================================== 2 · CẬP NHẬT DỮ LIỆU
if "cap_nhat_du_lieu" in tabs:
    with tabs["cap_nhat_du_lieu"]:
        st.subheader("1. Thêm / thay file Excel danh mục")
        st.caption("File Excel tải từ dichvucong.gov.vn. PDF hướng dẫn nhúng bên trong "
                   "sẽ được bóc tách tự động.")
        up = st.file_uploader("Chọn file .xlsx", type=["xlsx"], accept_multiple_files=True)
        if up and st.button("💾 Lưu file Excel"):
            for f in up:
                (EXCEL_DIR / f.name).write_bytes(f.getbuffer())
            st.success(f"Đã lưu {len(up)} file vào `file_dichvucong/`. "
                       "Bấm **Bóc tách lại** bên dưới.")

        st.divider()
        st.subheader("2. Bóc tách lại toàn bộ kho")
        st.caption("Chạy `tools/extract_tthc.py`: đọc mọi file Excel, bóc PDF nhúng, "
                   "trích text, sinh lại `data/manifest.json`. Phần sửa tay ở tab "
                   "*Kho thủ tục* được giữ nguyên.")
        if st.button("⚙️ Bóc tách lại", type="primary"):
            with st.spinner("Đang bóc tách…"):
                r = subprocess.run([sys.executable,
                                    str(ROOT / "tools" / "extract_tthc.py")],
                                   capture_output=True, text=True, cwd=str(ROOT))
            st.code((r.stdout or "") + (r.stderr or ""), language="text")
            kb.reload_kb()
            st.cache_data.clear()
            if r.returncode == 0:
                st.success(f"Đã cập nhật kho. Hiện có "
                           f"{kb.thong_ke()['so_thu_tuc']} thủ tục.")
            else:
                st.error("Bóc tách lỗi — xem log ở trên.")

        st.divider()
        st.subheader("3. Thay file PDF của một thủ tục")
        st.caption("Dùng khi thủ tục có văn bản mới mà Excel chưa cập nhật.")
        ds = kb.load_kb()
        if ds:
            tt = st.selectbox("Thủ tục", ds,
                              format_func=lambda t: f"{t.key} — {t.ten}")
            pdf_moi = st.file_uploader("PDF mới", type=["pdf"], key="pdf_le")
            if pdf_moi and st.button("💾 Thay PDF và trích lại text"):
                dest = tt.pdf_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    shutil.copy2(dest, dest.with_suffix(".pdf.bak"))
                dest.write_bytes(pdf_moi.getbuffer())
                try:
                    import pdfplumber
                    with pdfplumber.open(dest) as pdf:
                        txt = "\n".join((p.extract_text() or "") for p in pdf.pages)
                    (dest.parent / "raw.txt").write_text(txt, encoding="utf-8")
                    _cache_file(tt.key, CAU_HOI_MAC_DINH).unlink(missing_ok=True)
                    st.cache_data.clear()
                    st.success(f"Đã thay PDF ({len(txt):,} ký tự) và xoá câu trả lời cũ.")
                except Exception as e:
                    st.error(f"Lỗi đọc PDF: {e}")


# =================================================== 3 · KIỂM DUYỆT CÂU TRẢ LỜI
if "cau_tra_loi" in tabs:
    with tabs["cau_tra_loi"]:
        st.subheader("Cán bộ đọc lại câu AI viết trước khi bà con nghe")
        st.caption("Đây là chốt an toàn pháp lý: sửa được câu chữ, đánh dấu **đã duyệt**, "
                   "và câu đã duyệt sẽ được dùng vĩnh viễn thay cho bản AI.")

        # ------------------------------------------------ Duyệt hàng loạt
        NGUONG_AN_TOAN = 0.8

        def _quet_cau_tra_loi():
            """Chia các câu đã sinh thành 3 nhóm: đã duyệt / an toàn / cần đọc kỹ."""
            da_duyet, an_toan, can_doc = [], [], []
            for t in kb.load_kb():
                cf = _cache_file(t.key, CAU_HOI_MAC_DINH)
                if not cf.exists():
                    continue
                try:
                    d = json.loads(cf.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if d.get("_da_duyet"):
                    da_duyet.append((t, cf, d))
                elif (float(d.get("do_tin_cay", 0)) >= NGUONG_AN_TOAN
                      and not d.get("chua_ro")):
                    an_toan.append((t, cf, d))
                else:
                    can_doc.append((t, cf, d))
            return da_duyet, an_toan, can_doc

        def _ghi_duyet(muc, nguoi: str, hang_loat: bool = True) -> int:
            from datetime import datetime
            n = 0
            for _t, cf, d in muc:
                d.update({
                    "_da_duyet": True,
                    "_nguoi_duyet": nguoi,
                    "_tai_khoan_duyet": u["ten_dang_nhap"],
                    "_duyet_hang_loat": hang_loat,
                    "_duyet_luc": datetime.now().isoformat(timespec="seconds"),
                })
                cf.write_text(json.dumps(d, ensure_ascii=False, indent=2),
                              encoding="utf-8")
                n += 1
            return n

        _dd, _at, _cd = _quet_cau_tra_loi()
        tong_kho = len(kb.load_kb())

        with st.expander(f"⚡ Duyệt hàng loạt — đã duyệt {len(_dd)}/{tong_kho} thủ tục",
                         expanded=not _dd):
            c = st.columns(4)
            c[0].metric("Trong kho", tong_kho)
            c[1].metric("Đã duyệt", len(_dd))
            c[2].metric("Chờ duyệt — an toàn", len(_at))
            c[3].metric("Chờ duyệt — cần đọc", len(_cd))

            chua_tao = tong_kho - len(_dd) - len(_at) - len(_cd)
            if chua_tao > 0:
                st.info(f"Còn **{chua_tao} thủ tục chưa có câu trả lời**. "
                        "Sang tab *Kho thủ tục* bấm **🔥 Tạo sẵn câu trả lời** trước.")

            st.markdown(
                f"**Thế nào là an toàn:** AI tự chấm độ tin cậy từ "
                f"**{NGUONG_AN_TOAN:.0%}** trở lên **và** không báo thiếu thông tin nào. "
                "Những câu đó tài liệu gốc đã nói rõ mọi thứ, duyệt nhanh được.")
            st.markdown(
                "**Thế nào là cần đọc:** AI chấm tin cậy thấp, hoặc có mục "
                "*tài liệu không nêu rõ*. Đây đúng là những chỗ dễ chỉ sai bà con — "
                "nên đọc từng câu ở phần bên dưới.")

            if _cd:
                st.markdown("**Danh sách cần đọc kỹ:**")
                for t, _cf, d in _cd:
                    ly_do = []
                    if float(d.get("do_tin_cay", 0)) < NGUONG_AN_TOAN:
                        ly_do.append(f"tin cậy {float(d.get('do_tin_cay', 0)):.0%}")
                    if d.get("chua_ro"):
                        ly_do.append("thiếu: " + "; ".join(d["chua_ro"])[:90])
                    st.markdown(f"- `{t.key}` {t.ten[:60]} — {' · '.join(ly_do)}")

            nguoi_hl = st.text_input(
                "Người chịu trách nhiệm duyệt (họ tên, chức danh)",
                u.get("mo_ta") or u["ten_dang_nhap"], key="nguoi_hang_loat")

            b1, b2 = st.columns(2)
            if b1.button(f"✅ Duyệt {len(_at)} câu an toàn", type="primary",
                         use_container_width=True, disabled=not (_at and nguoi_hl.strip())):
                n = _ghi_duyet(_at, nguoi_hl.strip())
                st.cache_data.clear()
                st.success(f"Đã duyệt {n} thủ tục.")
                st.rerun()

            with b2:
                xac_nhan = st.checkbox(
                    f"Tôi chịu trách nhiệm duyệt cả {len(_cd)} câu chưa đọc",
                    disabled=not _cd, key="xn_hl")
                if st.button(f"⚠️ Duyệt TẤT CẢ {len(_at) + len(_cd)} câu còn lại",
                             use_container_width=True,
                             disabled=not (xac_nhan and nguoi_hl.strip())):
                    n = _ghi_duyet(_at + _cd, nguoi_hl.strip())
                    st.cache_data.clear()
                    st.success(f"Đã duyệt {n} thủ tục.")
                    st.rerun()

            st.caption("Câu duyệt hàng loạt được đánh dấu riêng (`_duyet_hang_loat`) để "
                       "sau này biết câu nào đã có người đọc từng chữ, câu nào chưa.")

            if _dd and st.button("↩️ Bỏ duyệt toàn bộ (giữ nguyên nội dung)"):
                for _t, cf, d in _dd:
                    for k in ("_da_duyet", "_nguoi_duyet", "_tai_khoan_duyet",
                              "_duyet_hang_loat", "_duyet_luc"):
                        d.pop(k, None)
                    cf.write_text(json.dumps(d, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
                st.cache_data.clear()
                st.success("Đã bỏ dấu duyệt. Nội dung câu trả lời không đổi.")
                st.rerun()

        st.divider()
        ds = kb.load_kb()
        if ds:
            tt = st.selectbox("Chọn thủ tục", ds,
                              format_func=lambda t: f"{t.key} — {t.ten}", key="kd")
            cf = _cache_file(tt.key, CAU_HOI_MAC_DINH)
            if not cf.exists():
                st.info("Chưa có câu trả lời. Bấm nút dưới để tạo.")
                if st.button("✨ Tạo câu trả lời bằng Gemini"):
                    try:
                        with st.spinner("Đang đọc PDF và rút gọn…"):
                            don_gian_hoa(tt)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Không tạo được: {e}")
            else:
                d = json.loads(cf.read_text(encoding="utf-8"))
                if d.get("_da_duyet"):
                    if d.get("_duyet_hang_loat"):
                        st.info(f"✅ Đã duyệt hàng loạt bởi "
                                f"**{d.get('_nguoi_duyet','—')}** "
                                f"({d.get('_duyet_luc','')[:16].replace('T', ' ')}) — "
                                "chưa có người đọc từng chữ.")
                    else:
                        st.success(f"✅ Đã duyệt bởi **{d.get('_nguoi_duyet','—')}**")
                else:
                    st.warning("🟡 Bản do AI sinh, chưa có người duyệt.")

                c1, c2 = st.columns(2)
                with c1:
                    tom_tat = st.text_input("Tóm tắt 1 câu", d.get("tom_tat_1_cau", ""))
                    noi = st.text_input("Đi đâu (nói dễ hiểu)",
                                        d.get("di_dau", {}).get("noi_don_gian", ""))
                    noi_ct = st.text_input("Tên chính thức của nơi đó",
                                           d.get("di_dau", {}).get("ten_chinh_thuc", ""))
                    bao_lau = st.text_input("Chờ bao lâu", d.get("bao_lau", ""))
                    tien = st.text_input("Tiền phải trả", d.get("bao_nhieu_tien", ""))
                with c2:
                    kich_ban = st.text_area(
                        "Kịch bản đọc thành tiếng (bản sẽ được dịch & phát)",
                        d.get("kich_ban_doc", ""), height=190)
                    st.caption(f"{len(kich_ban.split())} từ — nên dưới 80 từ.")

                st.markdown("**Giấy tờ cần mang**")
                df_giay = pd.DataFrame(d.get("mang_gi", []) or
                                       [{"ten_don_gian": "", "ten_chinh_thuc": "",
                                         "so_luong": "", "bat_buoc": True}])
                df_giay = st.data_editor(df_giay, num_rows="dynamic",
                                         use_container_width=True, key="ed_giay")

                if d.get("chua_ro"):
                    st.warning("AI báo tài liệu **không nêu rõ**: "
                               + "; ".join(d["chua_ro"]))
                if d.get("trich_dan"):
                    with st.expander("Trích nguyên văn tài liệu gốc (để đối chiếu)"):
                        for q in d["trich_dan"]:
                            st.markdown(f"> {q}")
                if tt.pdf_path.exists():
                    with st.expander("Text gốc đầy đủ"):
                        st.text_area("raw.txt", tt.text()[:20000], height=300,
                                     label_visibility="collapsed")

                def _thu_thap() -> dict:
                    return {
                        "tom_tat_1_cau": tom_tat,
                        "di_dau": {"noi_don_gian": noi, "ten_chinh_thuc": noi_ct},
                        "bao_lau": bao_lau, "bao_nhieu_tien": tien,
                        "kich_ban_doc": kich_ban,
                        "mang_gi": df_giay.fillna("").to_dict("records"),
                    }

                nguoi_mac_dinh = d.get("_nguoi_duyet") or (u.get("mo_ta")
                                                           or u["ten_dang_nhap"])
                nguoi = st.text_input("Người duyệt (họ tên, chức danh)", nguoi_mac_dinh)
                cc1, cc2 = st.columns(2)
                if cc1.button("💾 Lưu bản sửa", use_container_width=True):
                    d.update(_thu_thap())
                    cf.write_text(json.dumps(d, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
                    st.cache_data.clear()
                    st.success("Đã lưu.")
                if cc2.button("✅ Duyệt & phát hành", type="primary",
                              use_container_width=True):
                    if not nguoi.strip():
                        st.error("Nhập tên người duyệt trước.")
                    else:
                        d.update(_thu_thap())
                        d.update({"_da_duyet": True, "_nguoi_duyet": nguoi.strip(),
                                  "_tai_khoan_duyet": u["ten_dang_nhap"],
                                  "_duyet_hang_loat": False})
                        cf.write_text(json.dumps(d, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
                        st.cache_data.clear()
                        st.success("Đã duyệt và phát hành.")


# ================================================= 4 · TỪ VỰNG & GIỌNG ĐỌC
if "tu_vung_giong" in tabs:
    with tabs["tu_vung_giong"]:
        st.subheader("Từ điển thuật ngữ Việt – Mông")
        st.caption("Điền cột `tieng_mong_rpa` do người Mông bản địa chốt. Hệ thống sẽ "
                   "ép Gemini dịch đúng các từ này, không dịch tuỳ ý nữa.")
        if GLOSSARY_FILE.exists():
            g = pd.read_csv(GLOSSARY_FILE).fillna("")
        else:
            g = pd.DataFrame(columns=["tieng_viet", "tieng_mong_rpa",
                                      "ghi_chu", "nguoi_xac_nhan"])
        g2 = st.data_editor(g, num_rows="dynamic", use_container_width=True, key="ed_glo")
        if st.button("💾 Lưu từ điển"):
            g2.to_csv(GLOSSARY_FILE, index=False, encoding="utf-8-sig")
            from core.translate import _glossary_block
            _glossary_block.cache_clear()
            st.cache_data.clear()
            da_chot = int((g2["tieng_mong_rpa"].astype(str).str.strip() != "").sum())
            st.success(f"Đã lưu {len(g2)} dòng, trong đó {da_chot} từ đã chốt.")

        st.divider()
        st.subheader("Ngân hàng giọng đọc (người Mông thu sẵn)")
        st.caption("Đây là cách cho ra giọng Mông **chính xác nhất** và chạy offline. "
                   "Thu bằng điện thoại cũng được: 1 file mp3 cho 1 thủ tục.")
        ds = kb.load_kb()
        if ds:
            tt_a = st.selectbox("Gắn file âm thanh cho thủ tục", ds,
                                format_func=lambda t: f"{t.key} — {t.ten}", key="ab")
            f_audio = st.file_uploader("File âm thanh (mp3/wav/m4a)",
                                       type=["mp3", "wav", "m4a", "ogg"])
            if f_audio and st.button("💾 Lưu vào ngân hàng giọng"):
                ten = f"{tt_a.key}{Path(f_audio.name).suffix.lower()}"
                (AUDIO_BANK / ten).write_bytes(f_audio.getbuffer())
                idx_p = AUDIO_BANK / "index.json"
                idx = (json.loads(idx_p.read_text(encoding="utf-8"))
                       if idx_p.exists() else {})
                idx.setdefault("theo_thu_tuc", {})[tt_a.key] = ten
                idx_p.write_text(json.dumps(idx, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
                st.success(f"Đã lưu `{ten}`.")

            idx_p = AUDIO_BANK / "index.json"
            if idx_p.exists():
                idx = json.loads(idx_p.read_text(encoding="utf-8"))
                muc = idx.get("theo_thu_tuc", {})
                if muc:
                    st.markdown(f"**Đã có giọng thu sẵn ({len(muc)} thủ tục):**")
                    for k, v in muc.items():
                        t = kb.theo_key(k)
                        st.write(f"- `{k}` {t.ten if t else ''}")
                        if (AUDIO_BANK / v).exists():
                            st.audio(str(AUDIO_BANK / v))


# ======================================================= 5 · BỘ NHỚ TẠM
if "bo_nho_tam" in tabs:
    with tabs["bo_nho_tam"]:
        n_s = len(list(CACHE_SIMPLIFIED.glob("*.json")))
        n_a = len(list(CACHE_AUDIO.glob("*")))
        kb_s = sum(f.stat().st_size for f in CACHE_SIMPLIFIED.glob("*.json")) / 1024
        kb_a = sum(f.stat().st_size for f in CACHE_AUDIO.glob("*")) / 1024
        c = st.columns(2)
        c[0].metric("File câu trả lời đã lưu", n_s, f"{kb_s:.0f} KB")
        c[1].metric("File âm thanh đã lưu", n_a, f"{kb_a:.0f} KB")
        st.caption("Câu trả lời **đã được cán bộ duyệt** sẽ mất nếu xoá — hãy cân nhắc.")
        c1, c2, c3 = st.columns(3)
        if c1.button("🧹 Xoá cache âm thanh"):
            for f in CACHE_AUDIO.glob("*"):
                f.unlink()
            st.success("Đã xoá.")
        if c2.button("🧹 Xoá câu trả lời CHƯA duyệt"):
            n = 0
            for f in CACHE_SIMPLIFIED.glob("*.json"):
                if f.name == "models.json":
                    continue
                try:
                    if not json.loads(f.read_text(encoding="utf-8")).get("_da_duyet"):
                        f.unlink()
                        n += 1
                except Exception:
                    f.unlink()
                    n += 1
            st.cache_data.clear()
            st.success(f"Đã xoá {n} file.")
        if c3.button("♻️ Xoá cache RAM của Streamlit"):
            st.cache_data.clear()
            kb.reload_kb()
            st.success("Đã xoá.")

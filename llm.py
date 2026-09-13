# -*- coding: utf-8 -*-
"""Lớp bọc Gemini: tự dò model khả dụng, tự né model bị chặn, retry, cache đĩa.

Hai kiểu hỏng đã gặp thật và đều được xử lý tự động ở đây:

  404 NOT_FOUND        — Google gỡ model (gemini-2.5-pro với tài khoản mới).
  429 với "limit: 0"   — model CÓ tồn tại nhưng gói miễn phí không được dùng
                         (gemini-3.1-pro). Đây KHÔNG phải "hết lượt", mà là
                         "không có suất nào" -> chờ bao lâu cũng vô ích.

Cả hai đều dẫn tới: ghi model đó vào sổ đen (nhớ 24 giờ), chuyển ngay sang model
kế tiếp trong danh sách ưu tiên. Còn 429 thường (hết lượt mỗi phút) thì đổi sang
model khác trước — mỗi model có hạn mức riêng — hết cách mới chờ.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from core.config import (CACHE_MODELS, CACHE_SIMPLIFIED, LOAI_TRU_MODEL,
                         MODEL_FAST, MODEL_QUALITY, MODEL_STT, UU_TIEN_FAST,
                         UU_TIEN_QUALITY, UU_TIEN_STT)

_client: genai.Client | None = None
_da_chon: dict[str, str] = {}
_danh_sach: list[str] | None = None
_so_den: dict[str, float] | None = None          # {model: thoi_diem_bi_chan}

THOI_HAN_SO_DEN = 24 * 3600                      # thử lại sau 1 ngày
CHO_TOI_DA = 25                                  # không bao giờ bắt người dùng chờ quá 25s


def get_client(api_key: str | None = None) -> genai.Client:
    global _client
    if _client is None:
        if api_key is None:
            try:
                import streamlit as st
                api_key = st.secrets["GEMINI_API_KEY"]
            except Exception as e:  # pragma: no cover
                raise RuntimeError("Thiếu GEMINI_API_KEY") from e
        _client = genai.Client(api_key=api_key)
    return _client


# =============================================== ĐỌC / GHI FILE NHỚ MODEL
def _doc_file() -> dict:
    if CACHE_MODELS.exists():
        try:
            return json.loads(CACHE_MODELS.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _ghi_file(**truong) -> None:
    d = _doc_file()
    d.update(truong)
    CACHE_MODELS.parent.mkdir(parents=True, exist_ok=True)
    CACHE_MODELS.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


# ======================================================== SỔ ĐEN MODEL
def so_den() -> dict[str, float]:
    global _so_den
    if _so_den is None:
        d = _doc_file().get("bi_chan", {})
        bay_gio = time.time()
        _so_den = {k: v for k, v in d.items() if bay_gio - v < THOI_HAN_SO_DEN}
    return _so_den


def chan_model(ten: str, ly_do: str = "") -> None:
    s = so_den()
    s[ten] = time.time()
    _ghi_file(bi_chan=s, ly_do_chan={**_doc_file().get("ly_do_chan", {}), ten: ly_do})
    _da_chon.clear()                 # buộc chọn lại cho mọi vai trò


def xoa_so_den() -> None:
    global _so_den
    _so_den = {}
    _ghi_file(bi_chan={}, ly_do_chan={})
    _da_chon.clear()


def ly_do_chan() -> dict[str, str]:
    return {k: v for k, v in _doc_file().get("ly_do_chan", {}).items() if k in so_den()}


# ====================================================== DÒ MODEL KHẢ DỤNG
def danh_sach_model(lam_moi: bool = False) -> list[str]:
    """Tên các model tài khoản này gọi được (đã bỏ tiền tố 'models/')."""
    global _danh_sach
    if _danh_sach is not None and not lam_moi:
        return _danh_sach
    if not lam_moi:
        d = _doc_file()
        if d.get("models") and time.time() - d.get("ts", 0) < 7 * 24 * 3600:
            _danh_sach = d["models"]
            return _danh_sach
    ten: list[str] = []
    try:
        for m in get_client().models.list():
            n = (getattr(m, "name", "") or "").removeprefix("models/")
            hanh_dong = getattr(m, "supported_actions", None) or []
            if n and (not hanh_dong or "generateContent" in hanh_dong):
                ten.append(n)
    except Exception:
        ten = []
    _danh_sach = ten
    if ten:
        _ghi_file(ts=time.time(), models=ten)
    return ten


def _sinh_van_ban_duoc(ten: str) -> bool:
    return not any(x in ten for x in LOAI_TRU_MODEL)


def _khop(uu_tien: str, co_san: list[str]) -> str | None:
    """Khớp theo tiền tố, bỏ model sinh ảnh/giọng và model trong sổ đen.
    Ưu tiên bản chính thức (tên ngắn, không '-preview'/'-exp')."""
    den = so_den()
    ung_vien = [n for n in co_san
                if n.startswith(uu_tien) and n not in den and _sinh_van_ban_duoc(n)]
    if not ung_vien:
        return None
    ung_vien.sort(key=lambda n: ("preview" in n or "exp" in n, len(n)))
    return ung_vien[0]


def _uu_tien(vai_tro: str) -> list[str]:
    return {"fast": UU_TIEN_FAST, "quality": UU_TIEN_QUALITY, "stt": UU_TIEN_STT}[vai_tro]


def chon_model(vai_tro: str = "fast") -> str:
    """vai_tro: 'fast' | 'quality' | 'stt'. Trả về tên model dùng được."""
    ep_cung = {"fast": MODEL_FAST, "quality": MODEL_QUALITY, "stt": MODEL_STT}[vai_tro]
    if ep_cung:
        return ep_cung
    if vai_tro in _da_chon:
        return _da_chon[vai_tro]

    co_san = danh_sach_model()
    for ut in _uu_tien(vai_tro):
        ten = _khop(ut, co_san) if co_san else (ut if ut not in so_den() else None)
        if ten:
            _da_chon[vai_tro] = ten
            return ten
    con_lai = [m for m in _uu_tien(vai_tro) if m not in so_den()]
    ten = con_lai[0] if con_lai else _uu_tien(vai_tro)[-1]
    _da_chon[vai_tro] = ten
    return ten


def model_dang_dung() -> dict[str, str]:
    return {v: chon_model(v) for v in ("fast", "quality", "stt")}


def _model_ke_tiep(vai_tro: str, da_thu: set[str]) -> str | None:
    co_san = danh_sach_model()
    den = so_den()
    for ut in _uu_tien(vai_tro):
        ten = _khop(ut, co_san) if co_san else ut
        if ten and ten not in da_thu and ten not in den:
            _da_chon[vai_tro] = ten
            return ten
    return None


# ========================================================= PHÂN LOẠI LỖI
def _phan_tich_loi(e: Exception) -> tuple[str, float]:
    """Trả về (loai, so_giay_can_cho).

    loai: 'model_hong'  -> model này vô dụng với tài khoản, đừng thử lại
          'cho_quota'   -> hết lượt tạm thời, model khác có thể còn lượt
          'khac'        -> lỗi mạng / lỗi khác, retry bình thường
    """
    s = str(e)
    thap = s.lower()
    cho = 0.0
    m = re.search(r"retry in ([\d.]+)s", thap) or re.search(r'retryDelay["\':\s]+(\d+)', s)
    if m:
        try:
            cho = float(m.group(1))
        except ValueError:
            cho = 0.0

    if ("not_found" in thap or "404" in thap or "no longer available" in thap
            or "permission_denied" in thap or "is not supported" in thap):
        return "model_hong", cho
    # Model không hiểu response_schema / JSON mode -> model khác sẽ hiểu
    if "invalid_argument" in thap and ("schema" in thap or "response_mime" in thap
                                       or "json" in thap):
        return "model_hong", cho
    if "429" in thap or "resource_exhausted" in thap or "quota" in thap:
        # "limit: 0" = gói này KHÔNG có suất nào cho model đó -> chờ vô ích
        if re.search(r"limit:\s*0\b", thap):
            return "model_hong", cho
        return "cho_quota", cho
    return "khac", cho


# ============================================================== GỌI MODEL
def _key(*parts: Any) -> str:
    return hashlib.sha256("||".join(map(str, parts)).encode("utf-8")).hexdigest()[:32]


class LoiQuota(RuntimeError):
    """Hết lượt gọi API — không phải lỗi lập trình, chỉ cần chờ hoặc nâng gói."""


def goi_gemini(
    prompt: str,
    *,
    system: str | None = None,
    model: str | None = None,
    vai_tro: str = "fast",
    schema: dict | None = None,
    temperature: float = 0.2,
    max_retry: int = 4,
    cache_dir: Path | None = CACHE_SIMPLIFIED,
    cache_tag: str = "gen",
) -> str:
    """Gọi Gemini, trả về text (hoặc JSON string nếu có schema)."""
    ten_model = model or chon_model(vai_tro)

    ck = _key(cache_tag, vai_tro, system, prompt,
              json.dumps(schema, sort_keys=True) if schema else "")
    cfile = (cache_dir / f"{cache_tag}_{ck}.json") if cache_dir else None
    if cfile and cfile.exists():
        return json.loads(cfile.read_text(encoding="utf-8"))["text"]

    cfg: dict[str, Any] = {"temperature": temperature}
    if system:
        cfg["system_instruction"] = system
    if schema:
        cfg["response_mime_type"] = "application/json"
        cfg["response_schema"] = schema

    last_err: Exception | None = None
    loai_cuoi = "khac"
    da_thu: set[str] = set()

    for _ in range(max_retry):
        try:
            resp = get_client().models.generate_content(
                model=ten_model, contents=prompt,
                config=types.GenerateContentConfig(**cfg),
            )
            text = (resp.text or "").strip()
            if cfile and text:
                cfile.write_text(
                    json.dumps({"text": text, "model": ten_model, "ts": time.time()},
                               ensure_ascii=False), encoding="utf-8")
            return text

        except Exception as e:
            last_err = e
            da_thu.add(ten_model)
            loai, cho = _phan_tich_loi(e)
            loai_cuoi = loai

            if model is not None:            # người gọi ép cứng model -> không đổi
                if loai == "cho_quota" and cho:
                    time.sleep(min(cho, CHO_TOI_DA))
                    continue
                time.sleep(1.0)
                continue

            if loai == "model_hong":
                chan_model(ten_model, str(e)[:200])
                ke = _model_ke_tiep(vai_tro, da_thu)
                if ke:
                    ten_model = ke
                    continue                 # đổi model, thử lại ngay
                break

            if loai == "cho_quota":
                ke = _model_ke_tiep(vai_tro, da_thu)   # model khác, hạn mức khác
                if ke:
                    ten_model = ke
                    continue
                if cho and cho <= CHO_TOI_DA:
                    time.sleep(cho + 1)
                    da_thu.discard(ten_model)
                    continue
                break

            time.sleep(1.2)

    ds = ", ".join(sorted(da_thu))
    if loai_cuoi == "cho_quota":
        raise LoiQuota(
            f"Tài khoản Gemini đã hết lượt gọi miễn phí (đã thử: {ds}). "
            f"Chờ ít phút rồi thử lại, hoặc bật thanh toán cho dự án Google Cloud."
        ) from last_err
    if loai_cuoi == "model_hong":
        raise RuntimeError(
            f"Không còn model nào dùng được cho vai trò '{vai_tro}' "
            f"(đã thử: {ds}). Chạy `python tools/liet_ke_model.py` để xem tài khoản "
            f"của bạn gọi được model nào, rồi ép cứng bằng biến môi trường "
            f"LGB_MODEL_{vai_tro.upper()}."
        ) from last_err
    raise RuntimeError(f"Gemini thất bại (đã thử: {ds}): {last_err}")


def goi_gemini_json(prompt: str, *, schema: dict, **kw) -> dict:
    txt = goi_gemini(prompt, schema=schema, **kw)
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        s, e = txt.find("{"), txt.rfind("}")
        if s >= 0 and e > s:
            return json.loads(txt[s:e + 1])
        raise

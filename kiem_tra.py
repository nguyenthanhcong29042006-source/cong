# -*- coding: utf-8 -*-
"""Tự kiểm tra hệ thống trước khi demo:  python tools/kiem_tra.py"""
from __future__ import annotations

import pathlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OK, FAIL = "  [OK] ", "  [!!] "
loi = 0


def kiem(ten: str, fn):
    global loi
    try:
        kq = fn()
        print(OK + ten + (f" -> {kq}" if kq else ""))
    except Exception as e:
        loi += 1
        print(FAIL + ten + f" -> {type(e).__name__}: {e}")


print("== 1. Thu vien ==")
kiem("streamlit", lambda: __import__("streamlit").__version__)
kiem("google-genai", lambda: (__import__("google.genai", fromlist=["x"]) and "ok"))
kiem("pdfplumber", lambda: __import__("pdfplumber").__version__)
kiem("openpyxl", lambda: __import__("openpyxl").__version__)
kiem("pandas", lambda: __import__("pandas").__version__)
kiem("gTTS", lambda: (__import__("gtts") and "ok"))

print("== 2. Kho du lieu ==")
from core import kb
kiem("manifest + 27 thu tuc", lambda: kb.thong_ke())

print("== 3. Phien am tieng Mong ==")
from core.hmong.rpa_vi import rpa_sang_vi
kiem("RPA -> chu Viet", lambda: rpa_sang_vi("Nyob zoo koj mus rau lub tsev"))

print("== 4. Tai khoan & phan quyen ==")
from core import auth
kiem("users.json + 4 tai khoan", lambda: list(auth.khoi_tao_mac_dinh()))

print("== 5. Gemini (can mang + API key) ==")
def _key():
    import re
    f = pathlib.Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.toml"
    m = re.search(r'GEMINI_API_KEY\s*=\s*["\']([^"\']+)', f.read_text(encoding="utf-8"))
    return m.group(1)

def _models():
    from core.llm import danh_sach_model, get_client, model_dang_dung
    get_client(_key())
    n = len(danh_sach_model(lam_moi=True))
    return f"{n} model kha dung -> {model_dang_dung()}"
kiem("do model kha dung", _models)

def _gemini():
    from core.llm import goi_gemini
    return goi_gemini("Tra loi dung 1 chu: OK", cache_dir=None)[:20]
kiem("goi Gemini", _gemini)

print("== 6. TTS ==")
from core.tts import phat_tieng_mong, tts_tieng_viet
kiem("TTS tieng Viet", lambda: tts_tieng_viet("Xin chao ba con"))
kiem("TTS tieng Mong (chuoi du phong)", lambda: phat_tieng_mong("Nyob zoo"))

print(f"\n==> {'TAT CA OK' if loi == 0 else f'CO {loi} LOI can xu ly'}")
sys.exit(1 if loi else 0)

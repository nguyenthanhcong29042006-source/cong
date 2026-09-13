# -*- coding: utf-8 -*-
"""Xem tài khoản Gemini của bạn đang gọi được những model nào.

    python tools/liet_ke_model.py

Dùng khi gặp lỗi 404 "model is no longer available".
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _doc_key() -> str:
    import re
    f = ROOT / ".streamlit" / "secrets.toml"
    if not f.exists():
        sys.exit("Khong tim thay .streamlit/secrets.toml")
    m = re.search(r'GEMINI_API_KEY\s*=\s*["\']([^"\']+)', f.read_text(encoding="utf-8"))
    if not m:
        sys.exit("Khong tim thay GEMINI_API_KEY trong secrets.toml")
    return m.group(1)


def main() -> int:
    from core.llm import chon_model, danh_sach_model, get_client
    get_client(_doc_key())
    ds = danh_sach_model(lam_moi=True)
    print(f"Tai khoan nay goi duoc {len(ds)} model:\n")
    for n in sorted(ds):
        print("   ", n)
    print("\nApp se dung:")
    for vai in ("quality", "fast", "stt"):
        print(f"    {vai:8s} -> {chon_model(vai)}")
    print("\nMuon ep cung mot model, dat bien moi truong truoc khi chay streamlit:")
    print("    set LGB_MODEL_QUALITY=gemini-3.1-pro-preview")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

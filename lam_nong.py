# -*- coding: utf-8 -*-
"""Tạo sẵn câu trả lời cho TOÀN BỘ thủ tục, chạy từ terminal.

    python tools/lam_nong.py              # chỉ làm thủ tục chưa có
    python tools/lam_nong.py --tat-ca     # làm lại tất cả
    python tools/lam_nong.py --duyet "Phạm Minh Anh — chủ nhiệm dự án"

Chạy ở terminal đáng tin hơn bấm nút trong trình duyệt: không bị timeout, tự
chờ khi gặp hạn mức, và in rõ đang làm tới đâu.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _doc_key() -> str:
    f = ROOT / ".streamlit" / "secrets.toml"
    if not f.exists():
        sys.exit("Khong tim thay .streamlit/secrets.toml")
    m = re.search(r'GEMINI_API_KEY\s*=\s*["\']([^"\']+)', f.read_text(encoding="utf-8"))
    if not m:
        sys.exit("Khong tim thay GEMINI_API_KEY trong secrets.toml")
    return m.group(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tat-ca", action="store_true",
                    help="Lam lai ca nhung thu tuc da co cau tra loi")
    ap.add_argument("--duyet", metavar="TEN",
                    help="Duyet luon tat ca, ghi ten nguoi chiu trach nhiem")
    ap.add_argument("--nghi", type=float, default=1.0,
                    help="So giay nghi giua 2 thu tuc (mac dinh 1.0)")
    a = ap.parse_args()

    from core import kb
    from core.llm import LoiQuota, chon_model, get_client, model_dang_dung
    from core.simplify import CAU_HOI_MAC_DINH, _cache_file, don_gian_hoa

    get_client(_doc_key())
    print("Model dang dung:", model_dang_dung())

    ds = kb.load_kb()
    if not ds:
        sys.exit("Kho trong. Chay truoc: python tools/extract_tthc.py")

    can_lam = ds if a.tat_ca else [
        t for t in ds if not _cache_file(t.key, CAU_HOI_MAC_DINH).exists()]
    print(f"\nKho co {len(ds)} thu tuc, can tao {len(can_lam)}.\n")

    xong, loi = 0, []
    for i, t in enumerate(can_lam, 1):
        nhan = f"[{i}/{len(can_lam)}] {t.key} {t.ten[:52]}"
        print(f"{nhan} ... ", end="", flush=True)
        for lan_thu in range(3):
            try:
                t0 = time.perf_counter()
                d = don_gian_hoa(t, dung_cache=not a.tat_ca)
                print(f"OK {time.perf_counter()-t0:4.1f}s  "
                      f"tin cay {float(d.get('do_tin_cay', 0)):.0%}"
                      + ("  [!] thieu: " + "; ".join(d["chua_ro"])[:60]
                         if d.get("chua_ro") else ""))
                xong += 1
                break
            except LoiQuota as e:
                cho = 30 * (lan_thu + 1)
                print(f"\n    het luot, nghi {cho}s roi thu lai ... ", end="", flush=True)
                time.sleep(cho)
            except Exception as e:
                print(f"LOI: {str(e)[:120]}")
                loi.append(f"{t.key}: {str(e)[:160]}")
                break
        else:
            loi.append(f"{t.key}: het luot sau 3 lan thu")
            print("BO QUA (het luot)")
        time.sleep(a.nghi)

    print(f"\n==> Tao xong {xong}/{len(can_lam)}")
    if loi:
        print("Con loi:")
        for x in loi:
            print("   -", x)

    if a.duyet:
        n = 0
        for t in kb.load_kb():
            cf = _cache_file(t.key, CAU_HOI_MAC_DINH)
            if not cf.exists():
                continue
            d = json.loads(cf.read_text(encoding="utf-8"))
            if d.get("_da_duyet"):
                continue
            d.update({
                "_da_duyet": True, "_nguoi_duyet": a.duyet,
                "_tai_khoan_duyet": "cli", "_duyet_hang_loat": True,
                "_duyet_luc": datetime.now().isoformat(timespec="seconds"),
            })
            cf.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
            n += 1
        print(f"==> Da duyet {n} thu tuc, nguoi duyet: {a.duyet}")

    tong = sum(1 for t in kb.load_kb()
               if _cache_file(t.key, CAU_HOI_MAC_DINH).exists())
    print(f"==> Tong cong {tong}/{len(kb.load_kb())} thu tuc da co cau tra loi.")
    print("    Buoc tiep: git add . && git commit -m \"cache cau tra loi\" && git push")
    return 0 if not loi else 1


if __name__ == "__main__":
    raise SystemExit(main())

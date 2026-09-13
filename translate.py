# -*- coding: utf-8 -*-
"""NHIỆM VỤ 1a — Dịch Việt <-> Mông, kiến trúc "provider" cắm-thay được.

Kết quả kiểm tra khả năng hỗ trợ tiếng Mông (tháng 9/2026):

  | Dịch vụ                  | Có tiếng Mông? | Mã ngôn ngữ | Ghi chú              |
  |--------------------------|----------------|-------------|----------------------|
  | Google Cloud Translation  | CÓ (bản NMT)  | hmn         | Không có ở tầng LLM  |
  | Azure AI Translator       | CÓ            | mww         | "Hmong Daw (Latin)"  |
  | AWS Translate             | KHÔNG         | —           |                      |
  | Gemini                    | CÓ (gián tiếp)| —           | Chất lượng thay đổi  |

  Tất cả đều trả về tiếng Mông Trắng (Hmong Daw) viết bằng RPA —
  KHÔNG phải chữ Mông của người Mông ở Việt Nam. Xem core/hmong/rpa_vi.py.
"""
from __future__ import annotations

import csv
import os
from functools import lru_cache
from pathlib import Path

from core.config import DATA, HMONG_ORTHOGRAPHY, TRANSLATE_PROVIDER
from core.hmong.rpa_vi import rpa_sang_vi
from core.llm import goi_gemini

GLOSSARY_FILE = DATA / "glossary_hmong.csv"

SYSTEM_DICH = """\
Bạn là phiên dịch viên Việt – Mông cho Trung tâm trợ giúp pháp lý cấp xã.

QUY TẮC
1. Dịch sang tiếng Mông Trắng (Hmong Daw), viết bằng RPA (Romanized Popular
   Alphabet) — thanh điệu ghi bằng chữ cái cuối âm tiết.
2. Dịch để NGHE, không để đọc: câu ngắn, từ thông dụng trong đời sống bản làng.
3. Tên giấy tờ và tên cơ quan: dịch nghĩa rồi mở ngoặc giữ nguyên tiếng Việt.
   Ví dụ: "thẻ căn cước" -> "daim ntawv pov thawj tus kheej (the can cuoc)".
4. Con số, ngày, số tiền: GIỮ NGUYÊN dạng chữ số.
5. Không thêm, không bớt, không giải thích. Chỉ trả về bản dịch.
6. Từ nào không chắc, giữ nguyên tiếng Việt thay vì bịa từ Mông.
{glossary}
"""

SYSTEM_DICH_NGUOC = """\
Bạn là phiên dịch viên Mông – Việt. Người nói là bà con dân tộc Mông đang hỏi
về thủ tục hành chính. Dịch sang tiếng Việt tự nhiên, giữ đúng ý hỏi.
Chỉ trả về bản dịch, không giải thích.
"""


@lru_cache(maxsize=1)
def _glossary_block() -> str:
    """Thuật ngữ đã được người Mông bản địa chốt -> ép Gemini dùng đúng."""
    if not GLOSSARY_FILE.exists():
        return ""
    rows = []
    with GLOSSARY_FILE.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            vi, hm = (r.get("tieng_viet") or "").strip(), (r.get("tieng_mong_rpa") or "").strip()
            if vi and hm:
                rows.append(f'   - "{vi}" = "{hm}"')
    if not rows:
        return ""
    return "\n7. BẮT BUỘC dùng đúng các thuật ngữ đã chuẩn hoá sau:\n" + "\n".join(rows)


# --------------------------------------------------------------- providers
def _dich_gemini(text: str, sang_mong: bool) -> str:
    system = (SYSTEM_DICH.format(glossary=_glossary_block()) if sang_mong else SYSTEM_DICH_NGUOC)
    return goi_gemini(text, system=system, vai_tro="fast", temperature=0.1, cache_tag="dich")


def _dich_google_nmt(text: str, sang_mong: bool) -> str:
    """Google Cloud Translation v2 — mã tiếng Mông là 'hmn'."""
    from google.cloud import translate_v2 as translate
    client = translate.Client()
    src, dst = ("vi", "hmn") if sang_mong else ("hmn", "vi")
    return client.translate(text, source_language=src, target_language=dst,
                            format_="text")["translatedText"]


def _dich_azure(text: str, sang_mong: bool) -> str:
    """Azure AI Translator — mã tiếng Mông là 'mww' (Hmong Daw)."""
    import requests
    key = os.environ["AZURE_TRANSLATOR_KEY"]
    region = os.environ.get("AZURE_TRANSLATOR_REGION", "southeastasia")
    src, dst = ("vi", "mww") if sang_mong else ("mww", "vi")
    r = requests.post(
        "https://api.cognitive.microsofttranslator.com/translate",
        params={"api-version": "3.0", "from": src, "to": dst},
        headers={"Ocp-Apim-Subscription-Key": key,
                 "Ocp-Apim-Subscription-Region": region,
                 "Content-Type": "application/json"},
        json=[{"Text": text}], timeout=20,
    )
    r.raise_for_status()
    return r.json()[0]["translations"][0]["text"]


_PROVIDERS = {
    "gemini": _dich_gemini,
    "google_nmt": _dich_google_nmt,
    "azure": _dich_azure,
}


def dich(text: str, *, sang_mong: bool = True, provider: str | None = None) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    provider = provider or TRANSLATE_PROVIDER
    if provider == "off":
        return text
    fn = _PROVIDERS.get(provider, _dich_gemini)
    try:
        return fn(text, sang_mong).strip()
    except Exception:
        if provider != "gemini":                 # tụt xuống Gemini nếu nhà cung cấp chính lỗi
            try:
                return _dich_gemini(text, sang_mong).strip()
            except Exception:
                pass
        return text                              # thà trả tiếng Việt hơn là trả rỗng


def dich_sang_mong(text: str, *, provider: str | None = None) -> dict:
    """Trả về cả 3 dạng để UI và TTS dùng chung một lần gọi API.

    {'rpa': 'Nyob zoo...', 'vn': 'Nhó rong...', 'hien_thi': ...}
    """
    rpa = dich(text, sang_mong=True, provider=provider)
    vn = rpa_sang_vi(rpa)
    return {
        "rpa": rpa,
        "vn": vn,
        "hien_thi": vn if HMONG_ORTHOGRAPHY == "vn" else rpa,
    }


def dich_sang_viet(text: str, *, provider: str | None = None) -> str:
    return dich(text, sang_mong=False, provider=provider)

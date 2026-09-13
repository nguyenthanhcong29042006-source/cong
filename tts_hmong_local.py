# -*- coding: utf-8 -*-
"""KHUÔN MẪU — chạy model TTS tiếng Mông cục bộ.

core/tts.py gọi file này như một tiến trình riêng:
    python tools/tts_hmong_local.py --text "Nyob zoo" --out duong/dan/ra.wav

Tách tiến trình là có ý đồ: model TTS nặng 1-3 GB và hay xung đột thư viện
với Streamlit. Chạy riêng thì app không bao giờ sập vì TTS.

CÁC MODEL ĐANG CÓ TRÊN HUGGING FACE (kiểm tra 09/2026):
  - Xuajpaj2026/hmong-tts-weights   CosyVoice3-0.5B fine-tune tiếng Mông,
                                    có cả ONNX. Mới nhất.
  - Pakorn2112/F5TTS-Hmong          F5-TTS, 1 checkpoint safetensors + vocab.txt
                                    (cùng nhóm với repo YangNobody12/hmong-TTS)
  - Pakorn2112/Orpheus-TTS-hmong-3b Orpheus 3B, có bản GGUF chạy CPU
                                    (grimztha/Orpheus-3B-TTS-hmong-Q8_0-GGUF)

Tất cả đều là tiếng Mông ở Thái Lan/Lào (RPA hoặc chữ Thái), KHÔNG phải
tiếng Mông ở Việt Nam. Phải cho người Mông Việt Nam nghe thử trước khi dùng.

CÁCH BẬT: bỏ chú thích một trong các hàm dưới và cài thư viện tương ứng.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def sinh_bang_f5tts(text: str, out: Path) -> bool:
    """F5-TTS (Pakorn2112/F5TTS-Hmong).

    pip install f5-tts
    huggingface-cli download Pakorn2112/F5TTS-Hmong --local-dir models/f5tts-hmong
    Cần 1 file audio mẫu (ref_audio) + đúng câu trong audio đó (ref_text).
    """
    try:
        from f5_tts.api import F5TTS
    except ImportError:
        return False
    ckpt = Path("models/f5tts-hmong/model_159952.safetensors")
    vocab = Path("models/f5tts-hmong/vocab.txt")
    ref_audio = Path("models/f5tts-hmong/ref.wav")
    ref_text = "Nyob zoo"        # <-- đúng nội dung trong ref.wav
    if not (ckpt.exists() and vocab.exists() and ref_audio.exists()):
        return False
    tts = F5TTS(ckpt_file=str(ckpt), vocab_file=str(vocab))
    tts.infer(ref_file=str(ref_audio), ref_text=ref_text, gen_text=text,
              file_wave=str(out))
    return out.exists()


def sinh_bang_cosyvoice(text: str, out: Path) -> bool:
    """CosyVoice3 (Xuajpaj2026/hmong-tts-weights) — xem README trong repo đó."""
    return False


def sinh_bang_orpheus(text: str, out: Path) -> bool:
    """Orpheus 3B bản GGUF, chạy CPU qua llama-cpp-python. Chậm (~10-20s/câu)."""
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    for fn in (sinh_bang_f5tts, sinh_bang_cosyvoice, sinh_bang_orpheus):
        try:
            if fn(a.text, out):
                print(f"OK {fn.__name__} -> {out}")
                return 0
        except Exception as e:
            print(f"{fn.__name__} loi: {e}", file=sys.stderr)
    print("Khong co backend TTS tieng Mong nao san sang", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

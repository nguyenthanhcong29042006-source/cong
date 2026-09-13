# -*- coding: utf-8 -*-
"""Nhận diện giọng nói. Ưu tiên Gemini (1 API, đa ngôn ngữ, chịu nhiễu tốt),
dự phòng SpeechRecognition (Google Web Speech).
"""
from __future__ import annotations

import io

from google.genai import types

from core.llm import chon_model, danh_sach_model, get_client

PROMPT_VI = (
    "Đây là ghi âm của người dân tộc thiểu số nói tiếng Việt ở vùng cao, "
    "có thể lẫn tiếng địa phương và tiếng ồn. Hãy gõ lại CHÍNH XÁC nội dung "
    "họ nói bằng tiếng Việt có dấu. Chỉ trả về câu nói, không thêm gì khác. "
    "Nếu không nghe được, trả về đúng chữ: KHONG_RO"
)
PROMPT_HMONG = (
    "Đây là ghi âm tiếng Mông (Hmong). Hãy gõ lại nội dung bằng chữ Mông RPA, "
    "sau đó xuống dòng và ghi bản dịch tiếng Việt sau tiền tố 'VI: '. "
    "Nếu không nghe được, trả về đúng chữ: KHONG_RO"
)


def _mime(name: str) -> str:
    n = (name or "").lower()
    if n.endswith(".mp3"):
        return "audio/mpeg"
    if n.endswith(".m4a"):
        return "audio/mp4"
    if n.endswith(".ogg"):
        return "audio/ogg"
    return "audio/wav"


def stt_gemini(audio_bytes: bytes, *, ten_file: str = "rec.wav", tieng_mong: bool = False) -> str:
    part = types.Part.from_bytes(data=audio_bytes, mime_type=_mime(ten_file))
    noi_dung = [PROMPT_HMONG if tieng_mong else PROMPT_VI, part]
    ten_model = chon_model("stt")
    for lan in range(2):
        try:
            resp = get_client().models.generate_content(
                model=ten_model, contents=noi_dung,
                config=types.GenerateContentConfig(temperature=0.0),
            )
            return (resp.text or "").strip()
        except Exception as e:
            s = str(e).lower()
            if lan == 0 and ("404" in s or "not_found" in s or "no longer available" in s):
                danh_sach_model(lam_moi=True)          # model bị gỡ -> dò lại
                moi = chon_model("stt")
                if moi != ten_model:
                    ten_model = moi
                    continue
            raise
    return ""


def stt_du_phong(audio_file) -> str:
    """SpeechRecognition — chỉ dùng khi Gemini lỗi. Yêu cầu file WAV."""
    import speech_recognition as sr
    r = sr.Recognizer()
    with sr.AudioFile(audio_file) as source:
        return r.recognize_google(r.record(source), language="vi-VN")


def nghe(audio_value, *, tieng_mong: bool = False) -> tuple[str, str]:
    """Trả về (van_ban, nguon). audio_value = st.audio_input(...)"""
    raw = audio_value.getvalue() if hasattr(audio_value, "getvalue") else audio_value.read()
    ten = getattr(audio_value, "name", "rec.wav")
    try:
        txt = stt_gemini(raw, ten_file=ten, tieng_mong=tieng_mong)
        if txt and txt != "KHONG_RO":
            return txt, "gemini"
    except Exception:
        pass
    try:
        return stt_du_phong(io.BytesIO(raw)), "google_web_speech"
    except Exception:
        return "", "that_bai"

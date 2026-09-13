# -*- coding: utf-8 -*-
"""
tools/extract_tthc.py
---------------------
Bóc tách các file PDF "CHI TIẾT THỦ TỤC HÀNH CHÍNH" đang bị NHÚNG (OLE object)
bên trong 3 file Excel ở thư mục `file_dichvucong/`, rồi:

  1. Lưu ra `data/tthc/<ma_thu_tuc>/thu_tuc.pdf`
  2. Trích text thuần  -> `data/tthc/<ma_thu_tuc>/raw.txt`
  3. Sinh `data/manifest.json` = "sổ hộ tịch" của toàn bộ kho tri thức

Chạy:  python tools/extract_tthc.py
Chạy lại an toàn (idempotent): file đã có sẽ bị ghi đè.

Vì sao phải làm bước này?
  Excel không lưu PDF như một file rời. Nó nhúng PDF vào
  `xl/embeddings/oleObject<N>.bin` (OLE Compound File). Cột "File" trong sheet
  vì vậy LUÔN rỗng khi đọc bằng openpyxl -> code app không bao giờ
  "nhìn thấy" PDF nếu không bóc ra trước.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import unicodedata
import zipfile
from pathlib import Path

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    sys.exit("Thieu thu vien: pip install pdfplumber")

try:
    import openpyxl
except ImportError:  # pragma: no cover
    sys.exit("Thieu thu vien: pip install openpyxl")

ROOT = Path(__file__).resolve().parents[1]
SRC_EXCEL_DIR = ROOT / "file_dichvucong"
OUT_DIR = ROOT / "data" / "tthc"
RAW_EXCEL_DIR = ROOT / "data" / "raw_excel"
MANIFEST = ROOT / "data" / "manifest.json"

# Map tên file Excel -> nhóm thủ tục (khớp với DANH_MUC_THU_TUC trong core/config.py)
NHOM_THEO_FILE = {
    "khai sinh": "KHAI_SINH",
    "khai tử": "KHAI_TU",
    "đăng ký kết hôn": "KET_HON",
}

# ---------------------------------------------------------------- PDF carving
PDF_HEAD = b"%PDF"
PDF_TAIL = b"%%EOF"


def carve_pdf(ole_bytes: bytes) -> bytes | None:
    """Lấy phần PDF nằm trong stream OLE 'Package'.

    OLE Compound File bọc file gốc trong stream `Package` kèm header chứa
    tên file. Ta không cần parse CFB đầy đủ: chỉ cần cắt từ '%PDF' đến
    '%%EOF' cuối cùng. Đã kiểm chứng trên cả 28 object của 3 file Excel.
    """
    start = ole_bytes.find(PDF_HEAD)
    end = ole_bytes.rfind(PDF_TAIL)
    if start < 0 or end < 0 or end <= start:
        return None
    return ole_bytes[start:end + len(PDF_TAIL)]


def ole_objects(xlsx: Path) -> list[tuple[str, bytes]]:
    """Trả về [(ten_object, bytes)] theo đúng thứ tự số hiệu."""
    with zipfile.ZipFile(xlsx) as z:
        names = [n for n in z.namelist() if n.startswith("xl/embeddings/oleObject")]
        names.sort(key=lambda s: int(re.search(r"(\d+)", s.rsplit("/", 1)[-1]).group(1)))
        return [(n.rsplit("/", 1)[-1].replace(".bin", ""), z.read(n)) for n in names]


# ------------------------------------------------------- Đọc bảng danh sách
def doc_bang_tthc(xlsx: Path) -> list[dict]:
    """Đọc sheet 'Danh sách TTHC' -> [{ma, ten, co_quan_ban_hanh, co_quan_thuc_hien, linh_vuc}]"""
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    # Tìm dòng header (dòng có chữ 'Tên' và 'Lĩnh vực')
    header_idx = None
    for i, r in enumerate(rows[:10]):
        cells = [str(c or "").strip().lower() for c in r]
        if "tên" in cells and "lĩnh vực" in cells:
            header_idx = i
            break
    if header_idx is None:
        header_idx = 1

    out = []
    for r in rows[header_idx + 1:]:
        ma = str(r[0] or "").strip()
        ten = str(r[1] or "").strip()
        if not ten:
            continue
        out.append({
            "ma_thu_tuc": ma,
            "ten": re.sub(r"\s+", " ", ten),
            "co_quan_ban_hanh": str(r[2] or "").strip(),
            "co_quan_thuc_hien": re.sub(r"\s+", " ", str(r[3] or "").strip()),
            "linh_vuc": str(r[4] or "").strip(),
        })
    return out


# ------------------------------------------------------- Parse text trong PDF
FIELD_PATTERNS = {
    "ten_thu_tuc": r"Tên thủ tục\s*(.+?)(?=\nMã thủ tục)",
    "ma_thu_tuc": r"Mã thủ tục\s*([\d.]+)",
    "cap_thuc_hien": r"Cấp thực hiện\s*(.+?)(?=\n)",
    "linh_vuc": r"Lĩnh vực\s*(.+?)(?=\n)",
    "doi_tuong": r"Đối tượng thực hiện\s*(.+?)(?=\n)",
}
SECTION_HEADS = [
    "TRÌNH TỰ THỰC HIỆN",
    "CÁCH THỨC THỰC HIỆN",
    "THÀNH PHẦN HỒ SƠ",
    "TRÌNH TỰ, THỜI HẠN GIẢI QUYẾT",
    "YÊU CẦU, ĐIỀU KIỆN THỰC HIỆN",
    "CĂN CỨ PHÁP LÝ",
    "KẾT QUẢ THỰC HIỆN",
    "PHÍ, LỆ PHÍ",
    "THỜI HẠN GIẢI QUYẾT",
]


def pdf_to_text(pdf_path: Path) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


def parse_fields(text: str) -> dict:
    """Trích các trường đầu trang + cắt text thành các mục lớn."""
    meta = {}
    for key, pat in FIELD_PATTERNS.items():
        m = re.search(pat, text, flags=re.S)
        meta[key] = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""

    # Cắt theo tiêu đề mục (dùng để đưa ĐÚNG mục cần thiết cho Gemini,
    # thay vì nhồi cả 15.000 ký tự -> tiết kiệm token & giảm ảo giác)
    positions = []
    for head in SECTION_HEADS:
        idx = text.find(head)
        if idx >= 0:
            positions.append((idx, head))
    positions.sort()
    sections = {}
    for i, (idx, head) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        sections[head] = text[idx + len(head):end].strip()
    meta["sections"] = sections
    return meta


def slugify(s: str, maxlen: int = 60) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s[:maxlen] or "khong-ten"


# ------------------------------------------------------------------- Main
def main() -> int:
    if not SRC_EXCEL_DIR.exists():
        sys.exit(f"Khong tim thay {SRC_EXCEL_DIR}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_EXCEL_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {"version": 2, "thu_tuc": []}
    tong_ole, tong_ok = 0, 0

    for xlsx in sorted(SRC_EXCEL_DIR.glob("*.xlsx")):
        stem = xlsx.stem
        nhom = NHOM_THEO_FILE.get(stem, "KHAC")
        print(f"\n=== {xlsx.name}  (nhom={nhom}) ===")

        bang = doc_bang_tthc(xlsx)
        objs = ole_objects(xlsx)
        tong_ole += len(objs)
        print(f"  bang: {len(bang)} dong | pdf nhung: {len(objs)} object")

        for i, (obj_name, blob) in enumerate(objs):
            pdf_bytes = carve_pdf(blob)
            if pdf_bytes is None:
                print(f"  [!] {obj_name}: khong tim thay PDF ben trong -> bo qua")
                continue

            tmp = OUT_DIR / f"_tmp_{obj_name}.pdf"
            tmp.write_bytes(pdf_bytes)
            try:
                text = pdf_to_text(tmp)
            except Exception as e:
                print(f"  [!] {obj_name}: loi doc PDF ({e}) -> bo qua")
                tmp.unlink(missing_ok=True)
                continue

            meta = parse_fields(text)
            # Ưu tiên mã trong PDF; nếu PDF không có thì lấy theo thứ tự dòng bảng
            ma = meta.get("ma_thu_tuc") or (bang[i]["ma_thu_tuc"] if i < len(bang) else "")
            ten = meta.get("ten_thu_tuc") or (bang[i]["ten"] if i < len(bang) else obj_name)
            key = ma if ma else slugify(ten)

            folder = OUT_DIR / key
            folder.mkdir(parents=True, exist_ok=True)
            shutil.move(str(tmp), folder / "thu_tuc.pdf")
            (folder / "raw.txt").write_text(text, encoding="utf-8")
            (folder / "sections.json").write_text(
                json.dumps(meta.get("sections", {}), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            row = bang[i] if i < len(bang) else {}
            manifest["thu_tuc"].append({
                "key": key,
                "ma_thu_tuc": ma,
                "ten": ten,
                "nhom": nhom,
                "linh_vuc": meta.get("linh_vuc") or row.get("linh_vuc", ""),
                "cap_thuc_hien": meta.get("cap_thuc_hien", ""),
                "doi_tuong": meta.get("doi_tuong", ""),
                "co_quan_thuc_hien": row.get("co_quan_thuc_hien", ""),
                "pdf": f"data/tthc/{key}/thu_tuc.pdf",
                "raw_txt": f"data/tthc/{key}/raw.txt",
                "sections": sorted(meta.get("sections", {}).keys()),
                "nguon_excel": xlsx.name,
                "so_ky_tu": len(text),
            })
            tong_ok += 1
            print(f"  + {key}  <- {obj_name}  ({len(text)} ky tu)  {ten[:55]}")

        # lưu bản gốc Excel vào data/raw_excel để sau này chỉ còn 1 gốc dữ liệu
        shutil.copy2(xlsx, RAW_EXCEL_DIR / xlsx.name)

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n==> Boc duoc {tong_ok}/{tong_ole} PDF. Manifest: {MANIFEST}")
    print("    Buoc tiep: python tools/build_cache.py  (tao san cau tra loi don gian)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

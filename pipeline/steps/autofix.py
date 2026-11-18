"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
CLIP_CODES = {"BOX_OUT_OF_IMAGE"}
REMOVE_CODES = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}          # + mọi mã bắt đầu bằng DUP_IMAGE_


def _is_remove(code: str) -> bool:
    return code in REMOVE_CODES or code.startswith("DUP_IMAGE_")


def _fmt(v: float) -> str:
    return f"{v:.6f}".rstrip("0").rstrip(".") or "0"


def _clip(text: str):
    """Cắt box về [0,1]. Trả về dòng mới, hoặc None nếu box không còn diện tích (hoặc dòng không parse được)."""
    try:
        cls, cx, cy, w, h = parse_yolo_line(text)
    except ValueError:
        return None
    x1, x2 = max(0.0, cx - w / 2), min(1.0, cx + w / 2)
    y1, y2 = max(0.0, cy - h / 2), min(1.0, cy + h / 2)
    nw, nh = x2 - x1, y2 - y1
    if nw <= 1e-6 or nh <= 1e-6:
        return None
    return " ".join([str(cls), _fmt((x1 + x2) / 2), _fmt((y1 + y2) / 2), _fmt(nw), _fmt(nh)])


def _remove_image(ds, stem):
    p = ds.image_path(stem)
    if p is None:                               # đã xoá rồi (hai issue cùng ảnh) -> bỏ qua
        return None
    before = p.name
    p.unlink()
    lp = ds.label_path(stem)
    if lp.exists():
        lp.unlink()
        before += f" + labels/{lp.name}"
    ds._size_cache.pop(stem, None)
    return before


def _rename_classes(ds, classes):
    data = {}
    if ds.yaml_path.exists():
        data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
    old = data.get("names")
    if isinstance(old, dict):
        new = {i: n for i, n in enumerate(classes)}
        old_cmp = {int(k): v for k, v in old.items()}
    else:
        new, old_cmp = list(classes), old
    if old_cmp == new:
        return None
    data["names"] = new
    if "nc" in data:
        data["nc"] = len(classes)
    ds.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return str(old), str(new)


def fix(ds, issues, cfg):
    errors = [i for i in issues if i.severity == ERROR]
    fixes = []

    # 1) ảnh phải loại: xoá trước, để các issue dòng của chính ảnh đó bị bỏ qua êm
    removed = set()
    for i in sorted((i for i in errors if _is_remove(i.code)), key=lambda i: i.image):
        if i.image in removed:
            continue
        before = _remove_image(ds, i.image)
        removed.add(i.image)
        if before is not None:
            fixes.append(dict(image=i.image, line=None, action="remove_image", before=before,
                              after=f"(đã xoá: {i.code})"))

    # 2) data.yaml: tên lớp sai -> ghi lại đúng cfg["classes"] (một lần)
    if any(i.code == "BAD_CLASS_NAME" for i in errors):
        ch = _rename_classes(ds, cfg["classes"])
        if ch:
            fixes.append(dict(image="data.yaml", line=None, action="rename_classes", before=ch[0], after=ch[1]))

    # 3) ảnh chưa có nhãn: KHÔNG bịa nhãn, chỉ ghi dấu vết để chuyển người gán
    for stem in sorted({i.image for i in errors if i.code == "MISSING_LABEL_FILE"} - removed):
        if ds.image_path(stem) is not None and not ds.label_path(stem).exists():
            fixes.append(dict(image=stem, line=None, action="needs_label", before="(không có file)", after="chuyển người gán"))

    # 4) lỗi dòng: gom theo file -> {số dòng gốc: {mã lỗi}}, rồi ghi lại file MỘT lần
    per_file = defaultdict(lambda: defaultdict(set))
    for i in errors:
        if i.line is not None and (i.code in DROP_CODES or i.code in CLIP_CODES) and i.image not in removed:
            per_file[i.image][int(i.line)].add(i.code)

    for stem in sorted(per_file):
        lp = ds.label_path(stem)
        if not lp.exists():
            continue
        raw_lines = lp.read_text(encoding="utf-8", errors="replace").splitlines()   # giữ dòng trống: số dòng = số dòng gốc
        out, changed = [], False
        for no, text in enumerate(raw_lines, 1):
            codes = per_file[stem].get(no)
            if not codes or not text.strip():
                out.append(text)
                continue
            if codes & DROP_CODES:                        # xoá dòng thắng clip
                fixes.append(dict(image=stem, line=no, action="drop_line", before=text.strip(),
                                  after=f"(xoá: {','.join(sorted(codes & DROP_CODES))})"))
                changed = True
                continue
            new = _clip(text)
            if new is None:                               # nằm hẳn ngoài ảnh -> xoá thay vì ghi box rỗng
                fixes.append(dict(image=stem, line=no, action="drop_line", before=text.strip(),
                                  after="(xoá: box không còn diện tích sau khi cắt)"))
                changed = True
                continue
            if new != text.strip():
                fixes.append(dict(image=stem, line=no, action="clip_box", before=text.strip(), after=new))
                changed = True
            out.append(new)
        if changed:
            lp.write_text("".join(l + "\n" for l in out), encoding="utf-8")
    return fixes

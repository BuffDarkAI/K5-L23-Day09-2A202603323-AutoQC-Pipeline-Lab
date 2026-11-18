"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401

NAME = "label_format"


def _overflow(cx, cy, w, h) -> float:
    """Mức tràn lớn nhất của 4 mép box ra ngoài [0, 1] (0 nếu nằm trong ảnh)."""
    edges_low = (cx - w / 2, cy - h / 2)       # trái, trên: phải >= 0
    edges_high = (cx + w / 2, cy + h / 2)      # phải, dưới: phải <= 1
    return max(0.0, *(-e for e in edges_low), *(e - 1.0 for e in edges_high))


def check_lines(stem, lines, n_classes, img_size, c):
    """Kiểm các dòng [(số dòng, nội dung)] của một ảnh. Tách riêng để autofix/test dùng lại được."""
    issues = []
    kept = []                                   # (số dòng, box) hợp lệ đã thấy, để dò DUP_BOX
    for ln_no, text in lines:
        try:
            cls, cx, cy, w, h = parse_yolo_line(text)
        except ValueError as e:
            issues.append(Issue(NAME, ERROR, "BAD_FORMAT", stem, f"dòng không đúng 5 cột số: {e}", line=ln_no,
                                extra={"text": text.strip()[:80]}))
            continue
        if not 0 <= cls < n_classes:
            issues.append(Issue(NAME, ERROR, "BAD_CLASS_ID", stem, f"id lớp {cls} ngoài 0..{n_classes - 1}", line=ln_no,
                                extra={"class_id": cls}))
            continue
        if w <= 0 or h <= 0:
            issues.append(Issue(NAME, ERROR, "BOX_ZERO", stem, f"box rộng/cao <= 0 (w={w}, h={h})", line=ln_no))
            continue

        over = _overflow(cx, cy, w, h)
        if over > c["overflow_tol"]:
            issues.append(Issue(NAME, ERROR, "BOX_OUT_OF_IMAGE", stem, f"box tràn ảnh {over:.4f}", line=ln_no,
                                extra={"overflow": round(over, 6)}))

        box = (cx, cy, w, h)
        for prev_no, (pcls, pbox) in kept:
            if pcls == cls and iou_xywh(pbox, box) > c["dup_box_iou"]:
                issues.append(Issue(NAME, ERROR, "DUP_BOX", stem, f"trùng box dòng {prev_no} (cùng lớp {cls})",
                                    line=ln_no, extra={"dup_of": prev_no}))
                break
        kept.append((ln_no, (cls, box)))

        if img_size:
            iw, ih = img_size
            short_px = min(w * iw, h * ih)
            if short_px < c["min_box_px"]:
                issues.append(Issue(NAME, WARN, "BOX_TINY", stem, f"cạnh ngắn {short_px:.1f}px < {c['min_box_px']}px",
                                    line=ln_no, extra={"short_px": round(short_px, 2)}))
        if w * h > c["max_box_frac"]:
            issues.append(Issue(NAME, WARN, "BOX_HUGE", stem, f"box chiếm {w * h:.2%} ảnh", line=ln_no,
                                extra={"area_frac": round(w * h, 4)}))
    return issues


def run(ds, cfg):
    c = cfg["label_format"]
    n_classes = len(ds.classes)
    issues = []
    for lf in ds.label_files():
        stem = lf.stem
        lines = ds.read_label_lines(stem) or []
        if not lines:
            continue
        size = ds.image_size(stem)              # None nếu thiếu/hỏng ảnh -> bỏ qua BOX_TINY
        issues.extend(check_lines(stem, lines, n_classes, size, c))
    return issues

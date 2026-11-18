"""CHECK THƯỞNG — Box lệch tỉ lệ khung hình (aspect ratio) bất thường so với lớp của nó.   (bonus, RUBRIC: +3)

Test:  pytest tests/test_aspect_ratio.py -q
Chạy trên một dataset (không đụng luồng chính vì `checks/__init__.py` và `configs/pipeline.yaml` đã ghim):
    python -m pipeline.checks.aspect_ratio                         # quét data/raw, ghi submission/reports/extra_aspect_ratio.csv
    python -m pipeline.checks.aspect_ratio --data work/run/ds      # quét dataset sau pipeline

Ý tưởng: box là hình chữ nhật trong PIXEL (w*W, h*H). Một người đứng thường cao > rộng; một chiếc xe hiếm khi
cao gấp 3 lần rộng. Box "que diêm" (rất dẹt hoặc rất mảnh) thường là box gõ nhầm toạ độ, box bị cắt mất một phần,
hoặc box của vật bị che gần hết. Máy không biết chắc -> chỉ CẢNH BÁO cho người xem.

| code             | severity | khi nào                                                                          |
|------------------|----------|----------------------------------------------------------------------------------|
| BOX_ODD_ASPECT   | WARN     | tỉ lệ cạnh dài / cạnh ngắn (px) > `max_aspect`  (mọi lớp)                        |
| BOX_ODD_ASPECT   | WARN     | lớp có quy tắc riêng trong `class_hw` và h/w (px) nằm ngoài [lo, hi] của lớp đó  |

Ngưỡng đọc từ `cfg["aspect_ratio"]` nếu có; vì `configs/pipeline.yaml` bị ghim (RULES.md), khi thiếu khoá thì dùng
DEFAULTS bên dưới — đây là quy tắc dự án viết thành hằng số có tên, không rải số trong code.
Bỏ qua dòng hỏng / id lạ / box rỗng (label_format đã báo) và ảnh không đọc được kích thước.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from ..common import ROOT, WARN, Dataset, Issue, load_config, parse_yolo_line, write_issues_csv

NAME = "aspect_ratio"
DEFAULTS = {
    "max_aspect": 8.0,                        # dài/ngắn > 8 với bất kỳ lớp nào: gần như chắc là box hỏng
    "class_hw": {"person": [0.4, 6.0]},       # người: h/w ngoài [0.4, 6] (nằm ngang dẹt quá / mảnh như que) là lạ
}


def _params(cfg):
    p = dict(DEFAULTS)
    p.update((cfg or {}).get("aspect_ratio", {}) or {})
    return p


def run(ds, cfg):
    p = _params(cfg)
    max_aspect = float(p["max_aspect"])
    class_hw = p.get("class_hw", {}) or {}
    issues = []
    for lf in ds.label_files():
        stem = lf.stem
        size = ds.image_size(stem)
        if not size:
            continue
        W, H = size
        for no, text in ds.read_label_lines(stem) or []:
            try:
                cls, _, _, w, h = parse_yolo_line(text)
            except ValueError:
                continue
            if not 0 <= cls < len(ds.classes) or w <= 0 or h <= 0:
                continue
            wp, hp = w * W, h * H
            hw = hp / wp
            ratio = max(hw, 1 / hw)
            name = ds.classes[cls]
            rule = class_hw.get(name)
            extra = {"class": name, "h_over_w": round(hw, 3), "w_px": round(wp, 1), "h_px": round(hp, 1)}
            if ratio > max_aspect:
                issues.append(Issue(NAME, WARN, "BOX_ODD_ASPECT", stem,
                                    f"box {name} tỉ lệ {ratio:.1f}:1 > {max_aspect:g}:1 ({wp:.0f}x{hp:.0f}px)", line=no, extra=extra))
            elif rule and not (rule[0] <= hw <= rule[1]):
                issues.append(Issue(NAME, WARN, "BOX_ODD_ASPECT", stem,
                                    f"box {name} có h/w={hw:.2f} ngoài khoảng thường gặp [{rule[0]}, {rule[1]}]", line=no, extra=extra))
    return issues


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check thưởng: box lệch tỉ lệ khung hình")
    ap.add_argument("--data", default="data/raw")
    ap.add_argument("--out", default="submission/reports/extra_aspect_ratio.csv")
    ap.add_argument("--config", default="configs/pipeline.yaml")
    a = ap.parse_args(argv)
    cfg = load_config(ROOT / a.config)
    ds = Dataset(ROOT / a.data, cfg["classes"])
    issues = run(ds, cfg)
    write_issues_csv(issues, ROOT / a.out)
    n_img = len(ds.image_files())
    print(f"ảnh đã quét: {n_img}; BOX_ODD_ASPECT: {len(issues)} box trên {len({i.image for i in issues})} ảnh -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

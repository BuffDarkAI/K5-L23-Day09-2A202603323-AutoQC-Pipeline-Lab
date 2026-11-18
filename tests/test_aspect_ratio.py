"""Test cho check thưởng `aspect_ratio` (học viên viết thêm; không thuộc bộ test gốc)."""
from pipeline.checks import aspect_ratio


def codes(make_ds, cfg, lines, size=(640, 480)):
    ds = make_ds(images={"a": 1}, labels={"a": lines}, size=size)
    return [(i.code, i.line) for i in aspect_ratio.run(ds, cfg)]


def test_normal_boxes_are_silent(make_ds, cfg):
    # người đứng h/w = (0.5*480)/(0.15*640) = 2.5 ; xe 0.3x0.2 -> h/w = 0.5
    assert codes(make_ds, cfg, ["1 0.5 0.5 0.15 0.5", "0 0.3 0.3 0.3 0.2"]) == []


def test_extreme_ratio_any_class(make_ds, cfg):
    # xe: rộng 0.9*640=576px, cao 0.1*480=48px -> 12:1 > 8:1
    assert codes(make_ds, cfg, ["0 0.5 0.5 0.9 0.1"]) == [("BOX_ODD_ASPECT", 1)]


def test_ratio_is_measured_in_pixels_not_normalised_units(make_ds, cfg):
    # w=h=0.5 chuẩn hoá nhưng ảnh 1600x200 -> 800x100 px = 8:1 (chưa vượt), ảnh 1700x200 -> 8.5:1 (vượt)
    assert codes(make_ds, cfg, ["0 0.5 0.5 0.5 0.5"], size=(1600, 200)) == []
    assert codes(make_ds, cfg, ["0 0.5 0.5 0.5 0.5"], size=(1700, 200)) == [("BOX_ODD_ASPECT", 1)]


def test_person_lying_flat_is_flagged_but_car_with_same_shape_is_not(make_ds, cfg):
    # h/w = (0.1*480)/(0.3*640) = 0.25 < 0.4 với person; car không có quy tắc riêng
    assert codes(make_ds, cfg, ["1 0.5 0.5 0.3 0.1", "0 0.5 0.5 0.3 0.1"]) == [("BOX_ODD_ASPECT", 1)]


def test_thresholds_come_from_config(make_ds, cfg):
    cfg["aspect_ratio"] = {"max_aspect": 20, "class_hw": {}}
    assert codes(make_ds, cfg, ["0 0.5 0.5 0.9 0.1", "1 0.5 0.5 0.3 0.1"]) == []


def test_broken_lines_and_line_numbers(make_ds, cfg):
    got = codes(make_ds, cfg, ["garbage", "", "93 0.5 0.5 0.9 0.1", "1 0.5 0.5 0 0.2", "0 0.5 0.5 0.9 0.1"])
    assert got == [("BOX_ODD_ASPECT", 5)]
    ds = make_ds(images={"q": 1}, labels={"q": ["0 0.5 0.5 0.9 0.1"]})
    assert all(i.severity == "warn" for i in aspect_ratio.run(ds, cfg))

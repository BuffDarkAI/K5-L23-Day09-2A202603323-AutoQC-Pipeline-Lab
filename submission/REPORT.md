# Báo cáo Day 09 — Bùi Sỹ Tùng, 2A202603323

Số liệu lấy từ `submission/reports/` (lần chạy `make run` với `phash_dist=12`, `second_opinion.conf=0.6`, `config_sha1=58d1755…`), `submission/calibration/`.

## 1. Kết luận trước
**HOLD** (mã thoát 10). Quét **224** ảnh raw → nhận **202** ảnh (loại 22 ở cửa vào) → xuất **202** ảnh vào `submission/export/clean_v1/` dưới dạng **bản nháp, chưa phát hành** (manifest ghi `decision=Hold`).
Lý do: **0 lỗi bắt buộc** còn lại (`07_error_list_v3`), nhưng **38/202 ảnh = 18,8 %** còn cảnh báo **chưa người duyệt** ≥ ngưỡng 10 %. Hàng đợi có **125 ảnh**, ngân sách duyệt chỉ **80 ảnh** → 45 ảnh không ai xem, 38 trong số đó vẫn còn cảnh báo.

## 2. Lỗi và phân việc
Từ `01_intake` (mẫu số 224 ảnh) và `02_error_list_v1` (mẫu số 202 ảnh đã nhận). "Máy" = `autofix` (`03_fixes.csv`, 35 thay đổi: 20 `drop_line`, 8 `clip_box`, 6 `needs_label`, 1 `rename_classes`) hoặc loại ở cửa vào; "người" = `05_review_queue.csv`.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| DUP_IMAGE_EXACT | 8 ảnh / 224 | máy (loại ở cửa vào) | md5 trùng từng byte: chắc chắn, giữ ảnh đầu tiên |
| DUP_IMAGE_NEAR | 4 ảnh / 224 | máy (loại) | phash ≤ 12; đã mở xem cả 4 cặp, đều là cùng ảnh (đổi sáng, cắt, thu nhỏ) |
| LEAK_TEST | 5 ảnh / 224 | máy (loại) | trùng ảnh `data/test`: để lại thì điểm test bị thổi phồng |
| BAD_SIZE | 3 ảnh / 224 | máy (loại) | cạnh ngắn 180–226 px < 250 px |
| CORRUPT_IMAGE | 2 ảnh / 224 | máy (loại) | không `load()` được (cắt cụt / không phải ảnh) |
| BAD_CLASS_NAME | 2 tên trong `data.yaml` | máy (`rename_classes`) | `Person`, `Bus` → ghi lại đúng `cfg.classes` |
| BAD_CLASS_ID | 6 dòng / 6 ảnh | máy (`drop_line`) | id 93, 7, 4, −1: không đoán được lớp đúng → xoá dòng, ảnh vào hàng đợi (FIXED_DROP_LINE) |
| BAD_FORMAT | 3 dòng / 3 ảnh | máy (`drop_line`) | `nan`, thiếu cột |
| BOX_ZERO | 4 dòng / 4 ảnh | máy (`drop_line`) | w hoặc h = 0 |
| DUP_BOX | 7 dòng / 7 ảnh | máy (`drop_line`) | cùng lớp, IoU > 0.9 với dòng trước |
| BOX_OUT_OF_IMAGE | 8 dòng / 8 ảnh | máy (`clip_box`) | tràn 0,023–0,06; cắt về [0,1], giữ lớp |
| MISSING_LABEL_FILE | 6 ảnh / 202 | **người** (`needs_label`) | máy không bịa nhãn, không tạo file rỗng (rỗng = ảnh nền) |
| POSSIBLE_MISSING | 53 cờ | người | model lớn thấy vật mà nhãn không có |
| POSSIBLE_LOOSE_BOX | 28 cờ | người | đúng lớp nhưng IoU với model < 0,5 |
| POSSIBLE_FALSE_POS | 29 cờ (24 sau autofix) | người | box nhãn không khớp vật nào model thấy |
| POSSIBLE_WRONG_CLASS | 18 cờ | người | model nói lớp khác với IoU ≥ 0,5 (vd. img_0160 bus→truck, img_0070 car→person) |
| EMPTY_LABEL | 12 ảnh (15 sau autofix) | người | file rỗng: ảnh nền hay thiếu nhãn? (img_0004 rỗng nhưng có ô tô) |
| BOX_TINY / BOX_HUGE | 6 / 3 dòng | người | quy tắc dự án, chỉ cảnh báo |
| CLASS_RARE | 4 cờ cấp dataset | — | id lạ (93, 7, 4, −1) có < 5 box; hết sau khi xoá dòng |

**Hàng đợi.** `review_queue` cộng điểm theo trọng số cố định (`NEEDS_LABEL` 10, `WRONG_CLASS` 3, `MISSING`/`FALSE_POS`/`FIXED_DROP_LINE` 2, …) nhân `(1+conf)`. Vì vậy đầu hàng là **img_0020** (11,5: vừa bị xoá dòng id 93, vừa MISSING + WRONG_CLASS), rồi **6 ảnh chưa có nhãn** (10,0), rồi các ảnh nhiều cờ ngữ nghĩa với conf cao (img_0160 8,9; img_0127 8,8). Ngân sách 80/125 ảnh dừng ở mức ưu tiên 3,34 (img_0012), ảnh 81 (img_0210, một cờ MISSING) chỉ còn 3,33 điểm — phần bị cắt khỏi ngân sách là các ảnh một cờ, trọng số thấp. Sau duyệt (`07` so với `04`): WRONG_CLASS 18→3, MISSING 53→13, LOOSE_BOX 28→20, FALSE_POS 24→21, EMPTY_LABEL 15→4; 6 ảnh thiếu nhãn đã được gán → 0 lỗi bắt buộc. 45 ảnh còn lại trong hàng đợi chủ yếu là cờ LOOSE_BOX/FALSE_POS/BOX_TINY đơn lẻ.

**3 lỗi tôi tự nhìn thấy** (`viz_labels.py`): img_0070 — người phụ nữ đứng bị gán `car`; img_0160 — bãi xe hàng trăm xe tải nhưng chỉ có ~5 box (thiếu nhãn hàng loạt); img_0127 — box `person` dòng 1 phình to phủ cả đám đông phía dưới.

## 3. Calibration (2 ngưỡng)
Đo trên `data/calib` (39 ảnh, `MANIFEST.csv`), mỗi ô là precision / recall. Bảng đầy đủ: `submission/calibration/calibration_report.md`.

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **12** | NEAR 1,00/0,50 → **1,00/0,67**; EXACT 1,00/1,00 giữ nguyên. Trên raw: NEAR 2→4 ảnh, LEAK 4→5 | Đây là lỗi **máy tự loại ảnh**, FP = xoá nhầm ảnh tốt → ưu tiên precision. Precision 1,00 suốt 4–14, recall phẳng 0,67 ở 4–14; tôi chọn 12 (giữa vùng an toàn) vì trên raw cặp trùng thật xa nhất là dist 10 (img_0186↔img_0061, ảnh cắt) và cặp sai đầu tiên xuất hiện ở 16 → còn biên 2 mỗi phía. |
| `second_opinion.conf` | 0.25 | **0.6** | WRONG_CLASS 0,56/0,83 → **0,62/0,83**; MISSING 0,50/1,00 → **0,57/1,00**; LOOSE_BOX 0,29/0,40 → 0,20/0,20; FALSE_POS 0,31/1,00 không đổi (dùng `fp_conf` cố định). Trên raw: hàng đợi 143→125 ảnh, ảnh cảnh báo chưa duyệt 58→38 | Đây là **cảnh báo cho người** → giữ recall. 0,6 là mức cao nhất mà recall của 2 loại nặng nhất (WRONG_CLASS, MISSING) vẫn tối đa, trong khi precision tăng → bớt 18 ảnh báo động giả cho người. 0,7 làm MISSING recall rơi 1,00→0,88, 0,8 rơi →0,75. Cái giá: LOOSE_BOX recall 0,40→0,20 (trọng số thấp 1,5; xem §4 điểm mù). |

**Không chọn 0,8 dù nó cho Release.** Tôi đã thử cả sweep trên raw (`work/exp`, không commit): conf 0,25/0,4/0,5/0,6/0,7 → Hold với 28,7/24,8/21,8/18,8/14,4 % ảnh cảnh báo chưa duyệt; **0,8 → Release (7,9 %)**. Nhưng ở 0,8 calib cho MISSING recall 0,75 (bỏ sót 2/8 lỗi xoá box): Release đó là do checker "mù" bớt, không phải dữ liệu sạch hơn — đúng kiểu Release giả.

**Một chỗ calibration đánh lừa: `phash_dist`.** Trên calib, F1 của DUP_IMAGE_NEAR cao nhất ở **16** (1,00/0,83/0,91) và precision vẫn 1,00 → nếu chỉ nhìn calib tôi sẽ chọn 16. Nhưng chạy trên raw ở 16: LEAK_TEST nhảy **5→11** và có 3 cặp NEAR mới đều ở đúng dist 16; mở xem thì **img_0011 (tay vợt tennis) ↔ img_0008 (2 người trượt tuyết)** và **img_0177 (người lướt sóng) ↔ img_0113 (người ngồi bàn ăn)** là ảnh khác hẳn nhau, chỉ img_0084↔img_0074 là trùng thật (ảnh cắt). Ở 20 còn tệ hơn: raw bị loại 105 ảnh LEAK + 25 NEAR, và chính calib cũng cho EXACT recall rơi 1,00→0,33 (ảnh trùng byte bị gán nhầm thành LEAK). Lý do: calib chỉ có 6 cặp gần trùng và 39 ảnh — quá ít cặp "khác nhưng phash gần" để lộ FP; raw có 224 ảnh + 140 ảnh tham chiếu test/val nên xác suất va chạm phash tăng theo số cặp so sánh. Ngoài ra calib **không có** ca LEAK_TEST, nên không đo được FP của LEAK.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Gate chặn thật.** Chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb --work work/run_nb` (không có người duyệt): log in `kết luận: REWORK — còn 6 lỗi bắt buộc (MISSING_LABEL_FILE=6) trên 6 ảnh/mục…; tỉ lệ ảnh còn cảnh báo chưa duyệt: 112/202 = 55.5 %`, `echo $?` → **20**, dòng cuối `Bước 5/5 KHÔNG xuất: còn lỗi bắt buộc (Rework)` và thư mục `work/exp_nb` **không được tạo**. Autofix chỉ ghi `needs_label`, không tạo file nhãn rỗng, nên 6 ảnh thiếu nhãn vẫn là lỗi bắt buộc cho tới khi người gán. Ngược lại, gate không cho ảnh đã duyệt "che" lỗi bắt buộc (test `test_error_cannot_be_hidden_by_reviewed`).
**Tái lập:** chạy pipeline 2 lần (`submission/reports` và `work/rep_again`) → 8 file CSV giống hệt từng byte, nhãn export giống hệt (`diff -r` rỗng).

**(b) Điểm mù có bằng chứng.**
1. **Ảnh trùng bị cắt mạnh.** img_0084 là bản cắt của img_0074 nhưng phash cách 16 > 12 → lọt vào dataset (cả hai ảnh đều được nhận). Calib cũng còn 2/6 ca NEAR bỏ sót ở ngưỡng đã chọn. Muốn bắt phải đổi phương pháp (so khớp đặc trưng cục bộ/embedding), không phải nới ngưỡng (nới là gộp nhầm như §3).
2. **Box lỏng nhẹ.** LOOSE_BOX trên calib chỉ 0,20/0,20 ở conf 0,6 (bỏ sót 4/5); box phình vừa phải vẫn có IoU ≥ 0,5 với dự đoán nên không bị cờ. 20 cờ LOOSE_BOX vẫn còn sau duyệt, 16 ở ảnh chưa ai xem.
3. **Model lớn cũng nhầm / cũng mù.** WRONG_CLASS recall trên calib 0,83 ở mọi conf (1/6 ca không ngưỡng nào bắt được). Trên raw, sau khi người thay bằng nhãn chuẩn, **25/80 ảnh đã duyệt vẫn bị model cờ** (11 MISSING, 10 FALSE_POS, 4 LOOSE, 3 WRONG_CLASS) — đó là chỗ model và người bất đồng, tức báo động giả; chiều ngược lại (model nhầm *giống* nhãn) thì không cờ được. Vật nhỏ < 600 px² (bãi xe img_0160) bị `min_area_px` bỏ qua nên thiếu nhãn hàng loạt chỉ sinh 1 cờ MISSING.
4. **Check thưởng (aspect ratio)** bắt thêm 10 box hình "que" trên 9 ảnh raw (`submission/reports/extra_aspect_ratio.csv`), phần lớn là người bị che một nửa — loại lỗi mà 7 check gốc không nhìn thấy.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Colab T4, `notebooks/day09_train_compare.ipynb`: **yolo26n.pt, 20 epoch, batch 16, imgsz 640, seed 0 và 1** cho cả hai biến thể; cùng val (`gold_val`, 40 ảnh) và cùng test (`data/test`, 100 ảnh). `raw` = 224 ảnh nhãn gốc; `clean` = 202 ảnh của `clean_v1` (bản nháp **Hold**, `manifest_sha1=fb038a4…`). Bảng do `scripts/summarize_results.py` sinh (`submission/results/comparison.md`):

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 202 | 2 | 0.701 ± 0.025 | 0.487 ± 0.008 | 0.759 ± 0.003 | 0.625 ± 0.019 |

Chênh mAP50 (clean − raw) = **−0.025**.

**So với nhiễu.** −0.025 mAP50 đúng bằng **1 độ lệch chuẩn giữa seed của `clean`** (0.718 vs 0.683): seed 0 của clean (0.718) chỉ kém raw 0.008, seed 1 kém 0.043. Precision (−0.005) và recall (−0.024) nằm trong độ lệch (0.061 / 0.028). Riêng mAP50-95 (−0.025) lớn hơn độ lệch seed (0.004–0.008), nhưng độ lệch ước từ **2 seed** là rất kém tin cậy (raw có 2 seed gần trùng nhau 0.7256/0.7259 nên "± 0.000" chắc chắn đánh giá thấp nhiễu thật). Theo lớp, chênh lớn nhất ở **truck**: AP50 clean 0.590/0.486 vs raw 0.657/0.640 — đúng lớp mà test chỉ có **24 box** và hai seed của clean đã lệch nhau 0.10; car hơi thấp hơn (0.740/0.736 vs 0.751/0.724), person ngang (0.816/0.830 vs 0.813/0.832), bus ngang (0.726/0.681 vs 0.681/0.709).

**Giả thuyết và cách kiểm.**
1. **Rò rỉ test thổi phồng `raw`.** Pipeline đã phát hiện **5 ảnh LEAK_TEST** trong raw (img_0049, img_0101, img_0167, img_0174, img_0221 trùng test_033, 039, 044, 085, 009) — `raw` được train trên chính 5% ảnh test, `clean` thì không. *Kiểm:* đánh giá lại cả hai model trên test **bỏ 5 ảnh đó** (95 ảnh); nếu khoảng cách thu hẹp thì một phần lợi thế của raw là giả.
2. **`raw` có nhiều ảnh/bước cập nhật hơn.** 224 vs 202 ảnh với cùng 20 epoch → raw có thêm ~11% bước gradient; 12 ảnh trùng (8 trùng byte + 4 gần trùng) còn đóng vai augmentation. Với model nano train ngắn, số bước có thể quan trọng hơn vài chục box sai. *Kiểm:* train `clean` với số epoch quy đổi cùng số iteration (≈ 22 epoch), hoặc train `raw` đã bỏ trùng.
3. **`clean` chưa thật sự sạch và có thể "sạch khác kiểu" test.** Clean là bản Hold: 38/202 ảnh còn cảnh báo chưa duyệt (20 LOOSE_BOX, 21 FALSE_POS, 13 MISSING trong `07_error_list_v3`). Số box truck tăng 32 → 41 sau người duyệt (car 122 → 101): lớp truck/car được gán lại, model nano với 20 epoch chưa kịp học ranh giới car/truck mới. *Kiểm:* xem AP truck theo seed khi thêm seed, và confusion matrix car↔truck trên test.
4. **Test nhỏ.** 100 ảnh, chỉ 24 truck và 27 bus: một vài box đổi đúng/sai là AP lớp đó dao động 0.05–0.10. *Kiểm:* bootstrap trên ảnh test để có khoảng tin cậy cho mAP.

**Kết luận trung thực:** với 2 seed, **chưa kết luận được** clean tốt hơn hay kém hơn raw về mAP50: chênh −0.025 nằm trong nhiễu giữa seed của clean. Không có bằng chứng làm sạch giúp tăng mAP ở thí nghiệm này, và điểm của raw nhiều khả năng bị thổi phồng bởi 5 ảnh rò rỉ test. **Việc tiếp theo:** (1) ≥ 5 seed mỗi biến thể; (2) đánh giá trên test bỏ 5 ảnh rò rỉ; (3) duyệt thêm 38 ảnh còn cảnh báo để clean đạt Release, rồi train lại; (4) thêm biến thể `oracle` (nhãn người) làm chặn trên để biết khoảng cách còn lại do nhãn.

## 6. Quyết định và ghi chú AI
**(a) Quyết định: HOLD** — không phát hành `clean_v1`. Khớp `08_summary.json`: `n_errors=0`, `n_warn_images=38`, `n_images=202`, `warn_ratio=0.1881 ≥ 0.10`. Điều kiện để thành **Release**: duyệt thêm ít nhất **18** trong 38 ảnh còn cảnh báo (để còn ≤ 20/202 < 10 %), ưu tiên theo thứ tự `05_review_queue.csv` từ ảnh 81 (img_0210) trở đi — tức một vòng duyệt thứ hai, **không** phải nâng `conf` hay sửa ngưỡng gate. Nếu vòng duyệt sau làm phát sinh lỗi bắt buộc mới (vd. người xoá file nhãn), pipeline sẽ Rework và không xuất.

**(b) Dùng AI:** có, dùng Claude Code (trợ lý lập trình) để viết 4 module và check thưởng.
- *Prompt chính:* "Viết `run(ds, cfg)` cho `pipeline/checks/<tên>.py` theo đúng docstring: đầu vào Dataset YOLO + cfg, đầu ra `list[Issue]` với các mã/severity trong bảng; đọc ngưỡng từ `cfg`, không viết cứng; dòng hỏng không làm script chết; giữ số dòng gốc kể cả dòng trống; không đọc `data/test`, `MANIFEST`, `review_reference`; chỉ sửa `ds`, không đụng `data/raw`."
- *Cách kiểm:* chạy `pytest` từng file rồi toàn bộ (85/85 xanh, gồm 6 test check thưởng); tự thử thêm 3 ca ngoài test (một dòng dính `BOX_OUT_OF_IMAGE`+`DUP_BOX`, dòng trống ở giữa, ảnh có nhiều dự đoán trùng nhau); đối chiếu `make calibrate` với `MANIFEST.csv` (lỗi cú pháp 100 % P/R); mở `viz_labels.py` xem các ảnh bị cờ và các cặp ảnh bị cho là trùng.
- *Một lần AI sai:* bản đầu của `gate` thêm dòng lý do thứ hai cho cả Hold, lặp lại đúng con số tỉ lệ cảnh báo — báo cáo bị thừa; sửa lại chỉ thêm dòng tỉ lệ khi Rework. Bài học thứ hai: sweep trên raw cho thấy chỉ `conf=0,8` ra Release — một gợi ý "tối ưu" dễ dãi; tôi không chọn vì calib cho thấy MISSING recall rơi còn 0,75 (§3).

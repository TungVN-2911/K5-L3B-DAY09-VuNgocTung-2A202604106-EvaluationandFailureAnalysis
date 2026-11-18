# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5` (backend REPLAY: verdict của judge lưu sẵn trong CSV, không cần key).
Lớp dương = `FAIL` (việc của judge là *tìm* lỗi). Ngưỡng tối thiểu (FLOORS): κ ≥ 0.6, P ≥ 0.8, R ≥ 0.7. Nếu κ không xác định thì tính là FAIL.

| Tiêu chí | n | κ | Precision | Recall | Ma trận (tp/fp/fn/tn) | Tỉ lệ FAIL quan sát → hiệu chỉnh RG | Đạt FLOORS? | Quyết định |
|---|---|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | 24 / 4 / 6 / 66 | 0.28 → 0.30 | **PASS** (exit 0) | **dùng**, chỉ để báo (non-blocking) |
| helpful | 100 | 0.375 | 1.000 | 0.300 | 9 / 0 / 21 / 70 | 0.09 → 0.30 | **FAIL** (κ, R dưới sàn; exit 1) | **loại**, không dùng làm gate |

## Audit thủ công ≥5 case

### tone_ok (10 bất đồng: 6 FN, 4 FP)
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / hành động sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha…" | PASS | FAIL | **Người** | Judge nhầm suồng sã là thân thiện. Rubric thêm: *xưng hô phải là "LogiX" + "anh/chị"; xưng "em", "bạn" hoặc dùng tiểu từ "nha/nhé" ⇒ FAIL*, kèm 1 ví dụ âm. |
| 2 | H-017 "Dạ, bạn ơi LogiX đã hoàn…" | PASS | FAIL | **Người** | Cùng lỗi xưng hô với #1, quy tắc trên bao luôn. |
| 3 | H-029 "Dạ, vui lòng chờ… không cần nhắn thêm." | PASS | FAIL | **Người** | Judge chỉ bám vào từ lịch sự ở đầu câu. Rubric: *đánh giá cả câu; câu mệnh lệnh hoặc chặn khách liên hệ ⇒ FAIL dù mở đầu bằng "Dạ"*. |
| 4 | H-042 "Dạ, đơn O-808 đã hoàn 120.000đ…" | FAIL | PASS | **Người** | Judge phạt vì thiếu lời xin lỗi. Rubric: *không bắt buộc xin lỗi khi reply báo kết quả tích cực; ngắn mà đủ ý vẫn PASS*. |
| 5 | H-051 "…đã refund 90.000đ…" | FAIL | PASS | **Người** | Judge phạt vì có từ tiếng Anh. Rubric thêm *whitelist thuật ngữ CS LogiX cho phép (refund, voucher, COD…)*. |
| 6 | H-063 "…và sẽ hoàn thêm cho anh/chị ạ." | PASS | FAIL | **Người**, nhưng đây không phải lỗi tone | Hứa hẹn ngoài kết quả hệ thống là lỗi **nội dung**, không phải giọng điệu. Tách ra khỏi rubric tone, giao cho grader code (so reply với ledger, họ FM-08). |
| 7 | H-070 "…ạ 😂😂" | PASS | FAIL | **Người** | Rubric: *emoji cười trong ngữ cảnh khiếu nại ⇒ FAIL*. |
| 8 | H-081 "…chưa đủ điều kiện hoàn theo chính sách hiện hành ạ." | FAIL | PASS | **Judge** | Nhãn người sai (đọc nhầm ticket). **Sửa nhãn người** trong bản CSV kế tiếp và có người thứ hai kiểm lại. Sau khi sửa nhãn, tp=25, fn=6, fp=3: P và κ đều tăng. |
| 9 | H-088 "Dạ, dạ, LogiX…" | FAIL | PASS | **Mơ hồ**, nghiêng về người | Lặp từ do gõ phím là lỗi chính tả nhẹ, không phải giọng điệu. Rubric: *lỗi gõ đơn lẻ không làm FAIL tone*. |
| 10 | H-094 "Da, LogiX da hoan… xin loi…" (mất dấu) | PASS | FAIL | **Người** | Rubric: *tiếng Việt không dấu hoặc dịch máy ⇒ FAIL*. |

### helpful (21 bất đồng, **toàn bộ là FN**: judge cho PASS, người cho FAIL)
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / hành động |
|---|---|---|---|---|---|
| 1 | HL-015 "Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ." (ledger 40.000đ) | PASS | FAIL | **Người** | Judge không đọc ledger nên không thể biết số tiền sai. Đây là FM-08, phải chấm bằng **code**. |
| 2 | HL-016 xin lỗi 2 lần + "đã hoàn 55.000đ" (ledger 35.000đ) | PASS | FAIL | **Người** | Thiên vị độ dài/lịch sự: lời xin lỗi lặp lại che mất số tiền sai. |
| 3 | HL-043 "rất tiếc… đã hoàn 35.000đ…" (ledger 20.000đ) | PASS | FAIL | **Người** | Cùng mẫu với #2. |
| 4 | HL-090 xin lỗi + "đã hoàn 155.000đ" (ledger 120.000đ) | PASS | FAIL | **Người** | Cùng mẫu với #2. |
| 5 | HL-047 "Ok bạn, đơn O-515 xử lý rồi nhé." | PASS | FAIL | **Người** | Reply không nói kết quả, số tiền hay thời hạn. Rubric helpful thêm: *phải nêu trạng thái + số tiền (nếu có) + bước tiếp theo*. |
| 6 | HL-087 "Dạ, LogiX đã hoàn 60.000đ cho đơn O-202 ạ." (ledger 90.000đ) | PASS | FAIL | **Người** | Reply ngắn mà vẫn sai tiền, nên lỗi ở đây không chỉ do độ dài: judge hoàn toàn không kiểm số tiền. |

Tổng hợp 21 FN: **18 ca nói sai số tiền so với ledger** (13 ca có độn lời xin lỗi dài, 5 ca ngắn) và **3 ca trả lời mơ hồ** (HL-047/091/097). Judge không có FP nào (P = 1.0): khi judge nói FAIL thì đúng, nhưng judge bỏ sót 70% lỗi thật.

## Kết luận
- **Loại `helpful` khỏi gate.** Recall chỉ 0.30 (bỏ sót 21/30 lỗi) và κ = 0.375 < 0.6. Gate dùng judge này sẽ cho merge phần lớn regression. Lỗi bị bỏ sót lại chính là **sai số tiền** (FM-08), loại lỗi mà quy tắc bắt buộc chấm bằng **code**: so số tiền trong reply với `snapshot.refund_vnd` của ledger. P = 1.0 không cứu được judge vì gate cần bắt lỗi chứ không chỉ "không báo nhầm". Hiệu chỉnh Rogan-Gladen kéo tỉ lệ lỗi tổng 0.09 về 0.30, nhưng đó chỉ là ước lượng **tỉ lệ ở cấp tập dữ liệu**. Cách này không cho biết item nào lỗi, và với sens = 0.3 thì ước lượng rất nhạy với sai số của sens/spec.
- **Giữ `tone_ok`** vì đạt cả 3 sàn. Tỉ lệ FAIL hiệu chỉnh là 0.30 so với 0.28 quan sát được: judge hơi bỏ sót lỗi tone. Tuy vậy chỉ dùng tone để **báo** chứ không để blocking, vì tone không liên quan đến tiền hay approval. Sau khi áp các sửa rubric ở trên (xưng hô, mệnh lệnh, emoji, không dấu, whitelist thuật ngữ, không bắt buộc xin lỗi) cần calibrate lại trên nhãn mới.
- **Sửa dữ liệu:** H-081 là nhãn người sai, cần sửa nhãn và cho người thứ hai kiểm lại. H-063 là lỗi nội dung, chuyển sang grader code thay vì rubric tone.
- **Rủi ro còn lại:** judge chỉ được kiểm trên dữ liệu replay đã công khai (100 dòng mỗi tiêu chí, cũng chính là dữ liệu dùng để sửa rubric), nên các số trên là in-sample. Cần một bộ nhãn người mới làm held-out thật trước khi tin κ. Khi dùng LLM judge thật, verdict còn dao động giữa các lần chạy, nên phải calibrate lại.

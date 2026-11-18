# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `<shape> <claim>@<seed>`, run ID trong report |
| Triệu chứng | Grader nào fail; reply nói gì so với ledger ghi gì |
| Bước sai đầu tiên | Số thứ tự event + kind + trích payload (≤1 dòng) |
| Vì sao là bước *đầu tiên* | Các bước trước đó đúng ra sao (dẫn số event) |
| Failure mode | Mã FM-xx trong `docs/failure_taxonomy.md` |
| Đối chứng | Cùng claim@seed trên shape `fixed`: bước đó khác thế nào |
| Regression test | Tên test + grader/assert nào bắt được; đã thấy fail trên variant lỗi và pass trên `fixed` chưa |
| Chưa chắc chắn | Điều trace không chứng minh được |

## Case đã điền: baseline `swarm` C-002@55 (FM-03)

```bash
cd src
python -m lab9.trace_case --shape swarm --claim C-002 --seed 55
python -m lab9.trace_case --shape fixed --claim C-002 --seed 55   # đối chứng
```

| Trường | Nội dung |
|---|---|
| Trial | `swarm C-002@55`. Đây là trial lỗi **duy nhất** của baseline (1/70), nằm trong report baseline `E-swarm-20261118-9557` (eval set `9557997a5306`) |
| Triệu chứng | Grader Lab 8 FAIL `status resolved != denied`. `refund_amount_correct` = False: ledger 20.000đ (1 dòng), nhãn 0đ / `denied`. `db_fact_kept` = False. Shape `swarm` của Lab 8 không có event `reply`, nên không có gì để so reply với ledger; sai lệch chỉ lộ ra ở ledger. |
| Bước sai đầu tiên | **Event 3, `model_override`**, payload `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Ev1 `handoff` đúng (task `check_applicable_policy`, `facts: {}`, không nhồi dữ liệu ticket). Ev2 `investigator` đọc đúng DB: O-202 `status: delivered`, `delay_days: 2`. Đến ev3, agent lấy "trễ 5 ngày" trong ticket đè lên số 2 của DB. Mọi bước sau đều đúng *theo* con số sai đó: ev4 `quote` áp `SHIP-LATE-03` (≥ 3 ngày) ra 20.000đ, và host ghi đúng số được đề xuất. |
| Failure mode | **FM-03** ticket_trust (layer model/prompt) |
| Đối chứng | `fixed C-002@55` không có event `model_override`. Ev3 `quote` ra `amount_vnd: 0`, `reason: no_entitlement`; ev4 `reply` "chưa đủ điều kiện hoàn". Ledger 0đ, status `denied`, grader Lab 8 PASS. Hai trace giống nhau tới ev2 và chỉ tách ra ở ev3. |
| Regression test | `src/tests/test_lab9_trace_case.py`. `test_lab9_trace_case_swarm_c002_seed55_is_caught` assert `model_override {"delay_days": 5}` đứng ngay sau `investigator`, và `db_fact_kept`, `refund_amount_correct`, `pass_rate` đều fail. `test_lab9_trace_case_fixed_c002_seed55_passes` assert không có override, ledger 0 và mọi grader đều pass. Đã chạy: lỗi bị bắt trên `swarm` và qua trên `fixed`. Item E-002 trong eval set ghi `provenance.from_trace` trỏ tới trial này. |
| Chưa chắc chắn | (1) Trace chỉ cho thấy override xảy ra, không cho biết *vì sao*: điều kiện `seed % 5 == 0` đọc được từ code, không đọc được từ trace. Với LLM thật, điều kiện kích hoạt sẽ không cố định như vậy. (2) Shape `swarm` không ghi event `reply`, nên không biết khách được báo gì. (3) Biến thể `quiet_override` gây cùng lỗi mà **không** ghi `model_override`. Khi đó bước sai đầu tiên không nhìn thấy được trên trace và `db_fact_kept` không bắt được, chỉ còn grader outcome (`refund_amount_correct`, `pass_rate`). |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.

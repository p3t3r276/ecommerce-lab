# Guide kit: hướng dẫn sử dụng

Kit này biến hai plan của lab (Implementation plan v3 và Detail Plan) thành **hướng dẫn theo từng tuần** để bạn tự code theo. Agent không viết vào repo của bạn. Nó thiết kế contract cho từng bước, dựng một **repo tham chiếu** chạy thật (build và test xanh), rồi viết hướng dẫn với snippet lấy từ repo tham chiếu đó.

## 1. Thành phần

| Thành phần | Model | Việc |
|---|---|---|
| `step-designer` | Opus | Thiết kế một bước: quy ước, contract (event, API, interface, mã lỗi, bảng trạng thái), câu hỏi kiến trúc cho bạn, phân loại từng buổi |
| `reference-builder` | Sonnet | Dựng một tuần trong `reference/`: mỗi buổi một commit `bNNN:`, kiểm tra "Xong khi", ghi `build-log/wNN.md` |
| `guide-writer` | Sonnet | Viết `guides/sN/wNN.md` (tiếng Việt) từ Detail Plan, design, build log và commit của reference |
| `code-reviewer` | Opus | Review code bạn tự viết, ghi `reviews/wNN.md` (tiếng Việt) |

| Lệnh | Việc |
|---|---|
| `/kit-status` | Đang ở đâu, bước tiếp theo là gì |
| `/design-step SN` | Thiết kế bước N |
| `/decide SN` | Ghi lựa chọn của bạn vào `decisions.md`, duyệt design |
| `/build-reference [k]` | Dựng k tuần tiếp theo của reference (mặc định 1), tuần tự |
| `/write-guides` | Viết hướng dẫn cho các tuần đã dựng, tối đa 3 song song |
| `/review-my-code wNN` | Review code của bạn cho tuần NN |

Script (bạn tự chạy):
- `python3 tools/split-plans.py`: tách plan thành phần nhỏ. Chạy lại mỗi khi sửa plan.
- `python3 tools/kit-status.py`: bảng trạng thái.
- `bash tools/sync-to-shoplab.sh SN`: copy file dùng chung (contract, interface, seed, realm, test dùng chung) từ reference sang repo của bạn.
- `bash tools/export-guide.sh SN`: gộp các guide tuần của bước cùng phần contract (endpoint, event, mã lỗi) thành `docs/guides/ShopLab-SN.md` trong repo của bạn, đúng vị trí v3 quy định. Chạy lại mỗi khi có guide mới.

Agent bị chặn chạy hai script ghi vào repo của bạn; chỉ bạn chạy.

**Ngôn ngữ:** file cho agent (`CLAUDE.md`, agent, lệnh, `decisions.md`, `design/`, `build-log/`, `plans/ISSUES.md`) viết bằng tiếng Anh. Hướng dẫn, review và báo cáo của lệnh cho bạn bằng tiếng Việt.

## 2. Kit dùng hai plan thế nào

**v3 trả lời "xây gì và vì sao". Detail Plan trả lời "làm theo thứ tự nào, mỗi buổi xong khi nào".** Cả hai chỉ đọc. Mọi thay đổi ghi vào `decisions.md`, file này đứng trên cả hai plan.

`split-plans.py` tách hai file (khoảng 200 KB) thành phần nhỏ để mỗi agent chỉ đọc đúng phần cần:

```
plans/v3/steps/s0.md ... s8.md       bullet + gate từng bước
plans/v3/domain/*.md                 domain model theo context, events.md
plans/v3/0N-*.md                     stack, cấu trúc solution, lệnh, flash sale, data mẫu, kiểm thử
plans/detail/sN/wNN.md               88 file tuần: mục tiêu tuần + bảng 4 buổi
plans/detail/testing/*.md            hướng dẫn kiểm thử theo loại
plans/index.json, plans/sessions.tsv bước → tuần → buổi (352 buổi)
```

| Agent | Đọc từ v3 | Đọc từ Detail Plan |
|---|---|---|
| `step-designer` | `steps/sN.md`, domain liên quan, `events.md`, các mục cần thiết | `sN/_step.md`, mọi `sN/wNN.md` của bước, phần testing liên quan |
| `reference-builder` | Chỉ khi một buổi cần | `sN/wNN.md`: làm theo đúng thứ tự buổi, chạy cột "Lệnh", kiểm cột "Xong khi" |
| `guide-writer` | Đoạn "vì sao" liên quan | `sN/wNN.md` làm khung hướng dẫn |
| `code-reviewer` | Gate, test bắt buộc | "Xong khi" của tuần |

Cột của Detail Plan đi vào hướng dẫn như sau: **STT, Ngày** → heading buổi; **Việc** → Mục tiêu (và đề bài nếu là buổi `core`); **File** → danh sách file; **Lệnh** → khối lệnh đã chạy thật; **Xong khi** → Kiểm chứng. Hai mục **Thử đổi số** và **Lỗi thường gặp** lấy từ build log, tức là từ việc chạy thật.

## 3. Cài đặt (một lần)

1. Giải nén kit thành thư mục riêng, **cạnh** repo của bạn:
   ```
   ~/lab/
     guide-kit/     ← mở Claude Code ở đây
     shoplab/       ← repo bạn tự code
   ```
2. `cp kit.env.example kit.env`, sửa `SHOPLAB_PATH` nếu cần.
3. `cd guide-kit && git init && git add -A && git commit -m "kit"`. Kit nên có git riêng để theo dõi design, decisions và guide. `reference/` đã nằm trong `.gitignore` vì nó có git riêng.
4. Máy cần: .NET 10 SDK, Docker đang chạy (Testcontainers), Node 22, Aspire CLI. Đây cũng là buổi 1 của plan.
5. Mở Claude Code tại `guide-kit/`. Kiểm tra `/agents` có 4 agent, gõ `/` thấy 6 lệnh.
6. Để `code-reviewer` đọc được repo của bạn: chạy Claude Code với `--add-dir ../shoplab`, hoặc gõ `/add-dir ../shoplab` trong phiên.
7. Hai plan (xuất từ hai doc trên claude.ai lúc 03/11/2026 23:26) đã nằm trong `plans/source/` và đã được tách sẵn. Khi bạn sửa doc, xem `plans/source/README.md` để xuất lại và tách lại.

## 4. Vòng lặp mỗi bước

```
/design-step S0        Opus đọc plan + ISSUES → design/s0.md (draft)
   ↓ bạn đọc design/s0.md, tick lựa chọn (hoặc trả lời trong chat)
/decide S0             ghi decisions.md, shared/s0.txt, duyệt design
/clear
/build-reference 2     dựng w01, w02 (tuần tự, mỗi tuần một subagent)
/clear
/write-guides          viết guides/s0/w01.md, w02.md (song song)
   ↓ bạn code theo guide trong shoplab/
bash tools/sync-to-shoplab.sh S0     (đầu bước: lấy contract, seed...)
/review-my-code w01
   ↓ lặp build → guide → code → review cho các tuần còn lại
   ↓ hết bước: bạn viết notes/s0.md (mẫu ở notes/_TEMPLATE.md)
/design-step S1        đọc cả notes/s0.md
```

**Nhịp đề xuất:** dựng reference và viết guide trước bạn 1–2 tuần. Ví dụ cuối tuần chạy `/build-reference 2` và `/write-guides` cho hai tuần sau. Agent không được đi trước quá một bước: `/design-step SN` yêu cầu reference đã có tag `s(N-1)-done`. Nhờ vậy phản hồi của bạn trong `notes/` luôn kịp ảnh hưởng bước sau.

**Khi bạn muốn đi khác reference:** cứ code theo cách của bạn. Ghi vào `notes/sN.md`, đánh dấu có muốn reference cập nhật theo không. Contract (event, interface, route) thì nên giữ giống, vì các tuần sau dựa vào nó. Nếu muốn đổi contract, ghi rõ trong notes để bước sau thiết kế lại.

## 5. Một buổi hướng dẫn trông thế nào

Mỗi buổi có: Mục tiêu · Vì sao · File · Code · Kiểm chứng · Thử đổi số · Lỗi thường gặp. Phần Code tùy loại buổi:

| Loại | Nội dung |
|---|---|
| `scaffold` | Snippet trực tiếp: AppHost, csproj, CRUD, cấu hình |
| `core` | **Tự làm trước** (đề bài, gợi ý, chữ ký contract), lời giải ẩn trong `<details>` |
| `test` | Snippet test, đôi khi là bài tập |
| `manual` | Các bước bấm (Keycloak console…) và file kết quả |
| `gate` | Checklist gate và cách kiểm từng mục |

Phần **Thử đổi số** gắn nhãn **đã chạy thử** (builder chạy thật, có kết quả) hoặc **dự đoán**. Bạn chạy lại để so.

## 6. Khi bị ngắt hoặc hết token

- `/kit-status` cho biết bạn đang ở đâu và nên chạy gì tiếp.
- Builder commit sau mỗi buổi và ghi log ngay, nên bị ngắt thì chỉ mất buổi đang làm. Nếu `reference/` có thay đổi chưa commit, xem `git -C reference status` rồi `git -C reference stash` hoặc commit tay trước khi chạy lại.
- Build log `status: blocked` nghĩa là thiếu quyết định. Đọc lý do trong log, thêm quyết định (sửa design rồi `/decide`, hoặc thêm entry vào `decisions.md`), rồi chạy lại `/build-reference`.
- `/clear` giữa các lệnh lớn. Mọi trạng thái nằm trong file nên không cần lịch sử phiên.

## 7. Chi phí

- Opus chỉ chạy ở `/design-step` (9 lần cho cả lab) và `/review-my-code`. Phần nặng (dựng reference, viết guide) chạy Sonnet.
- Reference tốn nhất: mỗi tuần một subagent chạy build, test, Docker. Nếu cần tiết kiệm, dựng 1 tuần mỗi lần.
- Review không bắt buộc mỗi tuần. Ưu tiên tuần có buổi `core`.

## 8. Tình trạng hai plan

Hai plan đã qua nhiều vòng rà soát trong ngày 03/11/2026, và cả 92 điểm bất cập tìm được đã được sửa ngay trong doc (danh sách đầy đủ nằm trong `plan-issues.xlsx` của bạn, không nằm trong kit). Tôi đã kiểm lại 12 ca tính giá theo quy tắc engine, cả 12 khớp từng đồng.

`plans/ISSUES.md` chỉ còn một mục mở theo thiết kế của plan: payload các event "dự kiến" của S6 và S7 (`FlashReservationCreated`, `FlashReservationReleased`, `PosSaleRecorded`, `PosRefundRecorded`) sẽ được chốt khi chạy `/design-step S6` và `/design-step S7`. File này cũng liệt kê vài chỗ trông giống lỗi nhưng là chủ ý, để agent không "sửa" nhầm. Nếu designer tìm ra mâu thuẫn mới, nó sẽ thêm dòng từ I-12 trở đi.

## 9. Những điều chưa kiểm chứng

Tôi đã chạy thử `split-plans.py` trên hai plan thật (bản xuất từ doc lúc 03/11 23:26: 9 bước, 88 tuần, 352 buổi, không cảnh báo), cùng `kit-status.py`, `sync-to-shoplab.sh` và `export-guide.sh` trên dữ liệu giả lập. Tôi chưa chạy các agent và lệnh trong Claude Code thật. Lần đầu hãy kiểm tra:

- `/agents` hiện đủ 4 agent và dòng `model:` được áp dụng.
- Quy tắc trong `.claude/settings.json` không chặn nhầm. Khi Claude Code hỏi quyền cho lệnh hợp lý (ví dụ `aspire run`, `docker compose`), cho phép và thêm vào `allow`.
- `reference-builder` chạy được Testcontainers (Docker phải chạy) và `aspire run` có `timeout`.
- Tên API của Aspire 13.x, Nx/Angular, `RabbitMQ.Client` 7: designer liệt kê ở mục "Version checks", builder kiểm khi cài.

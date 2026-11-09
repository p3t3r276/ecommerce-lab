# plans/source

Hai file nguồn của kit, xuất từ hai doc trên claude.ai:

| File | Doc |
|---|---|
| `implement-plan-v3.md` | [Lab: E-commerce microservices — implement plan v3](https://claude.ai/artifact/Hcrxy2HoKaMf1VMkVJqHAx) |
| `detail-plan.md` | [Lab: E-commerce microservices — Detail Plan](https://claude.ai/artifact/BaTh8JtRC1Z79V4ixSHowu) |

Bản hiện tại xuất lúc 03/11/2026 23:26 (v3 rev 105, Detail rev 51). Hai sơ đồ nhúng trong doc không xuất ra Markdown được, nên trong file chỉ còn dòng giữ chỗ; agent không cần chúng.

## Khi bạn sửa doc

1. Mở doc, xuất ra Markdown (menu xuất của doc), lưu đè đúng tên file ở trên. Hoặc nhờ Claude trong chat xuất giúp.
2. Chạy `python3 tools/split-plans.py`. Script báo số bước, tuần, buổi và cảnh báo nếu đánh số lệch.
3. Nếu thay đổi chạm tới bước đã thiết kế (`design/sN.md` đã `approved`), ghi một dòng vào `plans/ISSUES.md` để `step-designer` xử lý ở lần thiết kế lại, hoặc thêm thẳng một entry vào `decisions.md`.

Agent không được sửa thư mục này (bị chặn trong `.claude/settings.json`).

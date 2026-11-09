---
week: wNN
step: SN
sessions: NNN-NNN
reference_tag: wNN
status: done
---

# Tuần NN · <mục tiêu tuần, lấy từ Detail Plan>

> **Bước SN** · Buổi NNN–NNN · Reference: tag `wNN`
> Trước khi bắt đầu: `bash tools/sync-to-shoplab.sh SN` (nếu là tuần đầu của bước) để có contract, interface và seed giống reference.

## Bức tranh của tuần
2–4 câu: tuần này thêm mảnh nào vào hệ thống, nó nối với tuần trước và tuần sau ra sao.

---

## Buổi NNN · T3 dd/mm · <việc>
**Loại:** scaffold | core | test | manual | gate

### Mục tiêu
### Vì sao
(Nếu khác Detail Plan: "Khác Detail Plan: … (D-xxx)")

### File
- `src/...`

### Code
<!-- scaffold/test: snippet trực tiếp -->
```csharp
// src/.../File.cs
...
```

<!-- core: đề bài trước, lời giải ẩn -->
#### Tự làm trước
- Đề bài: ...
- Contract phải thỏa:
```csharp
public interface IOutbox { ... }
```
- Gợi ý:
  1. ...
  2. ...

<details>
<summary>Lời giải tham khảo</summary>

```csharp
// src/.../File.cs
...
```
</details>

### Kiểm chứng
```bash
dotnet test tests/... --filter ...
```
Kết quả mong đợi: ...

### Thử đổi số
| Thay đổi | Cách làm | Quan sát | Nhãn |
|---|---|---|---|
| ... | ... | ... | đã chạy thử / dự đoán |

### Lỗi thường gặp
- **<thông báo lỗi>**: nguyên nhân → cách sửa.

---

## Cuối tuần
- [ ] Commit theo từng buổi: `git commit -m "bNNN: ..."`
- [ ] Chạy `/review-my-code wNN`
- [ ] Ghi điều muốn giữ khác reference vào `notes/sN.md`

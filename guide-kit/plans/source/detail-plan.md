# Lab: E-commerce microservices — Detail Plan

Oct 29, 2026 · @Khoa

## Kiến trúc tổng

Hệ thống khi xong S8 gồm 3 client, 3 cổng vào, 10 service và một event bus chung; mỗi thành phần mang nhãn bước mà nó xuất hiện, nên đọc sơ đồ cũng thấy thứ tự dựng.

&#91;embedded content: kiến trúc đích · 4 lớp, 10 service, nhãn = bước dựng\]

Màn hình Admin luôn gọi qua Gateway.Web; từ S5 riêng dashboard (`/api/admin/dashboard/**`) được Gateway.Web chuyển sang Bff.Admin. Chỉ Catalog, Ordering và Bff.Admin có kết nối MongoDB, mỗi bên một database riêng.

| STT | Thành phần | Sở hữu dữ liệu | Gọi đồng bộ (REST) | Phát event | Nghe event | Bước |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Gateway.Web | Không (rate limit S6 chạy trong bộ nhớ bằng ASP.NET Core RateLimiting) | Proxy tới mọi service, chặn `/internal`, kiểm JWT; S5: `/api/admin/dashboard` → Bff.Admin; S6: flash token | — | — | S0 |
| 2 | Catalog.Api | `catalogdb`, Mongo `catalog_read` (S5) | Phục vụ storefront/admin; `/internal/variants` cho Cart, Ordering | `ProductChanged` | `StockChanged` (`InStock`), `ProductChanged` (read model, S5) | S0–S1 |
| 3 | Customer.Api | `customerdb` | `/internal/customers` (trạng thái, địa chỉ) cho Ordering; S7: delta cho Bff.Pos | — | `OrderPaid` (cộng điểm, mọi kênh kể cả POS), PosRefundRecorded (trừ điểm, S7 nếu làm) | S2 |
| 4 | Cart.Api | Redis `cart:*` | Gọi Catalog (giá), Discount (báo giá, S4); `/internal/carts` cho Ordering | — | `OrderPaid` (chỉ xoá giỏ kênh `Online`) | S2 |
| 5 | Inventory.Api | `inventorydb` | `/internal/reservations` (S2, đồng bộ); S6: cấp `FlashAllocation` cho FlashSale | `StockChanged`, `StockReserved` / `StockReservationFailed` (S3) | `OrderCreated` (reserve), `OrderPaid` (commit reservation đang có của `OrderId`, không có thì bỏ qua), `OrderCancelled` (release), `PosSaleRecorded` (trừ tại `LocationId`, S7), PosRefundRecorded (movement Return, S7 nếu làm) | S2 |
| 6 | Ordering.Api | `orderingdb`, Mongo `ordering_read` (S5) | Gọi Cart, Catalog, Customer, Discount (`/internal/quote`); `/internal/orders/finished` cho Bff.Admin | `OrderCreated`, `OrderPaid`, `OrderCancelled` (bên duy nhất phát), `OrderStatusChanged`, `PaymentRequested`, `PaymentRefundRequested` | `StockReserved`/`Failed`, `PaymentSucceeded`/`Failed`, `CouponRedeemed`/`Failed` (saga); `OrderStatusChanged` (read model); `FlashReservationCreated` (OrderWorker), `FlashReservationReleased` (S6); `PosSaleRecorded` (S7) | S2 |
| 7 | Payment.Api | `paymentdb` | S2: `/internal/payments` (đồng bộ) | `PaymentSucceeded` / `PaymentFailed` | `PaymentRequested`, `PaymentRefundRequested` (đường hoàn tiền duy nhất; không nghe `OrderCancelled`) | S2 |
| 8 | Notification.Worker | Không (template trong code) | SMTP tới Mailpit | — | `OrderPaid` (bỏ qua kênh `Pos`) | S3 |
| 9 | Discount.Api | `discountdb` + Redis cache | `/internal/quote` cho Cart, Ordering; admin khuyến mãi; S7: delta cho Bff.Pos | `CouponRedeemed` / `CouponRedemptionFailed` | `OrderCreated` (trừ lượt), `OrderCancelled` (hoàn lượt / bia mộ) | S4 |
| 10 | Bff.Admin | Mongo `admin_read` | Phục vụ dashboard; gọi Ordering `/internal/orders/finished` khi rebuild | — | `OrderPaid` (doanh thu, top SKU), `OrderCancelled` (đếm đơn huỷ, không trừ doanh thu), `StockChanged` (tồn thấp), `FlashReservationReleased` (S6), `PosRefundRecorded` (trừ doanh thu, S7 nếu làm) | S5 |
| 11 | FlashSale.Api | `flashsaledb` + Redis `fs:*` | Lua trên Redis, SignalR; gọi Inventory cấp hàng lúc T − 1 phút | `FlashReservationCreated`, `FlashReservationReleased` | `OrderCreated`, `OrderPaid`, `OrderCancelled` (theo `ReservationId`; chỉ lo quota, không tạo/huỷ đơn) | S6 |
| 12 | Store.Api | `storedb` | REST ca, tiền mặt; nhận giao dịch từ Bff.Pos | `PosSaleRecorded` (có `ClientTxnId`, `LocationId`); PosRefundRecorded (nếu làm hoàn tiền) | — | S7 |
| 13 | Bff.Pos | Không | `sync/pull` gộp delta từ Catalog, Discount, Customer; `sync/push` tới Store | — | — (delta lấy qua REST `changes?since=`, không nghe event) | S7 |

Bảng trên chỉ tóm tắt giao tiếp chính của từng service, không đầy đủ. Danh sách event, payload, bên phát và bên nghe chuẩn nằm ở **bảng event trong Implement plan v3** (và `src/Contracts/` với event đã có trong repo); khi hai nơi lệch nhau thì theo bảng đó.

## Cách dùng plan

Plan xếp theo mức ước tính cao của v3: 88 tuần làm việc, 4 buổi mỗi tuần, tổng 352 buổi, từ **02/11/2026** đến **23/07/2028**. Mỗi buổi là một dòng trong bảng của tuần; cột STT là số thứ tự buổi trên toàn lab, nên lúc nào bạn cũng biết mình đang ở buổi thứ mấy trên 352.

**Lịch một tuần (11 giờ)**

| STT | Buổi | Thời lượng | Hợp với loại việc |
| --- | --- | --- | --- |
| 1 | Thứ Ba tối | 2 giờ | Việc nhỏ, rõ đầu ra: tạo project, entity, endpoint, viết test theo mẫu |
| 2 | Thứ Năm tối | 2 giờ | Như trên, hoặc nối tiếp việc dở của thứ Ba |
| 3 | Thứ Bảy | 3,5 giờ | Việc cần tập trung lâu: saga, Lua, sync offline, debug |
| 4 | Chủ nhật | 3,5 giờ | Test, chạy k6, viết ghi chú; tuần cuối mỗi bước dùng làm gate và dự phòng |

**Quy ước trong bảng**

- Lệnh chạy từ thư mục gốc `shoplab/`, trừ khi ghi `cd` khác. `<svc>` là tên service đang làm.
- "Xong khi" là điều kiện kiểm tra được. Chưa đạt thì buổi đó chưa xong.
- Cuối mỗi buổi commit: `git commit -m "s2: reserve endpoint"`. Mỗi bước một nhánh `step/sN-<tên>`, merge vào `main` khi qua gate, rồi gắn tag `sN-done`.
- Cuối mỗi bước viết `docs/notes/sN.md`: quyết định đã chọn, chỗ đã vấp, chỗ sẽ làm khác. Số đo hiệu năng để ở `docs/benchmarks/`.

**Khi bị trễ**

- Không dồn việc dở sang buổi tối kế tiếp. Dùng buổi Chủ nhật hoặc tuần gate cuối bước để làm bù.
- Trễ quá 2 tuần trong một bước: cắt những việc ghi "có thể cắt", không cắt test và gate.
- Các ngày lễ khác (30/4, 1/5, 2/9) không xếp riêng; dùng buổi dự phòng.

**Tuần nghỉ đã trừ ra khỏi lịch**

| STT | Tuần | Lý do |
| --- | --- | --- |
| 1 | 01/02–07/02/2027 | Tết Đinh Mùi (06/02/2027) |
| 2 | 24/01–30/01/2028 | Tết Mậu Thân (26/01/2028) |

## Hướng dẫn kiểm thử

Lab có 9 loại test. Mỗi loại có chỗ đặt riêng, công cụ riêng và một mẫu để chép. Quy tắc chung: buổi nào viết code thì viết test của code đó ngay trong buổi; gate chỉ chạy lại, không viết test mới.

| STT | Loại | Kiểm cái gì | Công cụ | Đặt ở đâu | Chạy khi nào |
| --- | --- | --- | --- | --- | --- |
| 1 | Unit (domain thuần) | Luật nghiệp vụ trong entity, engine tính giá, chuyển trạng thái | xUnit v3, Shouldly | `tests/<Svc>.Tests/` | Mỗi lần lưu file |
| 2 | Integration với DB thật | EF mapping, query, ràng buộc unique, concurrency | Testcontainers (mỗi test một database mới) | `tests/<Svc>.Tests/` | Trước mỗi commit |
| 3 | API | Endpoint, phân quyền, validation, mã lỗi | `ShopLabApiFactory<ApiMarker>` (TestKit), `TestAuthHandler` | `tests/<Svc>.Tests/` | Trước mỗi commit |
| 4 | Messaging | Outbox, Inbox, retry, DLQ, handler | Testcontainers RabbitMQ; saga test chạy từng bước như consumer host | `tests/BuildingBlocks.Tests/`, `tests/<Svc>.Tests/` | Trước mỗi commit |
| 5 | Luồng nhiều service | Saga checkout, flash sale end-to-end | Saga trên Postgres thật, service khác giả bằng `StubHandler` | `tests/Ordering.Tests/` (S6: `tests/FlashSale.Tests/`) | Cuối mỗi tuần |
| 6 | Kiến trúc | Ranh giới service, phụ thuộc giữa project | NetArchTest, Aspire.Hosting.Testing | `tests/Architecture.Tests/` | Trước mỗi commit |
| 7 | Frontend | Component, store, thư viện TS (pricing) | Jest (`@nx/jest` 21.5, `jest` 30), Angular TestBed | `src/Web/**/*.spec.ts` | Trước mỗi commit |
| 8 | Tải | p95, tỉ lệ lỗi, ngưỡng dưới tải | k6 | `load/` | Cuối bước có ghi baseline |
| 9 | Diễn tập sự cố | Hồi phục khi một thành phần chết | S2–S6: tắt/bật resource trong dashboard Aspire; S8: script `tools/chaos/kill.sh`; mẫu postmortem | `docs/postmortems/` | S2, S3, S6, S8 |

### Cấu hình chung cho mọi project test

Đặt file này ở `tests/Directory.Build.props`. Nó kế thừa file gốc rồi thêm xUnit v3, Shouldly cho mọi project test; `TestKit` đặt `IsTestProject=false` nên chỉ nhận phần extensibility. `TreatWarningsAsErrors` đang tắt cho cả repo tới S8 (S8 bật lại ở file gốc).

```xml
<!-- tests/Directory.Build.props -->
<Project>
  <Import Project="$([MSBuild]::GetPathOfFileAbove('Directory.Build.props', '$(MSBuildThisFileDirectory)../'))" />
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <IsPackable>false</IsPackable>
    <IsTestProject>true</IsTestProject>
  </PropertyGroup>
  <!-- TestKit đặt IsTestProject=false nên bỏ qua nhóm này -->
  <ItemGroup Condition="'$(IsTestProject)' == 'true'">
    <PackageReference Include="Microsoft.NET.Test.Sdk" />
    <PackageReference Include="xunit.v3" />
    <PackageReference Include="xunit.runner.visualstudio" />
  </ItemGroup>
  <ItemGroup Condition="'$(IsTestProject)' != 'true'">
    <PackageReference Include="xunit.v3.extensibility.core" />
  </ItemGroup>
  <ItemGroup>
    <PackageReference Include="Shouldly" />
    <Using Include="Xunit" />
    <Using Include="Shouldly" />
  </ItemGroup>
</Project>
```

Đặt tên test theo mẫu `<Hàm>_<Tình huống>_<Kết quả>`, ví dụ `Reserve_MoreThanAvailable_Throws`. Mỗi test viết theo ba phần Arrange / Act / Assert, cách nhau một dòng trống.

### 1. Unit test

Không có IO: không DB, không HTTP, không đồng hồ thật. Cần thời gian thì truyền `FakeTimeProvider` (package `Microsoft.Extensions.TimeProvider.Testing`).

```csharp
// tests/Inventory.Tests/Domain/StockLevelTests.cs
using Inventory.Api.Domain;

namespace Inventory.Tests.Domain;

public class StockLevelTests
{
    [Fact]
    public void Reserve_MoreThanAvailable_Throws()
    {
        var level = StockLevel.Create("SL-TEE-BASIC-M", Guid.NewGuid());
        level.Receive(5);

        var act = () => level.Reserve(6);

        Should.Throw<InsufficientStockException>(act);
    }

    [Theory]
    [InlineData(10, 3, 7)]
    [InlineData(10, 10, 0)]
    public void Reserve_WithinAvailable_ReducesAvailable(int onHand, int qty, int expected)
    {
        var level = StockLevel.Create("SL-TEE-BASIC-M", Guid.NewGuid());
        level.Receive(onHand);

        level.Reserve(qty);

        level.Available.ShouldBe(expected);
    }
}
```

Với bảng dữ liệu dài (12 case giá), đọc từ JSON thay vì viết `InlineData`:

```csharp
// tests/Discount.Tests/PricingEngineTests.cs (trích)
public static TheoryData<PricingCase> Cases()
{
    var path = Path.Combine(AppContext.BaseDirectory, "seed", "pricing-cases.json");
    var cases = JsonSerializer.Deserialize<List<PricingCase>>(File.ReadAllText(path), Json)!;
    var data = new TheoryData<PricingCase>();
    foreach (var c in cases) data.Add(c);
    return data;
}

[Theory]
[MemberData(nameof(Cases))]
public void Case_matches_expected(PricingCase c)
{
    var result = PricingEngine.Calculate(new PricingInput(
        c.Lines, c.Promotions, c.Coupon is null ? null : new CouponInput(c.Coupon.Code, c.Coupon.Promotion), c.Now, c.Channel));

    result.Total.ShouldBe(c.Expected.Total, c.Id);
    result.Lines.Select(l => l.Discount).ShouldBe(c.Expected.LineDiscounts, c.Id);
    result.Coupon?.ErrorCode.ShouldBe(c.Expected.CouponError, c.Id);
}
```

### 2. Integration test với DB thật

Một container Postgres cho mỗi class test (`IClassFixture<PostgresFixture>` trong `tests/TestKit`), mỗi test gọi `CreateDatabaseAsync()` để có database mới, nên không cần Respawn hay xoá dữ liệu. Không dùng EF InMemory: nó không có `xmin`, không có unique index lọc, không có transaction thật.

```csharp
// tests/TestKit/PostgresFixture.cs
public sealed class PostgresFixture : IAsyncLifetime
{
    private readonly PostgreSqlContainer _container = new PostgreSqlBuilder()
        .WithImage("postgres:17-alpine")
        .Build();

    public string ConnectionString => _container.GetConnectionString();
    public async ValueTask InitializeAsync() => await _container.StartAsync();
    public async ValueTask DisposeAsync() => await _container.DisposeAsync();

    /// <summary>Tạo database mới tên ngẫu nhiên, trả về connection string trỏ vào nó.</summary>
    public async Task<string> CreateDatabaseAsync(string prefix = "test")
    {
        var name = $"{prefix}_{Guid.NewGuid():N}"[..Math.Min(40, prefix.Length + 33)];
        await using var conn = new NpgsqlConnection(ConnectionString);
        await conn.OpenAsync();
        await using var cmd = new NpgsqlCommand($"CREATE DATABASE \"{name}\"", conn);
        await cmd.ExecuteNonQueryAsync();
        return new NpgsqlConnectionStringBuilder(ConnectionString) { Database = name }.ToString();
    }
}
```

Test nhận fixture qua constructor và tự tạo database của mình (helper `CatalogDb.CreateAsync` gọi `CreateDatabaseAsync` rồi `EnsureCreated`):

```csharp
// tests/Catalog.Tests/AuditTests.cs (trích)
public sealed class AuditTests(PostgresFixture pg) : IClassFixture<PostgresFixture>
{
    [Fact]
    public async Task Create_sets_CreatedAt_equal_UpdatedAt()
    {
        var (newDb, clock) = await CatalogDb.CreateAsync(pg);
        var category = await CatalogDb.AddCategoryAsync(newDb);

        await using var db = newDb();
        var saved = await db.Categories.SingleAsync(c => c.Id == category.Id);

        saved.CreatedAt.ShouldBe(clock.GetUtcNow());
        saved.UpdatedAt.ShouldBe(saved.CreatedAt);
        saved.IsDeleted.ShouldBeFalse();
    }
}
```

Mẹo cho nhanh: thêm `.WithReuse(true)` vào builder và đặt `TESTCONTAINERS_REUSE_ENABLE=true` trên máy dev để container sống giữa các lần chạy. Không bật reuse trong script gate.

### 3. API test

Chạy service thật trong process bằng `ShopLabApiFactory<ApiMarker>` (TestKit, bọc `WebApplicationFactory`). Mỗi service có class rỗng `ApiMarker` làm điểm neo thay cho `public partial class Program;`. Test đặt connection string qua `factory.Settings[...]`; factory tự bật `Messaging:Disabled` và thay JWT bằng `TestAuthHandler` đọc header `X-Test-Auth: <sub>;<roles>;<store>`.

```csharp
// tests/Customer.Tests/CustomerApiTests.cs (trích)
public sealed class CustomerApiTests(PostgresFixture pg) : IClassFixture<PostgresFixture>
{
    private async Task<HttpClient> ClientAsync()
    {
        var factory = new ShopLabApiFactory<ApiMarker>();
        factory.Settings["ConnectionStrings:customerdb"] = await pg.CreateDatabaseAsync("customer");
        return factory.CreateClient();
    }

    [Fact]
    public async Task EnsureMe_twice_creates_one_profile()
    {
        var newUser = Guid.NewGuid();
        var client = (await ClientAsync()).As(newUser, "customer");

        var first = await client.PostAsync("/me/ensure", null, TestContext.Current.CancellationToken);
        var second = await client.PostAsync("/me/ensure", null, TestContext.Current.CancellationToken);

        first.StatusCode.ShouldBe(HttpStatusCode.OK);
        (await second.Content.ReadFromJsonAsync<CustomerDto>())!.Id.ShouldBe(newUser);
    }
}
```

```csharp
// tests/TestKit/TestAuthHandler.cs (trích)
// Header "X-Test-Auth: <sub>;<role1,role2>;<store_id?>". Không có header → chưa đăng nhập.
protected override Task<AuthenticateResult> HandleAuthenticateAsync()
{
    if (!Request.Headers.TryGetValue(Header, out var value) || string.IsNullOrWhiteSpace(value))
        return Task.FromResult(AuthenticateResult.NoResult());

    var parts = value.ToString().Split(';');
    var claims = new List<Claim> { new("sub", parts[0]) };
    if (parts.Length > 1)
        claims.AddRange(parts[1].Split(',', StringSplitOptions.RemoveEmptyEntries).Select(r => new Claim("role", r)));
    if (parts.Length > 2 && !string.IsNullOrWhiteSpace(parts[2]))
        claims.Add(new Claim("store_id", parts[2]));

    var identity = new ClaimsIdentity(claims, Scheme, "preferred_username", "role");
    return Task.FromResult(AuthenticateResult.Success(new AuthenticationTicket(new ClaimsPrincipal(identity), Scheme)));
}

// Gắn vào client: client.As(TestUsers.An, "customer"), client.AsStaff(userId, storeId, "cashier")
```

Mỗi endpoint quan trọng có tối thiểu 4 test: không token → 401, sai role → 403, body sai → 400, đúng → 2xx.

```csharp
// tests/Catalog.Tests/CatalogAuthTests.cs (trích)
[Fact]
public async Task Customer_gets_403_on_admin_api()
{
    var client = (await CreateClientAsync()).As(TestUsers.An, "customer");
    var res = await client.GetAsync("/admin/products", TestContext.Current.CancellationToken);
    res.StatusCode.ShouldBe(HttpStatusCode.Forbidden);
}
```

### 4. Messaging test

Có hai cách kiểm message. Với hạ tầng (outbox, inbox, retry, DLQ) dùng RabbitMQ container thật trong `tests/BuildingBlocks.Tests` và hỏi lại điều kiện tới khi đúng hoặc hết giờ. Với luồng nghiệp vụ (saga, handler), repo gọi thẳng handler từng bước bằng `StepAsync`, giống việc consumer host làm: mở scope, chạy handler, `SaveChanges`; rồi kiểm DB và outbox.

```csharp
// tests/BuildingBlocks.Tests/ConsumerHostTests.cs (trích)
public sealed class ConsumerHostTests(PostgresFixture pg, RabbitMqFixture rabbit)
    : IClassFixture<PostgresFixture>, IClassFixture<RabbitMqFixture>
{
    [Fact]
    public async Task Same_event_delivered_twice_is_handled_once()
    {
        var (host, conn, newDb) = await StartAsync<CountingHandler>("test.inbox", InboxKind.EntityFramework);
        var evt = new SomethingHappened("dup-" + Guid.NewGuid());

        await PublishAsync(conn, evt);
        await PublishAsync(conn, evt); // cùng EventId: giả lập outbox gửi lại
        await Task.Delay(2000);

        await using var db = newDb();
        (await db.Notes.CountAsync(n => n.Text == evt.Text)).ShouldBe(1);
        (await db.Set<InboxMessage>().CountAsync(i => i.EventId == evt.EventId)).ShouldBe(1);
        await host.StopAsync(CancellationToken.None);
    }

    [Fact]
    public async Task Handler_failing_three_times_ends_in_dead_letter_queue()
    {
        var (host, conn, _) = await StartAsync<AlwaysFailingHandler>("test.failing", InboxKind.None);
        await PublishAsync(conn, new SomethingHappened("boom"));

        await using var ch = await conn.CreateChannelAsync();
        uint dlq = 0;
        for (var i = 0; i < 30 && dlq == 0; i++)   // hỏi lại tới khi có hoặc hết giờ
        {
            await Task.Delay(500);
            dlq = await ch.MessageCountAsync("test.failing.dlq");
        }
        dlq.ShouldBe(1u);
    }
}
```

```csharp
// tests/Ordering.Tests/CouponSagaTests.cs (trích)
[Fact]
public async Task Stock_reserved_alone_does_not_request_payment_until_coupon_redeemed()
{
    var t = await OrderingTestContext.CreateAsync(pg, CouponStub(QuoteWithCoupon));
    var orderId = await t.PlaceAsync();

    await t.StepAsync(s => s.OnStockReservedAsync(orderId, default));
    (await t.OutboxTypesAsync()).ShouldNotContain("payments.payment_requested");

    await t.StepAsync(s => s.OnCouponRedeemedAsync(orderId, default));
    await using (var db = t.NewDb())
        (await db.Orders.SingleAsync()).Status.ShouldBe(OrderStatus.PendingPayment);
    (await t.OutboxTypesAsync()).Count(x => x == "payments.payment_requested").ShouldBe(1);
}

// OrderingFixture.cs: mỗi bước mở DbContext mới, chạy saga, SaveChanges — giống consumer host
public async Task StepAsync(Func<CheckoutSaga, Task> step)
{
    await using var db = NewDb();
    await step(Saga(db));
    await db.SaveChangesAsync();
}
```

Những tình huống bắt buộc có test: rollback thì không có outbox; publisher chết giữa batch thì gửi lại; message trùng xử lý một lần; handler lỗi 3 lần thì vào DLQ; lỗi tạm thời của Mongo thì không vào DLQ.

### 5. Test luồng nhiều service

`OrderingTestContext` dựng database Ordering riêng trên Postgres container, đồng hồ giả `FakeTimeProvider`, và `StubHandler` trả lời thay Cart, Catalog, Discount, Customer. Test gọi `PlaceAsync()` rồi đẩy saga bằng `StepAsync(s => s.OnStockReservedAsync(...))`, `OnCouponRedeemedAsync`, `OnPaymentFailedAsync`…, sau đó kiểm trạng thái order, saga và danh sách event trong outbox.

```csharp
// tests/Ordering.Tests/CheckoutSagaTests.cs (trích)
[Fact]
public async Task Payment_failure_cancels_so_inventory_releases_stock()
{
    var t = await OrderingTestContext.CreateAsync(pg);
    var orderId = await t.PlaceAsync();
    await t.StepAsync(s => s.OnStockReservedAsync(orderId, default));

    await t.StepAsync(s => s.OnPaymentFailedAsync(orderId, "CARD_DECLINED", default));

    await using var db = t.NewDb();
    (await db.Orders.SingleAsync()).Status.ShouldBe(OrderStatus.Cancelled);
    (await db.Sagas.SingleAsync()).Step.ShouldBe(SagaStep.Compensated);
    (await t.OutboxTypesAsync()).Last().ShouldBe("orders.order_cancelled");
}
```

Cách này nhanh (dưới một giây mỗi test) và phủ hết nhánh của saga. Test end-to-end nhiều process (Aspire.Hosting.Testing, `tests/Checkout.IntegrationTests/`) là phần tuỳ chọn ở S8.

### 6. Test kiến trúc

```csharp
[Fact]
public void Services_DoNotReferenceEachOther()
{
    string[] projects = ["Catalog.Api", "Customer.Api", "Cart.Api", "Inventory.Api", "Discount.Api",
                         "Ordering.Api", "Payment.Api", "FlashSale.Api", "Store.Api",
                         "Notification.Worker", "Gateway.Web", "Bff.Admin", "Bff.Pos"];
    foreach (var p in projects)
    {
        var result = Types.InAssembly(Assembly.Load(p))
            .ShouldNot().HaveDependencyOnAny(projects.Where(x => x != p).ToArray())
            .GetResult();
        result.IsSuccessful.ShouldBeTrue($"{p}: {string.Join(", ", result.FailingTypeNames ?? [])}");
    }
}
```

### 7. Frontend test

Nx sinh sẵn cấu hình test runner cho mỗi app và lib. Thư viện thuần TypeScript (`libs/pricing`) test như unit test C#, đọc chung `seed/pricing-cases.json`. Component test chỉ kiểm hành vi người dùng thấy, không kiểm chi tiết render.

```typescript
// src/Web/libs/pricing/src/lib/engine.spec.ts — cần "resolveJsonModule": true trong tsconfig.spec.json
import cases from '../../../../../../seed/pricing-cases.json';
import { calculate } from './engine';

describe('pricing engine', () => {
  it.each(cases)('$id: $title', (c) => {
    const result = calculate({ lines: c.lines, promotions: c.promotions, coupon: c.coupon, now: c.now, channel: c.channel });
    expect(result.total).toBe(c.expected.total);
    expect(result.lines.map((l) => l.discount)).toEqual(c.expected.lineDiscounts);
  });
});
```

```typescript
// apps/storefront/src/app/pages/cart/coupon-box.component.spec.ts
it('shows the reason when the coupon is rejected', async () => {
  const cartApi = {
    applyCoupon: jest.fn().mockReturnValue(throwError(() => ({ error: { code: 'COUPON_MIN_SUBTOTAL' } }))),
  };
  await TestBed.configureTestingModule({
    imports: [CouponBoxComponent],
    providers: [{ provide: CartApi, useValue: cartApi }],
  }).compileComponents();
  const fixture = TestBed.createComponent(CouponBoxComponent);

  fixture.componentInstance.code.set('WELCOME50K');
  fixture.componentInstance.apply();
  fixture.detectChanges();

  expect(fixture.nativeElement.textContent).toContain('chưa đủ giá trị đơn');
});
```

Repo dùng Jest (`@nx/jest` đã có trong `package.json`); thêm target test cho app/lib bằng `npx nx g @nx/jest:configuration --project=<tên>`, chạy `npx nx test <tên>`.

### 8. Test tải với k6

Mỗi kịch bản có `thresholds` để k6 tự báo đạt/không đạt (exit code khác 0 khi trượt), và luôn xuất kết quả ra file để so giữa các bước.

```bash
k6 run -e BASE=http://localhost:5000 --summary-export docs/benchmarks/s3-checkout.json load/checkout-1000.js
```

Đọc kết quả theo thứ tự: `checks` (logic đúng không), `http_req_failed` (lỗi), `http_req_duration p(95)` (độ trễ), rồi mới tới `iterations` (thông lượng). Mỗi lần chạy ghi thêm số kết nối DB (`SELECT count(*) FROM pg_stat_activity`) và độ dài queue lúc cao điểm vào file benchmark.

### 9. Diễn tập sự cố

Mỗi lần diễn tập đi theo 5 bước và ghi vào `docs/postmortems/<tên>.md` theo mẫu:

1. **Giả thuyết**: "Kill Inventory 30 giây giữa checkout thì không order nào kẹt sau khi Inventory bật lại."
2. **Chuẩn bị**: dữ liệu, kịch bản k6 đang chạy, các câu SQL kiểm tra.
3. **Thực hiện**: `./tools/chaos/kill.sh inventory 30`, ghi thời điểm.
4. **Quan sát**: trace, độ dài queue, outbox lag, kết quả SQL trước/sau.
5. **Kết luận**: giả thuyết đúng hay sai, nguyên nhân, việc cần sửa, ngày chạy lại.

### Lệnh chạy test

| STT | Mục đích | Lệnh |
| --- | --- | --- |
| 1 | Toàn bộ test .NET | `dotnet test` |
| 2 | Một project | `dotnet test tests/Inventory.Tests` |
| 3 | Một nhóm test theo tên | `dotnet test --filter "FullyQualifiedName~StockLevelTests"` |
| 4 | Bỏ qua test chậm khi đang code | `dotnet test --filter "Category!=Slow"` (đánh dấu `[Trait("Category", "Slow")]`) |
| 5 | Toàn bộ test frontend | `cd src/Web && npx nx run-many -t test` |
| 6 | Chỉ phần bị ảnh hưởng bởi thay đổi | `cd src/Web && npx nx affected -t test` |
| 7 | Mọi thứ như gate | `./tools/check.sh` |

Mọi integration test cần Docker đang chạy. Nếu `dotnet test` treo ở bước khởi động container, kiểm `docker info` trước.

## Lịch tổng

Hai mốc đáng chú ý: hết S2 (09/05/2027) là lúc có web đặt hàng chạy được từ UI; hết S6 (05/03/2028) là lúc flash sale đạt gate.

&#91;embedded content: 9 bước theo lịch · 2 mốc chính tô đậm · đường đứt = tuần nghỉ Tết\]

| STT | Bước | Tuần | Từ ngày | Đến ngày | Buổi (STT) | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | S0. Nền móng sớm | 1–5 | 02/11/2026 | 06/12/2026 | 1–20 | Đăng nhập storefront qua Keycloak; `/api/ping` 200 có token, 401 không token |
| 2 | S1. Web catalog | 6–12 | 07/12/2026 | 24/01/2027 | 21–48 | Admin tạo sản phẩm, storefront thấy ngay; customer gọi API admin bị 403 |
| 3 | S2. Đặt hàng đồng bộ | 13–26 | 25/01/2027 | 09/05/2027 | 49–104 | Đặt hàng end-to-end từ UI; ghi lại 3 chỗ gãy |
| 4 | S3. Event-driven | 27–39 | 10/05/2027 | 08/08/2027 | 105–156 | 3 chỗ gãy ở S2 tự hồi phục; 1.000 checkout lỗi 10% không lệch kho |
| 5 | S4. Discount | 40–46 | 09/08/2027 | 26/09/2027 | 157–184 | 12 case giá đúng từng đồng |
| 6 | S5. Read model MongoDB | 47–53 | 27/09/2027 | 14/11/2027 | 185–212 | Xoá `catalog_read`, rebuild khớp 100% Postgres |
| 7 | S6. Flash sale | 54–68 | 15/11/2027 | 05/03/2028 | 213–272 | 0 oversell, p95 `/buy` < 150 ms, đủ 4 bài diễn tập |
| 8 | S7. POS | 69–81 | 06/03/2028 | 04/06/2028 | 273–324 | 20 giao dịch offline, sync lại không trùng |
| 9 | S8. Hardening | 82–88 | 05/06/2028 | 23/07/2028 | 325–352 | Postmortem cho mỗi lần kill, tự hồi phục |

## S0. Nền móng sớm (tuần 1–5)

Dựng năm thứ khó gắn về sau: AppHost + OpenTelemetry, Postgres, Keycloak + gateway, Nx workspace với auth và api-client, bộ test Testcontainers. Chưa có tính năng bán hàng nào. **Gate:** đăng nhập storefront qua Keycloak được; `GET /api/ping` qua gateway có token được 200, không token được 401.

Lệnh và nội dung file từng buổi: `docs/guides/ShopLab-S0.md` trong repo (mỗi bước một file `ShopLab-Sx.md` cùng thư mục; đây là bản chuẩn, không dùng link artifact).

### Tuần 1 · 02/11–08/11/2026

**Mục tiêu tuần:** máy đủ công cụ, repo có khung solution build được, `aspire run` mở dashboard và Postgres chạy.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 1 | T3 03/11 | Cài .NET 10 SDK, Docker Desktop, Node 22 LTS, k6; cài Aspire CLI và dotnet-ef | (không) | `dotnet --info`; `dotnet tool install -g Aspire.Cli`; `dotnet tool install -g dotnet-ef`; `docker info`; `k6 version` | Mọi lệnh in ra version, Docker đang chạy |
| 2 | T5 05/11 | Tạo repo, solution `.slnx`, file cấu hình build chung (`TargetFramework` net10.0), nhánh `step/s0-foundation` | `Directory.Build.props`: `TargetFramework` net10.0, `Nullable`, `ImplicitUsings`, `LangVersion`; `TreatWarningsAsErrors` tắt tới S8 | `git init`; `git checkout -b step/s0-foundation`; `dotnet new sln -n shoplab --format slnx`; `dotnet new buildprops`; `dotnet new packagesprops`; `dotnet new editorconfig`; `dotnet new gitignore` | Commit đầu tiên trên `master` |
| 3 | T7 07/11 | Tạo AppHost, ServiceDefaults, BuildingBlocks, Contracts; chạy Aspire lần đầu. Template sinh `PackageReference` có `Version`: chuyển version sang `Directory.Packages.props` (Central Package Management) rồi mới build để tránh NU1008, và làm vậy sau mọi lần `dotnet new` | `src/AppHost/AppHost.cs`, `src/ServiceDefaults/Extensions.cs`, `src/BuildingBlocks/`, `src/Contracts/` | `dotnet new aspire-apphost -n AppHost -o src/AppHost`; `dotnet new aspire-servicedefaults -n ServiceDefaults -o src/ServiceDefaults`; `dotnet new classlib -n BuildingBlocks -o src/BuildingBlocks`; `dotnet new classlib -n Contracts -o src/Contracts`; `dotnet sln add $(find src -name '*.csproj')`; `aspire run` | Dashboard mở được, chưa có resource |
| 4 | CN 08/11 | Thêm Postgres + pgAdmin vào AppHost (volume tên `shoplab-pg`), mỗi service một database bằng `AddDatabase` | `src/AppHost/AppHost.cs` (`pg.AddDatabase(...)` cho từng service, không dùng `init.sql`) | `dotnet add src/AppHost package Aspire.Hosting.PostgreSQL`; `aspire run` | Postgres xanh trên dashboard, pgAdmin thấy 8 database |

### Tuần 2 · 09/11–15/11/2026

**Mục tiêu tuần:** Keycloak chạy trong AppHost với realm `shoplab` tự import, lấy được access token cho user mẫu.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 5 | T3 10/11 | Thêm Keycloak vào AppHost với data volume tên `shoplab-keycloak` (`WithDataVolume("shoplab-keycloak")`) | `src/AppHost/AppHost.cs` | `dotnet add src/AppHost package Aspire.Hosting.Keycloak`; `aspire run` | Mở được Keycloak admin console |
| 6 | T5 12/11 | Tạo realm `shoplab` bằng tay: 4 role, client `storefront`, `admin`, `pos` (public + PKCE), `gateway` (audience), `shoplab-cli` (direct access grant, chỉ dev) | (cấu hình trong Keycloak UI) | (không) | Thấy đủ role và client trong realm |
| 7 | T7 14/11 | Tạo 6 user mẫu (admin, manager.q1, cashier.q1, an.nguyen, binh.tran, chi.le), mapper audience `gateway`, export realm và import tự động | `docker/keycloak/shoplab-realm.json`, `src/AppHost/AppHost.cs` (`.WithRealmImport(...)`) | Dừng resource `keycloak` trong dashboard; lấy đúng image Aspire đang dùng: `IMG=$(docker inspect <keycloak> --format '{{.Config.Image}}')`; `docker run --rm -v shoplab-keycloak:/opt/keycloak/data -v $PWD/docker/keycloak:/export $IMG export --realm shoplab --users realm_file --dir /export` (khác phiên bản có thể migrate dữ liệu trong volume) | Xoá volume Keycloak, `aspire run` lại, realm và user tự có |
| 8 | CN 15/11 | Viết lớp auth dùng chung: JWT Bearer trỏ Keycloak, đổi `realm_access.roles` thành role claim; script lấy token | `src/BuildingBlocks/Auth/AuthExtensions.cs`, `src/BuildingBlocks/Auth/KeycloakRolesTransformation.cs`, `tools/get-token.sh` | `dotnet add src/BuildingBlocks package Microsoft.AspNetCore.Authentication.JwtBearer`; `./tools/get-token.sh an.nguyen` | Script in ra access token; giải mã trên jwt.io thấy role `customer` |

### Tuần 3 · 16/11–22/11/2026

**Mục tiêu tuần:** request đi qua Gateway.Web tới Catalog.Api, có xác thực, và thấy được trace hai chặng trên dashboard.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 9 | T3 17/11 | Tạo Gateway.Web và Catalog.Api khung, Catalog có `GET /ping`; khai báo cả hai trong AppHost. Tạo tay `ApiMarker.cs` (class rỗng) và đặt `applicationUrl` cổng cố định trong `Properties/launchSettings.json` (Gateway 5000, Catalog 5101), đúng quy ước mà `tools/new-service.py` tự động hoá từ S2 | `src/Gateways/Gateway.Web/Program.cs`, `src/Services/Catalog.Api/Program.cs`, `src/AppHost/AppHost.cs`, `ApiMarker.cs`, `Properties/launchSettings.json` của hai project | `dotnet new web -n Gateway.Web -o src/Gateways/Gateway.Web`; `dotnet new web -n Catalog.Api -o src/Services/Catalog.Api`; `dotnet sln add …`; `dotnet add src/AppHost reference …` | Cả hai service xanh trên dashboard |
| 10 | T5 19/11 | Cấu hình YARP: route `/api/ping` và `/api/catalog/{**rest}` tới `https+http://catalog` qua service discovery; transform `PathRemovePrefix` bỏ `/api/catalog` (vd `/api/catalog/products` → `/products`), mọi route `/api/<svc>/...` làm theo cùng mẫu | `src/Gateways/Gateway.Web/yarp.json`, `Program.cs` | `dotnet add src/Gateways/Gateway.Web package Yarp.ReverseProxy`; `dotnet add src/Gateways/Gateway.Web package Microsoft.Extensions.ServiceDiscovery.Yarp` | `curl <gateway>/api/ping` trả 200 (chưa có auth) |
| 11 | T7 21/11 | Bật auth ở gateway (policy `authenticated` cho route) và ở Catalog; gateway chuyển tiếp header `Authorization` | `src/Gateways/Gateway.Web/Program.cs`, `yarp.json`, `src/Services/Catalog.Api/Program.cs` | `TOKEN=$(./tools/get-token.sh an.nguyen)`; `curl -H "Authorization: Bearer $TOKEN" <gateway>/api/ping` | Có token được 200, không token được 401 |
| 12 | CN 22/11 | Kiểm tra ServiceDefaults (OTel exporter, `/health`, `/alive`, resilience), viết file `.http` đầu tiên | `src/ServiceDefaults/Extensions.cs`, `http/ping.http` | `aspire run`; chạy `http/ping.http` trong IDE | Dashboard có một trace gồm span gateway và span catalog |

### Tuần 4 · 23/11–29/11/2026

**Mục tiêu tuần:** Nx workspace có `storefront` và `admin`, đăng nhập qua Keycloak, admin chặn người không có role `admin`.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 13 | T3 24/11 | Tạo Nx workspace và hai app Angular | `src/Web/` (nx.json, apps/storefront, apps/admin), `tools/scaffold-angular-app.sh` (viết script: project.json tối giản, builder `@angular/build`, proxy `/api` → gateway) | `cd src && npx create-nx-workspace@21.5.0 Web --preset=apps --pm=npm --nxCloud=skip --interactive=false`; `cd Web && npm i -D @nx/angular@21.5.0 @angular/build@^20.3 @angular/cli@^20.3 @angular/compiler-cli@^20.3`; `./tools/scaffold-angular-app.sh storefront 4200`; `./tools/scaffold-angular-app.sh admin 4300` | `npx nx serve storefront` và `npx nx serve admin` đều mở được |
| 14 | T5 26/11 | Khai báo hai app Angular trong AppHost bằng integration JavaScript (xem đúng tên API trong docs của bản Aspire đang dùng), truyền URL gateway qua biến môi trường | `src/AppHost/AppHost.cs`, `src/Web/apps/*/proxy.conf.json` | `dotnet add src/AppHost package Aspire.Hosting.JavaScript`; `aspire run` | Hai app hiện trên dashboard, mở được từ link |
| 15 | T7 28/11 | Thư viện auth: OIDC code flow + PKCE, interceptor gắn token, guard theo role | `libs/auth/src/lib/auth.config.ts`, `auth.service.ts`, `auth.interceptor.ts`, `role.guard.ts` | `npx nx g @nx/angular:library --directory=libs/auth --name=auth --importPath=@shoplab/auth --standalone`; `npm i angular-oauth2-oidc` | Build cả hai app không lỗi |
| 16 | CN 29/11 | Nút đăng nhập/đăng xuất, header hiện tên user; app admin yêu cầu role `admin` | `apps/storefront/src/app/layout/header.component.ts`, `apps/admin/src/app/app.routes.ts` | `npx nx serve storefront` | `an.nguyen` vào storefront được nhưng bị chặn ở admin; `admin@shoplab.local` vào admin được |

### Tuần 5 · 30/11–06/12/2026

**Mục tiêu tuần:** OpenAPI + Scalar cho Catalog, lib `api-client` viết tay gọi được `/api/ping`, có bộ test Testcontainers, qua gate S0.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 17 | T3 01/12 | Bật OpenAPI + Scalar cho Catalog; sinh file OpenAPI lúc build | `src/Services/Catalog.Api/Program.cs`, `Catalog.Api.csproj` (`OpenApiDocumentsDirectory` → `contracts/openapi/`) | `dotnet add src/BuildingBlocks package Microsoft.AspNetCore.OpenApi`; `dotnet add src/BuildingBlocks package Scalar.AspNetCore`; `dotnet add src/Services/Catalog.Api package Microsoft.Extensions.ApiDescription.Server`; `dotnet build` | Có `contracts/openapi/Catalog.Api.json`; mở `/scalar` thấy `/ping` |
| 18 | T5 03/12 | Lib `api-client` viết tay: mỗi service một file `*.api.ts` (sinh từ OpenAPI bằng `ng-openapi-gen` là bài tập mở rộng ở S8) | `src/Web/libs/api-client/src/lib/system.api.ts`, `src/Web/libs/api-client/src/index.ts` | `npx nx g @nx/angular:library --directory=libs/api-client --name=api-client --importPath=@shoplab/api-client --standalone` | Storefront gọi `/api/ping` qua `system.api.ts` viết tay, in kết quả ra console |
| 19 | T7 05/12 | Project test đầu tiên: `tests/Directory.Build.props` (xUnit v3, Shouldly cho mọi project test), Testcontainers Postgres, một test kết nối; xoá `Version` trong csproj sinh từ template và khai ở `Directory.Packages.props` (Central Package Management, tránh NU1008) | `tests/Directory.Build.props`, `tests/Catalog.Tests/Catalog.Tests.csproj`, `Infrastructure/PostgresFixture.cs`, `SmokeTests.cs`, `Directory.Packages.props` | `dotnet new install xunit.v3.templates`; `dotnet new xunit3 -n Catalog.Tests -o tests/Catalog.Tests`; `dotnet sln add tests/Catalog.Tests`; `dotnet add tests/Catalog.Tests package Testcontainers.PostgreSql`; `dotnet test` | `dotnet test` xanh, container Postgres tự lên rồi tự xoá |
| 20 | CN 06/12 | Chạy gate S0 từ đầu trên máy sạch (xoá volume của lab), viết ghi chú, xuất `docs/guides/ShopLab-S0.md`, merge và tag | `docs/notes/s0.md`, `docs/guides/ShopLab-S0.md` | `docker volume rm shoplab-pg shoplab-keycloak`; `aspire run`; `dotnet test`; `git checkout main && git merge --no-ff step/s0-foundation`; `git tag s0-done`; `git checkout -b step/s1-catalog` | Đạt gate S0; ghi chú có danh sách lỗi đã gặp |

## S1. Web catalog (tuần 6–12)

Catalog đầy đủ: audit + soft delete dùng chung, CRUD, tìm kiếm phân trang keyset, seed 7 sản phẩm; storefront xem danh sách và chi tiết; admin quản lý category và sản phẩm. **Gate:** admin tạo sản phẩm mới, storefront thấy ngay; user `customer` gọi API admin bị 403.

### Tuần 6 · 07/12–13/12/2026

**Mục tiêu tuần:** lớp audit + soft delete dùng chung chạy được, Catalog có DbContext và migration đầu tiên.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 21 | T3 08/12 | Base `Auditable`, `AuditInterceptor` (dùng `TimeProvider`), extension áp query filter `!IsDeleted` cho mọi `Auditable` | `src/BuildingBlocks/Persistence/Auditable.cs`, `AuditInterceptor.cs`, `SoftDeleteQueryFilter.cs` | `dotnet add src/BuildingBlocks package Microsoft.EntityFrameworkCore` | Build xanh |
| 22 | T5 10/12 | Entity Catalog và cấu hình EF: snake\_case, `Attributes` jsonb, unique index `Sku` lọc `is_deleted = false` | `src/Services/Catalog.Api/Domain/Category.cs`, `Product.cs`, `ProductVariant.cs`, `Data/CatalogDbContext.cs`, `Data/Configurations/*.cs` | `dotnet add src/BuildingBlocks package Aspire.Npgsql.EntityFrameworkCore.PostgreSQL`; `dotnet add src/BuildingBlocks package EFCore.NamingConventions` | Build xanh |
| 23 | T7 12/12 | Nối `catalogdb` trong AppHost, design-time factory, migration `Init`, tự migrate khi chạy Development | `src/AppHost/AppHost.cs`, `Data/CatalogDbContextFactory.cs`, `Data/Migrations/`, `Program.cs`, `tools/ef-migrations.sh` (viết script) | `dotnet add src/Services/Catalog.Api package Microsoft.EntityFrameworkCore.Design`; `./tools/ef-migrations.sh Init Catalog`; `aspire run` | pgAdmin thấy bảng `products`, `product_variants`, `categories` có 4 cột audit |
| 24 | CN 13/12 | `AuditTests`: tạo mới có `CreatedAt = UpdatedAt`; sửa chỉ đổi `UpdatedAt`; `Remove()` thành xoá mềm; xoá mềm SKU rồi tạo lại không lỗi. Tạo `tests/TestKit` (thư viện, `OutputType=Library`, `IsTestProject=false`), chuyển `PostgresFixture` sang đó | `tests/Catalog.Tests/AuditTests.cs`, `CatalogDb.cs`, `tests/TestKit/PostgresFixture.cs` | `dotnet new classlib -n TestKit -o tests/TestKit`; `dotnet sln add tests/TestKit`; `dotnet add tests/TestKit package Testcontainers.PostgreSql`; `dotnet remove tests/Catalog.Tests package Testcontainers.PostgreSql`; `dotnet add tests/Catalog.Tests reference tests/TestKit`; `dotnet test --filter AuditTests` | 4 test xanh |

### Tuần 7 · 14/12–20/12/2026

**Mục tiêu tuần:** CRUD category và sản phẩm qua Scalar, lỗi trả ProblemDetails thống nhất.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 25 | T3 15/12 | Cơ chế endpoint theo vertical slice: interface `IEndpoint`, quét assembly để map | `src/BuildingBlocks/Endpoints/IEndpoint.cs`, `src/BuildingBlocks/ApiExtensions.cs` | `dotnet build` | `/ping` chuyển sang `Features/Ping.cs` vẫn chạy |
| 26 | T5 17/12 | Kiểu `Result`, ánh xạ lỗi sang ProblemDetails, bật validation có sẵn của .NET 10 (`AddValidation`) | `src/BuildingBlocks/Results/AppErrors.cs`, `ProblemDetailsMapping.cs` | `dotnet build` | Gửi body thiếu trường trả 400 dạng ProblemDetails |
| 27 | T7 19/12 | Category: tạo, sửa, xoá, liệt kê | `Features/Categories/CreateCategory.cs`, `UpdateCategory.cs`, `DeleteCategory.cs`, `ListCategories.cs` | `aspire run` | Làm đủ 4 thao tác trên Scalar |
| 28 | CN 20/12 | Product: tạo kèm variant, sửa, xem, xoá mềm, bật/tắt `IsActive`, khôi phục; tăng `Version` mỗi lần ghi | `Features/Products/CreateProduct.cs`, `UpdateProduct.cs`, `GetProduct.cs`, `DeleteProduct.cs`, `SetProductActive.cs`, `RestoreProduct.cs`, `http/catalog.http` | Chạy `http/catalog.http` | Toàn bộ request trong file `.http` trả đúng mã |

### Tuần 8 · 21/12–27/12/2026

**Mục tiêu tuần:** tìm kiếm phân trang keyset và seed dữ liệu mẫu.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 29 | T3 22/12 | Cursor keyset dùng chung (mã hoá base64 của `(name, id)`) | `src/BuildingBlocks/Paging/KeysetCursor.cs` (gồm cả `PagedResult`) | `dotnet build` | Build xanh |
| 30 | T5 24/12 | `SearchProducts`: lọc theo category, từ khoá, chỉ bản `IsActive` và chưa xoá; index cho truy vấn | `Features/Products/SearchProducts.cs`, migration `AddSearchIndexes` | `./tools/ef-migrations.sh AddSearchIndexes Catalog` | `GET /products?category=dien-tu` trả trang đầu + `nextCursor` |
| 31 | T7 26/12 | Seed category và 7 sản phẩm khi bảng trống; copy thư mục `seed/` vào output | `seed/categories.json`, `seed/products.json`, `Data/SeedData.cs`, `Catalog.Api.csproj` | `aspire run` | Bảng `product_variants` có đủ 7 SKU |
| 32 | CN 27/12 | `SearchProductsTests`: sang trang không lặp, không sót; bản đã xoá hoặc tắt không hiện | `tests/Catalog.Tests/SearchProductsTests.cs` | `dotnet test` | Test xanh |

### Tuần 9 · 28/12/2026–03/01/2027

**Mục tiêu tuần:** phân quyền API admin, test 403, chuẩn bị thư viện UI.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 33 | T3 29/12 | Policy `Admin`, `Customer`; GET công khai cho phép ẩn danh; nhóm `/admin/products` yêu cầu `Admin`; thêm route gateway `/api/admin/catalog/{**rest}`; gateway thêm route `catalog-public` (GET `/api/catalog/**`) không gắn policy `authenticated` để storefront và k6 duyệt ẩn danh | `src/BuildingBlocks/Auth/AuthExtensions.cs`, `Features/**`, `src/Gateways/Gateway.Web/yarp.json` | `curl` với token `an.nguyen` và `admin@shoplab.local` | Customer gọi admin bị 403, admin được 200 |
| 34 | T5 31/12 | `WebApplicationFactory` cho Catalog với handler xác thực giả | `tests/TestKit/ShopLabApiFactory.cs`, `TestAuthHandler.cs`, `tests/Catalog.Tests/CatalogAuthTests.cs` | `dotnet add tests/TestKit package Microsoft.AspNetCore.Mvc.Testing`; `dotnet test` | Test 401, 403, 200 đều xanh |
| 35 | T7 02/01 | Thêm `catalog.api.ts` + `catalog.models.ts` vào `api-client` (viết tay theo OpenAPI của Catalog); thư viện `libs/ui` với Angular Material và pipe định dạng VND | `libs/api-client/src/lib/catalog.api.ts`, `catalog.models.ts`, `libs/ui/src/lib/vnd.pipe.ts`, `apps/*/src/styles.scss` | `npx nx g @nx/angular:library --directory=libs/ui --name=ui --importPath=@shoplab/ui --standalone`; `npm i @angular/material @angular/cdk` | `1.234.000 ₫` hiện đúng trong một component thử |
| 36 | CN 03/01 | Dự phòng nghỉ Tết dương: làm bù việc dở của tuần 6–9 | (tuỳ việc dở) | (tuỳ việc dở) | Không còn việc dở trước tuần 10 |

### Tuần 10 · 04/01–10/01/2027

**Mục tiêu tuần:** storefront có trang danh sách và trang chi tiết sản phẩm.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 37 | T3 05/01 | Route storefront: `/`, `/c/:slug`, `/p/:slug`; khung trang | `apps/storefront/src/app/app.routes.ts`, `pages/product-list/`, `pages/product-detail/` | `npx nx g @nx/angular:component apps/storefront/src/app/pages/product-list`; `npx nx g @nx/angular:component apps/storefront/src/app/pages/product-detail` | Điều hướng giữa ba route được |
| 38 | T5 07/01 | Trang danh sách: lưới sản phẩm, lọc category, nút "Xem thêm" theo cursor | `pages/product-list/product-list.component.ts`, `.html` | `npx nx serve storefront` | Thấy 7 sản phẩm, lọc theo category đúng |
| 39 | T7 09/01 | Trang chi tiết: chọn variant, giá VND, giá gạch, nhãn còn hàng | `pages/product-detail/product-detail.component.ts`, `.html` | `npx nx serve storefront` | Mở `/p/sl-buds-pro` thấy đủ thông tin |
| 40 | CN 10/01 | Trạng thái loading/lỗi, trang 404, ô tìm kiếm trên header | `apps/storefront/src/app/layout/header.component.ts`, `pages/not-found.component.ts` | `npx nx serve storefront` | Gõ "bình" ra đúng sản phẩm; slug sai ra trang 404 |

### Tuần 11 · 11/01–17/01/2027

**Mục tiêu tuần:** admin quản lý category và sản phẩm, gồm bật/tắt, xoá mềm, khôi phục.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 41 | T3 12/01 | Layout admin (menu trái), màn hình category: danh sách + dialog tạo/sửa | `apps/admin/src/app/layout/shell.component.ts`, `pages/categories/` | `npx nx serve admin` | Tạo/sửa category từ UI |
| 42 | T5 14/01 | Danh sách sản phẩm: bảng phân trang, tìm kiếm, lọc "đã xoá" (endpoint `includeDeleted=true` dùng `IgnoreQueryFilters`) | `pages/products/product-list.component.ts`, `Features/Products/AdminSearchProducts.cs` | `npx nx serve admin` | Thấy cả bản đã xoá khi bật lọc |
| 43 | T7 16/01 | Form sản phẩm: reactive form, `FormArray` cho variant, cặp key-value cho thuộc tính | `pages/products/product-form.component.ts`, `.html` | `npx nx serve admin` | Tạo sản phẩm 2 variant từ UI |
| 44 | CN 17/01 | Bật/tắt `IsActive`, xoá mềm có xác nhận, khôi phục | `pages/products/product-list.component.ts` | `npx nx serve admin` | Tắt sản phẩm thì storefront không thấy, bật lại thì thấy |

### Tuần 12 · 18/01–24/01/2027

**Mục tiêu tuần:** qua gate S1, ghi chú bước, dự phòng.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 45 | T3 19/01 | Chạy gate S1 bằng tay: admin tạo sản phẩm, storefront thấy; customer gọi API admin | `http/gate-s1.http` | Chạy `http/gate-s1.http` | Đạt cả hai điều kiện gate |
| 46 | T5 21/01 | Sửa lỗi phát hiện khi chạy gate | (tuỳ lỗi) | `dotnet test`; `npx nx run-many -t build` | Build và test toàn repo xanh |
| 47 | T7 23/01 | Ghi chú S1: keyset, soft delete, filtered index, những gì làm khác nếu làm lại | `docs/notes/s1.md` | (không) | File ghi chú xong |
| 48 | CN 24/01 | Dự phòng; merge `step/s1-catalog` vào `main` | `docs/guides/ShopLab-S1.md` (xuất hướng dẫn của bước trước khi merge) | `git checkout main && git merge --no-ff step/s1-catalog`; `git tag s1-done`; `git checkout -b step/s2-sync-ordering` | Tag `s1-done` có trên `main` |

## S2. Đặt hàng đồng bộ (tuần 13–26)

Thêm Customer, Inventory (sổ cái ngay từ đầu), Cart trên Redis, Ordering + Payment. Checkout cố ý viết đồng bộ: Ordering gọi HTTP lần lượt Cart → Catalog → Inventory → Payment trong một request, chưa có idempotency. Cuối bước, bạn chủ động làm hệ thống gãy ở 3 chỗ và ghi lại hậu quả. **Gate:** đặt hàng end-to-end từ UI; có baseline k6; có ghi chép 3 kịch bản gãy.

### Tuần 13 · 25/01–31/01/2027

**Mục tiêu tuần:** Customer.Api có hồ sơ khách và địa chỉ, tự tạo hồ sơ khi đăng nhập lần đầu.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 49 | T3 26/01 | Project Customer.Api, nối `customerdb`; entity `Customer`, `Address`, `LoyaltyAccount`; viết `tools/new-service.py` (csproj, launchSettings theo cổng cố định, `ApiMarker`, OpenAPI, EF Design) và dùng cho mọi service từ đây | `src/Services/Customer.Api/Domain/*.cs`, `Data/CustomerDbContext.cs`, `src/AppHost/AppHost.cs`, `tools/new-service.py` | `python3 tools/new-service.py Customer 5102`; `dotnet sln add src/Services/Customer.Api` | Service xanh trên dashboard |
| 50 | T5 28/01 | Migration `Init`, seed `customers.json`: `Id` = `sub` cố định của user trong realm (một định danh khách cho giỏ, đơn, `/internal/customers/{id}`) | `Data/Migrations/`, `seed/customers.json`, `Data/SeedData.cs` | `./tools/ef-migrations.sh Init Customer` | Bảng `customers` có `an.nguyen`, `binh.tran`, `chi.le` (Banned) |
| 51 | T7 30/01 | `EnsureMe` (tạo hồ sơ từ claim `sub`, `email`, `name` nếu chưa có), `GetMe`, `UpdateMe` | `Features/Me/EnsureMe.cs`, `GetMe.cs`, `UpdateMe.cs` | Chạy `http/customer.http` | Gọi `EnsureMe` 2 lần chỉ tạo 1 bản ghi |
| 52 | CN 31/01 | Địa chỉ: thêm, sửa, xoá mềm, đặt mặc định (chỉ một địa chỉ `IsDefault`) | `src/Services/Customer.Api/Features/Addresses/Addresses.cs`, `tests/Customer.Tests/CustomerApiTests.cs` | `dotnet new xunit3 -n Customer.Tests -o tests/Customer.Tests`; `dotnet sln add tests/Customer.Tests`; `dotnet add tests/Customer.Tests reference tests/TestKit`; `dotnet test` | Test địa chỉ mặc định xanh |

*Tuần 01/02–07/02/2027 nghỉ Tết.*

### Tuần 14 · 08/02–14/02/2027

**Mục tiêu tuần:** admin quản lý khách hàng; khởi tạo Inventory với Location và StockLevel.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 53 | T3 09/02 | Admin: danh sách, chi tiết, ban/unban khách; route gateway `/api/customers`, `/api/admin/customers` | `Features/Admin/AdminCustomers.cs`, `src/Gateways/Gateway.Web/yarp.json` | Chạy `http/customer.http` | Ban `an.nguyen` rồi unban được |
| 54 | T5 11/02 | Storefront gọi `EnsureMe` sau đăng nhập; trang hồ sơ + địa chỉ | `apps/storefront/src/app/pages/profile/`, `libs/auth/src/lib/auth.service.ts` | `npx nx serve storefront` | Đăng nhập lần đầu tạo hồ sơ; thêm địa chỉ từ UI |
| 55 | T7 13/02 | Endpoint nội bộ `GET /internal/customers/{id}/status` cho Ordering; test phân quyền | `Features/Internal/InternalCustomers.cs`, `tests/Customer.Tests/CustomerApiTests.cs` | `dotnet test` | `chi.le` trả `Banned` |
| 56 | CN 14/02 | Project Inventory.Api, nối `inventorydb`; entity `Location`, `StockLevel` với `Reserve`, `Release`, `Commit` | `src/Services/Inventory.Api/Domain/Location.cs`, `StockLevel.cs`, `src/AppHost/AppHost.cs` | `python3 tools/new-service.py Inventory 5104`; `dotnet sln add src/Services/Inventory.Api` | Build xanh |

### Tuần 15 · 15/02–21/02/2027

**Mục tiêu tuần:** sổ cái kho hoạt động: mọi thay đổi tồn kho đi qua `StockMovement`.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 57 | T3 16/02 | Entity `StockMovement` (append-only, unique `(RefType, RefId, Sku, Type, LocationId)`), `Reservation`; `xmin` làm concurrency token cho `StockLevel`; migration | `Domain/StockMovement.cs`, `Reservation.cs`, `Data/InventoryDbContext.cs`, `Data/Configurations/*.cs` | `./tools/ef-migrations.sh Init Inventory` | Có 4 bảng, `stock_movements` không có cột soft delete |
| 58 | T5 18/02 | `StockLevelTests`: reserve vượt available ném lỗi; release không làm `Reserved` âm; commit giảm cả `OnHand` và `Reserved` | `tests/Inventory.Tests/StockLevelTests.cs` | `dotnet new xunit3 -n Inventory.Tests -o tests/Inventory.Tests`; `dotnet sln add tests/Inventory.Tests`; `dotnet add tests/Inventory.Tests reference tests/TestKit`; `dotnet test` | 6 test xanh |
| 59 | T7 20/02 | `StockLedger.Apply()`: ghi movement và cập nhật `StockLevel` cùng một `SaveChanges`; endpoint nhập hàng và điều chỉnh | `src/Services/Inventory.Api/Domain/StockLedger.cs`, `Features/Admin/AdminStock.cs` | Chạy `http/inventory.http` | Nhập 10 cái thì `OnHand` +10 và có 1 movement `Receipt` |
| 60 | CN 21/02 | Chuyển kho: `TransferOut` + `TransferIn` trong cùng transaction | `Features/Admin/AdminStock.cs` (chuyển kho) | Chạy `http/inventory.http` | Chuyển 5 cái `WH-HCM` → `ST-Q1`, tổng hai bên không đổi |

### Tuần 16 · 22/02–28/02/2027

**Mục tiêu tuần:** truy vấn tồn kho, seed dữ liệu kho, API giữ hàng nội bộ cho Ordering.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 61 | T3 23/02 | Truy vấn: tồn theo SKU (mọi location), theo location, lịch sử movement của một SKU | `Features/Stock/GetStockBySku.cs`, `Features/Admin/AdminStock.cs` | Chạy `http/inventory.http` | Ba truy vấn trả đúng dữ liệu |
| 62 | T5 25/02 | Seed `locations.json`, `stock.json` dưới dạng movement `Receipt` với `RefType=Seed` | `seed/locations.json`, `seed/stock.json`, `Data/SeedData.cs` | `aspire run` | 4 location, 28 dòng `stock_levels` đúng bảng seed |
| 63 | T7 27/02 | `ReconcileTests`: chạy ngẫu nhiên 200 thao tác, kiểm tra tổng movement = `OnHand` cho mọi cặp (SKU, location) | `tests/Inventory.Tests/ReconcileTests.cs`, `InventoryDb.cs` | `dotnet test --filter ReconcileTests` | Test xanh |
| 64 | CN 28/02 | API nội bộ: `POST /internal/reservations` (mỗi SKU lấy trọn ở location bán online đầu tiên theo `Code` còn đủ hàng, không tách; không location nào đủ thì `OUT_OF_STOCK` cả đơn), `/commit`, `/release`; gọi lại cùng `orderId` không giữ thêm | `Features/Internal/Reservations.cs` | Chạy `http/inventory.http` | Giữ, commit, release đúng; gọi trùng không đổi số liệu |

### Tuần 17 · 01/03–07/03/2027

**Mục tiêu tuần:** giữ hàng an toàn khi nhiều request cùng lúc; khởi tạo Cart trên Redis.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 65 | T3 02/03 | Bắt `DbUpdateConcurrencyException`, thử lại tối đa 3 lần; `InventoryConcurrencyTests`: 50 task giữ 1 SKU còn 10 | `Features/Internal/Reservations.cs`, `tests/Inventory.Tests/InventoryConcurrencyTests.cs` | `dotnet test --filter InventoryConcurrencyTests` | Đúng 10 thành công, 40 nhận lỗi hết hàng |
| 66 | T5 04/03 | So sánh với cách `UPDATE ... WHERE on_hand - reserved >= @q` (không retry); ghi số lần retry và thời gian | `tests/Inventory.Tests/ConditionalUpdateTests.cs`, `docs/notes/s2-concurrency.md` | `dotnet test` | Ghi chú có bảng so sánh hai cách |
| 67 | T7 06/03 | Thêm Redis vào AppHost; project Cart.Api; model `Cart`, `RedisCartStore` (JSON, TTL 48 giờ, gia hạn mỗi lần sửa) | `src/Services/Cart.Api/Domain/Cart.cs`, `Data/RedisCartStore.cs`, `src/AppHost/AppHost.cs` | `dotnet add src/AppHost package Aspire.Hosting.Redis`; `python3 tools/new-service.py Cart 5103 --no-ef`; `dotnet sln add src/Services/Cart.Api`; `dotnet add src/BuildingBlocks package Aspire.StackExchange.Redis` | Cart.Api xanh, RedisInsight mở được |
| 68 | CN 07/03 | Cart: xem, thêm (lấy tên + giá từ Catalog qua typed HttpClient), sửa số lượng, xoá dòng, xoá giỏ; Catalog thêm `GET /internal/variants/{sku}`; Cart thêm `GET`/`DELETE /internal/carts/{customerId}` cho Ordering | `src/Services/Cart.Api/Features/CartEndpoints.cs`, `Domain/Cart.cs`, `Clients/CatalogClient.cs`, `Catalog.Api/Features/Internal/GetVariant.cs`, `Features/InternalCarts.cs` | Chạy `http/cart.http` | Thêm `SL-TEE-BASIC-M` vào giỏ có snapshot giá 199.000 |

### Tuần 18 · 08/03–14/03/2027

**Mục tiêu tuần:** giỏ khách vãng lai + gộp giỏ khi đăng nhập; khởi tạo Payment và Ordering.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 69 | T3 09/03 | Giỏ vãng lai theo header `X-Cart-Id` (`cart:guest:{id}`); `POST /cart/merge` khi đăng nhập (có thể cắt nếu trễ) | `Features/CartEndpoints.cs` (`POST /merge`), `Data/RedisCartStore.cs` | Chạy `http/cart.http` | Gộp giỏ cộng dồn số lượng đúng |
| 70 | T5 11/03 | `CartStoreTests` trên Redis container: thêm, sửa số lượng, gộp giỏ khách vào giỏ tài khoản, hết hạn | `tests/Cart.Tests/CartStoreTests.cs` | `dotnet new xunit3 -n Cart.Tests -o tests/Cart.Tests`; `dotnet sln add tests/Cart.Tests`; `dotnet add tests/TestKit package Testcontainers.Redis`; `dotnet add tests/Cart.Tests reference tests/TestKit`; `dotnet test` | Test xanh |
| 71 | T7 13/03 | Project Payment.Api, nối `paymentdb`; entity `Payment`; `FakePaymentProvider` cấu hình `FailureRate`, `MinLatencyMs`, `MaxLatencyMs`; `POST /internal/payments` | `src/Services/Payment.Api/Features/Internal/Payments.cs` | `python3 tools/new-service.py Payment 5106`; `dotnet sln add src/Services/Payment.Api`; `./tools/ef-migrations.sh Init Payment` | Đặt `FailureRate=1` thì mọi lần gọi trả `Failed` |
| 72 | CN 14/03 | Project Ordering.Api, nối `orderingdb`; entity `Order`, `OrderLine`; số đơn `SO-yyyyMMdd-000001` từ sequence Postgres | `src/Services/Ordering.Api/Domain/Order.cs`, `OrderLine.cs`, `Data/OrderingDbContext.cs`, `Data/OrderNumberGenerator.cs` | `python3 tools/new-service.py Ordering 5105`; `dotnet sln add src/Services/Ordering.Api`; `./tools/ef-migrations.sh Init Ordering` | Tạo 3 order thử có số tăng dần |

### Tuần 19 · 15/03–21/03/2027

**Mục tiêu tuần:** checkout đồng bộ chạy end-to-end qua API.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 73 | T3 16/03 | Typed client cho Cart, Customer, Catalog, Inventory, Payment trong Ordering | `src/Services/Ordering.Api/Clients/*.cs` | `dotnet build` | Build xanh |
| 74 | T5 18/03 | `POST /checkout` phần 1: đọc giỏ, kiểm tra khách không bị ban, lấy giá mới từ Catalog, tạo Order `PendingStock` (khách chưa có hồ sơ, vd user ảo của k6, được coi là Active) | `Features/Checkout/PlaceOrder.cs` | Chạy `http/checkout.http` | Có order `PendingStock` đúng tổng tiền |
| 75 | T7 20/03 | `POST /checkout` phần 2: giữ hàng → thanh toán → commit → `Paid` → xoá giỏ; lỗi thì `Cancelled` + release (làm hết sức, chưa đảm bảo) | `Features/Checkout/PlaceOrder.cs` | Chạy `http/checkout.http` | Order `Paid`, kho `OnHand` giảm đúng, giỏ trống |
| 76 | CN 21/03 | Đơn của tôi, chi tiết đơn, danh sách đơn admin; route gateway cho cart và orders | `Features/Orders/MyOrders.cs`, `Features/Admin/AdminOrders.cs`, `yarp.json` | Chạy `http/checkout.http` | Xem được đơn vừa đặt qua gateway |

### Tuần 20 · 22/03–28/03/2027

**Mục tiêu tuần:** storefront có giỏ hàng, checkout và đơn của tôi.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 77 | T3 23/03 | Thêm `cart.api.ts` vào `api-client`; nút "Thêm vào giỏ", badge số lượng (signal store) | `apps/storefront/src/app/state/cart.store.ts`, `pages/product-detail/` | `npx nx serve storefront` | Thêm vào giỏ thì badge tăng |
| 78 | T5 25/03 | Trang giỏ hàng: danh sách dòng, đổi số lượng, xoá, tạm tính | `pages/cart/` | `npx nx g @nx/angular:component apps/storefront/src/app/pages/cart` | Sửa số lượng thì tạm tính đổi đúng |
| 79 | T7 27/03 | Trang checkout: chọn địa chỉ, đặt hàng, trang kết quả | `pages/checkout/`, `pages/order-result/` | `npx nx serve storefront` | Đặt hàng từ UI ra trang kết quả có số đơn |
| 80 | CN 28/03 | Đơn của tôi: danh sách + chi tiết | `pages/my-orders/`, `pages/order-detail/` | `npx nx serve storefront` | Thấy đơn vừa đặt với đủ dòng hàng |

### Tuần 21 · 29/03–04/04/2027

**Mục tiêu tuần:** admin quản lý khách hàng, tồn kho và đơn hàng.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 81 | T3 30/03 | Màn hình khách hàng: danh sách, chi tiết, ban/unban | `apps/admin/src/app/pages/customers/` | `npx nx serve admin` | Ban khách từ UI; khách đó đặt hàng bị từ chối |
| 82 | T5 01/04 | Màn hình tồn kho theo location, lọc tồn thấp | `pages/inventory/stock-list.component.ts` | `npx nx serve admin` | Thấy đủ 28 dòng seed |
| 83 | T7 03/04 | Form nhập hàng và chuyển kho | `pages/inventory/receipt-form.component.ts`, `transfer-form.component.ts` | `npx nx serve admin` | Nhập và chuyển kho từ UI, số liệu cập nhật |
| 84 | CN 04/04 | Lịch sử movement theo SKU; danh sách đơn hàng admin | `pages/inventory/movements.component.ts`, `pages/orders/` | `npx nx serve admin` | Đơn đặt ở storefront hiện trong admin |

### Tuần 22 · 05/04–11/04/2027

**Mục tiêu tuần:** đo baseline hiệu năng của checkout đồng bộ bằng k6.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 85 | T3 06/04 | Môi trường LoadTest: handler xác thực bằng header `X-Test-User`, chỉ bật khi `ASPNETCORE_ENVIRONMENT=LoadTest`; profile LoadTest cho AppHost | `src/BuildingBlocks/Auth/TestUserAuthHandler.cs`, `src/AppHost/Properties/launchSettings.json` | `aspire run --launch-profile LoadTest` | Gọi API với `X-Test-User: loadtest-1` được 200; ở Development bị 401 |
| 86 | T5 08/04 | Script chuẩn bị dữ liệu tải: nhập thêm hàng cho SKU test (user `loadtest-*` không cần hồ sơ Customer, xem buổi 74) | `tools/seed-loadtest.sh` | `./tools/seed-loadtest.sh` | Mỗi SKU còn ≥ 100.000 cái ở `WH-HCM` |
| 87 | T7 10/04 | Kịch bản k6: thêm vào giỏ + checkout, tăng dần 20 → 50 request/giây trong 3 phút | `load/checkout-normal.js`, `load/README.md` | `k6 run -e BASE=<gateway> load/checkout-normal.js` | Chạy hết kịch bản không lỗi script |
| 88 | CN 11/04 | Chạy baseline, ghi p95, tỉ lệ lỗi, số kết nối DB (`pg_stat_activity`) | `docs/benchmarks/s2-baseline.md` | `k6 run --summary-export docs/benchmarks/s2-baseline.json …` | File benchmark có số liệu |

### Tuần 23 · 12/04–18/04/2027

**Mục tiêu tuần:** chạy 3 kịch bản gãy và ghi lại hậu quả.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 89 | T3 13/04 | Middleware chaos chỉ bật ở Development: `Chaos:DelayMs`, `Chaos:FailRate` cho từng service | `src/BuildingBlocks/Chaos/ChaosMiddleware.cs` | Đổi cấu hình trong `appsettings.Development.json` | Đặt `DelayMs=3000` thì Inventory trả chậm 3 giây |
| 90 | T5 15/04 | Kịch bản 1: tắt Inventory trên dashboard giữa lúc k6 đang chạy | `docs/notes/s2-failures.md` | `k6 run …`; truy vấn `SELECT status, count(*) FROM orders GROUP BY status` | Ghi được số order kẹt và số `Reserved` bị treo |
| 91 | T7 17/04 | Kịch bản 2: Payment trễ 30 giây; giữ nguyên `AddStandardResilienceHandler` mặc định của ServiceDefaults (timeout mỗi lần 10 s, tổng 30 s, retry 3) và ghi lại hệ quả lên order, payment | `docs/notes/s2-failures.md` | `k6 run …` | Ghi được ca thanh toán thành công nhưng order bị huỷ (nếu có) |
| 92 | CN 18/04 | Kịch bản 3: gửi cùng một checkout 2 lần song song (script nhận tham số chế độ: mặc định `checkout`, S6 thêm `flash`) | `tools/double-submit.sh`, `docs/notes/s2-failures.md` | `./tools/double-submit.sh` | Ghi được 2 order và 2 lần giữ hàng cho cùng một giỏ |

### Tuần 24 · 19/04–25/04/2027

**Mục tiêu tuần:** biến 3 chỗ gãy thành test hồi quy để S3 sửa.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 93 | T3 20/04 | Viết phân tích cho từng kịch bản: hiện tượng, dữ liệu lệch, nguyên nhân gốc, cách S3 sẽ sửa | `docs/notes/s2-failures.md` | (không) | Mỗi kịch bản có đủ 4 mục |
| 94 | T5 22/04 | Test tái hiện kịch bản 3 (đánh dấu Skip "sửa ở S3") | `tests/Ordering.Tests/SyncCheckoutFailureTests.cs` | `dotnet new xunit3 -n Ordering.Tests -o tests/Ordering.Tests`; `dotnet sln add tests/Ordering.Tests`; `dotnet add tests/Ordering.Tests reference tests/TestKit`; `dotnet test` | Bỏ Skip thì test đỏ đúng như mô tả |
| 95 | T7 24/04 | Test tái hiện kịch bản 1 và 2 với client giả lập lỗi | `tests/Ordering.Tests/SyncCheckoutFailureTests.cs`, `StubHandler.cs` | `dotnet test` | Bỏ Skip thì 2 test đỏ |
| 96 | CN 25/04 | Thông báo lỗi trên UI: hết hàng, khách bị khoá, thanh toán lỗi | `apps/storefront/src/app/pages/checkout/` | `npx nx serve storefront` | Ba lỗi hiện đúng thông điệp |

### Tuần 25 · 26/04–02/05/2027

**Mục tiêu tuần:** chạy thử gate S2, sửa lỗi, ghi chú bước.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 97 | T3 27/04 | Chạy thử gate: đăng nhập, thêm giỏ, đặt hàng, xem đơn; admin thấy đơn và kho thay đổi | `http/gate-s2.http` | Chạy `http/gate-s2.http` | Toàn bộ luồng chạy được |
| 98 | T5 29/04 | Sửa lỗi từ lần chạy thử | (tuỳ lỗi) | `dotnet test` | Test xanh |
| 99 | T7 01/05 | Dự phòng (lễ 1/5): làm bù việc đã cắt hoặc còn dở | (tuỳ việc dở) | (tuỳ việc dở) | Không còn việc dở |
| 100 | CN 02/05 | Ghi chú S2: sổ cái, xmin, đồng bộ dễ gãy ở đâu | `docs/notes/s2.md` | (không) | File ghi chú xong |

### Tuần 26 · 03/05–09/05/2027

**Mục tiêu tuần:** qua gate S2 trên môi trường sạch, merge và tag.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 101 | T3 04/05 | Xoá toàn bộ volume, dựng lại từ đầu, kiểm tra seed | (không) | `docker volume rm shoplab-pg shoplab-redis shoplab-keycloak`; `aspire run` (RabbitMQ chưa có ở S2) | Mọi resource xanh, seed đủ |
| 102 | T5 06/05 | Build và test toàn repo | (không) | `dotnet test`; `cd src/Web && npx nx run-many -t build test` | Tất cả xanh |
| 103 | T7 08/05 | Dự phòng | (tuỳ việc dở) | (tuỳ việc dở) | Không còn việc dở |
| 104 | CN 09/05 | Chạy gate S2 lần cuối, merge, tag | `docs/guides/ShopLab-S2.md` (xuất hướng dẫn của bước trước khi merge) | `git checkout main && git merge --no-ff step/s2-sync-ordering`; `git tag s2-done`; `git checkout -b step/s3-event-driven` | Đạt gate S2 |

## S3. Chuyển sang event-driven (tuần 27–39)

Tự viết lớp messaging (Outbox, publisher, consumer host, retry/DLQ, Inbox) trên RabbitMQ, rồi viết lại checkout thành saga có bù trừ, thêm timeout bằng Hangfire và `Idempotency-Key`. Thêm Notification (Mailpit) và cộng điểm khách. **Gate:** 3 kịch bản gãy ở S2 tự hồi phục; dừng RabbitMQ giữa lúc nhập 500 phiếu không mất event; 1.000 checkout với 10% lỗi thanh toán không lệch kho.

### Tuần 27 · 10/05–16/05/2027

**Mục tiêu tuần:** RabbitMQ chạy trong AppHost, có contract event và gửi/nhận được một message thử.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 105 | T3 11/05 | Thêm RabbitMQ + management plugin; lớp giữ một connection dùng chung | `src/BuildingBlocks/Messaging/RabbitMqPublisher.cs` (kết nối do `Aspire.RabbitMQ.Client` quản lý) | `dotnet add src/AppHost package Aspire.Hosting.RabbitMQ`; `dotnet add src/BuildingBlocks package Aspire.RabbitMQ.Client` | Mở được RabbitMQ management |
| 106 | T5 13/05 | Khai báo exchange `ecommerce.events` (topic, durable); base `IntegrationEvent` và 2 event đầu `StockChanged`, `ProductChanged` | `Messaging/RabbitMqPublisher.cs` (`RabbitMqTopology`), `src/Contracts/IntegrationEvent.cs`, `Contracts/Inventory/InventoryEvents.cs`, `Contracts/Catalog/CatalogEvents.cs` | `dotnet build` | Exchange hiện trong management |
| 107 | T7 15/05 | Phong bì message (tên type + payload JSON + header `CorrelationId`), bảng tra type theo tên | `Messaging/EventTypeRegistry.cs` | `dotnet build` | Serialize rồi deserialize một event ra đúng type |
| 108 | CN 16/05 | `RabbitMqSmokeTests`: gửi và nhận thử bằng Testcontainers RabbitMQ | `tests/BuildingBlocks.Tests/RabbitMqSmokeTests.cs` | `dotnet new xunit3 -n BuildingBlocks.Tests -o tests/BuildingBlocks.Tests`; `dotnet sln add tests/BuildingBlocks.Tests`; `dotnet add tests/TestKit package Testcontainers.RabbitMq`; `dotnet add tests/BuildingBlocks.Tests reference tests/TestKit`; `dotnet test` | Message gửi đi nhận lại đúng nội dung |

### Tuần 28 · 17/05–23/05/2027

**Mục tiêu tuần:** Outbox ghi event cùng transaction với dữ liệu nghiệp vụ.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 109 | T3 18/05 | Entity `OutboxMessage` + `InboxMessage`, extension `AddOutboxInbox()` cho `OnModelCreating` | `Messaging/OutboxMessage.cs` | `dotnet build` | Build xanh |
| 110 | T5 20/05 | `IOutbox.Enqueue(evt)` (`EfOutbox`) thêm dòng outbox vào cùng `DbContext`, nên cùng transaction với `SaveChanges` của nghiệp vụ; handler gọi tường minh, không dùng interceptor | `Messaging/Outbox.cs` | `dotnet build` | Build xanh |
| 111 | T7 22/05 | Inventory: thêm bảng outbox, `StockLedger` phát `StockChanged` (tổng available theo SKU) | `src/Services/Inventory.Api/Domain/StockLedger.cs`, migration `AddOutbox` | `./tools/ef-migrations.sh AddOutbox Inventory` | Nhập hàng thì có 1 dòng trong `outbox_messages` |
| 112 | CN 23/05 | `OutboxTests`: rollback thì không có message; commit thì đúng 1 message | `tests/BuildingBlocks.Tests/OutboxTests.cs` | `dotnet test tests/BuildingBlocks.Tests --filter OutboxTests` | Test xanh |

### Tuần 29 · 24/05–30/05/2027

**Mục tiêu tuần:** publisher đẩy outbox lên RabbitMQ an toàn khi chạy nhiều instance và khi bị dừng giữa chừng.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 113 | T3 25/05 | `OutboxPublisher` (BackgroundService): mỗi 500 ms lấy 50 dòng bằng `FOR UPDATE SKIP LOCKED`, publish, đánh dấu `processed_at` | `Messaging/OutboxPublisher.cs` | `aspire run` | Message từ Inventory xuất hiện trong exchange |
| 114 | T5 27/05 | Bật publisher confirm; nack hoặc lỗi thì tăng `attempts`, để lần sau gửi lại | `Messaging/OutboxPublisher.cs` | `aspire run` | Tắt RabbitMQ: dòng outbox giữ nguyên, bật lại thì gửi hết |
| 115 | T7 29/05 | Metric `outbox.pending`, `outbox.lag_seconds`; job dọn dòng đã gửi quá 7 ngày | `Messaging/MessagingTelemetry.cs`, `Messaging/OutboxPublisher.cs` (gồm cả `OutboxCleanup`) | `aspire run` | Thấy 2 metric trên Aspire dashboard |
| 116 | CN 30/05 | Test: 2 publisher chạy song song không gửi trùng; publisher dừng giữa batch thì gửi lại phần còn lại | `tests/BuildingBlocks.Tests/OutboxPublisherTests.cs` | `dotnet test` | Test xanh |

### Tuần 30 · 31/05–06/06/2027

**Mục tiêu tuần:** consumer host có retry, DLQ và Inbox chống xử lý trùng.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 117 | T3 01/06 | `RabbitMqConsumerHost`: mỗi handler một queue `<service>.<handler>`, bind routing key, prefetch, ack thủ công; interface `IEventHandler<T>`; bộ phân loại lỗi tạm thời `ITransientErrorClassifier` (lỗi kết nối Postgres/RabbitMQ retry không giới hạn, không vào DLQ) | `Messaging/RabbitMqConsumerHost.cs`, `Messaging/IEventHandler.cs` | `dotnet build` | Build xanh |
| 118 | T5 03/06 | Retry 3 lần qua queue chờ có TTL rồi quay lại; quá 3 lần vào `<queue>.dlq` | `Messaging/RabbitMqConsumerHost.cs` (khai báo `<q>.retry`, `<q>.dlq`) | `dotnet build` | Build xanh |
| 119 | T7 05/06 | `InboxMessage` (unique `EventId` + `Consumer`), handler và inbox chạy chung transaction | `Messaging/OutboxMessage.cs` (`InboxMessage`), `Messaging/RabbitMqConsumerHost.cs` (inbox EF/Redis) | `dotnet build` | Build xanh |
| 120 | CN 06/06 | `ConsumerHostTests`: event lặp xử lý một lần; handler lỗi 3 lần vào DLQ; lỗi tạm thời thì retry không vào DLQ | `tests/BuildingBlocks.Tests/ConsumerHostTests.cs` | `dotnet test` | Test xanh |

### Tuần 31 · 07/06–13/06/2027

**Mục tiêu tuần:** luồng event thật đầu tiên `StockChanged` → Catalog, và chứng minh không mất event khi RabbitMQ chết.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 121 | T3 08/06 | Catalog: bảng inbox, `StockChangedHandler` cập nhật `InStock`; Catalog phát `ProductChanged` mỗi lần lưu sản phẩm (dùng ở S5) | `src/Services/Catalog.Api/EventHandlers/StockChangedHandler.cs`, migration `AddMessaging` | `./tools/ef-migrations.sh AddMessaging Catalog` | Điều chỉnh tồn về 0 thì storefront hiện "hết hàng" |
| 122 | T5 10/06 | Script tạo 500 phiếu nhập liên tiếp | `tools/receipt-500.sh` | `./tools/receipt-500.sh` | 500 movement mới trong Inventory |
| 123 | T7 12/06 | Chạy thử: dừng RabbitMQ trên dashboard giữa lúc chạy script, đợi 1 phút, bật lại; đếm event Catalog đã xử lý | `docs/notes/s3-outbox.md` | `./tools/receipt-500.sh`; `SELECT count(*) FROM inbox_messages` | Catalog nhận đủ 500, không trùng |
| 124 | CN 13/06 | Dự phòng; xem lại code messaging trước khi dùng cho saga | (tuỳ việc dở) | `dotnet test` | Không còn việc dở |

### Tuần 32 · 14/06–20/06/2027

**Mục tiêu tuần:** checkout tạo order và giữ hàng qua event.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 125 | T3 15/06 | Contract cho saga: `OrderCreated`, `StockReserved`, `StockReservationFailed`, `PaymentRequested`, `PaymentSucceeded`, `PaymentFailed`, `OrderPaid`, `OrderCancelled` (mang đủ lines, total, channel, customerId) | `src/Contracts/Orders/OrderEvents.cs`, `Contracts/Inventory/InventoryEvents.cs`, `Contracts/Payments/PaymentEvents.cs` | `dotnet build` | Build xanh |
| 126 | T5 17/06 | Ordering: entity `CheckoutSagaState`, enum `SagaStep`, bảng outbox + inbox | `src/Services/Ordering.Api/Sagas/CheckoutSagaState.cs`, migration `AddSaga` | `./tools/ef-migrations.sh AddSaga Ordering` | Có bảng `checkout_saga_states` |
| 127 | T7 19/06 | Viết lại `PlaceOrder`: tạo Order `PendingStock` + saga + phát `OrderCreated`, trả `202 {orderId}` | `Features/Checkout/PlaceOrder.cs`, `Features/Checkout/CheckoutService.cs` | Chạy `http/checkout.http` | Nhận 202 ngay, order ở `PendingStock` |
| 128 | CN 20/06 | Inventory: `OrderCreatedHandler` giữ hàng rồi phát `StockReserved` hoặc `StockReservationFailed` | `src/Services/Inventory.Api/EventHandlers/OrderEventHandlers.cs` | `aspire run` | Trace trên dashboard nối Ordering → RabbitMQ → Inventory |

### Tuần 33 · 21/06–27/06/2027

**Mục tiêu tuần:** saga chạy hết luồng thành công và luồng bù trừ.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 129 | T3 22/06 | `CheckoutSaga`: `StockReserved` → `AwaitingPayment` + `PaymentRequested`; `StockReservationFailed` → `Cancelled` + `OrderCancelled` | `Sagas/CheckoutSaga.cs`, `EventHandlers/SagaEventHandlers.cs` | `aspire run` | Đặt SKU hết hàng thì order `Cancelled` |
| 130 | T5 24/06 | Payment: `PaymentRequestedHandler` gọi FakePayment, phát `PaymentSucceeded`/`PaymentFailed`; `OrderId` unique chặn trừ tiền hai lần | `src/Services/Payment.Api/EventHandlers/PaymentRequestedHandler.cs`, migration `AddMessaging` | `./tools/ef-migrations.sh AddMessaging Payment` | Mỗi order đúng 1 bản ghi payment |
| 131 | T7 26/06 | Ordering: `PaymentSucceeded` → `Paid` + `OrderPaid`; `PaymentFailed` → `Cancelled` + `OrderCancelled` | `EventHandlers/SagaEventHandlers.cs` | `aspire run` | Đặt `FailureRate=1` thì order `Cancelled` |
| 132 | CN 27/06 | Inventory: `OrderPaid` → commit reservation đang có của đơn (không có thì bỏ qua), `OrderCancelled` → release, chưa có reservation thì ghi bia mộ để `OrderCreated` tới muộn không giữ hàng; bia mộ là `Reservation` với `Sku = "*"`, `LocationId = Guid.Empty`, `Qty = 0`, `Status = Released`, không đụng `StockLevel.Reserved`, mọi truy vấn hàng đang giữ lọc `Status = Active`; Cart: `OrderPaid` kênh `Online` → xoá giỏ (chống trùng bằng `SETNX` trên Redis) | `Inventory.Api/EventHandlers/OrderEventHandlers.cs` (`OrderPaid` commit, `OrderCancelled` release), `Cart.Api/EventHandlers/OrderPaidHandler.cs`, `Domain/Reservation.cs` (`Tombstone`), `tests/Inventory.Tests/CancelBeforeCreateTests.cs` | `aspire run` | Order huỷ thì `Reserved` về đúng như trước |

### Tuần 34 · 28/06–04/07/2027

**Mục tiêu tuần:** order không thanh toán tự huỷ; gửi lại cùng request không tạo order trùng.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 133 | T3 29/06 | Hangfire trong Ordering, lưu ở schema `hangfire` của `orderingdb`; dashboard `/hangfire` chỉ cho admin | `src/Services/Ordering.Api/Program.cs`, `Jobs/HangfireDashboardAuth.cs` | `dotnet add src/Services/Ordering.Api package Hangfire.AspNetCore`; `dotnet add src/Services/Ordering.Api package Hangfire.PostgreSql` | Mở được dashboard Hangfire |
| 134 | T5 01/07 | Job định kỳ `ExpireUnpaidOrdersJob` (Hangfire, mỗi phút) huỷ đơn quá hạn thanh toán (mặc định 15 phút, `Checkout:PaymentDeadlineSeconds = 900`); tiền tới muộn sau khi đơn đã huỷ thì hoàn tiền | `Jobs/ExpireUnpaidOrdersJob.cs`, `Sagas/CheckoutSaga.cs` (`ExpireUnpaidAsync`) | Đặt deadline 30 giây trong `appsettings.Development.json` | Order kẹt tự huỷ sau 30 giây, kho được trả |
| 135 | T7 03/07 | `IdempotencyFilter` trên Redis: khoá `idem:{user}:{key}`, lưu response 24 giờ, cùng khoá đang xử lý thì trả 409; thêm lớp chặn ở DB: `Order.IdempotencyKey` unique (lọc NOT NULL) — dùng cả hai | `src/BuildingBlocks/Idempotency/IdempotencyFilter.cs` | `./tools/double-submit.sh` | Gửi đôi chỉ tạo 1 order |
| 136 | CN 04/07 | Storefront: gửi `Idempotency-Key` khi đặt hàng, hỏi trạng thái order mỗi giây tới khi `Paid`/`Cancelled` | `apps/storefront/src/app/pages/checkout/`, `pages/order-result/` | `npx nx serve storefront` | Trang kết quả chuyển từ "đang xử lý" sang "đã thanh toán" |

### Tuần 35 · 05/07–11/07/2027

**Mục tiêu tuần:** test tích hợp cho mọi nhánh của saga.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 137 | T3 06/07 | `OrderingTestContext`: database Ordering riêng trên Postgres container, `FakeTimeProvider`, `StubHandler` giả Cart/Catalog/Customer; `StepAsync` chạy từng bước saga như consumer host (mở scope, gọi handler, `SaveChanges`) | `tests/Ordering.Tests/OrderingFixture.cs`, `tests/Ordering.Tests/StubHandler.cs` | `dotnet build tests/Ordering.Tests` | `PlaceAsync()` tạo được order `PendingStock`, outbox có `OrderCreated` |
| 138 | T5 08/07 | Luồng thành công: `StockReserved` → `PaymentRequested`; `PaymentSucceeded` → order `Paid`, outbox có `OrderPaid` (Inventory commit và Cart xoá giỏ đã có test riêng ở service của mình) | `tests/Ordering.Tests/CheckoutSagaTests.cs` | `dotnet test tests/Ordering.Tests --filter CheckoutSagaTests` | Test xanh |
| 139 | T7 10/07 | Hết hàng và thanh toán lỗi: order `Cancelled`, saga `Compensated`, outbox có `OrderCancelled` (Inventory nhận event này thì trả `Reserved` về 0, test ở `Inventory.Tests`); event lặp bị bỏ qua | `tests/Ordering.Tests/CheckoutSagaTests.cs` | `dotnet test tests/Ordering.Tests --filter CheckoutSagaTests` | Test xanh |
| 140 | CN 11/07 | Quá hạn và tiền tới muộn: `ExpireUnpaidAsync` huỷ đơn; `PaymentSucceeded` tới sau khi huỷ thì saga phát `PaymentRefundRequested`; Payment chỉ nghe event này (không nghe `OrderCancelled`) và chuyển `Refunded` | `tests/Ordering.Tests/CheckoutRecoveryTests.cs`, `Payment.Api/EventHandlers/PaymentEventHandlers.cs` (`PaymentRefundRequestedHandler`) | `dotnet test tests/Ordering.Tests --filter CheckoutRecoveryTests` | Thanh toán đến muộn sau khi huỷ được hoàn tiền |

### Tuần 36 · 12/07–18/07/2027

**Mục tiêu tuần:** gửi email xác nhận và cộng điểm khi order thanh toán.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 141 | T3 13/07 | Mailpit trong AppHost; project Notification.Worker dùng consumer host | `src/AppHost/AppHost.cs`, `src/Services/Notification.Worker/Program.cs` | `dotnet new worker -n Notification.Worker -o src/Services/Notification.Worker`; `dotnet sln add src/Services/Notification.Worker`; `dotnet add src/Services/Notification.Worker reference src/BuildingBlocks src/ServiceDefaults`; `dotnet add src/Services/Notification.Worker package MailKit` | Mở được Mailpit UI |
| 142 | T5 15/07 | Template Liquid, `OrderPaidHandler` gửi email; chống trùng bằng khoá Redis `inbox:notification:{eventId}` | `Templates/order-paid.liquid`, `Handlers/OrderPaidHandler.cs` | `dotnet add src/Services/Notification.Worker package Fluid.Core` | Đặt hàng thì Mailpit có email |
| 143 | T7 17/07 | Customer: `OrderPaidHandler` cộng 1 điểm mỗi 10.000 ₫, cập nhật hạng (Silver từ 500 điểm, Gold từ 1.000 điểm) | `src/Services/Customer.Api/EventHandlers/OrderPaidHandler.cs`, migration `AddMessaging` | `./tools/ef-migrations.sh AddMessaging Customer` | Đơn 554.000 ₫ cộng 55 điểm |
| 144 | CN 18/07 | Storefront: trang hồ sơ hiện điểm và hạng | `apps/storefront/src/app/pages/profile/` | `npx nx serve storefront` | Thấy điểm tăng sau khi đặt hàng |

### Tuần 37 · 19/07–25/07/2027

**Mục tiêu tuần:** chạy lại 3 kịch bản gãy của S2 và chứng minh hệ thống tự hồi phục.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 145 | T3 20/07 | Thay `SyncCheckoutFailureTests` bằng `CheckoutSagaTests` + `CheckoutRecoveryTests` (hết hàng, thanh toán lỗi, event lặp, quá hạn, tiền tới muộn); xoá test đồng bộ cũ | `tests/Ordering.Tests/CheckoutSagaTests.cs`, `CheckoutRecoveryTests.cs`, `OrderingFixture.cs`, `tests/Payment.Tests/PaymentHandlerTests.cs` (`PaymentRequested` lặp không trừ tiền hai lần, `PaymentRefundRequested` → `Refunded`) | `dotnet new xunit3 -n Payment.Tests -o tests/Payment.Tests`; `dotnet sln add tests/Payment.Tests`; `dotnet add tests/Payment.Tests reference tests/TestKit`; `dotnet test` | Các test saga và test Payment xanh |
| 146 | T5 22/07 | Kịch bản 1: tắt Inventory giữa lúc k6 chạy, đợi 2 phút, bật lại | `docs/notes/s2-failures.md` (thêm cột "sau S3") | `k6 run …` | Không order nào kẹt sau khi Inventory bật lại |
| 147 | T7 24/07 | Kịch bản 2: Payment trễ 30 giây | `docs/notes/s2-failures.md` | `k6 run …` | Order hoặc `Paid` hoặc huỷ + hoàn tiền, không có trạng thái lệch |
| 148 | CN 25/07 | Kịch bản 3: gửi đôi | `docs/notes/s2-failures.md` | `./tools/double-submit.sh` | Đúng 1 order |

### Tuần 38 · 26/07–01/08/2027

**Mục tiêu tuần:** 1.000 checkout với 10% lỗi thanh toán không lệch kho, so sánh với baseline S2.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 149 | T3 27/07 | Sửa k6 cho luồng 202 + hỏi trạng thái; thêm kịch bản 1.000 checkout | `load/checkout-normal.js`, `load/checkout-1000.js` | `k6 run --vus 1 --iterations 1 load/checkout-1000.js` | Chạy thử 1 vòng không lỗi |
| 150 | T5 29/07 | Chạy 1.000 checkout với `FailureRate=0.1`; SQL đối chiếu `Reserved` với reservation `Active` | `tools/sql/check-reservations.sql` | `k6 run load/checkout-1000.js`; `psql -f tools/sql/check-reservations.sql` | Lệch = 0; không order nào kẹt quá 15 phút |
| 151 | T7 31/07 | So với baseline S2: p95, lỗi, kết nối DB | `docs/benchmarks/s3.md` | `k6 run --summary-export …` | Bảng so sánh có đủ số |
| 152 | CN 01/08 | Kiểm tra DLQ trống, theo dõi outbox lag trong lúc chạy | `docs/benchmarks/s3.md` | Xem RabbitMQ management và Aspire dashboard | DLQ = 0, ghi được outbox lag tối đa |

### Tuần 39 · 02/08–08/08/2027

**Mục tiêu tuần:** qua gate S3, ghi chú bước.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 153 | T3 03/08 | Chạy thử toàn bộ gate S3 | `http/gate-s3.http` | `dotnet test`; `k6 run load/checkout-1000.js` | Đạt đủ 3 điều kiện gate |
| 154 | T5 05/08 | Sửa lỗi từ lần chạy thử | (tuỳ lỗi) | `dotnet test` | Test xanh |
| 155 | T7 07/08 | Ghi chú S3: Outbox, Inbox, retry/DLQ, saga, những gì ABP từng làm hộ | `docs/notes/s3.md` | (không) | File ghi chú xong |
| 156 | CN 08/08 | Merge, tag | `docs/guides/ShopLab-S3.md` (xuất hướng dẫn của bước trước khi merge) | `git checkout main && git merge --no-ff step/s3-event-driven`; `git tag s3-done`; `git checkout -b step/s4-discount` | Tag `s3-done` có trên `main` |

## S4. Discount (tuần 40–46)

Engine tính giá là một hàm thuần (đầu vào giỏ + kênh + lịch sử dùng coupon, đầu ra bảng giảm giá), nên viết test trước rồi mới viết code. Sau đó nối vào Cart, Ordering và saga. **Gate:** 12 test case tính giá đúng từng đồng; 1.000 checkout của S3 vẫn xanh.

### Tuần 40 · 09/08–15/08/2027

**Mục tiêu tuần:** Discount.Api có dữ liệu, 12 test case đã viết sẵn (đang đỏ).

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 157 | T3 10/08 | Project Discount.Api, nối `discountdb`; entity `Promotion`, `Coupon`, `CouponRedemption` | `src/Services/Discount.Api/Domain/*.cs`, `Data/DiscountDbContext.cs`, `src/AppHost/AppHost.cs` | `python3 tools/new-service.py Discount 5107`; `dotnet sln add src/Services/Discount.Api` | Service xanh trên dashboard |
| 158 | T5 12/08 | Migration; seed 7 khuyến mãi (3 tự động, 3 gắn coupon, 1 đã hết hạn) và 3 coupon `WELCOME50K`, `GIAM100K`, `LAST5` từ `seed/promotions.json` | `Data/Migrations/`, `seed/promotions.json`, `Data/SeedData.cs` | `./tools/ef-migrations.sh Init Discount` | Bảng có 7 dòng `promotions`, 3 dòng `coupons` |
| 159 | T7 14/08 | File 12 test case và test `[Theory]` đọc từ JSON | `seed/pricing-cases.json` (C01–C12), `tests/Discount.Tests/PricingEngineTests.cs` | `dotnet new xunit3 -n Discount.Tests -o tests/Discount.Tests`; `dotnet sln add tests/Discount.Tests`; `dotnet add tests/Discount.Tests reference tests/TestKit`; `dotnet test` | 12 test chạy được (đang đỏ) |
| 160 | CN 15/08 | Kiểu dữ liệu của engine: `PricingInput`, `PricingLine`, `PricingResult`, `AppliedDiscount`, mã lỗi coupon | `Pricing/PricingModels.cs`, `Pricing/PricingEngine.cs` (khung) | `dotnet build` | Build xanh |

### Tuần 41 · 16/08–22/08/2027

**Mục tiêu tuần:** engine tính đúng 12 case.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 161 | T3 17/08 | Pha dòng: `PercentOff`/`AmountOff` theo scope `Category`/`Sku`, chặn `MaxDiscount`; pha đơn: scope `Order` tính trên phần còn lại, `MinSubtotal` của khuyến mãi đơn cũng xét trên phần còn lại sau giảm dòng (ca C03 kiểm) | `Pricing/PricingEngine.cs` | `dotnet test` | C01–C05 xanh |
| 162 | T5 19/08 | `BuyXGetY`: mỗi nhóm X+Y cái tặng Y cái rẻ nhất (seed: sổ tay mua 2 tặng 1) | `Pricing/PricingEngine.cs` | `dotnet test` | C06 xanh |
| 163 | T7 21/08 | Coupon trong engine (luôn áp, mã lỗi `COUPON_MIN_SUBTOTAL`…); `CouponService.CheckAsync` kiểm kênh, thời hạn, `UsageLimit`, `PerCustomerLimit` (`COUPON_EXPIRED`, `COUPON_USED_UP`, `COUPON_PER_CUSTOMER_LIMIT`, `COUPON_NOT_FOUND`) | `Pricing/PricingEngine.cs`, `Services/CouponService.cs` (`CheckAsync`) | `dotnet test` | C10, C11 xanh |
| 164 | CN 22/08 | Luật cộng dồn: mỗi pha lấy bên lớn hơn giữa khuyến mãi độc quyền tốt nhất và tổng các khuyến mãi cộng dồn; phân bổ giảm giá đơn về từng dòng theo phần dư lớn nhất | `Pricing/PricingEngine.cs` | `dotnet test` | Cả 12 case xanh |

### Tuần 42 · 23/08–29/08/2027

**Mục tiêu tuần:** API báo giá có cache, admin sửa được khuyến mãi qua API.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 165 | T3 24/08 | `POST /internal/quote`: nhận giỏ + kênh + coupon + khách, `QuoteService` lấy khuyến mãi từ cache rồi gọi engine; `CouponService` đọc số lần khách đã dùng từ DB | `Features/Quote/QuoteEndpoints.cs`, `Services/QuoteService.cs` | Chạy `http/discount.http` | Gửi giỏ của C09 trả đúng 640.800 |
| 166 | T5 26/08 | Cache danh sách khuyến mãi trên Redis (`discount:promotions:v1`, TTL 60 giây), xoá cache khi admin ghi | `Services/PromotionCache.cs` | (không, `Aspire.StackExchange.Redis` có sẵn qua BuildingBlocks) | Lần gọi thứ 2 không truy vấn DB (xem trace) |
| 167 | T7 28/08 | API admin: CRUD promotion và coupon, bật/tắt, xoá mềm | `Features/Admin/AdminPromotions.cs`, `Features/Admin/AdminCoupons.cs`, `yarp.json` | Chạy `http/discount.http` | Sửa promotion thì báo giá đổi ngay |
| 168 | CN 29/08 | Test API báo giá, API admin và việc xoá cache | `tests/Discount.Tests/DiscountApiTests.cs` | `dotnet test` | Test xanh |

### Tuần 43 · 30/08–05/09/2027

**Mục tiêu tuần:** giảm giá đi vào giỏ, đơn hàng và saga; lượt dùng coupon không vượt giới hạn.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 169 | T3 31/08 | Cart: `PUT /cart/coupon`, `DELETE /cart/coupon`; `GET /cart` trả kèm báo giá (`CartPricing`), Discount lỗi thì trả giỏ với `pricingUnavailable` | `src/Services/Cart.Api/Features/CartEndpoints.cs`, `Features/CartPricing.cs`, `Clients/DiscountClient.cs` | Chạy `http/cart.http` | Giỏ hiện dòng giảm giá |
| 170 | T5 02/09 | Ordering: báo giá lúc checkout, lưu `LineDiscount`, `DiscountTotal` vào order; `OrderCreated` mang `couponCode` | `src/Services/Ordering.Api/Features/Checkout/CheckoutService.cs`, `src/Contracts/Orders/OrderEvents.cs` | Chạy `http/checkout.http` | Order lưu đúng số tiền giảm |
| 171 | T7 04/09 | Discount nghe `OrderCreated`: trừ lượt bằng `UPDATE … WHERE id = @id AND (usage_limit IS NULL OR used_count < usage_limit)` rồi kiểm lượt của khách, phát `CouponRedeemed` hoặc `CouponRedemptionFailed`; saga chờ cả `StockReserved` và `CouponRedeemed` mới đòi tiền, thất bại thì huỷ order | `Discount.Api/EventHandlers/OrderEventHandlers.cs`, `Ordering.Api/EventHandlers/SagaEventHandlers.cs`, `Sagas/CheckoutSaga.cs`, `Sagas/CheckoutSagaState.cs` | `./tools/ef-migrations.sh AddMessaging Discount` | `WELCOME50K` (không giới hạn tổng) luôn trừ được; `CouponRedemptionTests`: 20 đơn tranh `LAST5` (5 lượt) ra đúng 5 |
| 172 | CN 05/09 | Discount nghe `OrderCancelled`: hoàn lượt dùng (chưa trừ thì ghi "bia mộ" để lần trừ tới sau bị bỏ qua); test cho cả hai handler và saga có coupon | `EventHandlers/OrderEventHandlers.cs`, `tests/Discount.Tests/CouponRedemptionTests.cs`, `tests/Ordering.Tests/CouponSagaTests.cs` | `dotnet test` | Order huỷ thì `used_count` trở lại như cũ |

### Tuần 44 · 06/09–12/09/2027

**Mục tiêu tuần:** khách nhập coupon và thấy giảm giá trên storefront.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 173 | T3 07/09 | Ô nhập coupon ở trang giỏ, bảng chi tiết giảm giá, thông báo lỗi theo mã | `apps/storefront/src/app/pages/cart/coupon-box.component.ts` | `npx nx serve storefront` | Nhập `WELCOME50K` với giỏ 199.000 thấy lỗi "chưa đủ giá trị đơn" |
| 174 | T5 09/09 | Trang checkout và chi tiết đơn hiện các dòng giảm giá | `pages/checkout/`, `pages/order-detail/` | `npx nx serve storefront` | Số tiền khớp với giỏ |
| 175 | T7 11/09 | Nhãn khuyến mãi trên danh sách sản phẩm (có thể cắt) | `pages/product-list/` | `npx nx serve storefront` | Sản phẩm thời trang có nhãn "-20%" |
| 176 | CN 12/09 | Chạy tay C01, C06, C09 qua UI (dùng khuyến mãi seed tương ứng; không chạy C04 vì seed còn khuyến mãi đơn 10% áp thêm) | (không) | `npx nx serve storefront` | Ba tổng tiền đúng bảng |

### Tuần 45 · 13/09–19/09/2027

**Mục tiêu tuần:** admin quản lý khuyến mãi và coupon.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 177 | T3 14/09 | Danh sách + form promotion (loại, phạm vi, kênh, điều kiện, thời gian) | `apps/admin/src/app/pages/promotions/` | `npx nx serve admin` | Tạo promotion mới từ UI |
| 178 | T5 16/09 | Danh sách + form coupon, xem lịch sử lượt dùng | `pages/coupons/` | `npx nx serve admin` | Đặt một đơn với `WELCOME50K` rồi thấy redemption của khách đó |
| 179 | T7 18/09 | Bật/tắt, xoá mềm promotion và coupon | `pages/promotions/`, `pages/coupons/` | `npx nx serve admin` | Tắt "Thời trang giảm 20%" trong admin thì giỏ 1 áo 199.000 không còn giảm 39.800 |
| 180 | CN 19/09 | Dự phòng | (tuỳ việc dở) | (tuỳ việc dở) | Không còn việc dở |

### Tuần 46 · 20/09–26/09/2027

**Mục tiêu tuần:** qua gate S4.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 181 | T3 21/09 | Viết `tools/coupon-race.sh` (20 đơn song song cùng dùng `LAST5` qua gateway, đếm redemption); chạy 12 ca, kịch bản 1.000 checkout và bài coupon | `tools/coupon-race.sh` | `dotnet test`; `k6 run load/checkout-1000.js`; `./tools/coupon-race.sh` | Cả ba xanh; `LAST5` có đúng 5 redemption |
| 182 | T5 23/09 | Sửa lỗi | (tuỳ lỗi) | `dotnet test` | Test xanh |
| 183 | T7 25/09 | Ghi chú S4: engine thuần, race của coupon, cache | `docs/notes/s4.md` | (không) | File ghi chú xong |
| 184 | CN 26/09 | Merge, tag | `docs/guides/ShopLab-S4.md` (xuất hướng dẫn của bước trước khi merge) | `git checkout main && git merge --no-ff step/s4-discount`; `git tag s4-done`; `git checkout -b step/s5-read-model` | Tag `s4-done` có trên `main` |

## S5. Read model MongoDB (tuần 47–53)

Một replica set `rs0` 3 node dùng chung; Catalog, Ordering và Bff.Admin mỗi bên một database và user riêng. Projection idempotent theo `Version`, ghi `w: majority`, lỗi tạm thời của Mongo thì retry chứ không đẩy vào DLQ. **Gate:** xoá `catalog_read`, rebuild, dữ liệu khớp 100% với Postgres; có số đo p95 trang danh sách trước và sau.

### Tuần 47 · 27/09–03/10/2027

**Mục tiêu tuần:** replica set 3 node chạy trong AppHost, mỗi bên có user riêng.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 185 | T3 28/09 | 3 container `mongo:8` chạy `--replSet rs0`, cổng 27017/27018/27019, mỗi node một volume | `src/AppHost/AppHost.cs` | `aspire run` | 3 container xanh |
| 186 | T5 30/09 | Container khởi tạo chạy `rs.initiate` một lần; tên host phân giải được từ cả container lẫn máy host (Linux thêm `--add-host host.docker.internal:host-gateway`) | `docker/mongo/init-replset.sh`, `docker/mongo/init-replset.js`, `src/AppHost/AppHost.cs` | `mongosh "mongodb://localhost:27017/?replicaSet=rs0" --eval "rs.status()"` | 1 PRIMARY, 2 SECONDARY |
| 187 | T7 02/10 | Mỗi bên một database riêng (`catalog_read`, `ordering_read`, `admin_read`), dùng chung connection string trong AppHost; lab không bật auth cho Mongo (replica set bật auth cần keyFile, để bài tập mở rộng) | `docker/mongo/init-replset.js`, `src/AppHost/AppHost.cs` (extension `WithMongo`) | `mongosh "mongodb://localhost:27017/?replicaSet=rs0" --eval "db.adminCommand('listDatabases')"` | Ba database xuất hiện sau lần ghi đầu của từng service |
| 188 | CN 03/10 | Thử tắt node primary, xem bầu lại; ghi các vấn đề tên host đã gặp | `docs/notes/s5-replset.md` | `docker stop <mongo1>`; `mongosh … --eval "rs.status()"` | Có primary mới trong vài giây |

### Tuần 48 · 04/10–10/10/2027

**Mục tiêu tuần:** projection Catalog đúng cả khi event lặp, đến sai thứ tự, hay sản phẩm bị xoá.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 189 | T3 05/10 | `ProductDocument` (có cờ `visible`, `searchText`), `ProductReadStore` ghi với `WriteConcern.WMajority`, tạo index khi khởi động | `src/Services/Catalog.Api/ReadModel/ProductDocument.cs`, `ReadModel/ProductReadStore.cs`, `src/BuildingBlocks/ReadModel/MongoExtensions.cs` | `dotnet add src/BuildingBlocks package MongoDB.Driver` | Collection `products` có 2 index |
| 190 | T5 07/10 | `ProductProjectionHandler`: nghe `ProductChanged` → đọc lại từ Postgres → `UpsertIfNewer` (lọc `Version` nhỏ hơn, upsert, bỏ qua lỗi duplicate key); bản xoá hoặc tắt thì ghi `visible = false`; sửa danh mục thì phát lại `ProductChanged` cho sản phẩm trong đó | `EventHandlers/ProductProjectionHandler.cs`, `src/BuildingBlocks/ReadModel/MongoProjection.cs`, `Features/Categories/UpdateCategory.cs` | `aspire run` | Sửa giá trong admin, document Mongo đổi theo |
| 191 | T7 09/10 | Bổ sung lỗi Mongo (mất kết nối, đang bầu primary) vào bộ phân loại lỗi tạm thời có từ S3: retry có backoff, không vào DLQ | `src/BuildingBlocks/Messaging/IEventHandler.cs` (`ITransientErrorClassifier`), `RabbitMqConsumerHost.cs` | `dotnet build` | Build xanh |
| 192 | CN 10/10 | `ProductProjectionTests`: lặp 2 lần, sai thứ tự, xoá mềm, tắt `IsActive` | `tests/Catalog.Tests/ProductProjectionTests.cs`, `tests/TestKit/MongoFixture.cs` | `dotnet add tests/TestKit package Testcontainers.MongoDb`; `dotnet test` | 4 test xanh |

### Tuần 49 · 11/10–17/10/2027

**Mục tiêu tuần:** storefront đọc Catalog từ Mongo, giữ nguyên contract API, có số đo so sánh.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 193 | T3 12/10 | `SearchProducts` đọc Mongo khi `ReadModel:Products = mongo` (AppHost bật, Mongo lỗi thì quay về Postgres); `searchText` bỏ dấu tiếng Việt khi ghi | `Features/Products/SearchProducts.cs`, `ReadModel/ProductReadStore.cs` (dùng `Slugs.RemoveDiacritics`) | `aspire run` | Gõ "binh" ra "Bình giữ nhiệt" |
| 194 | T5 14/10 | Kiểm storefront khi bật và tắt cờ; chi tiết sản phẩm (`GetProduct`) và API admin vẫn đọc Postgres | (không) | `npx nx serve storefront` | Storefront chạy như cũ |
| 195 | T7 16/10 | k6 duyệt sản phẩm, chạy hai lần: cờ tắt và cờ bật | `load/browse.js` | `k6 run load/browse.js` | Có số p95 cho cả hai |
| 196 | CN 17/10 | Ghi kết quả, kèm giải thích khi nào Mongo không nhanh hơn | `docs/benchmarks/s5-catalog.md` | (không) | File benchmark xong |

### Tuần 50 · 18/10–24/10/2027

**Mục tiêu tuần:** "đơn của tôi" đọc từ Mongo, chi tiết đơn vẫn đọc Postgres để thấy ngay sau checkout.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 197 | T3 19/10 | `OrderDocument` (đơn + dòng + số món ghép sẵn); Ordering phát `OrderStatusChanged` mỗi lần đổi trạng thái, `OrderProjectionHandler` nghe chính event đó và `UpsertIfNewer` | `src/Services/Ordering.Api/ReadModel/OrderReadStore.cs` (gồm `OrderDocument`), `EventHandlers/OrderProjectionHandler.cs` | (không, `MongoDB.Driver` có sẵn qua BuildingBlocks) | Mỗi order có document, `status` đổi theo từng bước của saga |
| 198 | T5 21/10 | "Đơn của tôi" (`GET /orders`) đọc Mongo khi `ReadModel:MyOrders = mongo`, lỗi thì quay về Postgres; admin vẫn đọc Postgres | `Features/Orders/MyOrders.cs`, `ReadModel/OrderReadStore.cs` | `aspire run` | Bật và tắt cờ ra cùng danh sách; trace cho thấy truy vấn đi Mongo khi bật |
| 199 | T7 23/10 | Chi tiết đơn ngay sau checkout vẫn đọc Postgres | `Features/Orders/MyOrders.cs` (`GET /orders/{id}` vẫn đọc Postgres) | `npx nx serve storefront` | Đặt hàng xong mở chi tiết luôn thấy đơn |
| 200 | CN 24/10 | Test projection Ordering | `tests/Ordering.Tests/OrderProjectionTests.cs` | `dotnet test` | Test xanh |

### Tuần 51 · 25/10–31/10/2027

**Mục tiêu tuần:** Bff.Admin có projection cho dashboard; Gateway.Web chuyển riêng route dashboard sang Bff.Admin.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 201 | T3 26/10 | Project Bff.Admin chỉ phục vụ dashboard; Gateway.Web thêm route `/api/admin/dashboard/**` sang Bff.Admin, các route admin khác giữ nguyên | `src/Gateways/Bff.Admin/Program.cs`, `src/Gateways/Gateway.Web/yarp.json` (route `dashboard-admin`), `src/AppHost/AppHost.cs` | `python3 tools/new-service.py Bff.Admin 5201 --gateway`; `dotnet sln add src/Gateways/Bff.Admin`; `dotnet add src/Gateways/Bff.Admin reference src/BuildingBlocks src/ServiceDefaults` | `GET /api/admin/dashboard/summary` qua Gateway.Web tới được Bff.Admin, admin app chạy như cũ |
| 202 | T5 28/10 | `daily_sales`, `sku_sales` cộng dồn từ `OrderPaid`; `OrderCancelled` chỉ tăng bộ đếm đơn huỷ theo ngày (không trừ doanh thu, vì không có chuyển `Paid` → `Cancelled`); chống cộng hai lần bằng `MongoInbox` (collection `inbox`) trong cùng transaction Mongo | `Dashboard/DashboardProjector.cs`, `Dashboard/DashboardDocuments.cs`, `Handlers/DashboardHandlers.cs`, `src/BuildingBlocks/ReadModel/MongoProjection.cs` (`MongoInbox`), `tests/BffAdmin.Tests/DashboardProjectionTests.cs` | `dotnet new xunit3 -n BffAdmin.Tests -o tests/BffAdmin.Tests`; `dotnet sln add tests/BffAdmin.Tests`; `dotnet add tests/BffAdmin.Tests reference tests/TestKit`; `dotnet test tests/BffAdmin.Tests` | Phát lại một event không làm doanh thu tăng |
| 203 | T7 30/10 | Collection `stock` từ `StockChanged` (ghi đè theo SKU), dashboard lọc dưới ngưỡng | `Handlers/DashboardHandlers.cs` (`StockChangedHandler`), `Dashboard/DashboardProjector.cs` | `aspire run` | Điều chỉnh tồn dưới ngưỡng thì SKU xuất hiện |
| 204 | CN 31/10 | `GET /admin/dashboard/summary` gộp doanh thu theo ngày, top SKU, tồn thấp + projection lag | `Features/DashboardEndpoints.cs` | Chạy `http/bff-admin.http` | Trả đủ 4 phần |

### Tuần 52 · 01/11–07/11/2027

**Mục tiêu tuần:** rebuild được mọi read model khi hệ thống đang chạy.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 205 | T3 02/11 | Catalog rebuild: ghi vào `products_rebuild`, tạo index, `renameCollection` với `dropTarget`; `GET /admin/read-model/compare` so số lượng Postgres với Mongo | `src/Services/Catalog.Api/Features/ReadModel/ReadModelAdmin.cs` | `curl -X POST <catalog>/admin/read-model/rebuild` | Rebuild trong lúc k6 duyệt không lỗi |
| 206 | T5 04/11 | Ordering rebuild (`POST /admin/read-model/rebuild`); endpoint xuất `GET /internal/orders/finished?after=&size=` cho Bff.Admin | `Ordering.Api/Features/Admin/OrderReadModelAdmin.cs`, `Features/Internal/FinishedOrders.cs` | Chạy `http/ordering.http` | Xuất được toàn bộ order theo trang |
| 207 | T7 06/11 | Bff.Admin rebuild từ endpoint xuất của Ordering | `src/Gateways/Bff.Admin/Features/DashboardEndpoints.cs` (`POST /admin/dashboard/rebuild`), `Dashboard/OrderingClient.cs` | `curl -X POST <bff-admin>/admin/dashboard/rebuild` | Doanh thu sau rebuild bằng trước rebuild |
| 208 | CN 07/11 | Script so Postgres với Mongo: số lượng + hash từng document | `tools/compare-catalog.sh` | `./tools/compare-catalog.sh` | Báo khớp 100% |

### Tuần 53 · 08/11–14/11/2027

**Mục tiêu tuần:** dashboard admin trên UI, qua gate S5.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 209 | T3 09/11 | Trang dashboard: doanh thu theo ngày, top SKU, tồn thấp, projection lag | `apps/admin/src/app/pages/dashboard/` | `npx nx serve admin` | Dashboard hiện số liệu thật |
| 210 | T5 11/11 | Gate: xoá `catalog_read`, rebuild, so sánh | (không) | `mongosh … --eval "db.getSiblingDB('catalog_read').dropDatabase()"`; `curl -X POST <catalog>/admin/read-model/rebuild`; `./tools/compare-catalog.sh` | Khớp 100% |
| 211 | T7 13/11 | Ghi chú S5: projection, version, write concern, đọc primary hay secondary | `docs/notes/s5.md` | (không) | File ghi chú xong |
| 212 | CN 14/11 | Merge, tag | `docs/guides/ShopLab-S5.md` (xuất hướng dẫn của bước trước khi merge) | `git checkout main && git merge --no-ff step/s5-read-model`; `git tag s5-done`; `git checkout -b step/s6-flash-sale` | Tag `s5-done` có trên `main` |

## S6. Flash sale (tuần 54–68)

Làm bản naive trên Postgres trước và đo, rồi mới làm bản Redis + Lua + queue, phòng chờ, token, SignalR. Kịch bản chuẩn: campaign `LAB-1111`, 5.000 user ảo, 3 SKU, tổng quota 900. **Gate:** 0 oversell, 0 user vượt giới hạn, p95 `/buy` < 150 ms, p95 trang catalog < 300 ms trong lúc sale, đủ 4 bài diễn tập sự cố.

### Tuần 54 · 15/11–21/11/2027

**Mục tiêu tuần:** FlashSale.Api có campaign mẫu và một endpoint mua kiểu naive.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 213 | T3 16/11 | Project FlashSale.Api, nối `flashsaledb` và Redis; entity `Campaign`, `CampaignItem`, `FlashPurchase`; migration | `src/Services/FlashSale.Api/Domain/*.cs`, `Data/FlashSaleDbContext.cs`, `src/AppHost/AppHost.cs` | `python3 tools/new-service.py FlashSale 5108`; `dotnet sln add src/Services/FlashSale.Api`; `./tools/ef-migrations.sh Init FlashSale` | Service xanh trên dashboard |
| 214 | T5 18/11 | Seed campaign `LAB-1111` với 3 item; API admin tạo campaign và item | `seed/flash-campaigns.json`, `Features/Admin/CreateCampaign.cs`, `AddCampaignItem.cs` | Chạy `http/flash.http` | Có campaign `Draft` với 3 item |
| 215 | T7 20/11 | Bản naive `POST /flash/{camp}/buy-naive`: giữ quota bằng `UPDATE campaign_items SET sold = sold + @q WHERE campaign_id = @c AND sku = @s AND sold + @q <= quota` (cột `Sold` chỉ cho bản naive), giới hạn mỗi user bằng `SUM`, ghi `FlashPurchase` rồi phát `FlashReservationCreated` qua outbox để Ordering tạo đơn như bản thật | `Features/Naive/BuyNaive.cs`, `Domain/CampaignItem.cs` (`Sold`) | Chạy `http/flash.http` | Mua 1 lần thành công |
| 216 | CN 21/11 | SQL kiểm tra oversell và vượt giới hạn mỗi user | `tools/sql/check-flash.sql` | `psql -f tools/sql/check-flash.sql` | Trả 0 dòng vi phạm với dữ liệu thử |

### Tuần 55 · 22/11–28/11/2027

**Mục tiêu tuần:** đo bản naive dưới tải và hiểu vì sao nó gãy.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 217 | T3 23/11 | Kịch bản k6 hai nhóm: `buyers` (ramping-arrival-rate tới 3.000/giây) và `browsers` (50/giây) | `load/flash-sale.js` | `k6 run -e MODE=naive --duration 10s load/flash-sale.js` | Chạy thử 10 giây không lỗi script |
| 218 | T5 25/11 | Chạy đủ kịch bản bản naive; thu p95, lỗi, số kết nối, sự kiện chờ khoá | `docs/benchmarks/s6-naive.md` | `k6 run -e MODE=naive load/flash-sale.js`; `SELECT wait_event, count(*) FROM pg_stat_activity GROUP BY 1` | Có bảng số liệu |
| 219 | T7 27/11 | Phân tích khoá: `pg_locks` trên hàng `stock_levels` nóng, connection pool cạn, chạy `check-flash.sql` | `docs/benchmarks/s6-naive.md` | `psql -f tools/sql/check-flash.sql` | Ghi được có oversell hay không và nguyên nhân chậm |
| 220 | CN 28/11 | Viết đoạn giải thích hot row, lock wait, pool | `docs/benchmarks/s6-naive.md` | (không) | Đoạn giải thích xong |

### Tuần 56 · 29/11–05/12/2027

**Mục tiêu tuần:** campaign tự chuyển trạng thái đúng giờ.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 221 | T3 30/11 | Hàm chuyển trạng thái trong `Campaign`: `Schedule`, `FailAllocation` (→ `AllocationFailed`), `Reschedule` (`AllocationFailed` → `Scheduled`), `GoLive`, `End`, `MarkReconciled`; chặn xoá mềm/tắt khi đang `Live` | `Domain/Campaign.cs` | `dotnet build` | Build xanh |
| 222 | T5 02/12 | Hangfire trong FlashSale; lên lịch job T−10 phút (Scheduled), T−1 phút (cấp quota), T (Live), EndsAt (Ended), EndsAt + hạn thanh toán (10 phút) + 2 phút (reconcile) | `Jobs/CampaignScheduler.cs`, `Program.cs` | `dotnet add src/Services/FlashSale.Api package Hangfire.AspNetCore`; `dotnet add src/Services/FlashSale.Api package Hangfire.PostgreSql` | Đặt giờ mở bán sau 5 phút, trạng thái đổi đúng giờ |
| 223 | T7 04/12 | `GET /flash/time` (giờ server), `GET /flash/{camp}` (thông tin công khai) | `Features/GetServerTime.cs`, `GetCampaign.cs` | Chạy `http/flash.http` | Hai endpoint trả đúng |
| 224 | CN 05/12 | Test chuyển trạng thái với `FakeTimeProvider` | `tests/FlashSale.Tests/CampaignLifecycleTests.cs` | `dotnet new xunit3 -n FlashSale.Tests -o tests/FlashSale.Tests`; `dotnet sln add tests/FlashSale.Tests`; `dotnet add tests/FlashSale.Tests reference tests/TestKit`; `dotnet test` | Test xanh |

### Tuần 57 · 06/12–12/12/2027

**Mục tiêu tuần:** quota được cấp từ kho sang Redis trước giờ mở bán, cấp thiếu thì campaign không Live.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 225 | T3 07/12 | Inventory: `POST /internal/flash-allocations` ghi movement `FlashAllocation` (`RefType=FlashCampaign`), gọi lại không ghi thêm | `Inventory.Api/Features/Internal/AllocateFlash.cs` | Chạy `http/inventory.http` | `WH-HCM` giảm 100 Buds, gọi lại không giảm thêm |
| 226 | T5 09/12 | `AllocateJob`: cấp từng item, đủ thì `SET fs:{camp}:stock:{sku}`; thiếu thì trả phần đã cấp, chuyển `AllocationFailed`, ghi cảnh báo | `Jobs/AllocateJob.cs`, `Redis/FlashKeys.cs` | `aspire run` | Đặt quota lớn hơn tồn thì campaign `AllocationFailed`, kho không lệch |
| 227 | T7 11/12 | Inventory: `POST /internal/flash-returns` ghi `FlashReturn` | `Inventory.Api/Features/Internal/ReturnFlash.cs` | Chạy `http/inventory.http` | Trả 20 cái thì `OnHand` +20 |
| 228 | CN 12/12 | Test cấp quota lặp 2 lần và cấp thiếu | `tests/FlashSale.Tests/AllocationTests.cs` | `dotnet test` | Test xanh |

### Tuần 58 · 13/12–19/12/2027

**Mục tiêu tuần:** `reserve.lua` và `release.lua` đúng dưới 1.000 request song song.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 229 | T3 14/12 | Hai script Lua làm embedded resource, nạp sẵn khi khởi động | `Redis/reserve.lua`, `Redis/release.lua`, `Redis/LuaScripts.cs` | `dotnet build` | Script nạp được vào Redis |
| 230 | T5 16/12 | `FlashStockStore.Reserve(...)` và `Release(...)` trả kết quả rõ ràng (`Reserved`, `SoldOut`, `LimitReached`) | `Redis/FlashStockStore.cs` | `dotnet build` | Build xanh |
| 231 | T7 18/12 | `FlashReserveLuaTests`: 1.000 request song song, quota 100, giới hạn 1 | `tests/FlashSale.Tests/FlashReserveLuaTests.cs` | `dotnet test` | Đúng 100 thành công, không user nào quá 1 |
| 232 | CN 19/12 | Test release: gọi 2 lần chỉ trả 1 lần; đã có cờ `paid` thì không trả | `tests/FlashSale.Tests/FlashReleaseLuaTests.cs` | `dotnet test` | Test xanh |

### Tuần 59 · 20/12–26/12/2027

**Mục tiêu tuần:** endpoint `/buy` chạy hoàn toàn trên Redis, không chạm Postgres.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 233 | T3 21/12 | `POST /flash/{camp}/buy`: kiểm campaign `Live` (cache trong bộ nhớ), chạy Lua, publish `FlashReservationCreated` có confirm; publish lỗi thì release và trả 503 | `Features/Buy.cs`, `Contracts/FlashSale/FlashSaleEvents.cs` | Chạy `http/flash.http` | Trả 202 kèm `reservationId` |
| 234 | T5 23/12 | Gắn `IdempotencyFilter` cho `/buy` | `Features/Buy.cs` | Gửi cùng khoá 3 lần | Chỉ 1 reservation |
| 235 | T7 25/12 | Trả `409 SOLD_OUT` / `409 LIMIT_REACHED`; trace xác nhận không có span Postgres | `Features/Buy.cs` | `aspire run` | Trace của `/buy` chỉ có Redis và RabbitMQ |
| 236 | CN 26/12 | Dự phòng | (tuỳ việc dở) | (tuỳ việc dở) | Không còn việc dở |

### Tuần 60 · 27/12/2027–02/01/2028

**Mục tiêu tuần:** mỗi reservation thành một order kênh FlashSale; thanh toán và huỷ cập nhật ngược lại FlashSale.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 237 | T3 28/12 | FlashSale nghe chính `FlashReservationCreated` → ghi `FlashPurchase` `Reserved` (prefetch 20) | `Workers/PurchaseRecorder.cs` | `aspire run` | Mỗi reservation có 1 dòng `flash_purchases` |
| 238 | T5 30/12 | OrderWorker (consumer chạy trong Ordering.Api) nghe `FlashReservationCreated` → tạo order `FlashSale`, `PendingPayment`, `IdempotencyKey = reservationId`, hạn 10 phút, giá flash; saga bỏ bước giữ kho. Thêm field tuỳ chọn `ReservationId?` vào `OrderCreated`, `OrderPaid` và `OrderCancelled`; đơn flash phát cả ba event kèm giá trị này | `Ordering.Api/EventHandlers/FlashReservationCreatedHandler.cs`, `Sagas/CheckoutSaga.cs`, `src/Contracts/Orders/OrderEvents.cs` | `aspire run` | Order có giá 990.000 và kênh `FlashSale`; message `OrderCreated` trong RabbitMQ có `reservationId` |
| 239 | T7 01/01 | Dự phòng (Tết dương) | (tuỳ việc dở) | (tuỳ việc dở) | (không) |
| 240 | CN 02/01 | FlashSale nghe `OrderCreated` (có `ReservationId` thì gắn `OrderId` vào `FlashPurchase`, chuyển `OrderCreated`; không có thì bỏ qua), `OrderPaid` (theo `ReservationId` đặt cờ `paid` trên Redis và chuyển `Paid`, không cần đợi `OrderCreated`), `OrderCancelled` (theo `ReservationId`: release + `Released`). Mọi handler (kể cả `PurchaseRecorder`) upsert `FlashPurchase` theo `ReservationId`, trạng thái chỉ tiến (`Reserved` < `OrderCreated` < `Paid`; `Released` là kết thúc), nên thứ tự event tới không làm mất trạng thái | `EventHandlers/OrderCreatedHandler.cs`, `OrderPaidHandler.cs`, `OrderCancelledHandler.cs` | `aspire run` | `FailureRate=1` thì quota trả lại Redis; test giao `OrderPaid` trước `OrderCreated` vẫn có cờ `paid` và `ExpiryWorker` không trả quota (oversell = 0) |

### Tuần 61 · 03/01–09/01/2028

**Mục tiêu tuần:** reservation hết hạn tự trả quota; cuối campaign đối chiếu và trả hàng dư về kho; có hub SignalR.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 241 | T3 04/01 | Lưới an toàn (luồng chính là `ExpireUnpaidOrdersJob` của Ordering huỷ đơn → `OrderCancelled` → FlashSale trả quota): `ExpiryWorker` mỗi 5 giây quét `fs:{camp}:expiry` với hạn = hạn thanh toán + 2 phút, chạy release, phát `FlashReservationReleased`. Ordering nghe: đơn còn `PendingPayment` → huỷ và phát `OrderCancelled`; chưa có đơn → ghi bia mộ theo reservationId. FlashSale không bao giờ phát `OrderCancelled` | `Workers/ExpiryWorker.cs`, `Ordering.Api/EventHandlers/FlashReservationReleasedHandler.cs` | Đặt hạn 30 giây trong Development | Không thanh toán thì quota trả lại trong 30–90 giây (job mỗi phút); tắt job thì lưới an toàn trả sau khoảng 2 phút 30 giây |
| 242 | T5 06/01 | `ReconcileJob` (chạy lúc EndsAt + hạn thanh toán + 2 phút, khi không còn reservation nào trong hạn): đếm `Paid`, trả `quota − đã bán` về kho bằng `FlashReturn`, chuyển `Reconciled` | `Jobs/ReconcileJob.cs` | `aspire run` | Tổng movement ở `WH-HCM` = `OnHand` sau reconcile |
| 243 | T7 08/01 | Test hết hạn và reconcile | `tests/FlashSale.Tests/ExpiryTests.cs`, `ReconcileTests.cs` | `dotnet test` | Test xanh |
| 244 | CN 09/01 | Hub SignalR `FlashHub` với Redis backplane, nhóm theo customerId; xác thực JWT qua query `access_token` (`JwtBearerEvents.OnMessageReceived` cho đường dẫn `/hubs/flash`) | `Realtime/FlashHub.cs`, `Program.cs` | `dotnet add src/Services/FlashSale.Api package Microsoft.AspNetCore.SignalR.StackExchangeRedis` | Client thử kết nối thẳng FlashSale (chưa qua gateway, WebSocket qua gateway làm ở buổi 247) |

### Tuần 62 · 10/01–16/01/2028

**Mục tiêu tuần:** phòng chờ, flash token ký HMAC, gateway chặn request không có token.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 245 | T3 11/01 | `POST /flash/{camp}/queue`: `ZADD NX fs:admit:{camp}`, trả vị trí | `Features/JoinQueue.cs` | Chạy `http/flash.http` | Vào hàng 2 lần vẫn giữ vị trí cũ |
| 246 | T5 13/01 | `AdmissionWorker`: mỗi giây lấy 200 user đầu, ký token (customerId, campId, hết hạn 120 giây), đẩy qua SignalR | `Workers/AdmissionWorker.cs`, `Security/FlashTokenService.cs` | `aspire run` | User trong hàng nhận được token |
| 247 | T7 15/01 | Gateway: `FlashTokenValidator` cho `/api/flash/*/buy` (secret là parameter của AppHost), rate limit 5 request/giây/user, cho WebSocket đi qua | `src/Gateways/Gateway.Web/FlashTokenValidator.cs`, `RateLimitPolicies.cs`, `yarp.json` | `curl` không token tới `/buy` | Không token trả 403; spam trả 429 |
| 248 | CN 16/01 | Ở môi trường LoadTest, `X-Test-User` được bỏ qua bước token và phòng chờ | `FlashTokenValidator.cs` | `aspire run --launch-profile LoadTest` | k6 gọi `/buy` trực tiếp được |

### Tuần 63 · 17/01–23/01/2028

**Mục tiêu tuần:** trang flash sale trên storefront chạy hết luồng phòng chờ → mua → kết quả.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 249 | T3 18/01 | Event SignalR: `Admitted`, `Reserved`, `OrderCreated`, `Rejected` | `Realtime/FlashNotifier.cs` | `aspire run` | Client thử nhận đủ 4 loại event |
| 250 | T5 20/01 | Trang `/flash/:camp`: đếm ngược theo giờ server (tính độ lệch với giờ máy) | `apps/storefront/src/app/pages/flash/flash-page.component.ts`, `services/server-clock.ts` | `npm i @microsoft/signalr`; `npx nx serve storefront` | Đổi giờ máy vẫn đếm ngược đúng |
| 251 | T7 22/01 | Vào phòng chờ, hiện vị trí, nhận token | `pages/flash/` | `npx nx serve storefront` | Thấy vị trí giảm dần rồi nút "Mua" sáng lên |
| 252 | CN 23/01 | Nút mua gửi `Idempotency-Key`, chuyển sang trang đơn; trang đơn có nút Thanh toán gọi `POST /api/orders/{id}/pay` (Ordering thêm endpoint này; với kênh `FlashSale` saga không tự đòi tiền mà chờ lệnh này rồi mới phát `PaymentRequested`) | `pages/flash/`, `Ordering.Api/Features/Orders/PayOrder.cs`, `Sagas/CheckoutSaga.cs` | `npx nx serve storefront` | Mua thành công ra trang đơn có giá flash |

*Tuần 24/01–30/01/2028 nghỉ Tết.*

### Tuần 64 · 31/01–06/02/2028

**Mục tiêu tuần:** hoàn thiện UI flash sale cho khách và admin; thử 200 user thật qua Keycloak.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 253 | T3 01/02 | Storefront: trạng thái hết hàng, hết giới hạn, đếm ngược 10 phút giữ hàng | `pages/flash/` | `npx nx serve storefront` | Ba trạng thái hiện đúng |
| 254 | T5 03/02 | Admin: danh sách và form campaign (item, quota, giới hạn, giá, giờ) | `apps/admin/src/app/pages/flash-campaigns/` | `npx nx serve admin` | Tạo campaign mới từ UI |
| 255 | T7 05/02 | Admin: dashboard realtime số đã bán / còn lại theo SKU qua SignalR | `pages/flash-campaigns/live-dashboard.component.ts`, `Realtime/AdminNotifier.cs` | `npx nx serve admin` | Số nhảy theo thời gian thực khi có người mua |
| 256 | CN 06/02 | Tạo 200 user trong Keycloak bằng admin REST API; k6 chạy luồng thật (token + phòng chờ) | `tools/kc-create-users.sh`, `load/flash-real-200.js` | `./tools/kc-create-users.sh 200`; `k6 run load/flash-real-200.js` | 200 user đi hết luồng, không lỗi |

### Tuần 65 · 07/02–13/02/2028

**Mục tiêu tuần:** chạy kịch bản chuẩn trên bản Redis và so với bản naive.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 257 | T3 08/02 | Chạy đủ kịch bản 5.000 user bản Redis | `docs/benchmarks/s6-redis.md` | `k6 run -e MODE=redis load/flash-sale.js` | Có số liệu |
| 258 | T5 10/02 | Kiểm tra 7 tiêu chí bằng SQL và k6 | `tools/sql/check-flash.sql` | `psql -f tools/sql/check-flash.sql` | Ghi được tiêu chí nào chưa đạt |
| 259 | T7 12/02 | Tinh chỉnh: prefetch, pool kết nối Redis/Postgres, giới hạn Kestrel; chạy lại | (tuỳ chỗ chỉnh) | `k6 run -e MODE=redis load/flash-sale.js` | p95 `/buy` < 150 ms |
| 260 | CN 13/02 | Bảng so sánh naive và Redis kèm giải thích | `docs/benchmarks/s6-compare.md` | (không) | Bảng có đủ p95, lỗi, kết nối DB, oversell |

### Tuần 66 · 14/02–20/02/2028

**Mục tiêu tuần:** 4 bài diễn tập sự cố.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 261 | T3 15/02 | Diễn tập 1: Stop Ordering.Api (nơi chạy OrderWorker) 20 giây giữa lúc sale | `docs/notes/s6-drills.md` | `k6 run …`; dừng resource trên dashboard | Không mất reservation nào sau khi bật lại |
| 262 | T5 17/02 | Diễn tập 2: lỗi thanh toán 30% | `docs/notes/s6-drills.md` | Đặt `FailureRate=0.3`; `k6 run …` | Quota trả lại được bán tiếp; vẫn 0 oversell |
| 263 | T7 19/02 | Diễn tập 3: restart Redis ở giây thứ 30 (AOF `everysec`) | `docs/notes/s6-drills.md` | `docker restart <redis>` | Ghi được phần mất; reconcile phát hiện lệch |
| 264 | CN 20/02 | Diễn tập 4: cùng `Idempotency-Key` 3 lần | `docs/notes/s6-drills.md` | `./tools/double-submit.sh flash` | Chỉ 1 reservation |

### Tuần 67 · 21/02–27/02/2028

**Mục tiêu tuần:** sửa những gì diễn tập tìm ra, chạy lại toàn bộ.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 265 | T3 22/02 | Sửa lỗi từ diễn tập | (tuỳ lỗi) | `dotnet test` | Test xanh |
| 266 | T5 24/02 | Sửa lỗi từ diễn tập | (tuỳ lỗi) | `dotnet test` | Test xanh |
| 267 | T7 26/02 | Chạy lại kịch bản chuẩn và 4 bài diễn tập | `docs/notes/s6-drills.md` | `k6 run -e MODE=redis load/flash-sale.js` | Cả 4 bài đạt |
| 268 | CN 27/02 | Viết kết luận cho từng bài diễn tập | `docs/notes/s6-drills.md` | (không) | Mỗi bài có hiện tượng, nguyên nhân, cách sửa |

### Tuần 68 · 28/02–05/03/2028

**Mục tiêu tuần:** qua gate S6.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 269 | T3 29/02 | Chạy gate trên môi trường sạch, điền bảng 7 tiêu chí | `docs/benchmarks/s6-gate.md` | `docker volume rm shoplab-pg shoplab-redis shoplab-rabbit shoplab-keycloak shoplab-mongo1 shoplab-mongo2 shoplab-mongo3`; `aspire run --launch-profile LoadTest`; `k6 run …` | Đạt 7/7 tiêu chí |
| 270 | T5 02/03 | Sửa lỗi nếu còn | (tuỳ lỗi) | `dotnet test` | Test xanh |
| 271 | T7 04/03 | Ghi chú S6: Redis làm nguồn quota, load leveling, phòng chờ, token | `docs/notes/s6.md` | (không) | File ghi chú xong |
| 272 | CN 05/03 | Merge, tag | `docs/guides/ShopLab-S6.md` (xuất hướng dẫn của bước trước khi merge) | `git checkout main && git merge --no-ff step/s6-flash-sale`; `git tag s6-done`; `git checkout -b step/s7-pos` | Tag `s6-done` có trên `main` |

## S7. POS (tuần 69–81)

Store.Api quản lý cửa hàng, quầy, ca và tiền mặt; Bff.Pos đồng bộ hai chiều; app `pos` là PWA chạy offline với IndexedDB và engine tính giá viết lại bằng TypeScript, chạy chung 12 test case với bản C#. **Gate:** tắt mạng, bán 20 giao dịch, bật mạng: server nhận đủ 20 order kênh Pos; đẩy lại lần 2 không tạo trùng; chênh lệch tiền khi đóng ca hiển thị đúng.

### Tuần 69 · 06/03–12/03/2028

**Mục tiêu tuần:** Store.Api có dữ liệu cửa hàng, quầy; nhân viên chỉ thao tác được trên cửa hàng của mình.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 273 | T3 07/03 | Project Store.Api, nối `storedb`; entity `Store`, `Register`, `Shift`, `CashMovement`, `PosTransaction`; migration | `src/Services/Store.Api/Domain/*.cs`, `Data/StoreDbContext.cs`, `src/AppHost/AppHost.cs` | `python3 tools/new-service.py Store 5109`; `dotnet sln add src/Services/Store.Api`; `./tools/ef-migrations.sh Init Store` | Service xanh trên dashboard |
| 274 | T5 09/03 | Seed `stores.json`; Keycloak thêm attribute `store_id` cho `manager.q1`, `cashier.q1` + mapper vào token; export lại realm | `seed/stores.json`, `docker/keycloak/shoplab-realm.json` | `./tools/get-token.sh cashier.q1` | Token có claim `store_id` |
| 275 | T7 11/03 | Policy `Cashier`, `StoreManager` kèm kiểm `store_id` khớp cửa hàng trên route | `src/BuildingBlocks/Auth/StoreAccessHandler.cs` | `dotnet build` | Build xanh |
| 276 | CN 12/03 | API quầy: danh sách, gắn `DeviceId` | `Features/Registers/ListRegisters.cs`, `BindDevice.cs` | Chạy `http/store.http` | `cashier.q1` gọi sang `ST-CG` bị 403 |

### Tuần 70 · 13/03–19/03/2028

**Mục tiêu tuần:** mở ca, thu chi tiền mặt, đóng ca có chênh lệch.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 277 | T3 14/03 | Mở ca với tiền đầu ca; mỗi quầy chỉ một ca đang mở | `Features/Shifts/OpenShift.cs` | Chạy `http/store.http` | Mở ca thứ hai cùng quầy bị từ chối |
| 278 | T5 16/03 | Thu/chi tiền mặt (`PayIn`, `PayOut`) | `Features/Shifts/RecordCashMovement.cs` | Chạy `http/store.http` | Có dòng `cash_movements` |
| 279 | T7 18/03 | Đóng ca: nhập tiền đếm được, tính tiền phải có = đầu ca + bán tiền mặt + thu − chi − hoàn | `Features/Shifts/CloseShift.cs` | Chạy `http/store.http` | Trả đúng chênh lệch |
| 280 | CN 19/03 | `ShiftTests` | `tests/Store.Tests/ShiftTests.cs` | `dotnet new xunit3 -n Store.Tests -o tests/Store.Tests`; `dotnet sln add tests/Store.Tests`; `dotnet add tests/Store.Tests reference tests/TestKit`; `dotnet test` | Test xanh |

### Tuần 71 · 20/03–26/03/2028

**Mục tiêu tuần:** Bff.Pos trả về phần dữ liệu đã đổi kể từ lần đồng bộ trước.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 281 | T3 21/03 | Project Bff.Pos; Catalog thêm `GET /internal/variants/changes?since=` (theo `UpdatedAt`, kèm cờ đã xoá/tắt) | `src/Gateways/Bff.Pos/Program.cs`, `Catalog.Api/Features/Internal/GetVariantChanges.cs` | `python3 tools/new-service.py Bff.Pos 5202 --gateway`; `dotnet sln add src/Gateways/Bff.Pos` | Endpoint Catalog trả đúng các SKU vừa sửa |
| 282 | T5 23/03 | Discount thêm `GET /internal/promotions?channel=Pos&since=`; Customer thêm `GET /internal/customers/changes?since=` (SĐT, tên, điểm); cả hai trả kèm cờ `isActive`, `isDeleted` để POS gỡ bản đã tắt/xoá | `Discount.Api/Features/Internal/GetPromotionChanges.cs`, `Customer.Api/Features/Internal/GetCustomerChanges.cs` | Chạy `http/bff-pos.http` | Hai endpoint trả dữ liệu |
| 283 | T7 25/03 | `GET /sync/pull?since=` gộp 3 nguồn; `nextSince` = giờ server − 5 giây (bản ghi commit muộn vẫn được lấy lần sau), client bỏ trùng theo id | `src/Gateways/Bff.Pos/Sync/PullDelta.cs` | Chạy `http/bff-pos.http` | Lần đầu trả đủ; lần sau chỉ trả phần đổi |
| 284 | CN 26/03 | Test pull delta | `tests/Bff.Pos.Tests/PullDeltaTests.cs` | `dotnet new xunit3 -n Bff.Pos.Tests -o tests/Bff.Pos.Tests`; `dotnet sln add tests/Bff.Pos.Tests`; `dotnet add tests/Bff.Pos.Tests reference tests/TestKit`; `dotnet test` | Test xanh |

### Tuần 72 · 27/03–02/04/2028

**Mục tiêu tuần:** đẩy batch giao dịch từ POS lên, nhận trùng bao nhiêu lần cũng chỉ ghi một lần.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 285 | T3 28/03 | Store.Api `POST /internal/pos-transactions/batch`: ghi theo `ClientTxnId` (`ON CONFLICT DO NOTHING`); kiểm theo `ShiftId` của giao dịch (ca tồn tại, thuộc quầy, `OccurredAt` trong khoảng mở ca), không theo việc ca còn mở lúc đẩy lên | `Features/Internal/ReceivePosBatch.cs` | Chạy `http/store.http` | Gửi lại cùng batch không thêm dòng |
| 286 | T5 30/03 | Bff.Pos `POST /sync/push` chuyển batch, trả trạng thái từng giao dịch | `src/Gateways/Bff.Pos/Sync/PushTransactions.cs` | Chạy `http/bff-pos.http` | Nhận lại danh sách `Received`/`Rejected` |
| 287 | T7 01/04 | Áp giao dịch: ghi `CashMovement` `Sale` nếu trả tiền mặt, chuyển `Applied`, phát `PosSaleRecorded` qua outbox, kèm `LocationId` của cửa hàng tra trong `storedb` | `Features/Internal/ApplyPosTransaction.cs`, `Contracts/Stores/StoreEvents.cs` | `./tools/ef-migrations.sh AddMessaging Store` | Có event `PosSaleRecorded` trong RabbitMQ |
| 288 | CN 02/04 | Lý do từ chối: ca không tồn tại / không thuộc quầy, `OccurredAt` ngoài khoảng mở ca; Store không kiểm SKU (không có dữ liệu catalog), SKU lạ để Inventory ghi cảnh báo; giao dịch bị từ chối không phát event | `Features/Internal/ApplyPosTransaction.cs` | Chạy `http/store.http` | Giao dịch offline của ca đã đóng vẫn `Applied` nếu `OccurredAt` nằm trong ca; giao dịch ngoài ca ra `Rejected` |

### Tuần 73 · 03/04–09/04/2028

**Mục tiêu tuần:** bán ở quầy sinh order, trừ kho cửa hàng, cộng điểm khách.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 289 | T3 04/04 | Ordering: `PosSaleRecordedHandler` tạo order kênh `Pos`, `Completed`, `IdempotencyKey = ClientTxnId`, rồi phát `OrderPaid` (kênh `Pos`, có `StoreId`) qua outbox; đơn POS không phát `OrderCreated` (không giữ hàng, không coupon). Doanh thu và điểm đều đi theo `OrderPaid` | `Ordering.Api/EventHandlers/PosSaleRecordedHandler.cs` | `aspire run` | Order kênh `Pos` có `StoreId`; dashboard admin có doanh thu POS |
| 290 | T5 06/04 | Inventory: `PosSaleRecordedHandler` ghi movement `PosSale` tại `LocationId` trong event; cho phép `OnHand` âm riêng với `PosSale` và ghi cảnh báo. `OrderPaid` giữ quy tắc chung từ S3: chỉ commit reservation đang có của `OrderId`, không có thì không làm gì (đơn `Pos` và `FlashSale` đều rơi vào trường hợp này, không cần lọc theo kênh) | `Inventory.Api/EventHandlers/PosSaleRecordedHandler.cs`, `EventHandlers/OrderEventHandlers.cs`, `Domain/StockLevel.cs` | `aspire run` | `ST-Q1` giảm đúng số đã bán |
| 291 | T7 08/04 | Customer: cộng điểm chỉ từ `OrderPaid` (mọi kênh); không nghe `PosSaleRecorded` để không cộng hai lần. Notification bỏ qua `OrderPaid` kênh `Pos`; Cart chỉ xoá giỏ với kênh `Online` (đã vậy từ S3, nên đơn `Pos` và `FlashSale` không làm mất giỏ) | `Customer.Api/EventHandlers/OrderPaidHandler.cs`, `Notification.Worker/Handlers/OrderPaidHandler.cs`, `Cart.Api/EventHandlers/OrderPaidHandler.cs` | `aspire run` | `an.nguyen` mua ở quầy được cộng điểm đúng một lần, không có email |
| 292 | CN 09/04 | `PosSyncTests`: đẩy cùng batch 2 lần thì số `PosTransaction` và số `PosSaleRecorded` trong outbox không đổi; phía Ordering có test riêng `IdempotencyKey = ClientTxnId` không tạo đơn thứ hai | `tests/Store.Tests/PosSyncTests.cs`, `tests/Ordering.Tests/PosOrderTests.cs` | `dotnet test` | Test xanh |

### Tuần 74 · 10/04–16/04/2028

**Mục tiêu tuần:** app `pos` cài được như PWA, thu ngân đăng nhập, chọn quầy, mở ca.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 293 | T3 11/04 | Tạo app `pos`, bật PWA | `apps/pos/`, `apps/pos/ngsw-config.json`, `manifest.webmanifest` | `./tools/scaffold-angular-app.sh pos 4400`; `cd src/Web && npx nx g @angular/pwa --project=pos` | Build production có service worker |
| 294 | T5 13/04 | Đăng nhập thu ngân, chọn quầy, lưu `DeviceId` trên máy | `apps/pos/src/app/pages/login/`, `pages/select-register/` | `npx nx serve pos` | Mở lại app vẫn nhớ quầy |
| 295 | T7 15/04 | Layout POS toàn màn hình, nút lớn; route bán hàng, ca, đồng bộ | `apps/pos/src/app/layout/`, `app.routes.ts` | `npx nx serve pos` | Điều hướng được giữa 3 màn hình |
| 296 | CN 16/04 | Màn hình mở ca | `pages/shift/open-shift.component.ts` | `npx nx serve pos` | Mở ca từ UI, server có ca mới |

### Tuần 75 · 17/04–23/04/2028

**Mục tiêu tuần:** dữ liệu bán hàng nằm sẵn trên máy, tra cứu được khi mất mạng.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 297 | T3 18/04 | Schema IndexedDB: `products`, `promotions`, `customers`, `pendingTxns`, `meta` | `apps/pos/src/app/data/pos-db.ts` | `npm i dexie` | Mở DevTools thấy 5 bảng |
| 298 | T5 20/04 | `SyncService` pull khi mở app, mỗi 5 phút và khi có mạng lại; lưu `lastSince` | `data/sync.service.ts` | `npx nx serve pos` | Bảng `products` có 7 SKU |
| 299 | T7 22/04 | Tra sản phẩm theo barcode hoặc SKU từ IndexedDB | `data/product-lookup.service.ts` | `npx nx serve pos` | Tắt mạng vẫn tra được |
| 300 | CN 23/04 | Chỉ báo online/offline và số giao dịch chờ đẩy | `layout/sync-indicator.component.ts` | `npx nx serve pos` | Tắt mạng thì chỉ báo đổi màu |

### Tuần 76 · 24/04–30/04/2028

**Mục tiêu tuần:** màn hình bán hàng: quét mã, giỏ, khách hàng.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 301 | T3 25/04 | Ô quét mã luôn focus, Enter thì thêm sản phẩm (máy quét hoạt động như bàn phím) | `pages/sale/barcode-input.component.ts` | `npx nx serve pos` | Gõ `8930000000011` + Enter thêm Buds vào giỏ |
| 302 | T5 27/04 | Giỏ bán hàng: sửa số lượng, xoá dòng | `pages/sale/sale-cart.component.ts`, `state/sale.store.ts` | `npx nx serve pos` | Sửa được giỏ |
| 303 | T7 29/04 | Tra khách theo SĐT từ bộ nhớ đệm | `pages/sale/customer-lookup.component.ts` | `npx nx serve pos` | Gõ `0901000001` ra `an.nguyen` khi offline |
| 304 | CN 30/04 | Tổng tiền tạm tính (chưa giảm giá) | `pages/sale/sale-total.component.ts` | `npx nx serve pos` | Tổng đúng |

### Tuần 77 · 01/05–07/05/2028

**Mục tiêu tuần:** engine tính giá bằng TypeScript cho kết quả giống hệt bản C# trên cùng 12 case.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 305 | T3 02/05 | Thư viện `libs/pricing`: kiểu dữ liệu, `PercentOff`, `AmountOff` | `libs/pricing/src/lib/models.ts`, `rules/percent-off.ts`, `rules/amount-off.ts` | `npx nx g @nx/js:library libs/pricing` | Build xanh |
| 306 | T5 04/05 | `BuyXGetY`, kiểm tra coupon, luật cộng dồn | `rules/buy-x-get-y.ts`, `coupon-validator.ts`, `engine.ts` | `npx nx build pricing` | Build xanh |
| 307 | T7 06/05 | Test Jest đọc chính `seed/pricing-cases.json` | `libs/pricing/src/lib/engine.spec.ts` | `npx nx test pricing` | 12 case xanh, giống bản C# |
| 308 | CN 07/05 | Gắn engine vào màn hình bán hàng | `pages/sale/sale-total.component.ts` | `npx nx serve pos` | Giỏ 1 Balo ở `ST-Q1` ra 801.000 (khuyến mãi seed kênh Pos) |

### Tuần 78 · 08/05–14/05/2028

**Mục tiêu tuần:** thanh toán, in hoá đơn, đẩy giao dịch lên server có retry.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 309 | T3 09/05 | Thanh toán tiền mặt (tính tiền thừa), thẻ, VietQR (chỉ ghi nhận) | `pages/sale/payment.component.ts` | `npx nx serve pos` | Khách đưa 1.000.000 cho đơn 801.000 hiện thừa 199.000 |
| 310 | T5 11/05 | Tạo giao dịch với `ClientTxnId = crypto.randomUUID()`, lưu vào `pendingTxns` | `data/transaction.service.ts` | `npx nx serve pos` | Thanh toán xong có dòng chờ đẩy |
| 311 | T7 13/05 | `PushService`: đẩy theo batch, backoff khi lỗi, đánh dấu `synced`/`rejected` | `data/push.service.ts` | `npx nx serve pos` | Có mạng thì giao dịch chuyển `synced` |
| 312 | CN 14/05 | In hoá đơn bằng CSS `@media print` và `window.print` | `pages/sale/receipt.component.ts`, `receipt.scss` | `npx nx serve pos` | Bản in khổ 80 mm hiển thị đúng |

### Tuần 79 · 15/05–21/05/2028

**Mục tiêu tuần:** đóng ca, thu chi, hoàn tiền trên POS.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 313 | T3 16/05 | Màn hình đóng ca: nhập tiền đếm được, hiện tiền phải có và chênh lệch (cần mạng) | `pages/shift/close-shift.component.ts` | `npx nx serve pos` | Chênh lệch khớp với server |
| 314 | T5 18/05 | Màn hình thu/chi tiền mặt | `pages/shift/cash-movement.component.ts` | `npx nx serve pos` | Thu 200.000 thì tiền phải có tăng tương ứng |
| 315 | T7 20/05 | Hoàn tiền cho `store_manager` (có thể cắt khỏi v1): `CashMovement` `Refund`, phát `PosRefundRecorded` qua outbox; Inventory nghe → movement `Return`, Customer trừ điểm, Bff.Admin trừ doanh thu | `pages/sale/refund.component.ts`, `Store.Api/Features/Refunds/RecordRefund.cs`, `Contracts/Stores/StoreEvents.cs` (`PosRefundRecorded`) | `npx nx serve pos` | Hoàn tiền thì kho `ST-Q1` tăng lại |
| 316 | CN 21/05 | In báo cáo ca | `pages/shift/shift-report.component.ts` | `npx nx serve pos` | In được báo cáo |

### Tuần 80 · 22/05–28/05/2028

**Mục tiêu tuần:** chạy kịch bản offline của gate.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 317 | T3 23/05 | DevTools chế độ Offline, bán 20 giao dịch | `docs/notes/s7-offline.md` | `npx nx run pos:serve-static` | 20 dòng `pendingTxns` |
| 318 | T5 25/05 | Bật mạng, đợi đẩy, đối chiếu server | `tools/sql/check-pos.sql` | `psql -f tools/sql/check-pos.sql` | Đủ 20 order kênh `Pos`, kho `ST-Q1` giảm đúng |
| 319 | T7 27/05 | Đặt lại cờ `synced` trên máy rồi đẩy lần 2 | `docs/notes/s7-offline.md` | `psql -f tools/sql/check-pos.sql` | Vẫn đúng 20 order |
| 320 | CN 28/05 | Đóng ca, kiểm chênh lệch | `docs/notes/s7-offline.md` | `npx nx serve pos` | Chênh lệch hiển thị đúng |

### Tuần 81 · 29/05–04/06/2028

**Mục tiêu tuần:** qua gate S7.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 321 | T3 30/05 | Sửa lỗi từ kịch bản offline | (tuỳ lỗi) | `dotnet test`; `npx nx run-many -t test` | Test xanh |
| 322 | T5 01/06 | Chạy lại gate trên môi trường sạch | (không) | `docker volume rm shoplab-pg shoplab-redis shoplab-rabbit shoplab-keycloak shoplab-mongo1 shoplab-mongo2 shoplab-mongo3`; `aspire run` | Đạt gate S7 |
| 323 | T7 03/06 | Ghi chú S7: offline-first, client-generated ID, engine chạy hai nơi | `docs/notes/s7.md` | (không) | File ghi chú xong |
| 324 | CN 04/06 | Merge, tag | `docs/guides/ShopLab-S7.md` (xuất hướng dẫn của bước trước khi merge) | `git checkout main && git merge --no-ff step/s7-pos`; `git tag s7-done`; `git checkout -b step/s8-hardening` | Tag `s7-done` có trên `main` |

## S8. Hardening (tuần 82–88)

Khoá kiến trúc bằng test, thêm metric vận hành, rồi chủ động phá từng phần (Mongo primary, service checkout, service flash sale, Postgres) trong lúc có tải và viết postmortem. **Gate:** mỗi lần kill có postmortem 1 trang; hệ thống tự hồi phục mà không cần sửa DB bằng tay.

### Tuần 82 · 05/06–11/06/2028

**Mục tiêu tuần:** ranh giới giữa các service được kiểm bằng test, không chỉ bằng quy ước.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 325 | T3 06/06 | Project Architecture.Tests: không service nào reference service khác | `tests/Architecture.Tests/ServiceBoundaryTests.cs` | `dotnet new xunit3 -n Architecture.Tests -o tests/Architecture.Tests`; `dotnet sln add tests/Architecture.Tests`; `dotnet add tests/Architecture.Tests package NetArchTest.Rules` | Test xanh |
| 326 | T5 08/06 | `Contracts` chỉ dùng BCL; `BuildingBlocks` không reference service | `tests/Architecture.Tests/ContractsTests.cs` | `dotnet test tests/Architecture.Tests` | Test xanh |
| 327 | T7 10/06 | Dựng model của AppHost trong test, kiểm chỉ Catalog, Ordering, Bff.Admin tham chiếu Mongo, mỗi bên đúng DB của mình | `tests/Architecture.Tests/MongoReferenceTests.cs` | `dotnet add tests/Architecture.Tests package Aspire.Hosting.Testing`; `dotnet test` | Thêm thử tham chiếu sai thì test đỏ |
| 328 | CN 11/06 | Script chạy toàn bộ kiểm tra một lần; bật lại `TreatWarningsAsErrors` ở `Directory.Build.props` và sửa hết cảnh báo | `tools/check.sh` | `./tools/check.sh` | Script chạy hết .NET test, Nx test, build |

### Tuần 83 · 12/06–18/06/2028

**Mục tiêu tuần:** nhìn thấy sức khoẻ hệ thống qua metric: queue, outbox, projection, p95.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 329 | T3 13/06 | Metric độ dài queue: consumer host định kỳ khai báo passive để lấy số message | `src/BuildingBlocks/Messaging/QueueDepthMonitor.cs` | `aspire run` | Thấy `queue.depth` theo từng queue |
| 330 | T5 15/06 | Metric projection lag ở Catalog, Ordering, Bff.Admin | `src/BuildingBlocks/ReadModel/ProjectionMetrics.cs` | `aspire run` | Thấy `projection.lag_seconds` |
| 331 | T7 17/06 | Bảng theo dõi trên Aspire dashboard; Prometheus + Grafana nếu muốn (có thể cắt) | `docker/grafana/dashboards/shoplab.json`, `src/AppHost/AppHost.cs` | `aspire run` | Một màn hình thấy queue, outbox lag, projection lag, p95 checkout |
| 332 | CN 18/06 | Ghi ngưỡng cảnh báo cho từng metric | `docs/ops/thresholds.md` | (không) | Mỗi metric có ngưỡng và cách xử lý |

### Tuần 84 · 19/06–25/06/2028

**Mục tiêu tuần:** diễn tập failover MongoDB khi đang có tải.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 333 | T3 20/06 | Script tìm node primary và dừng nó | `tools/chaos/kill-mongo-primary.sh` | `./tools/chaos/kill-mongo-primary.sh` | Script dừng đúng node primary |
| 334 | T5 22/06 | Chạy k6 duyệt sản phẩm + checkout, kill primary ở giữa; đo thời gian có primary mới và số request lỗi | `docs/postmortems/mongo-failover.md` | `k6 run load/browse.js & k6 run load/checkout-1000.js`; `./tools/chaos/kill-mongo-primary.sh` | Ghi được thời gian bầu lại |
| 335 | T7 24/06 | Kiểm `w: majority`: so số document với Postgres, xem thư mục rollback của node cũ | `docs/postmortems/mongo-failover.md` | `./tools/compare-catalog.sh` | Không mất dữ liệu đã xác nhận |
| 336 | CN 25/06 | Viết postmortem failover | `docs/postmortems/mongo-failover.md` | (không) | Postmortem 1 trang xong |

### Tuần 85 · 26/06–02/07/2028

**Mục tiêu tuần:** chaos cho luồng checkout.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 337 | T3 27/06 | Mẫu postmortem; script dừng một resource trong N giây rồi bật lại | `docs/postmortems/_template.md`, `tools/chaos/kill.sh` | `./tools/chaos/kill.sh ordering 30` | Script chạy được |
| 338 | T5 29/06 | Kill Ordering, rồi Inventory giữa lúc k6 checkout | `docs/postmortems/checkout-ordering.md`, `checkout-inventory.md` | `k6 run load/checkout-1000.js`; `./tools/chaos/kill.sh …` | Ghi được hành vi và thời gian hồi phục |
| 339 | T7 01/07 | Kill Payment, rồi RabbitMQ | `docs/postmortems/checkout-payment.md`, `checkout-rabbitmq.md` | `./tools/chaos/kill.sh …`; `psql -f tools/sql/check-reservations.sql` | Lệch kho = 0 sau khi hồi phục |
| 340 | CN 02/07 | Hoàn thiện 4 postmortem checkout | `docs/postmortems/checkout-*.md` | (không) | 4 file xong |

### Tuần 86 · 03/07–09/07/2028

**Mục tiêu tuần:** chaos cho flash sale và cho Postgres dùng chung.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 341 | T3 04/07 | Kill FlashSale.Api giữa lúc sale | `docs/postmortems/flash-service.md` | `k6 run -e MODE=redis load/flash-sale.js`; `./tools/chaos/kill.sh flashsale 20` | 0 oversell sau khi hồi phục |
| 342 | T5 06/07 | Kill Gateway.Web | `docs/postmortems/flash-gateway.md` | `./tools/chaos/kill.sh gateway 20` | Ghi được hành vi của client và SignalR |
| 343 | T7 08/07 | Kill container Postgres (mọi service cùng chịu) | `docs/postmortems/postgres-down.md` | `./tools/chaos/kill.sh pg 60` | Outbox tự gửi tiếp, không order kẹt |
| 344 | CN 09/07 | Hoàn thiện 3 postmortem | `docs/postmortems/*.md` | (không) | 3 file xong |

### Tuần 87 · 10/07–16/07/2028

**Mục tiêu tuần:** sửa những gì chaos tìm ra và chạy lại.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 345 | T3 11/07 | Sửa lỗi từ chaos | (tuỳ lỗi) | `./tools/check.sh` | Kiểm tra xanh |
| 346 | T5 13/07 | Sửa lỗi từ chaos | (tuỳ lỗi) | `./tools/check.sh` | Kiểm tra xanh |
| 347 | T7 15/07 | Chạy lại các bài chaos từng thất bại | `docs/postmortems/*.md` (thêm mục "sau khi sửa") | `./tools/chaos/kill.sh …` | Mọi bài tự hồi phục |
| 348 | CN 16/07 | Chạy nhanh lại gate S2–S7 | (không) | `./tools/check.sh`; `k6 run …` | Không gate nào bị hỏng |

### Tuần 88 · 17/07–23/07/2028

**Mục tiêu tuần:** đóng lab: tài liệu, kịch bản demo, tổng kết.

| STT | Ngày | Việc | File tạo / sửa | Lệnh | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 349 | T3 18/07 | README tổng: sơ đồ kiến trúc, cách chạy, cấu trúc repo | `README.md` | (không) | Người khác clone về chạy được theo README |
| 350 | T5 20/07 | Kịch bản demo 15 phút: đặt hàng, flash sale, POS offline, kill một service | `docs/demo.md` | Chạy thử theo kịch bản | Demo trọn 15 phút không vấp |
| 351 | T7 22/07 | Tổng kết lab: những gì học được ở từng bước, những gì sẽ làm khác trong dự án thật | `docs/notes/s8.md`, `docs/notes/lab-summary.md` | (không) | File tổng kết xong |
| 352 | CN 23/07 | Merge, tag phiên bản cuối | `docs/guides/ShopLab-S8.md` (xuất hướng dẫn của bước trước khi merge) | `git checkout main && git merge --no-ff step/s8-hardening`; `git tag s8-done`; `git tag v1.0` | Tag `v1.0` có trên `main` |

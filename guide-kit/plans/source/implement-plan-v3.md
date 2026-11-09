# Lab: E-commerce microservices — implement plan v3

Oct 27, 2026 · @Khoa

**Thay đổi ở v3:** lộ trình đi từ một web bán hàng đơn giản, gọi nhau đồng bộ, lên dần bản đầy đủ; hạ tầng chỉ thêm vào khi bước đó cần, trừ năm thứ khó gắn về sau. Thêm một MongoDB replica set dùng chung làm read DB, chỉ Catalog, Ordering và Bff.Admin dùng. Bản v2 vẫn còn trong lịch sử của doc.

## Mục tiêu và phạm vi v1

V1 là một lab chạy hoàn toàn trên máy local: 10 service .NET, 3 cổng vào (Gateway.Web, Bff.Admin, Bff.Pos), 3 UI Angular, khởi động bằng một lệnh, và chịu được bài test flash sale 5.000 user giành 100 sản phẩm mà không oversell.

Mục tiêu học, theo thứ tự ưu tiên:

1. Tự tay dựng các pattern mà framework (ABP) thường che đi: Outbox, Saga, idempotency, service discovery, distributed tracing.
2. Hiểu chỗ hệ thống gãy dưới tải: hot row, lock contention, queue backlog, cache stampede.
3. Có một repo đủ thật để đem đi phỏng vấn hoặc demo.

Nguyên tắc làm lab:

- **Mỗi phase phải chạy được end-to-end** trước khi sang phase sau. Không viết cả 10 service rồi mới nối.
- **Không dùng ABP** trong lab này. Mục đích là thấy từng mảnh ghép, không phải dùng lại framework quen.
- **Đo trước, tối ưu sau.** Mỗi thay đổi kiến trúc cho flash sale đều đi kèm số liệu k6 trước/sau.
- Ngoài phạm vi v1: Kubernetes, CI/CD, multi-region, payment gateway thật, Elasticsearch. Ghi lại ở mục bài tập mở rộng.

## Stack công nghệ

Chọn .NET 10 (LTS) + Aspire 13.x làm xương sống, và tự viết lớp messaging (Outbox, Inbox, Saga) thay vì dùng MassTransit, vì [MassTransit v9 đã chuyển sang license thương mại](https://masstransit.io/introduction/v9-announcement) còn v8 chỉ được vá đến hết 2026.

| STT | Lớp | Lựa chọn | Lý do |
| --- | --- | --- | --- |
| 1 | Runtime | .NET 10, C# 14 | LTS hiện tại, Aspire 13.4 chạy trên SDK 10.0.x |
| 2 | Orchestration local | [Aspire 13.x](https://devblogs.microsoft.com/aspire/whats-new-aspire-13-5/) AppHost (C#) | Một lệnh chạy cả 20+ resource, có dashboard log/trace/metric sẵn, service discovery |
| 3 | API style | Minimal API + vertical slice, handler tự viết | Bỏ MediatR (v13 cũng đã thương mại hóa); thấy rõ pipeline |
| 4 | ORM | EF Core 10 + Npgsql | Quen tay; dùng `xmin` làm concurrency token cho Inventory |
| 5 | Database | PostgreSQL 17, 1 container, **mỗi service 1 database** | Đủ cô lập dữ liệu, nhẹ máy |
| 6 | Read DB | MongoDB 8, một replica set 3 node `rs0` dùng chung | Chỉ Catalog, Ordering, Bff.Admin; mỗi bên một database riêng (không bật auth), Postgres vẫn là nguồn sự thật |
| 7 | Cache / stock flash | Redis 7 | Cart, discount cache, Lua stock, phòng chờ flash (rate limit ở gateway chạy trong bộ nhớ) |
| 8 | Message broker | RabbitMQ 4 + `RabbitMQ.Client` 7 | Tự viết Outbox/Inbox để hiểu cơ chế; topic exchange `ecommerce.events` |
| 9 | Gateway | YARP + ASP.NET Core RateLimiting | Cùng codebase .NET, dễ debug |
| 10 | Identity | Keycloak 26 (container) | OIDC thật, realm có sẵn role `customer`, `admin`, `cashier`, `store_manager` |
| 11 | Background job | Hangfire (PostgreSQL storage) | Huỷ đơn quá hạn thanh toán (Ordering, S3); lịch campaign và reconcile flash sale (FlashSale, S6) |
| 12 | Real-time | SignalR | Đẩy kết quả flash sale, dashboard admin |
| 13 | Email dev | Mailpit | Bắt email Notification service gửi ra |
| 14 | Frontend | Angular 20.3 (ghim cùng Nx 21.5.0, không dùng `@latest`), Nx workspace preset `apps`: `storefront`, `admin`, `pos`; test frontend bằng Jest (`@nx/jest`) | Đúng stack của bạn; POS là PWA + IndexedDB |
| 15 | Test | xUnit v3, Testcontainers, Shouldly, k6 | Integration test với Postgres/Redis/RabbitMQ thật; k6 cho flash sale |

Hai thư viện cố tình tránh: MediatR và FluentAssertions (cả hai đã có bản thương mại). Nếu sau này muốn so sánh, phase mở rộng có bài thay lớp messaging tự viết bằng Wolverine hoặc MassTransit v8.

## Cấu trúc solution

Một mono-repo `shoplab`, mỗi service là một project Web độc lập (không có Domain/Application/Infrastructure tách project), cắt theo feature folder. Chỉ có 2 project dùng chung: `BuildingBlocks` (messaging, outbox, auth) và `Contracts` (event DTO).

```text
shoplab/
├─ shoplab.slnx                  # dotnet sln add sau mỗi project mới (tools/sln-sync.py để đồng bộ lại, tuỳ chọn)
├─ Directory.Build.props         # net10.0, nullable, implicit usings; TreatWarningsAsErrors tắt tới S8
├─ Directory.Packages.props      # Central Package Management
├─ .gitignore, .editorconfig     # dotnet new gitignore / editorconfig
├─ contracts/openapi/            # OpenAPI sinh lúc build, không commit
├─ docker/
│  ├─ keycloak/shoplab-realm.json        # realm, client, role, user mẫu (ID cố định)
│  └─ mongo/init-replset.sh, init-replset.js   # rs0 3 node (S5)
├─ seed/
│  ├─ categories.json, products.json           # S1
│  ├─ customers.json, locations.json, stock.json   # S2
│  ├─ promotions.json, pricing-cases.json      # S4 (12 ca golden, dùng chung C# và TS)
│  ├─ flash-campaigns.json                     # S6
│  └─ stores.json                              # S7
├─ src/
│  ├─ AppHost/            # AppHost.cs, ShopLabResourceExtensions.cs, Properties/launchSettings.json
│  ├─ ServiceDefaults/    # OTel (source/meter "ShopLab"), /health /alive, resilience, discovery
│  ├─ BuildingBlocks/
│  │  ├─ Auth/            # AuthExtensions, KeycloakRolesTransformation, CurrentUser; TestUserAuthHandler (S2);
│  │  │                   #   StoreAccessHandler (S7)
│  │  ├─ Persistence/     # Auditable, AuditInterceptor, SoftDeleteQueryFilter, DbContextExtensions
│  │  ├─ Results/         # AppErrors (lỗi có mã), ProblemDetailsMapping (23505 → 409)
│  │  ├─ Endpoints/       # IEndpoint: mỗi resource hoặc use case một class Map()
│  │  ├─ Paging/          # KeysetCursor, PagedResult
│  │  ├─ ApiExtensions.cs # AddShopLabApi / UseShopLabApi
│  │  ├─ Http/            # ServiceResponse: ProblemDetails service khác → AppException (S2)
│  │  ├─ Chaos/           # ChaosMiddleware: trễ/lỗi giả (S2)
│  │  ├─ Messaging/       # S3: EventTypeRegistry, OutboxMessage+InboxMessage, Outbox (IOutbox → EfOutbox),
│  │  │                   #     OutboxPublisher (SKIP LOCKED) + OutboxCleanup, RabbitMqPublisher + Topology,
│  │  │                   #     RabbitMqConsumerHost (inbox EF/Redis, retry, DLQ), IEventHandler, MessagingExtensions;
│  │  │                   #     QueueDepthMonitor (S8)
│  │  ├─ Idempotency/     # IdempotencyFilter: header Idempotency-Key, Redis 24h (S3)
│  │  └─ ReadModel/       # MongoExtensions, MongoProjection (UpsertIfNewer, MongoInbox) (S5); ProjectionMetrics (S8)
│  ├─ Contracts/          # IntegrationEvent + [EventName]; mỗi service một file
│  │  ├─ Catalog/CatalogEvents.cs       # ProductChanged
│  │  ├─ Inventory/InventoryEvents.cs   # StockChanged, StockReserved, StockReservationFailed
│  │  ├─ Orders/OrderEvents.cs          # OrderCreated, OrderPaid, OrderCancelled, OrderStatusChanged
│  │  ├─ Payments/PaymentEvents.cs      # PaymentRequested/Succeeded/Failed, PaymentRefundRequested
│  │  ├─ Discount/DiscountEvents.cs     # CouponRedeemed, CouponRedemptionFailed
│  │  ├─ FlashSale/FlashSaleEvents.cs   # FlashReservationCreated, FlashReservationReleased (S6)
│  │  └─ Stores/StoreEvents.cs          # PosSaleRecorded, PosRefundRecorded (S7)
│  ├─ Gateways/
│  │  ├─ Gateway.Web/     # Program.cs (chặn /internal), yarp.json (S5: /api/admin/dashboard → Bff.Admin);
│  │  │                   #   S6: RateLimitPolicies, FlashTokenValidator
│  │  ├─ Bff.Admin/       # Dashboard/ (DashboardProjector, OrderingClient), Handlers/, Features/DashboardEndpoints.cs
│  │  └─ Bff.Pos/         # Sync/PullDelta.cs, Sync/PushTransactions.cs (S7)
│  ├─ Services/           # mỗi service: Program.cs, ApiMarker.cs, Domain/, Data/ (DbContext, SeedData),
│  │  │                   #   Features/ (IEndpoint theo resource/use case), EventHandlers/, appsettings.json
│  │  ├─ Catalog.Api/     # Features/{Categories,Products,Internal,ReadModel}, ReadModel/ProductReadStore.cs,
│  │  │                   #   EventHandlers/StockChangedHandler.cs, ProductProjectionHandler.cs;
│  │  │                   #   S7: Features/Internal/GetVariantChanges.cs (delta cho Bff.Pos)
│  │  ├─ Customer.Api/    # Domain/Customer.cs (+Address, LoyaltyAccount), Features/{Me,Addresses,Admin,Internal};
│  │  │                   #   S7: Features/Internal/GetCustomerChanges.cs
│  │  ├─ Cart.Api/        # Redis: Data/RedisCartStore.cs, Clients/{Catalog,Discount}Client.cs,
│  │  │                   #   Features/CartEndpoints.cs, CartPricing.cs, InternalCarts.cs
│  │  ├─ Inventory.Api/   # Domain/{Location,StockLevel,StockMovement,Reservation,StockLedger}.cs
│  │  ├─ Discount.Api/    # Domain/{Promotion,Coupon}.cs, Pricing/PricingEngine.cs,
│  │  │                   #   Services/{PromotionCache,CouponService,QuoteService}.cs, Features/{Quote,Admin};
│  │  │                   #   S7: Features/Internal/GetPromotionChanges.cs
│  │  ├─ Ordering.Api/    # Domain/Order.cs, Sagas/{CheckoutSaga,CheckoutSagaState}.cs, Clients/ServiceClients.cs,
│  │  │                   #   Features/Checkout/CheckoutService.cs, Jobs/ExpireUnpaidOrdersJob.cs, ReadModel/,
│  │  │                   #   EventHandlers/FlashReservationCreatedHandler.cs = OrderWorker (S6)
│  │  ├─ Payment.Api/     # Domain/Payment.cs, FakeGateway/FakePaymentProvider.cs
│  │  ├─ Notification.Worker/  # Templates/order-paid.liquid, Handlers/OrderPaidHandler.cs
│  │  ├─ FlashSale.Api/   # S6, chỉ lo quota: Domain/{Campaign,CampaignItem,FlashPurchase}.cs,
│  │  │                   #   Redis/{FlashKeys,FlashStockStore,LuaScripts}.cs, Jobs/{AllocateJob,CampaignScheduler,ReconcileJob}.cs,
│  │  │                   #   Workers/{AdmissionWorker,ExpiryWorker,PurchaseRecorder}.cs, Realtime/FlashHub.cs,
│  │  │                   #   Features/Naive/BuyNaive.cs (bản ngây thơ để so), EventHandlers/
│  │  └─ Store.Api/       # Domain/{Store,Register,Shift,CashMovement,PosTransaction}.cs (S7)
│  └─ Web/                # Nx workspace
│     ├─ apps/storefront/  apps/admin/  apps/pos/ (S7)
│     └─ libs/auth/  libs/api-client/ (viết tay)  libs/ui/  libs/pricing/ (S7)
├─ tests/
│  ├─ Directory.Build.props   # xUnit v3 + Shouldly cho mọi project test
│  ├─ TestKit/                # Postgres/Redis/RabbitMq/MongoFixture, ShopLabApiFactory<T>, TestAuthHandler
│  ├─ BuildingBlocks.Tests/   # outbox, publisher, consumer host
│  ├─ Catalog.Tests/  Customer.Tests/  Cart.Tests/  Inventory.Tests/
│  ├─ Ordering.Tests/  Discount.Tests/  BffAdmin.Tests/
│  ├─ FlashSale.Tests/  Store.Tests/       # S6, S7
│  └─ Architecture.Tests/     # NetArchTest (S8)
├─ tools/          # new-service.py, sln-sync.py (tuỳ chọn), scaffold-angular-app.sh, get-token.sh, ef-migrations.sh,
│                  #   seed-loadtest.sh, double-submit.sh, receipt-500.sh, coupon-race.sh (S4), compare-catalog.sh (S5), kc-create-users.sh (S6), sql/,
│                  #   chaos/ (kill.sh…, S8), check.sh (S8: build + test + kiểm tra một lần)
├─ http/           # *.http theo service + gate-sN.http
├─ load/           # k6: checkout-normal.js, checkout-1000.js, browse.js (S5), flash-sale.js, flash-real-200.js (S6), README.md
└─ docs/           # notes/sN-*.md, benchmarks/, postmortems/,
                   #   guides/ShopLab-Sx.md (hướng dẫn từng bước — bản chuẩn để Claude Code đọc, không dùng link artifact)
```

Quy ước bên trong mỗi service:

- `Features/` gom endpoint theo resource: CRUD nhỏ của một resource nằm chung một file (vd `Features/Admin/AdminStock.cs`, `Features/Addresses/Addresses.cs`), use case có logic riêng thì một file (vd `Features/Checkout/PlaceOrder.cs`). Mỗi file là một class `IEndpoint` có `Map()` khai báo route, request record (validation bằng DataAnnotations) và handler. `UseShopLabApi` quét assembly và map mọi endpoint. Đọc một file là hiểu một resource hoặc một use case.
- `Domain/` chứa entity có hành vi (vd `StockLevel.Reserve(qty)` ném lỗi khi thiếu hàng), không có anemic model.
- Mỗi DbContext có bảng `outbox_messages` và `inbox_messages` riêng, schema = tên service.

## Lệnh khởi tạo và chạy

Toàn bộ hệ thống chạy bằng `aspire run` từ thư mục gốc; Postgres, Redis, RabbitMQ, Keycloak, Mailpit đều là container do AppHost tự kéo lên. Máy cần khoảng 8 GB RAM trống cho Docker.

**1. Cài công cụ (một lần)**

```bash
# .NET 10 SDK, Docker Desktop/Podman, Node 22 LTS, k6 cài theo trang chủ của từng tool
dotnet tool install -g Aspire.Cli
dotnet tool install -g dotnet-ef
dotnet new install Aspire.ProjectTemplates
npm i -g nx
```

**2. Dựng khung solution**

```bash
mkdir shoplab && cd shoplab
git init
dotnet new gitignore && dotnet new editorconfig
dotnet new buildprops && dotnet new packagesprops   # Directory.Build.props, Directory.Packages.props
dotnet new sln -n shoplab --format slnx

# Project dùng chung (S0)
dotnet new aspire-apphost         -n AppHost         -o src/AppHost
dotnet new aspire-servicedefaults -n ServiceDefaults -o src/ServiceDefaults
dotnet new classlib -n BuildingBlocks -o src/BuildingBlocks
dotnet new classlib -n Contracts      -o src/Contracts
dotnet new web -n Gateway.Web -o src/Gateways/Gateway.Web
dotnet new web -n Catalog.Api -o src/Services/Catalog.Api
dotnet sln add src/AppHost src/ServiceDefaults src/BuildingBlocks src/Contracts src/Gateways/Gateway.Web src/Services/Catalog.Api

# Service mới ở các bước sau: script của repo tạo csproj + launchSettings + ApiMarker theo quy ước
python3 tools/new-service.py Customer 5102          # S2 (Inventory 5104, Ordering 5105, Payment 5106)
python3 tools/new-service.py Cart 5103 --no-ef      # service không dùng Postgres
python3 tools/new-service.py Discount 5107          # S4
python3 tools/new-service.py Bff.Admin 5201 --gateway   # S5
dotnet new worker -n Notification.Worker -o src/Services/Notification.Worker   # S3
dotnet sln add src/Services/Customer.Api            # mỗi project mới một lệnh, làm ngay sau khi tạo

# Test
dotnet new install xunit.v3.templates
dotnet new xunit3 -n Catalog.Tests -o tests/Catalog.Tests
dotnet new classlib -n TestKit -o tests/TestKit     # S1: fixture dùng chung
dotnet sln add tests/Catalog.Tests tests/TestKit

# Tuỳ chọn: đồng bộ lại solution với mọi csproj trong src/ và tests/ nếu lỡ quên sln add
python3 tools/sln-sync.py
```

Cổng cố định của từng project (`applicationUrl` trong `Properties/launchSettings.json`, là tham số thứ hai của `tools/new-service.py`). AppHost vẫn cấp endpoint qua service discovery; cổng này dùng cho file `http/*.http` và khi chạy riêng một service.

| Project | Cổng | Bước | Ghi chú |
| --- | --- | --- | --- |
| Gateway.Web | 5000 | S0 | cửa vào duy nhất của storefront/admin |
| Catalog.Api | 5101 | S0 |  |
| Customer.Api | 5102 | S2 |  |
| Cart.Api | 5103 | S2 | Redis, không Postgres |
| Inventory.Api | 5104 | S2 |  |
| Ordering.Api | 5105 | S2 | Hangfire dashboard `/hangfire` (S3) |
| Payment.Api | 5106 | S2 |  |
| Discount.Api | 5107 | S4 |  |
| FlashSale.Api | 5108 | S6 |  |
| Store.Api | 5109 | S7 |  |
| Bff.Admin | 5201 | S5 |  |
| Bff.Pos | 5202 | S7 |  |
| Notification.Worker | — | S3 | worker, không mở cổng |
| storefront / admin / pos | 4200 / 4300 / 4400 | S0 / S0 / S7 | Nx dev server, proxy `/api` → Gateway.Web |
| Keycloak / Mailpit UI / Mongo rs0 | 8080 / 8025 / 27017–27019 | S0 / S3 / S5 | cổng cố định trong AppHost |

**3. Package chính (khai báo trong Directory.Packages.props)**

```bash
# AppHost
dotnet add src/AppHost package Aspire.Hosting.PostgreSQL
dotnet add src/AppHost package Aspire.Hosting.Redis
dotnet add src/AppHost package Aspire.Hosting.RabbitMQ
dotnet add src/AppHost package Aspire.Hosting.Keycloak
dotnet add src/AppHost package Aspire.Hosting.JavaScript

# BuildingBlocks (mọi service dùng qua project reference, không tự khai lại)
dotnet add src/BuildingBlocks package Microsoft.AspNetCore.Authentication.JwtBearer   # S0
dotnet add src/BuildingBlocks package Aspire.Npgsql.EntityFrameworkCore.PostgreSQL    # S1
dotnet add src/BuildingBlocks package EFCore.NamingConventions
dotnet add src/BuildingBlocks package Microsoft.AspNetCore.OpenApi
dotnet add src/BuildingBlocks package Scalar.AspNetCore
dotnet add src/BuildingBlocks package Aspire.RabbitMQ.Client                          # S3 (Redis ở dòng dưới có từ S2)
dotnet add src/BuildingBlocks package Aspire.StackExchange.Redis                      # S2 (Cart), dùng lại ở S3, S4
dotnet add src/BuildingBlocks package MongoDB.Driver                                  # S5

# Theo service
dotnet add src/Services/<Svc>.Api package Microsoft.EntityFrameworkCore.Design         # service có DB
dotnet add src/Services/Ordering.Api package Hangfire.AspNetCore                      # S3
dotnet add src/Services/Ordering.Api package Hangfire.PostgreSql
dotnet add src/Services/FlashSale.Api package Hangfire.AspNetCore                     # S6
dotnet add src/Services/FlashSale.Api package Hangfire.PostgreSql
dotnet add src/Services/Notification.Worker package MailKit
dotnet add src/Services/Notification.Worker package Fluid.Core

# Gateway
dotnet add src/Gateways/Gateway.Web package Yarp.ReverseProxy
dotnet add src/Gateways/Gateway.Web package Microsoft.Extensions.ServiceDiscovery.Yarp

# Test (TestKit)
dotnet add tests/TestKit package Microsoft.AspNetCore.Mvc.Testing
dotnet add tests/TestKit package Testcontainers.PostgreSql   # + .Redis, .RabbitMq, .MongoDb
dotnet add tests/TestKit package Microsoft.Extensions.TimeProvider.Testing
```

**4. AppHost.cs (rút gọn)**

```csharp
var builder = DistributedApplication.CreateBuilder(args);

var pg       = builder.AddPostgres("pg").WithPgAdmin().WithDataVolume("shoplab-pg");
var redis    = builder.AddRedis("redis").WithRedisInsight().WithDataVolume("shoplab-redis");
var rabbit   = builder.AddRabbitMQ("rabbit").WithManagementPlugin().WithDataVolume("shoplab-rabbit");
// S5: 3 node Mongo dùng volume shoplab-mongo1, shoplab-mongo2, shoplab-mongo3
var keycloak = builder.AddKeycloak("keycloak", 8080)
                      .WithDataVolume("shoplab-keycloak")
                      .WithRealmImport("../../docker/keycloak");
var mailpit  = builder.AddContainer("mailpit", "axllent/mailpit")
                      .WithHttpEndpoint(8025, 8025, "ui")
                      .WithEndpoint(1025, 1025, name: "smtp");

var catalogDb   = pg.AddDatabase("catalogdb");
var inventoryDb = pg.AddDatabase("inventorydb");
var orderingDb  = pg.AddDatabase("orderingdb");
var flashsaleDb = pg.AddDatabase("flashsaledb");
// ... customerdb, discountdb, paymentdb, storedb

var inventory = builder.AddProject<Projects.Inventory_Api>("inventory")
    .WithReference(inventoryDb).WithReference(rabbit).WithReference(keycloak)
    .WaitFor(inventoryDb).WaitFor(rabbit);

var flashsale = builder.AddProject<Projects.FlashSale_Api>("flashsale")
    .WithReference(flashsaleDb)
    .WithReference(redis).WithReference(rabbit).WaitFor(redis);

// ... các service còn lại theo cùng mẫu

builder.AddProject<Projects.Gateway_Web>("gateway")
    .WithReference(inventory).WithReference(flashsale) /* + catalog, cart, ordering... */
    .WithReference(redis).WithExternalHttpEndpoints();

builder.Build().Run();
```

**MongoDB replica set (thêm ở S5).** Integration MongoDB của Aspire dựng một node; để có replica set 3 node, AppHost khai báo 3 container `mongo:8.0` (cổng 27017–27019, `--replSet rs0`) và container `mongo-init` chạy `docker/mongo/init-replset.sh` một lần; service dùng `WaitForCompletion(mongoInit)`. Chỗ dễ vấp nhất: tên host trong `rs.initiate` phải phân giải được từ cả container lẫn service chạy trên máy host, nên member khai báo bằng `host.docker.internal` (macOS/Linux thêm `127.0.0.1 host.docker.internal` vào /etc/hosts). Lab không bật auth cho Mongo; mỗi service chỉ dùng database của mình. Connection string chung: `mongodb://host.docker.internal:27017,host.docker.internal:27018,host.docker.internal:27019/?replicaSet=rs0`; database do code chọn (`catalog_read`, `ordering_read`, `admin_read`).

**5. Migration cho từng service**

```bash
./tools/ef-migrations.sh Init Inventory      # = dotnet ef migrations add Init -p src/Services/Inventory.Api -o Data/Migrations (bỏ tên service = mọi service)
# lặp lại cho Catalog, Customer, Discount, Ordering, Payment, FlashSale, Store khi cần
```

Ở môi trường Development/LoadTest, `InitializeDatabaseAsync<T>()` của mỗi service chạy `MigrateAsync()` nếu đã có migration, chưa có thì `EnsureCreatedAsync()`, rồi `SeedData.RunAsync()` (đọc `seed/*.json` khi bảng trống). Vì vậy lab chạy được ngay không cần migration; khi đổi model mà chưa có migration thì xoá volume `shoplab-pg`. Cart và Bff.Admin không có Postgres.

**6. Frontend**

```bash
cd src
npx create-nx-workspace@21.5.0 Web --preset=apps --pm=npm --nxCloud=skip --interactive=false
cd Web
npm i -D @nx/angular@21.5.0 @angular/build@^20.3 @angular/cli@^20.3 @angular/compiler-cli@^20.3
npx nx g @nx/angular:library --directory=libs/ui         --name=ui         --importPath=@shoplab/ui --standalone
npx nx g @nx/angular:library --directory=libs/auth       --name=auth       --importPath=@shoplab/auth --standalone
npx nx g @nx/angular:library --directory=libs/api-client --name=api-client --importPath=@shoplab/api-client --standalone
cd ../..
./tools/scaffold-angular-app.sh storefront 4200     # app tối giản, builder @angular/build, proxy /api → gateway
./tools/scaffold-angular-app.sh admin 4300
./tools/scaffold-angular-app.sh pos 4400            # S7, rồi: cd src/Web && npx nx g @angular/pwa --project=pos
```

**7. Chạy và kiểm tra**

```bash
aspire run                           # mở dashboard, mọi resource xanh là được
k6 run load/flash-sale.js            # sau khi đã có S6
dotnet test                          # Testcontainers tự dựng hạ tầng riêng
```

| STT | Địa chỉ local | Dùng để |
| --- | --- | --- |
| 1 | Aspire dashboard (link in ra khi `aspire run`) | Log, trace, metric của mọi service |
| 2 | `localhost:8080` | Keycloak admin (admin/admin) |
| 3 | `localhost:8025` | Mailpit, xem email gửi đi |
| 4 | RabbitMQ management (port do Aspire cấp) | Xem exchange, queue, DLQ |
| 5 | `localhost:27017–27019` | MongoDB replica set `rs0` (từ S5) |
| 6 | Gateway.Web | Điểm vào duy nhất cho storefront và k6 |

## Domain model

Mỗi service sở hữu đúng các bảng dưới đây; service khác chỉ biết `Sku`, `CustomerId`, `OrderId` dưới dạng giá trị, không có foreign key xuyên service. Tiền dùng `long` theo VND (không có phần lẻ), mọi thời gian là `DateTimeOffset` UTC.

**Audit và soft delete (dùng chung cho mọi service)**

```csharp
// Ký hiệu rút gọn (không phải cú pháp C#): lớp trừu tượng Auditable có 4 property
abstract Auditable { bool IsDeleted (mặc định false); bool IsActive (mặc định true); DateTimeOffset CreatedAt; DateTimeOffset UpdatedAt }

// Model có ": Auditable" mang đủ 4 cột trên; mọi thời gian là DateTimeOffset UTC
```

- `AuditInterceptor` (SaveChangesInterceptor trong BuildingBlocks): entity mới thì gán `CreatedAt = UpdatedAt = TimeProvider.GetUtcNow()`; entity bị sửa thì cập nhật `UpdatedAt`; entity bị xoá thì đổi trạng thái thành Modified và đặt `IsDeleted = true`. Code nghiệp vụ không tự gán các cột này.
- Global query filter `HasQueryFilter(e => !e.IsDeleted)` cho mọi `Auditable`. Màn hình admin xem bản đã xoá bằng `IgnoreQueryFilters()`.
- Unique index phải có lọc, ví dụ `HasIndex(x => x.Sku).IsUnique().HasFilter("is_deleted = false")`. Không lọc thì xoá mềm một SKU rồi tạo lại sẽ bị lỗi trùng.
- `IsActive` khác `Status`: `IsActive` là công tắc bật/tắt của admin (ẩn sản phẩm, khoá quầy POS, tạm dừng coupon); `Status` là vòng đời nghiệp vụ (Draft/Active/Archived, PendingPayment/Paid…).
- Read model trên Mongo giữ cả bản đã xoá/tắt nhưng đánh dấu `visible = false` (Status Active + IsActive + chưa xoá + category đang bật), storefront chỉ đọc bản visible. Xoá mềm hoặc tắt IsActive cũng phát event như mọi thay đổi khác; giữ document thay vì xoá để event cũ tới muộn không tạo lại bản đã xoá.
- Bản ghi append-only (`StockMovement`, `CouponRedemption`, `CashMovement`, `PosTransaction`) và dòng con nằm trong aggregate (`OrderLine`) chỉ có `CreatedAt`, không có soft delete. Sổ cái chỉ được thêm bút toán đảo, không được sửa hay xoá.

**Catalog** (`catalogdb`)

```csharp
Category(Guid Id, string Name, string Slug, Guid? ParentId) : Auditable
Product(Guid Id, string Name, string Slug, string Description, Guid CategoryId, string Brand, ProductStatus Status, long Version) : Auditable
ProductVariant(Guid Id, Guid ProductId, string Sku, string Name, long Price, long? CompareAtPrice, string? Barcode, Dictionary<string, string> Attributes, bool InStock) : Auditable

// ProductStatus: Draft | Active | Archived
// Sku unique (lọc is_deleted = false) · Attributes lưu jsonb · InStock là projection từ StockChanged
// Version tăng mỗi lần ghi, dùng cho projection sang Mongo
```

**Customer** (`customerdb`)

```csharp
Customer(Guid Id, string KeycloakUserId, string Email, string? Phone, string FullName, CustomerStatus Status) : Auditable
Address(Guid Id, Guid CustomerId, string Line1, string Ward, string District, string City, bool IsDefault) : Auditable
LoyaltyAccount(Guid CustomerId, int Points, LoyaltyTier Tier) : Auditable

// CustomerStatus: Active | Banned · LoyaltyTier: Member | Silver (≥ 500 điểm) | Gold (≥ 1.000 điểm); 1 điểm / 10.000 ₫
// Id = sub của Keycloak (ID cố định trong realm), dùng cho giỏ, đơn, /internal/customers/{id}; KeycloakUserId = Id dạng chuỗi
// Khách chưa có hồ sơ (vd user ảo k6) được coi là Active khi checkout
// Phone unique (lọc is_deleted = false)
```

**Cart** (Redis, không có DB)

```text
key  cart:{customerId} | cart:guest:{cartId}    JSON, TTL 48h, gia hạn mỗi lần sửa
{ key, couponCode?, updatedAt,
  lines: [ { sku, qty, unitPriceSnapshot, nameSnapshot, productSlug, categorySlug } ] }
// Giỏ vãng lai gửi header X-Cart-Id; đăng nhập thì POST /merge gộp vào giỏ user
// categorySlug (S4) để Discount áp khuyến mãi theo danh mục; giá trong giỏ là snapshot, checkout lấy giá mới
```

**Inventory** (`inventorydb`): trái tim của lab, viết kỹ nhất

```csharp
Location(Guid Id, string Code, string Name, LocationType Type, bool SellableOnline) : Auditable
StockLevel(string Sku, Guid LocationId, int OnHand, int Reserved, uint Version) : Auditable
StockMovement(long Id, string Sku, Guid LocationId, int Qty, MovementType Type, string RefType, string RefId, string By, DateTimeOffset CreatedAt)
Reservation(Guid Id, Guid OrderId, string Sku, Guid LocationId, int Qty, ReservationStatus Status, DateTimeOffset ExpiresAt) : Auditable

// LocationType: Warehouse | Store
// StockLevel: PK (Sku, LocationId) · Available = OnHand - Reserved · Version = xmin
//             hành vi: Reserve(qty), Release(qty), Commit(qty)
// StockMovement: append-only · Qty có dấu · unique (RefType, RefId, Sku, Type, LocationId) để DB chặn ghi trùng
// MovementType: Receipt | Sale | Return | TransferOut | TransferIn | Adjustment | FlashAllocation | FlashReturn | PosSale
// ReservationStatus: Active | Committed | Released · bia mộ: Sku = "*", Qty 0, LocationId = Guid.Empty, Released khi OrderCancelled tới trước OrderCreated;
//   không đụng StockLevel.Reserved (cột của StockLevel, không cộng từ reservation), mọi truy vấn hàng đang giữ lọc Status = Active
// Reserve: mỗi SKU lấy trọn ở location bán online đầu tiên (theo Code) đủ hàng, không tách; không đủ thì OUT_OF_STOCK cả đơn
```

Quy tắc: `StockLevel` chỉ được đổi cùng transaction với một `StockMovement` mới. Tổng `Qty` của movement theo (Sku, Location) luôn bằng `OnHand`; test reconcile kiểm tra đúng điều này.

**Discount** (`discountdb`)

```csharp
Promotion(Guid Id, string Name, string? Description, PromotionKind Kind, PromotionScope Scope, string? Target, long Value, long? MaxDiscount, long MinSubtotal, int? BuyQty, int? GetQty, DateTimeOffset StartsAt, DateTimeOffset? EndsAt, int Priority, bool Stackable, bool RequiresCoupon, List<string> Channels, uint Version) : Auditable
Coupon(Guid Id, string Code, Guid PromotionId, int? UsageLimit, int PerCustomerLimit, int UsedCount, uint Version) : Auditable
CouponRedemption(long Id, Guid CouponId, string Code, Guid OrderId, Guid? CustomerId, long Amount, RedemptionKind Kind, DateTimeOffset CreatedAt)

// PromotionKind: PercentOff | AmountOff | BuyXGetY · PromotionScope: Order | Category | Sku (Target = slug hoặc SKU)
// Channels: ["Online", "Pos"] (text[]) · RequiresCoupon = false: tự áp; true: chỉ áp qua coupon
// Coupon: Code unique (lọc is_deleted = false), check used_count <= usage_limit
// CouponRedemption append-only: Redeem / Revert, unique (OrderId, Kind); Revert số tiền 0 = "bia mộ" khi huỷ tới trước
// Engine giá thuần: Pricing/PricingEngine.cs, quy tắc ở mục Data mẫu
```

**Ordering** (`orderingdb`)

```csharp
Order(Guid Id, string Number, Guid? CustomerId, string? CustomerEmail, SalesChannel Channel, Guid? StoreId, OrderStatus Status, long Subtotal, long DiscountTotal, long Total, string? CouponCode, long CouponDiscount, string? ShippingAddress, string? CancelReason, string? IdempotencyKey, long Version) : Auditable
OrderLine(Guid OrderId, string Sku, string Name, int Qty, long UnitPrice, long LineDiscount, DateTimeOffset CreatedAt)
CheckoutSagaState(Guid OrderId, SagaStep Step, bool StockOk, bool CouponOk, Guid? PaymentId, string? LastError, DateTimeOffset PaymentDeadline, uint Version) : Auditable

// Number dạng SO-20261027-000123 (sequence Postgres) · IdempotencyKey unique (lọc NOT NULL)
// SalesChannel: Online | Pos | FlashSale
// OrderStatus: PendingStock → PendingPayment → Paid, hoặc → Cancelled; Completed chỉ dùng cho đơn Pos
//              (đơn online/flash dừng ở Paid vì v1 không có giao hàng)
//              (hết hàng / hết hạn thanh toán / thanh toán lỗi / coupon hết lượt)
// LineDiscount = giảm của dòng + phần giảm giá đơn được phân bổ (S4)
// SagaStep: AwaitingStock | AwaitingPayment | Completed | Compensated; đòi tiền khi StockOk && CouponOk
//           (từ S4, AwaitingStock = chờ giữ hàng và trừ lượt coupon; S6 kênh FlashSale chờ lệnh /pay)
// Order.Version tăng mỗi lần đổi trạng thái, dùng cho projection sang Mongo
```

**Payment** (`paymentdb`)

```csharp
Payment(Guid Id, Guid OrderId, long Amount, PaymentMethod Method, PaymentStatus Status, string? ProviderRef) : Auditable

// OrderId unique · PaymentMethod: Fake | Cash | Card | VietQr
// PaymentStatus: Pending | Succeeded | Failed | Refunded
```

`FakePaymentProvider` cấu hình được tỉ lệ thất bại (vd 10%) và độ trễ (200–2.000 ms) để luyện nhánh bù trừ của saga.

**FlashSale** (`flashsaledb` + Redis)

```csharp
Campaign(Guid Id, string Name, DateTimeOffset StartsAt, DateTimeOffset EndsAt, CampaignStatus Status) : Auditable
CampaignItem(Guid CampaignId, string Sku, long FlashPrice, int Quota, int PerUserLimit, Guid SourceLocationId, int Sold) : Auditable   // Sold chỉ dùng cho bản naive
FlashPurchase(Guid ReservationId, Guid CampaignId, string Sku, Guid CustomerId, int Qty, FlashPurchaseStatus Status, Guid? OrderId, DateTimeOffset ExpiresAt) : Auditable

// CampaignStatus: Draft | Scheduled | AllocationFailed | Live | Ended | Reconciled
//   AllocationFailed: AllocateJob lúc T − 1 phút không đủ kho, đã trả phần vừa cấp và cảnh báo admin;
//   admin sửa quota hoặc nhập kho rồi lên lịch lại (về Scheduled). Không bao giờ sang Live từ trạng thái này.
// FlashPurchaseStatus: Reserved | OrderCreated | Paid | Released
// CampaignItem PK: (CampaignId, Sku) · FlashPurchase PK: ReservationId
// Campaign đã Live không cho xoá mềm hay tắt IsActive; muốn dừng thì chuyển Ended
```

```text
fs:{campId}:stock:{sku}     INT     số còn lại, nạp lúc Scheduled → Live
fs:{campId}:buyers:{sku}    HASH    customerId → số đã giữ
fs:{campId}:res:{resId}     HASH    sku, qty, customerId; TTL = hạn thanh toán + 5 phút (phải dài hơn mốc ExpiryWorker hạn + 2 phút)
fs:{campId}:expiry          ZSET    resId → hạn (unix giây) = hạn thanh toán + 2 phút; reserve.lua ZADD, release.lua ZREM,
                                    ExpiryWorker ZRANGEBYSCORE -inf now mỗi 5 giây
fs:{campId}:sold:{sku}      INT     đếm để dashboard admin
fs:admit:{campId}           ZSET    phòng chờ: customerId → thứ tự vào
```

**Store / POS** (`storedb`)

```csharp
Store(Guid Id, string Code, string Name, Guid LocationId) : Auditable
Register(Guid Id, Guid StoreId, string Name, string DeviceId) : Auditable
Shift(Guid Id, Guid RegisterId, string CashierId, DateTimeOffset OpenedAt, DateTimeOffset? ClosedAt, long OpeningCash, long ExpectedCash, long? CountedCash) : Auditable
CashMovement(Guid Id, Guid ShiftId, CashMovementType Type, long Amount, string? RefId, DateTimeOffset CreatedAt)
PosTransaction(Guid ClientTxnId, Guid RegisterId, Guid ShiftId, DateTimeOffset OccurredAt, SyncStatus Status, string PayloadJson, DateTimeOffset CreatedAt)

// Store.LocationId trỏ sang Inventory.Location · PosTransaction PK: ClientTxnId, sinh trên máy POS
// CashMovement, PosTransaction append-only · OccurredAt = giờ trên máy POS, CreatedAt = giờ server nhận
// CashMovementType: Sale | Refund | PayIn | PayOut · SyncStatus: Received | Applied | Rejected
```

**Read model** (MongoDB, replica set `rs0`, chỉ 3 bên dùng)

```js
// catalog_read.products: 1 document / product, Catalog chiếu từ ProductChanged (đọc lại bản mới từ Postgres)
{ _id: "<productId>", version: 7, name: "Tai nghe SL Buds Pro", slug: "sl-buds-pro", brand: "ShopLab",
  searchText: "tai nghe sl buds pro shoplab", categoryId: "<id>", categorySlug: "dien-tu", categoryName: "Điện tử",
  minPrice: 2490000, compareAtPrice: 2990000, inStock: true, visible: true,
  variants: [ { sku: "SL-BUDS-PRO-BLK", name: "Đen", price: 2490000, compareAtPrice: 2990000, inStock: true } ],
  updatedAt: ISODate("..."), projectedAt: ISODate("...") }

// ordering_read.orders: 1 document / order, Ordering chiếu từ OrderStatusChanged
{ _id: "<orderId>", version: 4, number: "SO-20261027-000123", customerId: "<id>", channel: "Online",
  status: "Paid", subtotal: 599000, discountTotal: 45000, total: 554000, couponCode: null, itemCount: 2,
  lines: [ { sku: "SL-MOUSE-WL", name: "Chuột không dây SL", qty: 1, unitPrice: 450000, lineDiscount: 45000 } ],
  createdAt: ISODate("..."), updatedAt: ISODate("...") }

// admin_read (Bff.Admin): daily_sales, sku_sales cộng dồn $inc trong transaction cùng inbox; stock ghi đè theo thời điểm
{ _id: "2026-10-27|Online", date: "2026-10-27", channel: "Online", orders: 42, revenue: 31250000, discount: 900000, items: 57, cancelled: 3 }
{ _id: "2026-10-27|SL-MOUSE-WL", date: "2026-10-27", sku: "SL-MOUSE-WL", name: "Chuột không dây SL", qty: 9, revenue: 3645000 }
{ _id: "SL-NOTE-A5", availableOnline: 3, onHandTotal: 3, updatedAt: ISODate("...") }
```

Index: products có `{ visible: 1, categorySlug: 1, name: 1, _id: 1 }` và `{ visible: 1, name: 1, _id: 1 }` cho keyset; tìm `q` bằng regex trên `searchText` (đã bỏ dấu, viết thường), không dùng text index vì text index không tìm được một phần từ. orders có `{ customerId: 1, createdAt: -1, _id: -1 }`. Projection phải idempotent: `UpsertIfNewer` chỉ ghi khi `version` mới lớn hơn bản trong document. Postgres vẫn là nguồn sự thật: `POST /admin/read-model/rebuild` dựng lại, `GET /admin/read-model/compare` so (Id, Version) giữa hai bên.

**Integration event**

| STT | Event (routing key) | Payload | Phát bởi | Nghe bởi |
| --- | --- | --- | --- | --- |
| 1 | `ProductChanged` (`catalog.product_changed`) | `ProductId, ProductVersion` — event mỏng, bên nghe đọc lại | Catalog | Catalog (read model Mongo, S5). Bff.Pos không nghe event, delta lấy qua REST \`changes?since=\` (S7) |
| 2 | `StockChanged` (`inventory.stock_changed`) | `Sku, AvailableOnline, OnHandTotal` | Inventory | Catalog (`InStock`), Bff.Admin (cảnh báo tồn thấp) |
| 3 | `OrderCreated` (`orders.order_created`) | `OrderId, Number, CustomerId?, Channel, Total, Lines[Sku, Name, Qty, UnitPrice, LineDiscount]` (S3), `RequiresStock` (S3; `false` với đơn `FlashSale`), `CouponCode?` (có từ S3, luôn null tới S4), `CouponDiscount` (S4), `ReservationId?` (S6, chỉ đơn FlashSale); consumer cũ bỏ qua field mới. Đơn `Pos` không phát `OrderCreated`, chỉ `OrderPaid` | Ordering | Inventory (reserve), Discount (redeem coupon), FlashSale (gắn orderId vào reservation, báo SignalR) |
| 4 | `StockReserved` / `StockReservationFailed` (`inventory.stock_reserved` / `inventory.stock_reservation_failed`) | `OrderId` / `OrderId, Reason` | Inventory | Ordering (saga) |
| 5 | `PaymentRequested` (`payments.payment_requested`) | `OrderId, Amount` | Ordering | Payment |
| 6 | `PaymentSucceeded` / `PaymentFailed` (`payments.payment_succeeded` / `payments.payment_failed`) | `OrderId, PaymentId, Amount` / `OrderId, Reason` | Payment | Ordering (saga) |
| 7 | `OrderPaid` (`orders.order_paid`) | `OrderId, Number, CustomerId?, CustomerEmail?, Channel, StoreId?, Total, DiscountTotal, Lines, PaidAt, ReservationId?` — event béo; `ReservationId` thêm ở S6 (chỉ đơn FlashSale) để FlashSale đặt cờ `paid` kể cả khi `OrderPaid` tới trước `OrderCreated` | Ordering | Inventory (commit các reservation đang có của `OrderId`, không có thì không làm gì — đúng cho cả `Pos` lẫn `FlashSale`, không commit theo danh sách dòng của event), Notification (bỏ qua kênh `Pos`), Customer (cộng điểm, mọi kênh), Cart (chỉ xoá giỏ với kênh `Online`), Bff.Admin (doanh thu, mọi kênh), FlashSale (theo `ReservationId` đặt cờ `paid` để `release.lua` không trả quota). Đây là event duy nhất báo "đã thu tiền", kể cả đơn POS |
| 8 | `OrderCancelled` (`orders.order_cancelled`) | `OrderId, CustomerId?, Channel, Reason, CouponCode?, ReservationId?` — `ReservationId` thêm ở S6 để FlashSale trả quota không phụ thuộc thứ tự tới của `OrderCreated` | Ordering (duy nhất) | Inventory (release), Discount (hoàn lượt dùng), FlashSale (trả quota), Bff.Admin (đếm đơn huỷ, không trừ doanh thu vì không có Paid → Cancelled). Payment **không** nghe event này |
| 9 | `FlashReservationCreated` (`flashsale.reservation_created`, dự kiến) | `ReservationId, CampaignId, CustomerId, Sku, Qty, FlashPrice, ExpiresAt` | FlashSale | Ordering (tạo order kênh FlashSale) |
| 10 | `FlashReservationReleased` (`flashsale.reservation_released`, dự kiến) | `ReservationId, CampaignId, Sku, Qty, Reason` | FlashSale | Ordering (huỷ đơn chưa trả tiền / ghi bia mộ), Bff.Admin (dashboard) |
| 11 | `PosSaleRecorded` (`stores.pos_sale_recorded`, dự kiến) | `ClientTxnId, StoreId, LocationId, RegisterId, CustomerId?, Lines, Total, PaymentMethod, SoldAt` — `ClientTxnId` là khoá chính của `PosTransaction` (sinh trên máy POS), Ordering dùng làm `IdempotencyKey`; `LocationId` là kho của cửa hàng (Store tra trong `storedb`), Inventory trừ thẳng tại đó | Store | Ordering (tạo order kênh `Pos` ở trạng thái `Completed`, rồi phát `OrderPaid`), Inventory (movement `PosSale` tại `LocationId`). Customer **không** nghe event này, điểm lấy từ `OrderPaid` |
| 12 | `OrderStatusChanged` (`orders.order_status_changed`) | `OrderId, Status, OrderVersion` | Ordering | Ordering (read model “đơn của tôi”, S5) |
| 13 | `PaymentRefundRequested` (`payments.refund_requested`) | `OrderId, Reason` | Ordering (saga, khi tiền về sau lúc đơn đã huỷ) | Payment (hoàn tiền; đây là đường duy nhất dẫn tới `Refunded`) |
| 14 | `CouponRedeemed` / `CouponRedemptionFailed` (`discount.coupon_redeemed` / `discount.coupon_redemption_failed`) | `OrderId, Code, Amount` / `OrderId, Code, Reason` | Discount | Ordering (saga: đòi tiền khi đã giữ hàng và trừ lượt coupon / huỷ đơn) |
| 15 | PosRefundRecorded (stores.pos\_refund\_recorded, dự kiến, S7, có thể cắt) | RefundId, OriginalClientTxnId, StoreId, LocationId, CustomerId?, Lines\[Sku, Qty, UnitPrice\], Amount, RefundedAt | Store | Inventory (movement Return tại LocationId), Customer (trừ điểm theo Amount, 1 điểm / 10.000 ₫), Bff.Admin (trừ doanh thu ngày hoàn) |

Mọi event kế thừa `IntegrationEvent` (`EventId`, `OccurredAt`, `CorrelationId`, `Version`; ý nghĩa từng field ở đoạn quy ước ngay dưới). Event ghi "dự kiến" (S6, S7) chốt khi thiết kế bước đó và cập nhật lại bảng này; event đã có trong repo lấy `src/Contracts/` làm chuẩn. Thêm field mới luôn là field tuỳ chọn (nullable, có mặc định) để consumer cũ không vỡ. API: chuẩn là file OpenAPI sinh lúc build ở `contracts/openapi/<Service>.json`; mỗi file `ShopLab-Sx.md` liệt kê endpoint mới của bước.

Quy ước phong bì: `EventId` (Guid v7, khoá của inbox); `OccurredAt`; `CorrelationId` = id của luồng nghiệp vụ mà event thuộc về — `OrderId` cho mọi event của một đơn (kể cả đơn flash sau khi đã tạo), `ReservationId` cho event flash sale trước khi có đơn (`FlashReservationCreated`, `FlashReservationReleased`), `ClientTxnId` cho `PosSaleRecorded`, `OriginalClientTxnId` cho `PosRefundRecorded` (hoàn tiền thuộc luồng của giao dịch bán gốc), rỗng với event không thuộc luồng nào (`ProductChanged`, `StockChanged`); `Version` (mặc định 1). Exchange: `ecommerce.events` (topic), routing key `<service>.<event>`, mỗi consumer một queue + một DLQ, nên hai event khác loại có thể được xử lý khác thứ tự phát: handler không được giả định `OrderCreated` đã chạy trước `OrderPaid`/`OrderCancelled`.

## Lộ trình theo phase

V3 đi từ một web bán hàng đơn giản, các service gọi nhau đồng bộ, lên dần bản đầy đủ qua 9 bước S0–S8. Mỗi bước thêm đúng một lớp hạ tầng hoặc một năng lực mới, và luôn để lại một hệ thống chạy được từ UI. Tổng 85–121 ngày công, tự code hoàn toàn. Làm ngoài giờ khoảng 11 giờ/tuần thì có **web đặt hàng được sau 4,5–6 tháng**, **flash sale sau 11–16 tháng**, **đủ tính năng sau 14–20,5 tháng**.

So với v2: web có giao diện ngay từ S1 thay vì đợi tới tháng 7,5–11, nhưng flash sale đến muộn hơn 5–7 tháng và tổng dài hơn khoảng 1,5–2,5 tháng. Phần dài thêm đến từ MongoDB (S5) và việc cố ý viết checkout đồng bộ ở S2 rồi chuyển sang event-driven ở S3. Lần viết lại này là có chủ đích: bạn thấy hệ thống đồng bộ gãy ở đâu trước khi dùng Outbox và Saga để sửa.

&#91;embedded content: 9 bước từ web đơn giản đến đầy đủ · dòng 1: hạ tầng thêm vào · dòng 2: gate\]

S2 là mốc có web đặt hàng được; S6 là trọng tâm của lab.

| STT | Bước | Ngày công | Ngoài giờ (11 giờ/tuần) | Cộng dồn ngoài giờ |
| --- | --- | --- | --- | --- |
| 1 | S0. Nền móng sớm | 5–7 | 4–5 tuần | 1 tháng |
| 2 | S1. Web catalog | 7–10 | 5–7 tuần | 2–3 tháng |
| 3 | S2. Đặt hàng đồng bộ | 14–19 | 10–14 tuần | **4,5–6 tháng** |
| 4 | S3. Chuyển sang event-driven | 13–18 | 9–13 tuần | 6,5–9 tháng |
| 5 | S4. Discount | 7–10 | 5–7 tuần | 7,5–11 tháng |
| 6 | S5. Read model MongoDB | 7–10 | 5–7 tuần | 9–12,5 tháng |
| 7 | S6. Flash sale | 14–20 | 10–15 tuần | **11–16 tháng** |
| 8 | S7. POS | 12–18 | 9–13 tuần | 13–19 tháng |
| 9 | S8. Hardening | 6–9 | 4–7 tuần | **14–20,5 tháng** |

### Hạ tầng dựng sớm và hạ tầng để sau

| STT | Thành phần | Bước | Lý do |
| --- | --- | --- | --- |
| 1 | AppHost + ServiceDefaults (OpenTelemetry) | S0 | Trace là công cụ debug chính khi có nhiều service; gắn sau thì phải sửa lại từng service |
| 2 | PostgreSQL + pipeline migration/seed | S0 | Mọi service có ghi dữ liệu đều dùng |
| 3 | Keycloak + Gateway.Web | S0 | Đổi mô hình auth về sau phải sửa mọi API lẫn UI; gateway giữ URL `/api/*` cố định để tách service sau không đụng frontend |
| 4 | Nx workspace, `libs/auth`, `libs/api-client` viết tay (mỗi service một `*.api.ts`, đối chiếu OpenAPI sinh lúc build) | S0 | UI có từ S1; `api-client` viết tay nên API đổi thì sửa `*.api.ts` cùng commit (sinh tự động bằng `ng-openapi-gen` là bài tập mở rộng) |
| 5 | Testcontainers harness | S0 | Bước nào viết test ngay bước đó, không dồn về cuối |
| 6 | Redis, k6 | S2 | Lần đầu có giỏ hàng; lấy baseline của checkout đồng bộ |
| 7 | RabbitMQ, Hangfire, Mailpit | S3 | Lần đầu cần event, job hẹn giờ, email |
| 8 | MongoDB replica set `rs0` | S5 | Read model chỉ có ý nghĩa khi đã có event để chiếu sang |

### Các bước

**S0. Nền móng sớm (5–7 ngày)**

- [ ] AppHost với Postgres, Keycloak; ServiceDefaults với OpenTelemetry, `/health`, `/alive`, resilience handler
- [ ] Keycloak realm `shoplab`: 4 role, client `storefront`, `admin`, `pos`, `gateway`, shoplab-cli (direct access grant, chỉ dev, cho get-token.sh), user mẫu
- [ ] Gateway.Web: YARP + JWT, route `/api/*`
- [ ] Nx workspace với `apps/storefront`, `apps/admin` trống; `libs/auth` (OIDC), `libs/api-client` viết tay (`system.api.ts` gọi `/api/ping`)
- [ ] Bộ test Testcontainers với 1 test mẫu chạy trong `dotnet test`
- [ ] Gate: đăng nhập storefront qua Keycloak được; `GET /api/ping` qua gateway có token được 200, không token được 401

**S1. Web catalog (7–10 ngày)**

- [ ] Catalog: CRUD product/variant/category, tìm theo tên + category, phân trang keyset; seed `categories.json`, `products.json`
- [ ] Storefront: danh sách và chi tiết sản phẩm
- [ ] Admin: quản lý sản phẩm, category
- [ ] Gate: admin tạo sản phẩm mới, storefront thấy ngay; user `customer` gọi API admin bị 403

**S2. Đặt hàng đồng bộ (14–19 ngày)**

- [ ] Customer: tạo hồ sơ khi đăng nhập lần đầu (từ claim Keycloak), địa chỉ, ban/unban
- [ ] Cart trên Redis: thêm/sửa/xoá dòng, snapshot giá
- [ ] Inventory với Location, StockLevel, StockMovement ngay từ đầu (đổi mô hình kho về sau rất tốn); nhập hàng, chuyển kho; seed `locations.json`, `stock.json`
- [ ] Ordering + Payment: `POST /checkout` gọi HTTP lần lượt Catalog (giá) → Inventory (reserve) → FakePayment → commit, tất cả trong một request; chưa có `Idempotency-Key`
- [ ] Storefront: giỏ hàng, checkout, "đơn của tôi"; Admin: khách hàng, tồn kho theo location
- [ ] k6 `checkout-normal.js`: ghi baseline p95 và tỉ lệ lỗi
- [ ] Gate: đặt hàng end-to-end từ UI được; chạy 3 kịch bản gãy và ghi lại hậu quả: (1) kill Inventory giữa checkout, (2) FakePayment trễ 30 giây, (3) client bấm "Đặt hàng" 2 lần

**S3. Chuyển sang event-driven (13–18 ngày)**

- [ ] `IOutbox` (`EfOutbox` ghi cùng transaction), `OutboxPublisher` (FOR UPDATE SKIP LOCKED), `RabbitMqConsumerHost` (inbox EF/Redis, retry, DLQ), `InboxMessage`
- [ ] `StockChanged` → Catalog cập nhật `InStock`
- [ ] Viết lại checkout thành saga trong Ordering, có bù trừ; job Hangfire mỗi phút (ExpireUnpaidOrdersJob) huỷ order quá `PaymentDeadline`; thêm `Idempotency-Key`
- [ ] Notification.Worker gửi email qua Mailpit; Customer cộng điểm khi `OrderPaid`
- [ ] Gate: 3 kịch bản gãy ở S2 giờ tự hồi phục; dừng RabbitMQ giữa lúc nhập 500 phiếu không mất event; 1.000 checkout với 10% lỗi thanh toán không lệch kho; so k6 với baseline S2

**S4. Discount (7–10 ngày)**

- [ ] Engine giá thuần `PricingEngine`: 3 loại khuyến mãi, scope Order/Category/Sku, Stackable, MaxDiscount, MinSubtotal, Channels, phân bổ giảm giá đơn về dòng; Redis cache rule; `POST /internal/quote` cho Cart và Ordering
- [ ] Nối vào saga: `OrderCreated` → trừ lượt (UPDATE có điều kiện) → `CouponRedeemed` / `CouponRedemptionFailed`; saga chỉ đòi tiền khi đã giữ hàng và trừ lượt; `OrderCancelled` → hoàn lượt (hoặc ghi bia mộ)
- [ ] Storefront: nhập coupon ở giỏ hàng; Admin: quản lý promotion và coupon
- [ ] Gate: 12 ca trong seed/pricing-cases.json đúng từng đồng; 20 khách giành coupon 5 lượt (tools/coupon-race.sh) ra đúng 5 đơn Paid; checkout ở S3 vẫn xanh

**S5. Read model MongoDB (7–10 ngày)**

- [ ] Replica set `rs0` 3 node dùng chung; mỗi bên một database riêng: `catalog_read`, `ordering_read`, `admin_read` (không bật auth, bật thì cần keyFile — bài tập mở rộng)
- [ ] Catalog: `ProductDocument` cập nhật từ event; `SearchProducts` (danh sách, tìm kiếm của storefront) đọc Mongo khi bật cờ, giữ nguyên contract; chi tiết sản phẩm và API admin vẫn đọc Postgres
- [ ] Ordering: `OrderDocument` cho danh sách "đơn của tôi" (đọc primary); chi tiết đơn và danh sách đơn admin vẫn đọc Postgres
- [ ] Bff.Admin: projection doanh thu theo ngày, top SKU, tồn thấp; dashboard hiển thị projection lag
- [ ] Endpoint rebuild cho từng projection
- [ ] Gate: xoá `catalog_read`, rebuild, dữ liệu khớp 100% với Postgres; đo lại p95 trang danh sách so với S4

**S6. Flash sale (14–20 ngày)**

- [ ] Bản naive trên Postgres trước, đo k6 và ghi số liệu
- [ ] FlashSale.Api: campaign, item, chuyển trạng thái bằng Hangfire; cấp quota từ Inventory sang Redis
- [ ] Phòng chờ + flash token HMAC; FlashSale: `reserve.lua`, `ExpiryWorker` + `release.lua`, `ReconcileJob`; Ordering: `OrderWorker` (consumer `FlashReservationCreated` trong Ordering.Api)
- [ ] Storefront: trang flash sale có đếm ngược, phòng chờ, kết quả qua SignalR; Admin: tạo campaign, dashboard realtime
- [ ] Bảng so sánh naive và Redis, kèm giải thích vì sao khác nhau
- [ ] Gate: kịch bản flash sale ở mục dưới đạt toàn bộ tiêu chí và cả 4 bài diễn tập sự cố

**S7. POS (12–18 ngày)**

- [ ] Store.Api: store, register, mở/đóng ca, tiền mặt
- [ ] Bff.Pos: `GET /sync/pull?since=`, `POST /sync/push` (batch giao dịch)
- [ ] Angular `pos`: PWA, IndexedDB, quét mã vạch bằng bàn phím, in hoá đơn qua `window.print`
- [ ] `PosSaleRecorded` (có `LocationId`) → Ordering (order `Pos` `Completed` + phát `OrderPaid`) + Inventory (trừ tại `LocationId`); Customer cộng điểm và Bff.Admin tính doanh thu từ `OrderPaid`, không từ `PosSaleRecorded`
- [ ] Gate: tắt mạng, bán 20 giao dịch, bật mạng: server nhận đủ 20 order kênh Pos, đẩy lại lần 2 không tạo trùng, chênh lệch tiền khi đóng ca hiển thị đúng

**S8. Hardening (6–9 ngày)**

- [ ] Architecture tests: không service nào reference service khác; chỉ Catalog, Ordering, Bff.Admin có connection string Mongo, mỗi bên chỉ trỏ vào database của mình
- [ ] Dashboard: độ dài queue, outbox lag, projection lag, p95 checkout
- [ ] Diễn tập failover Mongo: kill primary khi storefront đang tải và Ordering đang ghi projection; đo thời gian bầu lại, xem driver tự kết nối lại
- [ ] Chaos thủ công: kill từng service giữa checkout và flash sale
- [ ] Bật lại `TreatWarningsAsErrors` trong `Directory.Build.props` (tắt từ S0 tới giờ), sửa hết cảnh báo; `tools/check.sh` build + test + kiểm tra kiến trúc một lần
- [ ] Gate: postmortem 1 trang cho mỗi lần kill; hệ thống tự hồi phục không cần sửa DB tay

## Scenario flash sale

Kịch bản chuẩn: 5.000 user ảo giành 3 SKU với tổng quota 900 trong 2 phút; đạt khi bán ra đúng bằng quota, không oversell, không user nào vượt giới hạn, và trang sản phẩm thường vẫn giữ p95 dưới 300 ms trong lúc sale.

**Campaign `LAB-1111`**

| STT | SKU | Tên | Giá gốc (VND) | Giá flash (VND) | Quota | Giới hạn/user | Lấy từ kho |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `SL-BUDS-PRO-BLK` | Tai nghe SL Buds Pro, đen | 2.490.000 | 990.000 | 100 | 1 | `WH-HCM` |
| 2 | `SL-BOTTLE-500-SLV` | Bình giữ nhiệt SL 500 ml, bạc | 390.000 | 149.000 | 500 | 2 | `WH-HCM` |
| 3 | `SL-CHG-65W-WHT` | Sạc nhanh SL 65W, trắng | 690.000 | 299.000 | 300 | 3 | `WH-HN` |

**Mốc thời gian (T = giờ mở bán)**

1. T − 10 phút: Hangfire chuyển campaign `Scheduled`; trang flash sale được render tĩnh, đếm ngược theo `GET /flash/time` (giờ server).
2. T − 1 phút: FlashSale gọi Inventory ghi movement `FlashAllocation` (−quota tại kho nguồn), rồi `SET fs:{camp}:stock:{sku} <quota>`. Nếu kho không đủ, campaign không được Live và admin nhận cảnh báo.
3. T − 1 phút → T: user vào phòng chờ `POST /flash/{camp}/queue`, nhận vị trí (`ZADD NX`).
4. Từ T: mỗi giây `AdmissionWorker` cho 200 user đầu hàng đợi qua, cấp flash token HMAC (customerId, campId, exp 120 s) qua SignalR.
5. User gọi `POST /flash/{camp}/buy` kèm token + `Idempotency-Key`. Gateway kiểm token, rate limit 5 req/s/user.
6. FlashSale chạy `reserve.lua`. Trả `202 {reservationId}` hoặc `409 SOLD_OUT` / `409 LIMIT_REACHED` ngay, không chạm Postgres.
7. `OrderWorker` là consumer chạy trong **Ordering.Api** (`EventHandlers/FlashReservationCreatedHandler.cs`, do `RabbitMqConsumerHost` gọi), không phải project riêng. Nó đọc `FlashReservationCreated` (prefetch 20), tạo Order kênh `FlashSale` với `IdempotencyKey = reservationId`, trạng thái `PendingPayment`, hạn 10 phút. Ordering là service duy nhất ghi `orderingdb`; FlashSale nghe `OrderCreated` để gắn orderId vào reservation và báo client qua SignalR chuyển sang trang thanh toán; ở đó user bấm Thanh toán, gọi POST /api/orders/{id}/pay (Ordering phát PaymentRequested; với kênh FlashSale saga không tự đòi tiền).
8. Thanh toán thành công → `OrderPaid` (có `ReservationId`) → FlashSale đánh dấu `Paid` theo `ReservationId`; Inventory chạy quy tắc chung "commit reservation đang có của `OrderId`" và không tìm thấy reservation nào (đơn flash bỏ bước giữ kho), nên không trừ thêm — hàng đã rời kho nguồn ở bước allocation; Cart không đụng giỏ vì kênh không phải `Online`.
9. Hết hạn thanh toán: `ExpireUnpaidOrdersJob` của Ordering huỷ đơn và phát `OrderCancelled` — **Ordering là bên duy nhất phát event này**; FlashSale nghe nó và chạy `release.lua` trả quota. Lưới an toàn: mỗi 5 giây `ExpiryWorker` của FlashSale quét `ZRANGEBYSCORE fs:{camp}:expiry -inf now` (hạn thanh toán + 2 phút) cho reservation chưa có đơn, chạy `release.lua` rồi phát `FlashReservationReleased`; Ordering nghe event đó, huỷ đơn nếu đã tạo mà chưa trả tiền, hoặc ghi bia mộ theo reservationId để `FlashReservationCreated` tới muộn không tạo đơn.
10. Hết campaign, đợi EndsAt + hạn thanh toán + 2 phút (không còn reservation nào trong hạn): `ReconcileJob` so `quota − stock Redis` với số FlashPurchase `Paid`, ghi `FlashReturn` trả phần dư về kho nguồn, chuyển `Reconciled`.

**`reserve.lua`**

```lua
-- KEYS: 1 stock, 2 buyers, 3 res:{resId}, 4 expiry zset
-- ARGV: 1 customerId, 2 qty, 3 limit, 4 resId, 5 sku, 6 expireAtUnix, 7 ttlSeconds
local bought = tonumber(redis.call('HGET', KEYS[2], ARGV[1]) or '0')
if bought + tonumber(ARGV[2]) > tonumber(ARGV[3]) then return {-2, 0} end
local stock = tonumber(redis.call('GET', KEYS[1]) or '0')
if stock < tonumber(ARGV[2]) then return {-1, 0} end
redis.call('DECRBY', KEYS[1], ARGV[2])
redis.call('HINCRBY', KEYS[2], ARGV[1], ARGV[2])
redis.call('HSET', KEYS[3], 'customerId', ARGV[1], 'sku', ARGV[5], 'qty', ARGV[2])
redis.call('EXPIRE', KEYS[3], tonumber(ARGV[7]) + 300)
redis.call('ZADD', KEYS[4], ARGV[6], ARGV[4])
return {1, stock - tonumber(ARGV[2])}
```

`release.lua` làm ngược lại và **chỉ chạy nếu `res:{resId}` còn tồn tại và chưa có cờ `paid`**, sau đó `DEL` key đó; nhờ vậy job hết hạn và sự kiện thanh toán đến cùng lúc không thể hoàn hàng hai lần. Mọi key dùng hash tag `{camp}` để chạy được trên Redis Cluster. Bật AOF `appendfsync everysec` cho Redis.

**Hai phiên bản để so sánh (phần quan trọng nhất của lab)**

1. **Naive**: trực tiếp trong Postgres của FlashSale, `UPDATE campaign_items SET sold = sold + @q WHERE campaign_id = @c AND sku = @s AND sold + @q <= quota` (giới hạn theo quota, không theo tồn kho), giới hạn mỗi user bằng `SUM`, rồi phát `FlashReservationCreated` qua outbox để Ordering tạo đơn như bản thật (FlashSale vẫn không tạo đơn). Ghi lại p95, lỗi, số kết nối DB, có oversell hay không.
2. **Redis + queue** như trên. Chạy cùng kịch bản, so bảng số liệu. Viết 1 đoạn giải thích vì sao khác nhau (hot row, lock wait, connection pool).

**k6 (`load/flash-sale.js`, rút gọn)**

```javascript
import http from 'k6/http';
import { check } from 'k6';
import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

export const options = {
  scenarios: {
    buyers:  { executor: 'ramping-arrival-rate', startRate: 0, timeUnit: '1s',
               preAllocatedVUs: 2000, maxVUs: 5000,
               stages: [{ target: 3000, duration: '10s' }, { target: 3000, duration: '50s' },
                        { target: 0, duration: '60s' }], exec: 'buy' },
    browsers:{ executor: 'constant-arrival-rate', rate: 50, timeUnit: '1s', duration: '2m',
               preAllocatedVUs: 50, exec: 'browse' },
  },
  thresholds: {
    'http_req_duration{scenario:browsers}': ['p(95)<300'],
    'http_req_duration{name:buy}':          ['p(95)<150'],
    'http_req_failed{name:buy}':            ['rate<0.01'],   // 409 không tính là failed
  },
};
const BASE = __ENV.BASE, CAMP = 'LAB-1111';
const SKUS = ['SL-BUDS-PRO-BLK', 'SL-BOTTLE-500-SLV', 'SL-CHG-65W-WHT'];
http.setResponseCallback(http.expectedStatuses(202, 409));

export function buy() {
  const user = `loadtest-${Math.floor(Math.random() * 5000)}`;
  const sku  = SKUS[Math.floor(Math.random() * SKUS.length)];
  const res = http.post(`${BASE}/api/flash/${CAMP}/buy`, JSON.stringify({ sku, qty: 1 }), {
    headers: { 'Content-Type': 'application/json', 'X-Test-User': user,
               'Idempotency-Key': uuidv4() }, tags: { name: 'buy' } });
  check(res, { '202 or 409': r => r.status === 202 || r.status === 409 });
}
export function browse() { http.get(`${BASE}/api/catalog/products?size=20`); }
```

Header `X-Test-User` chỉ được gateway chấp nhận khi `ASPNETCORE_ENVIRONMENT=LoadTest`; nó thay cho việc cấp 5.000 token Keycloak và bỏ qua phòng chờ. Chạy riêng một bài nhỏ (200 user thật qua Keycloak + phòng chờ) để kiểm luồng token.

**Tiêu chí đạt**

| STT | Tiêu chí | Ngưỡng | Đo bằng |
| --- | --- | --- | --- |
| 1 | Oversell | 0 | `SUM(qty) FlashPurchase status≠Released` ≤ quota từng SKU |
| 2 | Vượt giới hạn/user | 0 user | `GROUP BY customer_id, sku HAVING SUM(qty) > limit` |
| 3 | Reservation thành order | 100% trong 30 s | `Reserved` không có OrderId sau 30 s = 0 |
| 4 | p95 `/buy` | < 150 ms | k6 |
| 5 | p95 trang catalog trong lúc sale | < 300 ms | k6 scenario `browsers` |
| 6 | Hoàn hàng hết hạn (hạn thanh toán 10 phút) | 100% trong hạn + 2 phút 10 giây (job mỗi phút trả trong hạn + 1 phút; lưới an toàn ở mốc hạn + 2 phút) | stock Redis + Paid = quota |
| 7 | Lệch kho sau reconcile | 0 | tổng movement = OnHand ở `WH-HCM`, `WH-HN` |

**Bài diễn tập sự cố (chạy lại kịch bản với từng lỗi)**

- Stop `Ordering.Api` (nơi chạy `OrderWorker`) 20 giây ở giữa: message `FlashReservationCreated` dồn queue, sau khi bật lại không mất reservation nào.
- Lỗi thanh toán 30%: quota được trả lại và bán tiếp cho người khác trong cùng campaign.
- Restart Redis lúc giây thứ 30: ghi lại mất gì với AOF everysec, và reconcile có bắt được lệch không.
- Gửi lại cùng `Idempotency-Key` 3 lần: chỉ một reservation.

## Data mẫu

Bộ seed nhỏ, có chủ đích: 7 SKU, 4 location, 7 khuyến mãi + 3 coupon, đủ cho luồng mua hàng và kịch bản flash sale. 12 ca tính giá nằm riêng ở `seed/pricing-cases.json`, mỗi ca tự khai báo khuyến mãi của nó nên không phụ thuộc seed. Chưa có seed số lượng lớn; muốn đo hiệu năng tìm kiếm thì viết thêm script sinh dữ liệu (vd Bogus) — để ở S8.

**Sản phẩm (`seed/products.json`)**

| STT | SKU | Tên | Category | Giá (VND) |
| --- | --- | --- | --- | --- |
| 1 | `SL-BUDS-PRO-BLK` | Tai nghe SL Buds Pro, đen | `dien-tu` | 2.490.000 |
| 2 | `SL-CHG-65W-WHT` | Sạc nhanh SL 65W, trắng | `dien-tu` | 690.000 |
| 3 | `SL-MOUSE-WL` | Chuột không dây SL | `dien-tu` | 450.000 |
| 4 | `SL-BOTTLE-500-SLV` | Bình giữ nhiệt SL 500 ml, bạc | `gia-dung` | 390.000 |
| 5 | `SL-BACKPACK-20L` | Balo SL 20L | `thoi-trang` | 890.000 |
| 6 | `SL-TEE-BASIC-M` | Áo thun SL Basic, size M | `thoi-trang` | 199.000 |
| 7 | `SL-NOTE-A5` | Sổ tay SL A5 | `van-phong-pham` | 49.000 |

```json
{
  "slug": "sl-buds-pro",
  "name": "Tai nghe SL Buds Pro",
  "category": "dien-tu",
  "brand": "ShopLab",
  "status": "Active",
  "description": "Tai nghe true wireless, chống ồn chủ động, pin 30 giờ.",
  "variants": [
    { "sku": "SL-BUDS-PRO-BLK", "name": "Đen", "price": 2490000,
      "compareAtPrice": 2990000, "barcode": "8930000000011",
      "attributes": { "color": "black" } }
  ]
}
```

**Location (`seed/locations.json`)**

| STT | Code | Tên | Loại | Bán online |
| --- | --- | --- | --- | --- |
| 1 | `WH-HCM` | Kho tổng TP.HCM | Warehouse | có |
| 2 | `WH-HN` | Kho tổng Hà Nội | Warehouse | có |
| 3 | `ST-Q1` | SL Store Quận 1 | Store | không |
| 4 | `ST-CG` | SL Store Cầu Giấy | Store | không |

**Tồn kho ban đầu (`seed/stock.json`, sinh thành movement `Receipt` với `RefType=Seed`)**

```csv
sku,WH-HCM,WH-HN,ST-Q1,ST-CG
SL-BUDS-PRO-BLK,250,120,15,10
SL-CHG-65W-WHT,80,400,12,8
SL-MOUSE-WL,200,150,20,15
SL-BOTTLE-500-SLV,800,300,40,30
SL-BACKPACK-20L,150,100,10,8
SL-TEE-BASIC-M,500,300,60,50
SL-NOTE-A5,1000,800,200,150
```

Đủ cho campaign `LAB-1111`: Buds lấy 100/250 ở `WH-HCM`, bình lấy 500/800 ở `WH-HCM`, sạc lấy 300/400 ở `WH-HN`.

**Khách hàng và tài khoản Keycloak**

| STT | Username | Role | Ghi chú |
| --- | --- | --- | --- |
| 1 | `admin@shoplab.local` | admin | Toàn quyền admin portal |
| 2 | `manager.q1` | store\_manager | Cửa hàng `ST-Q1`, đóng ca, hoàn tiền |
| 3 | `cashier.q1` | cashier | Quầy `Q1-R1` |
| 4 | `an.nguyen` | customer | Khách thường, SĐT 0901000001, Gold, 1.200 điểm |
| 5 | `binh.tran` | customer | Khách thường, 80 điểm; dùng `WELCOME50K` lần hai để thấy `COUPON_PER_CUSTOMER_LIMIT` |
| 6 | `chi.le` | customer | Trạng thái `Banned`, mọi API mua hàng trả 403 |
| 7 | `loadtest-0` … `loadtest-4999` | customer | Không tạo trong Keycloak; chỉ dùng qua header `X-Test-User` ở môi trường LoadTest |

Mật khẩu dev chung: `Passw0rd!`, nằm trong `shoplab-realm.json`, không dùng ở đâu khác.

**Cửa hàng (`seed/stores.json`)**: `ST-Q1` có 2 quầy `Q1-R1`, `Q1-R2`; `ST-CG` có 1 quầy `CG-R1`. Tiền đầu ca mặc định 2.000.000.

**Khuyến mãi và coupon (`seed/promotions.json`)** — ngày bắt đầu/kết thúc tính tương đối lúc seed (`startsInDays`, `durationDays`) để luôn còn hiệu lực khi chạy lab.

| STT | Khuyến mãi | Loại | Giá trị | Phạm vi | Kênh | Điều kiện | Cộng dồn | Áp dụng |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Giảm 10% đơn từ 500.000 ₫ | PercentOff | 10%, tối đa 100.000 | Cả đơn | Online, Pos | đơn từ 500.000 | không | tự áp |
| 2 | Thời trang giảm 20% | PercentOff | 20% | Danh mục `thoi-trang` | Online | không | không | tự áp |
| 3 | Sổ tay A5 mua 2 tặng 1 | BuyXGetY | mua 2 tặng 1 | SKU `SL-NOTE-A5` | Online, Pos | không | không | tự áp |
| 4 | WELCOME50K | AmountOff | 50.000 | Cả đơn | Online | đơn từ 300.000; 1 lần/khách | có | coupon `WELCOME50K`, không giới hạn tổng |
| 5 | GIAM100K | AmountOff | 100.000 | Cả đơn | Online | đơn từ 1.000.000; 1 lần/khách | không | coupon `GIAM100K`, 100 lượt |
| 6 | LAST5 | PercentOff | 15%, tối đa 200.000 | Cả đơn | Online | 1 lần/khách | không | coupon `LAST5`, 5 lượt (để thử tranh lượt) |
| 7 | Tai nghe giảm 300.000 ₫ | AmountOff | 300.000 / chiếc | SKU `SL-BUDS-PRO-BLK` | Online | đã hết hạn (để thử) | không | tự áp |

Quy tắc engine (`PricingEngine`, TS `libs/pricing` ở S7 phải giống hệt): pha dòng (Category/Sku) trước, pha đơn (Order) tính trên phần còn lại. `MinSubtotal` của khuyến mãi dòng so với tạm tính cả đơn, của khuyến mãi đơn so với phần còn lại. Trong mỗi pha, cái độc quyền tốt nhất so với tổng các cái cộng dồn, lấy bên lớn hơn. Coupon hợp lệ luôn được áp: coupon độc quyền thay khuyến mãi tự động cùng pha, coupon cộng dồn áp thêm. Giảm giá đơn phân bổ về từng dòng theo tỉ lệ (largest remainder); mọi số làm tròn xuống 1 ₫.

**12 ca tính giá (gate S4, `seed/pricing-cases.json`)** — mỗi ca tự khai báo khuyến mãi và thời điểm `now`, kèm kết quả kỳ vọng (giảm từng dòng, khuyến mãi đã áp, lỗi coupon).

Đầu vào đầy đủ của 12 ca (cột "Khuyến mãi của ca"). Mỗi ca tự khai khuyến mãi riêng, không đọc `seed/promotions.json`; mọi ca dùng `now = 2026-11-11T03:00:00Z`, kênh `Online`. Giá: Sạc 65W 690.000, Tai nghe 2.490.000, Chuột 450.000, Áo thun 199.000 (`thoi-trang`), Balo 890.000 (`thoi-trang`), Sổ tay A5 49.000, Bình giữ nhiệt 390.000. File `seed/pricing-cases.json` phải viết xong và commit (test đỏ) trước khi viết engine; cấm sửa khuyến mãi hay số mong đợi của một ca để test xanh, chỉ sửa engine.

| Ca | Kiểm tra | Giỏ | Khuyến mãi của ca | Coupon | Giảm (₫) | Tổng (₫) |
| --- | --- | --- | --- | --- | --- | --- |
| C01 | Giảm 10% đơn từ 500.000 ₫, đơn 690.000 ₫ | 1 Sạc 65W | PercentOff 10%, Order, MinSubtotal 500.000, độc quyền | không | 69.000 | 621.000 |
| C02 | Giảm 10% tối đa 50.000 ₫ trên đơn 2.490.000 ₫ | 1 Tai nghe | PercentOff 10%, Order, MaxDiscount 50.000 | không | 50.000 | 2.440.000 |
| C03 | Chưa đủ tối thiểu sau giảm dòng: `MinSubtotal` của khuyến mãi đơn xét trên phần còn lại | 3 Áo thun (597.000) | (a) PercentOff 20% Category `thoi-trang`; (b) PercentOff 10% Order, MinSubtotal 500.000 — còn 477.600 < 500.000 nên (b) không áp | không | 119.400 | 477.600 |
| C04 | Giảm 20% danh mục Thời trang, chỉ dòng thuộc danh mục | 2 Áo thun + 1 Chuột | PercentOff 20%, Category `thoi-trang` | không | 79.600 | 768.400 |
| C05 | Giảm 50.000 ₫ mỗi chiếc tai nghe, mua 2 | 2 Tai nghe | AmountOff 50.000, Sku `SL-BUDS-PRO-BLK` (mỗi chiếc) | không | 100.000 | 4.880.000 |
| C06 | Mua 2 tặng 1 sổ tay, mua 7 → tặng 2 | 7 Sổ tay A5 | BuyXGetY mua 2 tặng 1, Sku `SL-NOTE-A5` | không | 98.000 | 245.000 |
| C07 | Hai khuyến mãi không cộng dồn: chọn cái giảm nhiều hơn | 2 Sạc 65W | (a) PercentOff 10% Order; (b) AmountOff 100.000 Order; cả hai độc quyền | không | 138.000 | 1.242.000 |
| C08 | Cộng dồn (5% + 50.000) so với độc quyền 8%: lấy bên lớn hơn | 1 Tai nghe | (a) PercentOff 5% Order cộng dồn; (b) AmountOff 50.000 Order cộng dồn; (c) PercentOff 8% Order độc quyền | không | 199.200 | 2.290.800 |
| C09 | Giảm theo dòng trước, giảm theo đơn tính trên phần còn lại | 1 Balo | (a) PercentOff 20% Category `thoi-trang`; (b) PercentOff 10% Order, MinSubtotal 500.000 | không | 249.200 | 640.800 |
| C10 | Coupon không cộng dồn thay cho khuyến mãi đơn tự động | 1 Sạc 65W + 1 Bình giữ nhiệt | PercentOff 5% Order tự động | GIAM100K: AmountOff 100.000 Order, MinSubtotal 300.000, độc quyền | 100.000 | 980.000 |
| C11 | Coupon chưa đủ giá trị tối thiểu: báo lỗi, khuyến mãi tự động vẫn áp | 1 Chuột | PercentOff 5% Order tự động | GIAM100K1TR: AmountOff 100.000 Order, MinSubtotal 1.000.000 → `COUPON_MIN_SUBTOTAL` | 22.500 | 427.500 |
| C12 | Phân bổ giảm giá đơn về từng dòng (dư 1 ₫), khuyến mãi hết hạn bị bỏ qua | 1 Áo thun + 1 Sổ tay A5 + 1 Chuột | (a) AmountOff 100.000 Order; (b) PercentOff 50% Order đã hết hạn trước `now` | không | 100.000 | 598.000 |

## Kiểm thử và bài tập mở rộng

Mỗi service có logic có ít nhất một bộ integration test chạy trên Testcontainers (kể cả `Payment.Tests`: `PaymentRequested` lặp không trừ tiền hai lần, `PaymentRefundRequested` → `Refunded`; `BffAdmin.Tests`: `DashboardProjectionTests`). Gateway.Web và Notification.Worker chỉ có smoke test qua gate. Unit test chỉ dành cho domain có logic (StockLevel, engine giá, saga transition).

**Test bắt buộc trước khi đóng v1**

- [ ] `StockLevelTests`: Reserve vượt Available ném lỗi; Release không làm Reserved âm
- [ ] `InventoryConcurrencyTests`: 50 task cùng reserve 1 SKU còn 10 → đúng 10 thành công (xmin + retry); `ConditionalUpdateTests`: cách `UPDATE … WHERE available >= qty` cũng không bán vượt; `ReconcileTests`: tổng movement luôn bằng OnHand
- [ ] `BuildingBlocks.Tests`: `OutboxTests` (commit có đúng một dòng outbox, rollback không còn dòng nào), `OutboxPublisherTests` (2 publisher song song không gửi trùng, gửi lỗi thì thử lại), `ConsumerHostTests` (giao 2 lần chỉ xử lý 1, lỗi 3 lần vào DLQ)
- [ ] `PricingEngineTests`: 12 ca trong `seed/pricing-cases.json` dạng `[Theory]`; `CouponRedemptionTests`: 20 đơn tranh 5 lượt ra đúng 5, giới hạn mỗi khách khi song song, huỷ tới trước tạo để lại bia mộ
- [ ] `CheckoutSagaTests`, `CheckoutRecoveryTests`, `CouponSagaTests`: hết hàng, thanh toán lỗi, quá hạn, tiền về muộn (refund), coupon hết lượt đều về Cancelled và hoàn kho; 3 kịch bản gãy của S2 xanh
- [ ] `FlashReserveLuaTests`: chạy `reserve.lua` 1.000 lần song song trên Redis container, quota 100 → đúng 100 thành công, không user vượt limit
- [ ] `PosSyncTests`: push cùng batch 2 lần → số order không đổi
- [ ] `ArchitectureTests`: service không reference nhau, `Contracts` không reference gì ngoài BCL
- [ ] `ProductProjectionTests`, `OrderProjectionTests`, `DashboardProjectionTests`: event lặp hoặc sai thứ tự thì document Mongo vẫn đúng; tìm kiếm Mongo ra cùng kết quả với Postgres khi gõ có dấu (Mongo còn tìm được không dấu, Postgres thì không); rebuild sau khi mất dữ liệu khớp 100%; cùng `OrderPaid` giao 5 lần song song chỉ cộng doanh thu 1 lần
- [ ] `AuditTests`: tạo mới có `CreatedAt = UpdatedAt`; sửa chỉ đổi `UpdatedAt`; `Remove()` thành xoá mềm và query thường không thấy; xoá mềm SKU rồi tạo lại cùng SKU không lỗi trùng; ghi `StockMovement` lần hai bị chặn sửa/xoá

**Bài tập mở rộng (sau v1)**

1. Thay lớp messaging tự viết bằng Wolverine hoặc MassTransit v8, so số dòng code và hành vi khi lỗi.
2. Chuyển Catalog search sang Elasticsearch hoặc PostgreSQL full-text + `unaccent` cho tiếng Việt.
3. Saga dạng choreography thay cho orchestration, viết lại luồng checkout và so độ khó debug.
4. Deploy lên Kubernetes bằng `aspire publish` (Docker Compose hoặc Kubernetes target), thêm HPA cho FlashSale.
5. Tích hợp VietQR / cổng thanh toán sandbox thật, xử lý webhook idempotent.
6. Event sourcing đầy đủ cho Inventory (StockLevel chỉ còn là projection rebuild được).
7. Multi-tenant (nhiều thương hiệu trên cùng hệ thống), tận dụng kinh nghiệm multi-tenant sẵn có.
8. Sinh `libs/api-client` từ OpenAPI của các service bằng `ng-openapi-gen`, so với bản viết tay (số dòng, lỗi bắt được lúc build khi API đổi).

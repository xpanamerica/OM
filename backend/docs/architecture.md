# 架构与模块边界

## 部署拓扑（推荐生产形态）

```text
Nginx（TLS 终止、静态资源、反代、限流与 gzip）
        ↓ 反代至 Uvicorn / Gunicorn workers
FastAPI 应用（本仓库 `app/`）
        ↓
PostgreSQL（权威数据）          Redis（会话外状态：限流、幂等等，见下文「Redis 与缓存」）
```

- **Nginx** 与 **`CORS_ORIGINS` / `AUTH_TRUST_X_FORWARDED_FOR`** 配合：仅在受信反代后信任 `X-Forwarded-For` 等头。
- 与上线 TLS、端口、健康检查探针等操作细节见 **[`DEPLOYMENT.md`](DEPLOYMENT.md)**。

## 视频与媒体（第一版与演进）

- **第一版**：视频播放地址使用 **`videos.video_url`（及可选 `cover_url`）外链字段**（HTTPS URL），由前端或 CDN 直接拉流/封面；API 只存元数据与业务状态，**不落二进制到应用盘**。
- **后续演进**：可接入 **阿里云 VOD**（转码、播放凭证、播放域名）或 **OSS**（对象存储 + 签名 URL / CDN）；届时在 **`app.infrastructure`** 增加 SDK 封装，**迁移**中可新增列（如 `vod_media_id`、`oss_object_key`）或与 `video_url` 并存过渡，避免第一版接口形态与领域模型过度耦合。运维与发版步骤见独立 Runbook：**[`runbooks/aliyun-vod-oss.md`](runbooks/aliyun-vod-oss.md)**。

## 依赖方向（建议团队遵守）

1. **`app.api.v1.routes`** 与 **`app.api.deps`** 主要依赖 `app.services`、`app.schemas.v1`（deps 另可依赖 `app.core`、`app.db`）。**禁止**在路由或依赖中直接 `from app.repositories` 做业务数据访问。`from app.models` **仅允许**用于依赖注入/类型标注（如 `User` 作 `Depends` 返回值类型），不得在服务逻辑外直接查库。
2. **`app.services`** 可依赖 `app.repositories`、`app.models`、`app.core`、`app.mappers`、`app.schemas.v1`。**允许的跨 service 依赖（须保持单向、无环）：**
   - **`admin_service`**：仅提供 `write_audit`（向当前 `Session` 追加 `AuditLog` 并 `flush`，**不** `commit`），供视频/评论等用例与业务行同事务落库。
   - **`video_service`**：可被 **`interaction_service`** 调用以复用「仅已发布可互动」等读校验（如 `get_video_for_interaction`）。
   - 其他跨域组合优先在 **route 层编排** 或后续引入 `application/` 包；新增 service→service 边须代码评审避免循环依赖。
3. **`app.repositories`** 只依赖 `app.models` 与 SQLAlchemy；不包含业务规则（状态机、权限文案等）。
4. **`app.mappers`** 只做 ORM → DTO 字段映射；**禁止**访问 `Session`、**禁止**调用 repository。
5. **`app.infrastructure`** 封装 Redis、指标、追踪、第三方 SDK；**禁止**反向依赖 `services`。
6. **`app.schemas.v1`** 仅 Pydantic 模型，不依赖 ORM（可用 `from_attributes` 做校验，但不要在 schema 里写 I/O）。

## 事务边界

- **`app.repositories`**：`create` / `save` / `update` / `delete` 等只做 `flush`（及必要时的 `refresh`），**不在 repository 内 `commit`**，便于与审计、计数等多表写入共事务。
- **`app.services`**：在**用例方法末尾**对当前 `Session` 调用 **`db.commit()`**（或显式 `rollback`），保证「业务行 + 审计」等同成功或同回滚；`admin_service.write_audit` 不单独提交。
- **读路径副作用**（如公开 `get_video` 增加 `view_count`）可在该 service 方法内单独 `commit`，与上条不冲突。

## 健康检查

- **`GET /health`**（应用根路径）与 **`GET /api/v1/admin/health`**（需超级用户）均返回 `health_service.full_health_report`：`status`（`ok` / `degraded`）、`database`、`redis`，便于负载均衡与后台探针口径一致。
- **`status` 与评论限流**：当开启 **严格 Redis 限流**（`COMMENT_RATE_LIMIT_USE_REDIS=true` 且 `COMMENT_RATE_LIMIT_REDIS_FALLBACK_MEMORY=false`）且 `redis` 探测失败时，`comment_rate_limit_operational` 为 `false`，`status` 为 **`degraded`**（与 `redis` 字段一致，便于编排层与评论 SLA 对齐）。

## 数据模型要点（与迁移 `0002_schema_improvements` 对齐）

- **users.deleted_at**：软删用户；登录与 `get_by_id` 均排除已删行。
- **videos**：`reviewed_by_id`、`submitted_at`、`first_published_at`、`offline_at` 支撑审核 SLA 与上下架时间线；`category_id` 外键 `ON DELETE SET NULL`。
- **comments.deleted_at**：与 `is_deleted` 同步写入，便于留存与清理策略。
- **categories / tags**：`sort_order`、`is_active`；公开列表默认仅 `is_active=true`，`?include_inactive=true` 仅管理员。
- **计数列**：仍以应用层维护为主；PostgreSQL 上通过 CHECK 保证非负；定期对账 job 建议后续在 `workers/` 实现。

## Redis 与缓存

- 所有 Redis 访问经 `app.infrastructure.redis`（或后续拆分的 `cache` 子模块），键名、TTL、版本前缀在文档或代码常量中集中维护。
- **评论发帖限流**（`COMMENT_RATE_LIMIT_USE_REDIS=true` 且 Redis 可达时）：键 `rl:comment:post:v1:{user_id}:{video_id}`，ZSET 存滑动窗口内时间戳，`EXPIRE` 约为窗口 + 10s。`COMMENT_RATE_LIMIT_REDIS_FALLBACK_MEMORY=true` 时 Redis 异常回退进程内 deque（与登录限流类似，多实例不再一致）。**严格模式**（`COMMENT_RATE_LIMIT_REDIS_FALLBACK_MEMORY=false`）下 Redis 失败抛出 `CommentRateLimitBackendError`，API 映射为 **503** + `COMMENT_RATE_LIMIT_BACKEND_UNAVAILABLE`（须运维保证 Redis SLA）。`GET /health` 含 `comment_rate_limit_storage`（`redis` / `memory` / `disabled`）、`comment_rate_limit_use_redis`、`comment_rate_limit_redis_fallback_memory`。
- **评论列表游标**：`X-Next-Cursor` / `cursor` 为末条评论 `id` 的 opaque 编码；仓储内再加载锚点行做 `(created_at, id)` 复合比较，避免跨方言时间绑定误差。新建评论在 `comment_repository.create` 写入微秒级 `created_at`（Python `datetime.now(UTC)`），保证升序与分页稳定。
- **评论列表条件 GET**：`GET .../videos/{id}/comments` 返回弱 `ETag`（随未软删总数、`max(updated_at)` 与分页键变化）；`If-None-Match` 命中时 **304** 且无正文，降低带宽；`Vary: Authorization` 与视频详情一致，避免共享缓存串身份。

## 观测

- `app.infrastructure.observability` 下集中初始化 metrics / tracing；避免在业务 service 内散落创建 exporter。
- **Prometheus 兼容**：`EXPOSE_PROMETHEUS_METRICS=true` 时挂载 `GET /metrics`（text/plain OpenMetrics 风格）；评论计数器带 **`worker` 标签**（默认 `pid_<进程号>`，可通过 `METRICS_INSTANCE_ID` 设为 Pod 名等，便于 Uvicorn 多 worker / 多副本抓取后区分时间序列）。另含 `app_comments_metrics_exposition_info{schema="v2"}`、`app_auth_rate_limit_metrics_exposition_info{schema="v1"}` 等 gauge。认证限流维度见 `app_auth_rate_limit_exceeded_total{kind=...}`（固定低基数 `kind`）。无额外 pip 依赖；若需跨进程原子聚合 histogram，可再接入 `prometheus_client` 的 `PROMETHEUS_MULTIPROC_DIR` 模式。
- **请求关联**：`RequestIdMiddleware` 生成或透传 `X-Request-ID`，并写入 `request_id_cv`；`app.comment.audit` 日志含 `request_id` 字段（无则 `-`）。

## 数据库权威与测试

- **生产与迁移的权威 schema 以 PostgreSQL + Alembic 为准**（含 `0002_schema_improvements` 中的外键、`ON DELETE`、CHECK、补充索引等）。
- **SQLite / `create_all` 仅用于部分单元或本地快速启动**时，约束与 PG 可能不完全等价；涉及状态与计数、外键级联的用例应在 CI 或集成环境中针对 PG 再跑一遍迁移与关键路径。
- 默认 **GitHub Actions**（`.github/workflows/backend-ci.yml`）在推送/PR 时跑 `pytest` 与 `compileall`，并含 **auth-rate-limit-redis** job（Redis 服务 + `RUN_AUTH_RATE_LIMIT_REDIS`）覆盖认证限流 EVALSHA 路径；生产级约束验证建议另加 **PostgreSQL job**（`alembic upgrade head` + 标记为 integration 的用例）。

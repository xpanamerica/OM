# HTTP API 速览

**基路径**：由环境变量 `API_V1_PREFIX` 决定，默认 **`/api/v1`**。下文记 **`P = /api/v1`**（若你改成了 `/api/v2`，则全文替换前缀）。

**OpenAPI**：默认在 `ENVIRONMENT=local` 等开发态下可访问 **`http://<host>:<port>/docs`** 与 **`/openapi.json`**；生产类环境默认关闭（见 `app/core/config.py` 中 `expose_openapi_docs`）。

**鉴权**：除明确标注「可匿名」的接口外，请求头需带 **`Authorization: Bearer <access_token>`**；登录使用 OAuth2 密码流表单（见 Auth）。

---

## Auth（`P/auth`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `P/auth/registration-options` | **可匿名**；JSON：`invite_code_required`（平台是否强制邀请码注册） |
| POST | `P/auth/register` | JSON：`email`、`username`、`password`（≥8 字符）；可选 `invite_code`。当后台开启内测邀请码时，未填或无效码返回 400 及对应文案；201 返回用户公开信息 |
| POST | `P/auth/login` | `application/x-www-form-urlencoded`：`username`（可填用户名或邮箱）、`password`；200 返回 `access_token`、`token_type` |
| POST | `P/auth/forgot-password` | **可匿名**；JSON：`email`；防枚举固定 200 文案；对已注册且启用用户签发一次性重置令牌（见环境变量 `AUTH_PASSWORD_RESET_*` / `SMTP_*`）；启用限流且超配额时 **429** |
| POST | `P/auth/reset-password` | **可匿名**；JSON：`token`（邮件/日志中的明文令牌）、`password`（新口令，规则同注册）；200 成功；令牌无效或过期 **400**，`code`=`PASSWORD_RESET_INVALID` |

**注册与邀请码（补充）**：`AUTH_REGISTER_MAX_ATTEMPTS_PER_MINUTE` 默认为 **0**（不启用），此时「每分钟」注册上限完全由 `AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_MINUTE` 决定；设为 **20–60** 等正值时**仅覆盖该分钟维度**（小时仍用 `AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_HOUR`），便于生产单独调参。**同一邀请码多进程并发仅一人 201**：`pytest` 的 `TestClient` 非进程级并发模型，仓库未加多线程压测用例；「第二人必败」已由 `test_register_rejects_used_invite` 等覆盖。若需进程级压测，请自建 **httpx + 独立 Uvicorn 子进程** 或 **pytest-xprocess** 类脚本，勿依赖 `TestClient` 多线程。

认证限流（`AUTH_RATE_LIMIT_ENABLED=true` 且 Redis 可用时多实例一致）：默认配额为注册每 IP 每分钟 3 / 每小时 10（若 `AUTH_REGISTER_MAX_ATTEMPTS_PER_MINUTE>0` 则「每分钟」以前者为准，见上节）；登录每 IP 每分钟 5；同一登录标识 15 分钟内失败 5 次后拒绝；忘记密码每 IP 每小时 3、每邮箱每小时 2。各维度滑动窗口秒数（如 `AUTH_RATE_LIMIT_REGISTER_MINUTE_WINDOW_SECONDS`）与配额均可经环境变量覆盖（见 `app/core/config.py`）。Redis 路径使用 ``SCRIPT LOAD`` + ``EVALSHA``（键前缀 ``rl:auth:v2:``，含窗口的维度如 ``login:fail:w{秒}:``）；进程内曾判定 Redis 不可达时，可按 `AUTH_RATE_LIMIT_REDIS_STALE_REPROBE_SECONDS` 周期性重探测。`EXPOSE_PROMETHEUS_METRICS=true` 时 ``GET /metrics`` 含 ``app_auth_rate_limit_exceeded_total{kind=...}``、``app_auth_rate_limit_redis_errors_total``、``app_auth_rate_limit_memory_fallback_total``。可选真 Redis 集成测试：`RUN_AUTH_RATE_LIMIT_REDIS=1 pytest tests/integration/test_auth_rate_limit_redis.py`；CI 中由 workflow job **auth-rate-limit-redis** 固定执行。超限事件写入 `security_events` 表。

---

## User（`P/users`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `P/users/me` | 须 Bearer；返回当前用户公开信息 |

### 站内消息（个人中心 / App 通知）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `P/users/me/notifications/unread-count` | 须 Bearer；JSON：`{ "unread_count": n }`（首次进入个人中心时会插入一条欢迎通知） |
| GET | `P/users/me/notifications` | 须 Bearer；分页 `offset`/`limit`；响应头 `X-Total-Count`、`X-Unread-Count` |
| PATCH | `P/users/me/notifications/{notification_id}/read` | 须 Bearer；单条标为已读 |
| POST | `P/users/me/notifications/read-all` | 须 Bearer；全部标为已读；JSON：`{ "marked": n }` |

### 个人中心聚合与关注

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `P/users/me/profile-hub` | 须 Bearer；JSON：`following_count`、`followers_count`、`likes_and_favorites_received`（已发布稿件上获赞+收藏合计）、`unread_notification_count`、`recent_videos`（作者本人最近稿件，含草稿等） |
| POST | `P/users/{user_id}/follow` | 须 Bearer；关注用户；**204**；不可关注自己 |
| DELETE | `P/users/{user_id}/follow` | 须 Bearer；取消关注；**204** |

---

## Category / Tag（`P/categories`、`P/tags`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `P/categories` | 公开；列表 + 分页/游标（见响应头 `X-Total-Count` 等） |
| POST | `P/categories` | **管理员**；创建分类 |
| PATCH | `P/categories/{category_id}` | **管理员** |
| DELETE | `P/categories/{category_id}` | **管理员** |
| GET | `P/tags` | 公开 |
| POST | `P/tags` | **管理员** |
| PATCH | `P/tags/{tag_id}` | **管理员** |
| DELETE | `P/tags/{tag_id}` | **管理员** |

---

## Video（`P/videos`）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `P/videos` | 须登录；创建草稿；可带 `Idempotency-Key` |
| GET | `P/videos` | 列表；匿名仅 `published`；管理员可用 `status` 等筛选 |
| GET | `P/videos/{video_id}` | 详情；支持 `If-None-Match` / `ETag` |
| PATCH | `P/videos/{video_id}` | 作者/管理员更新；可带 `Idempotency-Key` |
| DELETE | `P/videos/{video_id}` | **管理员**；物理删除稿件及本机封面/成片；**204** |

### 审核与工作流（同一前缀 `P/videos`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `P/videos/{video_id}/workflow-events` | 审计列表；作者或管理员 |
| POST | `P/videos/{video_id}/submit-review` | 提交审核 |
| POST | `P/videos/{video_id}/approve` | **管理员**通过 |
| POST | `P/videos/{video_id}/reject` | **管理员**驳回（JSON：`rejection_reason`） |
| POST | `P/videos/{video_id}/offline` | **管理员**平台下架（`published` → `offline`） |

---

## Comment（`P/videos` + `P/comments`）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `P/videos/{video_id}/comments` | 须登录；仅已发布视频 |
| GET | `P/videos/{video_id}/comments` | 列表；可见性与视频详情一致；支持 ETag/游标 |
| DELETE | `P/comments/{comment_id}` | 须登录；作者或管理员软删；**204** 无正文 |

---

## Like / Favorite（`P/videos`）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `P/videos/{video_id}/like` | 须登录；仅 `published` |
| DELETE | `P/videos/{video_id}/like` | 取消点赞 |
| POST | `P/videos/{video_id}/favorite` | 须登录；仅 `published` |
| DELETE | `P/videos/{video_id}/favorite` | 取消收藏 |

响应体含 `likes_count`、`favorites_count` 等聚合字段（见 OpenAPI 模型 `VideoInteractionCountsOut`）。

---

## ViewRecord（`P/videos` + `P/users`）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `P/videos/{video_id}/view-record` | 须登录；仅 `published`；上报/更新进度 |
| GET | `P/users/me/view-records` | 须登录；我的播放记录；`offset`/`cursor` 分页 |

---

## Admin（`P/admin`）

**均须管理员角色（JWT + `role=admin`）。**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `P/admin/videos` | 全状态视频列表；`status`、`keyword` 等查询参数 |
| GET | `P/admin/users` | 用户列表；`keyword`、`role`、`is_active` 等 |
| PATCH | `P/admin/users/{user_id}/active` | JSON：`is_active`；禁用后 **再登录** 为 401（与错密同文案）；已签发令牌在受保护接口上仍会 403 |
| GET | `P/admin/statistics/platform` | 平台汇总：用户数、视频数、按状态计数、播放量/点赞/收藏总和 |
| GET | `P/admin/settings` | 平台开关；含 `video_publish_without_review_enabled`、`registration_invite_code_required`（内测须邀请码注册）等 |
| PATCH | `P/admin/settings` | JSON 部分字段更新；同上 |
| GET | `P/admin/invite-codes` | 邀请码分页列表；`offset`/`limit`；JSON：`items`、`total` |
| POST | `P/admin/invite-codes` | 创建；JSON：`max_uses`、可选 `expires_at`；响应含新建 `invite`（含明文 `code`） |
| POST | `P/admin/invite-codes/{invite_id}/revoke` | 作废仍为 `active` 的邀请码 |

---

## 其它全局路由（不在 `P` 下）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查（数据库/Redis 等子项） |
| GET | `/metrics` | Prometheus 文本；默认 **404**，需 `EXPOSE_PROMETHEUS_METRICS=true` |

---

更细的请求/响应字段、状态码与 Header 以 **`/openapi.json`** 为准；架构约定见同目录 [`architecture.md`](architecture.md)。

**库表提示（与 OpenAPI 路径无关）**：点赞 / 收藏在数据库中的表名为 **`video_likes`**、**`video_favorites`**（迁移 `0017_*`），文档或清单中若写作 `likes`/`favorites` 均指上述表。

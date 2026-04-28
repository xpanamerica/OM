# 上线前检查清单

在将本后端发布到 **staging / production** 前，建议逐项确认（负责人签字/打勾）。

---

## 配置与安全

- [ ] **`ENVIRONMENT`** 已设为 `production` / `prod` / `staging`（非 `local`）。
- [ ] **默认 Compose 密钥**：**未**将仓库默认的 `SECRET_KEY`、`POSTGRES_PASSWORD`、`FIRST_SUPERUSER_PASSWORD` 等直接用于公网或生产等价环境；已通过 **`.env`（不提交 Git）** 或密钥管理系统替换。
- [ ] **`SECRET_KEY`** 为独立高熵随机串（如 `openssl rand -hex 32`），**未**使用 `.env.example`、`docker-compose.yml` 示例或单测默认密钥。
- [ ] **`CORS_ORIGINS`** 已列出真实前端 Origin，**无**单独的 `*`（生产类环境会在启动校验阶段拒绝 `*`）。
- [ ] **`DATABASE_URL` / `REDIS_URL`** 指向生产实例，账号最小权限原则。
- [ ] **`FIRST_SUPERUSER_PASSWORD`**（若仍使用引导账号）为强口令，且首登后已计划改密或禁用引导流程。
- [ ] **`EXPOSE_OPENAPI_DOCS`**：生产默认关闭；若内网临时开启，已评估信息暴露风险。
- [ ] **`EXPOSE_PROMETHEUS_METRICS`**：未对公网暴露 `/metrics`，或已加网络 ACL。
- [ ] **`AUTH_TRUST_X_FORWARDED_FOR`**：仅在受信反代后开启；否则保持 `false`。
- [ ] **`AUTH_LOGIN_MAX_ATTEMPTS_PER_MINUTE`**：生产为合理正整数（如 60），非 `0`。

---

## 数据库与迁移

- [ ] 已在**目标库**执行 **`alembic upgrade head`**（或与镜像启动命令一致的一键迁移）。
- [ ] 已阅读 `alembic/versions/` 中最近迁移，确认无破坏性变更未做数据修复脚本。
- [ ] **备份**：上线窗口前完成 `pg_dump`（或等价），并验证可恢复性（至少在 staging 演练一次）。

---

## 应用与接口

- [ ] **Compose 烟测（可选但推荐）**：在 `backend/` 执行 `bash scripts/verify_compose_stack_smoke.sh` 或 `make verify-compose-smoke`（CI 已包含等价步骤），确认 **`/health`**（JSON **`database=connected`**）、**`/docs`**、**`/openapi.json`** 可访问。
- [ ] **`GET /health`** 返回 `database=connected`（及你方要求的 Redis 等项）；`status` 为 `ok` 或可接受的 `degraded` 且原因已知。
- [ ] **数据表与文档用语**：点赞/收藏在库中为表 **`video_likes`**、**`video_favorites`**（非字面 `likes`/`favorites`）；迁移与 ORM 以此为准。
- [ ] **关键业务路径**已在 staging 手工或自动化验证（注册/登录、视频发布流、评论、点赞、播放记录、管理员接口）。
- [ ] **JWT 过期时间** `ACCESS_TOKEN_EXPIRE_MINUTES` 与前端刷新策略一致。

---

## 网关与网络

- [ ] **HTTPS** 已启用，HTTP 重定向策略正确。
- [ ] **反代** 超时、 body 大小、WebSocket（若未来使用）已评估。
- [ ] **防火墙**：仅暴露 443（及必要的 SSH/VPN），数据库/Redis **不**对公网监听。

---

## 观测与应急

- [ ] 日志已接入集中式存储；**日志保留与脱敏**策略已确认（尤其登录、鉴权相关）。
- [ ] 告警：至少 health、5xx 率、DB 连接、磁盘与内存。
- [ ] **回滚方案**：上一版本镜像 tag + 数据库迁移 **downgrade** 或备份恢复步骤已文档化并演练。

---

## 发布动作（示例）

```bash
# 在 CI 或发布机：构建并推送镜像（标签按你们规范）
docker build -t your-registry/video-api:$(git rev-parse --short HEAD) .

# 目标环境拉取、迁移、滚动重启（伪代码，按实际编排替换）
docker compose pull api && docker compose up -d api
```

---

## 发布后快速验证

```bash
curl -fsS https://your-api.example.com/health | jq .
```

（将 URL 换成实际上线域名与路径前缀；若 API 仅内网，则在 jump 主机上执行。）

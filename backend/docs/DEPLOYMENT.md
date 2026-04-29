# 部署说明（Docker Compose 为主）

面向：**在本机或单机服务器上**用仓库自带编排拉起 **PostgreSQL + Redis + API**。假设你已安装 **Docker Engine** 与 **Docker Compose v2**。

**阿里云 ECS / 单机生产**（Gunicorn、Nginx 示例、备份与日志卷）见 **[`PRODUCTION_DEPLOYMENT.md`](PRODUCTION_DEPLOYMENT.md)**。

---

## 1. Docker Compose 部署方式

### 1.1 准备

```bash
cd /home/xixiang2025/OM/backend
bash scripts/init_local_compose_env.sh   # 首次：生成随机 SECRET_KEY / 数据库口令等写入 .env（勿提交）
# 可选：再参考 .env.example 增补 COMPOSE_HTTP_TIMEOUT、镜像源等
```

**路径说明**：`/home/xixiang2025/OM` 为本机实际仓库根；须进入其下的 **`backend/`**。含义与 **`test -f docker-compose.yml`** 自检见 **[`../README.md`](../README.md)** 中的 **「4.5 启动前检查」**。

### 1.2 启动（前台，可看日志）

```bash
cd /home/xixiang2025/OM/backend
COMPOSE_HTTP_TIMEOUT=300 docker compose up --build
```

**仅本机访问 API（回环绑定 8000）**：与默认栈叠加 **`docker-compose.api-loopback.yml`**：

```bash
COMPOSE_HTTP_TIMEOUT=300 docker compose -f docker-compose.yml -f docker-compose.api-loopback.yml up --build
```

或使用 Makefile（同样带较长拉取超时）：

```bash
cd /home/xixiang2025/OM/backend
make up
```

### 1.3 启动后容器内行为

`Dockerfile` 默认入口等价于：

```bash
python -m alembic -c /app/alembic.ini upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

即：**先执行迁移，再起服务**。首次启动会执行 `init_db`（见 `app/main.py` lifespan + `app/db/init_db.py`），若配置了 `FIRST_SUPERUSER_*` 且库中无同名用户则创建首个管理员。

### 1.4 常用运维命令

```bash
cd /home/xixiang2025/OM/backend

# 后台起栈
docker compose up -d --build

# 看 API 日志
docker compose logs -f api
# 或
make logs

# 停栈并删卷（会清空 Postgres 数据卷，慎用）
make down

# 仅执行迁移（api 已运行）
make migrate
# 等价于
docker compose exec api python -m alembic -c /app/alembic.ini upgrade head

# 容器内跑测试
docker compose exec api pytest -q
```

### 1.5 镜像拉取超时 / 代理问题

**要点（读完即可排障；细节与分步脚本见下方链接）**：

- **`docker pull` / `docker compose build` 由 dockerd 执行**；只在当前 shell `unset HTTP_PROXY` **通常不能**修复拉取失败。
- 若错误含 **`proxyconnect`**、**`lookup http`**：优先检查 **`/etc/systemd/system/docker.service.d/*.conf`** 是否向 dockerd 注入了无效或占位的 `HTTP_PROXY`。
- **自检（无需 sudo）**：`cd /home/xixiang2025/OM/backend && bash scripts/verify_docker_network_ready.sh`
- **`context deadline exceeded`**：适当加大 **`COMPOSE_HTTP_TIMEOUT`**；默认 **`docker-compose.yml`** 已使用 **DaoCloud 对 Docker Hub 的镜像前缀**，可在 **`.env`** 中改 **`MEDIA_POSTGRES_IMAGE`** / **`MEDIA_REDIS_IMAGE`** / **`MEDIA_PYTHON_IMAGE`**（见 **`.env.example`**）。

分步说明、客户端 **`~/.docker/config.json`** 与 **registry-mirrors** 等见：

- [`docs/runbooks/docker-network-proxy.md`](runbooks/docker-network-proxy.md)
- [`docs/runbooks/docker-registry-pull.md`](runbooks/docker-registry-pull.md)

一条命令修复（需一次 sudo 密码；会尝试安装 docker 相关 NOPASSWD、清空 systemd 中无效 Docker 代理并重启 `docker`）：

```bash
cd /home/xixiang2025/OM/backend
sudo bash "$(realpath scripts/one_shot_fix_docker_all.sh)"
```

等价：`cd /home/xixiang2025/OM/backend && make fix-docker-once`（Makefile 内对上述脚本的封装）。

国内可选镜像覆盖：`.env.example` 中 `MEDIA_*_IMAGE`；或使用 `make up-mirror`（`docker-compose.mirror.yml`）。

---

## 2. PostgreSQL 配置

Compose 中服务名 **`db`**，凭据由 **`docker-compose.yml`** 与项目根 **`.env`** 插值（与 `api` 默认 `DATABASE_URL` **同源**）：

| 变量（容器内） | 说明 |
|----------------|------|
| `POSTGRES_USER` | 默认 `postgres`；可通过 `.env` 中 `POSTGRES_USER` 覆盖 |
| `POSTGRES_PASSWORD` | 默认 `postgres`；**生产须改**；改后须同步 `DATABASE_URL` 或依赖 compose 内默认连接串的自动拼接 |
| `POSTGRES_DB` | 默认 `videodb` |

API 使用的连接串由 `api.environment.DATABASE_URL` 给出：若未设置 `DATABASE_URL`，默认值为 **`postgresql+psycopg://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@db:5432/${POSTGRES_DB:-videodb}`**（与 `db` 环境变量一致）。无 `.env` 时解析结果等价于：

```text
postgresql+psycopg://postgres:postgres@db:5432/videodb
```

**宿主机端口**：默认 **`docker-compose.yml`** 将 Postgres **仅绑定 `127.0.0.1:5432`**（容器内其它服务仍用主机名 `db`）。远程宿主机上的其它机器默认无法直连该映射；需本机工具连库时使用 `127.0.0.1`。

**生产**：务必改为强密码与专用数据库用户，并同步修改 `DATABASE_URL`；数据目录通过命名卷 **`pgdata`** 持久化（`docker compose down -v` 会删除）。

---

## 3. Redis 配置

服务名 **`redis`**。默认 **`docker-compose.yml`** 将 Redis **仅绑定到宿主机 `127.0.0.1:6379`**（与 Postgres 相同策略），容器间仍使用服务名 `redis:6379`。API 默认：

```text
redis://redis:6379/0
```

### 3.1 生产启用口令（`requirepass`）示例

在自建 **`docker-compose.override.yml`**（勿提交密钥）中为 `redis` 增加 `command`，并在 **`api.environment.REDIS_URL`** 使用带口令 URL；**口令中含 `@`、`:`、`/` 等须做 URL 编码**（见 `README.md` FAQ「数据库连接串」）。

```yaml
services:
  redis:
    command: ["redis-server", "--requirepass", "${REDIS_PASSWORD}"]
  api:
    environment:
      REDIS_URL: "redis://:${REDIS_PASSWORD}@redis:6379/0"
```

`.env` 中设 `REDIS_PASSWORD=...`（Compose 插值写入容器）。若口令含特殊字符，可对**仅口令段**使用 `urllib.parse.quote(..., safe="")` 生成 URL 后再拼进 `REDIS_URL`。

**生产**：建议启用 Redis ACL/密码；同时评估 `IDEMPOTENCY_ALLOW_MEMORY_FALLBACK`（多实例时应为 **false** 且 Redis 必须可用）。

---

## 4. 与 `.env` / `docker-compose.yml` 的关系（默认栈）

**`docker-compose.yml`**：`SECRET_KEY` 与 **`POSTGRES_PASSWORD`** 须由 **`backend/.env`**（或导出环境变量）提供，**无**内联弱默认；`DATABASE_URL` 等其余项仍可按 **`${VAR:-默认值}`** 插值。在 **`backend/`** 下放置 **`.env`** 后，Compose 解析 YAML 时会把同名变量写入容器的 `environment`。

**`api.environment.ENVIRONMENT`** 在默认 compose 中 **写死为 `local`**，避免仅因 `.env` 中 `ENVIRONMENT=staging` 导致容器启动阶段弱口令/配置校验失败；若你确需在容器内使用其他运行级别，请在自建 **`docker-compose.override.yml`** 中显式覆盖（勿提交含生产密钥的文件）。模板键名仍以 **`.env.example`** 与 **`README.md`** 为准。

**烟测脚本**：`scripts/read_compose_first_superuser_password.py` **优先**读取 **`.env`** 中的 `FIRST_SUPERUSER_PASSWORD`，否则读环境变量，再回退到 compose 中 **`${FIRST_SUPERUSER_PASSWORD:-…}`** 默认段；若需覆盖，可对 `verify_docker_endpoints.sh` 设置 **`DOCKER_FIRST_SUPERUSER_PASSWORD`**。

---

## 5. 生产环境变量（最小集）

在编排层为 **`api`** 注入（勿把生产密钥写进镜像层）：

| 变量 | 要求 |
|------|------|
| `ENVIRONMENT` | `production` / `prod` / `staging`（会收紧 CORS、SECRET、OpenAPI 等） |
| `SECRET_KEY` | JWT HMAC 密钥：**仅环境变量**；UTF-8 至少 32 字节，生产类环境建议 ≥48；**禁止**使用 `.env.example` 或文档中的示例占位（见 `app/core/config.py` 校验） |
| `DATABASE_URL` | 生产 Postgres 连接串 |
| `REDIS_URL` | 生产 Redis 连接串 |
| `CORS_ORIGINS` | **逗号分隔**的前端 Origin 列表；生产类环境**禁止**仅为 `*` |
| `EXPOSE_OPENAPI_DOCS` | 默认生产关文档；若内网需要可显式 `true` |
| `AUTH_RATE_LIMIT_ENABLED` | 生产建议 `true`（注册/登录/忘记密码配额见实现）；本地/单测常 `false` |
| `AUTH_RATE_LIMIT_USE_REDIS` / `AUTH_RATE_LIMIT_REDIS_FALLBACK_MEMORY` | 多实例须 `USE_REDIS=true`；生产可关回退以在 Redis 故障时快速失败 |
| `AUTH_RATE_LIMIT_REDIS_STALE_REPROBE_SECONDS` | 进程内曾判定 Redis 不可达时，认证限流侧每隔若干秒再探测（默认 30；`0` 不重探测） |
| `AUTH_RATE_LIMIT_REGISTER_*` / `LOGIN_*` / `FORGOT_*` | 各维度配额（整数），默认与产品规格一致，可按环境调优 |
| `AUTH_RATE_LIMIT_*_WINDOW_SECONDS` | 各滑动窗口长度（秒）；须满足「注册小时窗 ≥ 分钟窗」 |
| `LOG_LEVEL` | `INFO` 或 `WARNING` |

可选：`FIRST_SUPERUSER_*`（仅首次建库）、`EXPOSE_PROMETHEUS_METRICS`、`COMMENT_*`、`AUTH_TRUST_X_FORWARDED_FOR`（仅当反代可信且写入 `X-Forwarded-For` 时启用）。

完整说明与默认值见项目根下 **`backend/.env.example`** 与源码 **`app/core/config.py`**。

---

## 6. 反向代理建议

- 将 **TLS 终止**放在 Nginx / Caddy / Traefik / 云 LB。
- 反代到 upstream 时使用 **`http://127.0.0.1:8000`**（或 Docker 网络内 `http://api:8000`），保持 **HTTP/1.1** 与合理 **`proxy_read_timeout`**（大文件上传若开启需调大）。
- 传递客户端 IP：配置 **`X-Forwarded-For`** / **`X-Forwarded-Proto`**；仅在反代可信时设置 API 环境变量 **`AUTH_TRUST_X_FORWARDED_FOR=true`**。
- **不要**把 `/metrics` 暴露到公网；若开启 `EXPOSE_PROMETHEUS_METRICS`，应用 IP 白名单或独立监听接口。

---

## 7. HTTPS 建议

- 公网入口强制 **HTTPS 301**；HSTS（在网关配置）。
- 应用层可依赖反代头部；不必在 Uvicorn 内重复配置证书（除非无反代）。

---

## 8. 日志查看方式

- **Compose**：`docker compose logs -f api` 或 `make logs`。
- 应用使用标准 **stdout** 日志（`app.core.logging` + 访问日志 `app.http.access`）；生产请用 **容器日志驱动** 或 **边车** 收集到 Loki/ELK/CloudWatch。
- **注意**：访问日志中间件**不记录** `Authorization` 与请求体，避免口令/token 落盘；错误栈仍可能含业务异常信息，应对接脱敏与保留策略。

---

## 9. 数据备份建议

- **PostgreSQL**：定期逻辑备份，例如：

  ```bash
  docker compose exec -T db pg_dump -U postgres videodb > backup_$(date +%F).sql
  ```

  恢复使用 `psql` 或 `pg_restore`（视格式而定）。
- **Redis**：若仅作缓存/限流/幂等，可按 RPO 接受度决定快照策略；**业务真相以 Postgres 为准**。
- **卷**：`pgdata` 命名卷所在磁盘做快照前请停写或配合 `pg_dump` 一致性策略。

---

## 10. 起栈后验收命令

```bash
cd /home/xixiang2025/OM/backend
bash scripts/verify_docker_endpoints.sh
```

可选鉴权烟测（密码需与 **容器内** 实际引导口令一致：无 `.env` 覆盖时与 compose 默认段一致；若 `.env` 改了 `FIRST_SUPERUSER_PASSWORD`，请设 **`DOCKER_FIRST_SUPERUSER_PASSWORD`** 与之一致）：

```bash
VERIFY_DOCKER_AUTH=1 bash scripts/verify_docker_endpoints.sh
```

等价 Makefile 目标：`make verify-docker`、`make verify-docker-auth`。

# 生产部署指南（单机：阿里云 ECS / 通用 Linux）

面向：**单台 ECS 或裸金属**，使用 **Docker Compose** 拉起 **PostgreSQL + Redis + API**，前置 **Nginx** 反向代理；**不引入 Kubernetes**。业务代码路径以仓库 **`backend/`** 为工作目录。

与开发编排的差异见 **`docker-compose.yml`**（源码挂载 + uvicorn）对比 **`docker-compose.prod.yml`**（生产镜像 + **Gunicorn + Uvicorn Worker** + 日志卷）。

---

## 1. 架构一览

```
Internet → Nginx(443/80) → 127.0.0.1:8000 → API 容器(Gunicorn)
                                    ↘ Redis / PostgreSQL（compose 内网）
```

- **TLS**：建议在宿主机用 **certbot**（Let's Encrypt）或阿里云证书，由 Nginx 终结 HTTPS。
- **真实 IP**：API 置于受信反代之后时，设置 **`AUTH_TRUST_X_FORWARDED_FOR=true`**（已在 `deploy/env.production.example` 默认示例中打开）。

---

## 2. 服务器准备

- Docker Engine 20.10+、Docker Compose v2。
- 安全组：**仅开放 80/443**（及 SSH 管理端口）；**勿**将 Postgres/Redis 暴露公网。
- 系统时区与时间同步（chrony）便于备份与日志对齐。

---

## 3. 首次部署步骤

### 3.1 获取代码与配置

```bash
cd /opt   # 示例路径
git clone <你的仓库> OM
cd OM/backend
cp deploy/env.production.example .env.production
# 编辑 .env.production：SECRET_KEY、POSTGRES_PASSWORD、DATABASE_URL、首启管理员等
```

### 3.2 应用日志目录权限（compose 将 `./logs` 挂载到容器内 `LOG_FILE_DIR`）

容器进程用户 **`appuser` uid=10001**（见 `Dockerfile.prod`）。在 **backend/** 下执行：

```bash
mkdir -p logs
sudo chown -R 10001:10001 logs
```

若跳过此步，应用仍可运行，但 **`app.log` 文件日志** 可能因权限无法创建；**stdout 日志**（`docker compose logs`）不受影响。

### 3.3 构建并启动

```bash
cd /opt/OM/backend
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

- 入口脚本 **`scripts/docker-entrypoint-prod.sh`**：`alembic upgrade head` 后启动 **Gunicorn**，worker 类为 **`uvicorn.workers.UvicornWorker`**。
- 并发：环境变量 **`WEB_CONCURRENCY`**（默认 `4`）、超时 **`GUNICORN_TIMEOUT`**（默认 `120` 秒）。

### 3.4 Nginx

```bash
sudo cp deploy/nginx/om-media-api.conf.example /etc/nginx/sites-available/media-api.conf
# 编辑 server_name、SSL 路径、/metrics 访问策略
sudo ln -sf /etc/nginx/sites-available/media-api.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

示例配置假设 API 监听 **`127.0.0.1:8000`**，与 `docker-compose.prod.yml` 端口映射一致。

---

## 4. 健康检查

- **应用**：`GET /health` 返回 JSON（数据库/Redis 等字段）；HTTP **始终 200**（`status` 字段区分 `ok` / `degraded`）。
- **容器**：`Dockerfile.prod` 与 `docker-compose.prod.yml` 均配置 **`HEALTHCHECK`**，探测 `http://127.0.0.1:8000/health`。
- **编排**：`depends_on: condition: service_healthy` 确保 DB/Redis 就绪后再启动 API。

---

## 5. 日志

| 方式 | 说明 |
|------|------|
| **stdout** | Gunicorn `--access-logfile -` / `--error-logfile -`，由 `docker compose logs` 收集 |
| **文件（可选）** | 设置 **`LOG_FILE_DIR`**（生产 compose 默认 `/var/log/media-api`，挂载 `./logs`）；`setup_logging` 追加 **`app.log`** |

生产类环境建议由 **logrotate** 或 **阿里云日志服务** 采集 `logs/app.log` 或容器标准输出。

---

## 6. 数据库备份

脚本 **`scripts/backup_postgres.sh`**：使用 **`pg_dump`**（需宿主机安装 `postgresql-client`）。

```bash
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD='...'
export POSTGRES_DB=videodb
export POSTGRES_HOST=127.0.0.1   # 若 DB 在 compose 映射到宿主机
export POSTGRES_PORT=5432
export BACKUP_ROOT=/var/backups/OM
./scripts/backup_postgres.sh
```

**cron 示例**（每日 02:10）：

```
10 2 * * * cd /opt/OM/backend && POSTGRES_PASSWORD=... ./scripts/backup_postgres.sh >>/var/log/pg-backup.log 2>&1
```

对象存储（OSS）上传备份为第二版运维任务，本文不展开。

---

## 7. 升级与回滚

```bash
cd /opt/OM/backend
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

Alembic 在容器启动时自动 **`upgrade head`**。大版本升级前请在预发环境跑迁移与回归。

---

## 8. 与开发镜像的差异

| 项 | `Dockerfile` + `docker-compose.yml` | `Dockerfile.prod` + `docker-compose.prod.yml` |
|----|---------------------------------------|-----------------------------------------------|
| 进程 | uvicorn 单进程 | **Gunicorn + UvicornWorker** |
| 代码 | 挂载 `./` | 打入镜像 |
| 用户 | root（开发便利） | **非 root `appuser`（uid 10001）** |
| 日志卷 | 无默认 | **`./logs` → `/var/log/media-api`** |

---

## 9. 阿里云 ECS 提示

- **安全组**：最小暴露；数据库仅内网。
- **镜像拉取**：可设置 `MEDIA_PYTHON_IMAGE` / `MEDIA_POSTGRES_IMAGE` / `MEDIA_REDIS_IMAGE` 为 ACR 或 DaoCloud 代理（见 `docker-compose.prod.yml` 注释）。
- **监控**：可对接云监控；应用 **`/metrics`** 默认可能关闭，见 `EXPOSE_PROMETHEUS_METRICS`。

更多背景见 **`docs/DEPLOYMENT.md`**（开发向）、**`docs/architecture.md`**。

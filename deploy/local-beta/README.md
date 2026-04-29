# 本机 Beta 部署（临时服务器 · 小范围外测）

目标：本机 Docker 拉起 **PostgreSQL、Redis、API**，**Nginx** 提供用户端 / 管理端静态资源并**同源反代** `/api/v1`；**不将 PostgreSQL、Redis 暴露到公网**（仅 `127.0.0.1` 绑定或仅容器网络）；对外仅通过隧道暴露 **Nginx 端口**。视频成片默认可走 **本站磁盘**（`LOCAL_VIDEO_STORAGE_DIR`）；附件走 **`ATTACHMENT_STORAGE_DIR`**；**阿里云 VOD 为可选**（密钥仅在 `backend/.env.local-beta`，按需填写）。

**没有技术背景、希望「一步一步点哪里、复制什么」**：请直接打开 **[`GUIDE_新手一步一步_外测注册登录.md`](./GUIDE_新手一步一步_外测注册登录.md)**（从装软件到隧道发链接让别人注册登录）。

---

## 1. `docker-compose.local-beta.yml`（仓库根目录）

路径：`OM/docker-compose.local-beta.yml`（Git 克隆目录名 **`OM`**；本文档已使用本机实际路径 **`/home/xixiang2025/OM`**）。

Compose **项目名**为 **`om-media-local-beta`**（见文件首部 `name:`）。若你曾用旧版项目名 `media-local-beta` 起过栈，升级前建议在旧目录执行 `docker compose -p media-local-beta -f docker-compose.local-beta.yml down`，避免两套容器并存。

| 服务 | 说明 |
|------|------|
| `db` | Postgres；宿主机默认 **`127.0.0.1:15432`** → 容器 `5432`（避免与本机另一套 compose 占用 5432；可用 `BETA_BIND_PG_PORT` 改） |
| `redis` | 宿主机默认 **`127.0.0.1:16379`** → 容器 `6379`（可用 `BETA_BIND_REDIS_PORT` 改） |
| `api` | FastAPI；**仅 `expose: 8000`**，不映射到宿主机；启动时执行 `alembic upgrade head`；带 `healthcheck` |
| `nginx` | 挂载 `user-web/dist`、`admin-web/dist` 与 `deploy/local-beta/nginx/local-beta.conf`；`depends_on: api` 健康后再起 |

可选环境变量（与 compose 文件内注释一致）：`MEDIA_POSTGRES_IMAGE`、`MEDIA_REDIS_IMAGE`、`MEDIA_PYTHON_IMAGE`、`MEDIA_NGINX_IMAGE`、`BETA_BIND_PG_PORT`、`BETA_BIND_REDIS_PORT`、`BETA_USER_WEB_PORT`、`BETA_ADMIN_WEB_PORT`。

---

## 2. Nginx 配置

路径：`deploy/local-beta/nginx/local-beta.conf`。

- **8080**：用户站 SPA + 反代 `/api/v1/`、`/health`、`/docs`、`/redoc`、`/openapi.json`。
- **8081**：管理端 SPA + 相同 API 反代规则。
- 反代上游：`api:8000`（Docker 服务名）。
- 已传 `X-Forwarded-For`、`X-Forwarded-Proto`、`X-Forwarded-Host`（后端可配合 `AUTH_TRUST_X_FORWARDED_FOR`）。

**大文件与上传（满分对齐项）**

| 配置项 | 当前约定 | 说明 |
|--------|----------|------|
| `client_max_body_size` | `2048m`（`http` 块） | 须 **≥** 后端 `MAX_VIDEO_SIZE_MB` 与 `MAX_ATTACHMENT_SIZE_MB` 中的较大者；若收紧后端上限，可同步调小本值。 |
| `client_body_timeout` | `7200s` | 慢上行时避免默认 60s 中断 body 读取。 |
| `proxy_request_buffering` | `off`（`/api/v1/`） | 成片等大文件 **边收边转** upstream，避免 Nginx 默认先把整包落到临时文件再转发（本机体感会慢很多）。 |
| `/api/v1/` 反代超时 | `proxy_send_timeout` / `proxy_read_timeout` 均为 `7200s` | 附件 **POST 经 Nginx** 到 API；点播 **视频直传 OSS 不经本 Nginx**。若仍遇 504，再查隧道/上游超时。 |

本站成片：用户端默认 **`PUT /api/v1/videos/{id}/local-media-binary`**（原始 body，不经 multipart 双写）；兼容 **`POST …/local-media`**。数据写入 **`api` 容器内路径**（compose 默认 **`./backend:/app`** 时，数据在宿主机 `backend/data/` 下，重启不丢）。若改用绝对路径如 `/data/...`，请在 compose 中为 `api` **增加卷挂载**并同步 `backend/.env.local-beta`。  
使用 **阿里云点播** 时：浏览器可凭证 **直传 OSS**（不经本 Nginx 上行）；需配置 VOD 相关变量（见 `backend/.env.local-beta.example`）。

---

## 3. 用户端前端 `.env.production`

模板（**提交到 Git**）：`user-web/.env.production.example`。

```bash
cd "$(git rev-parse --show-toplevel)/user-web"
cp .env.production.example .env.production
npm ci
npm run build
```

核心变量：`VITE_API_BASE_URL=/api/v1`（与 Nginx 同源，隧道只开用户站端口时无需改前端）。

**若使用 Capacitor 壳（Android / iOS 工程）**：`npm run build` **不会**自动更新 `android/`、`ios/` 内嵌的 `public` 静态资源；旧壳里创作页仍会请求阿里云 VOD 并报「未配置」。请在 `user-web` 目录执行：

```bash
npm run cap:copy
```

（等价于 `npm run build` 后 `npx cap copy android` 与 `npx cap copy ios`。）

---

## 4. 管理后台 `.env.production`

模板：`admin-web/.env.production.example`。

```bash
cd "$(git rev-parse --show-toplevel)/admin-web"
cp .env.production.example .env.production
npm ci
npm run build
```

---

## 5. 后端 `backend/.env.local-beta` 示例

复制示例并编辑（**勿提交真实文件**）：

```bash
cp backend/.env.local-beta.example backend/.env.local-beta
```

至少填写：`POSTGRES_PASSWORD` 与 `DATABASE_URL` 密码一致、 `DATABASE_URL` 主机为 **`db`**、`REDIS_URL` 主机为 **`redis`**、`SECRET_KEY`、`FIRST_SUPERUSER_*`。**阿里云 VOD 可留空**：用户站「创作」会把视频传到 **`LOCAL_VIDEO_STORAGE_DIR`**（示例默认 `data/local_videos`），附件到 **`ATTACHMENT_STORAGE_DIR`**；示例已将 **`ATTACHMENT_MIN_RESERVED_DISK_MB=0`** 以利于小磁盘内测。完整说明见 `backend/.env.local-beta.example`。**Redis 在本栈中亦为限流后端**：默认开启时，附件上传等「每用户每分钟」配额在 **多 API 副本间共享**；单实例内测可将 `ATTACHMENT_POST_RATE_LIMIT_USE_REDIS` 等设为 `false`。

Compose 使用同一文件做变量替换：

```bash
docker compose --env-file ./backend/.env.local-beta -f docker-compose.local-beta.yml ...
```

---

## 6. 启动命令（一步一步）

**路径说明（常见误解）**

- 文档中的 **`/home/xixiang2025/OM`** 已是本机实际仓库根目录，可直接复制执行；若换到另一台机器，再改成那台机器的实际克隆路径。
- 若你已在 Git 仓库里打开终端，可用 **`cd "$(git rev-parse --show-toplevel)"`** 自动进入仓库根（该目录下应能看到 `docker-compose.local-beta.yml`）。
- 运行 **`./deploy/local-beta/build-and-up.sh`** 时，脚本会**自己**定位仓库根；**请先在仓库根执行** `chmod +x ...`，本机仓库根为 `/home/xixiang2025/OM`。
- 脚本里的 **`==> npm ci && npm run build (user-web)`** 等行是**正常进度提示**，表示正在构建，不是报错。

**步骤 0：前置**

- 安装 Docker Engine、Docker Compose v2、Node.js（建议 20 LTS）。

**步骤 1：后端环境**

```bash
cd "$(git rev-parse --show-toplevel)"
cp backend/.env.local-beta.example backend/.env.local-beta
${EDITOR:-nano} backend/.env.local-beta
```

**步骤 2：构建两个前端（生产构建，读 `.env.production`）**

```bash
cd "$(git rev-parse --show-toplevel)/user-web"
cp .env.production.example .env.production
npm ci
npm run build

cd "$(git rev-parse --show-toplevel)/admin-web"
cp .env.production.example .env.production
npm ci
npm run build
```

**步骤 3：启动栈**

```bash
cd "$(git rev-parse --show-toplevel)"
docker compose --env-file ./backend/.env.local-beta -f docker-compose.local-beta.yml up -d --build
```

或一键「构建前端 + 启动」（须已存在 `backend/.env.local-beta` 与两个前端的 `.env.production`）。

**必须在仓库根目录执行**（该目录下能看到 `docker-compose.local-beta.yml`、`deploy/`；**不要**在 `user-web` 子目录里跑 `deploy/...`）：

```bash
cd "$(git rev-parse --show-toplevel)"
chmod +x deploy/local-beta/build-and-up.sh
./deploy/local-beta/build-and-up.sh
```

若你当前终端在 `user-web` 里，可任选其一：

```bash
cd .. && chmod +x deploy/local-beta/build-and-up.sh && ./deploy/local-beta/build-and-up.sh
# 或（在 user-web 下）
npm run local-beta:up
```

**步骤 4：看日志（可选）**

```bash
docker compose --env-file ./backend/.env.local-beta -f docker-compose.local-beta.yml logs -f api
```

**步骤 5：本机浏览器**

- 用户站：`http://127.0.0.1:8080`
- 管理端：`http://127.0.0.1:8081`（使用 `FIRST_SUPERUSER_*` 首次启动创建的账号）

**步骤 6：停止（保留数据库卷）**

```bash
cd "$(git rev-parse --show-toplevel)"
docker compose --env-file ./backend/.env.local-beta -f docker-compose.local-beta.yml down
```

**步骤 7：停止并清空 Postgres 数据（慎用）**

```bash
docker compose --env-file ./backend/.env.local-beta -f docker-compose.local-beta.yml down -v
```

---

## 7. 数据库 migration 命令

**首次 `up` 时**：API 容器入口已执行 `alembic upgrade head`（见 `backend/Dockerfile`），一般无需手工再跑。

**栈已启动时手动再执行一遍**：

```bash
cd "$(git rev-parse --show-toplevel)"
docker compose --env-file ./backend/.env.local-beta -f docker-compose.local-beta.yml exec api alembic upgrade head
```

**本机不通过 Docker、仅连已映射的 Postgres**（示例）：

```bash
cd "$(git rev-parse --show-toplevel)/backend"
export DATABASE_URL="postgresql+psycopg://postgres:你的密码@127.0.0.1:15432/videodb"
./.venv/bin/alembic upgrade head
```

---

## 8. Seed 测试数据命令

本仓库**无**一键灌大量业务数据的统一 CLI；内测最小路径如下。

**A. 首个管理员（超级用户）**

在 `backend/.env.local-beta` 配置 `FIRST_SUPERUSER_EMAIL`、`FIRST_SUPERUSER_USERNAME`、`FIRST_SUPERUSER_PASSWORD`。库中**尚无**同名用户时，API 启动时 `init_db` 会创建一次。查看日志确认无报错后，用管理端登录。

**B. 注册普通演示用户（可选）**

```bash
cd "$(git rev-parse --show-toplevel)"
chmod +x deploy/local-beta/scripts/register_demo_user.sh
BETA_PUBLIC_BASE=http://127.0.0.1:8080 ./deploy/local-beta/scripts/register_demo_user.sh
```

可覆盖环境变量：`BETA_DEMO_EMAIL`、`BETA_DEMO_USERNAME`、`BETA_DEMO_PASSWORD`。

**C. 上传、过审、在列表中可见**

1. 用户站注册/登录 → **创作**：上传视频（本站磁盘）与可选附件 → 详情页 **提交审核**。  
2. 管理端 **视频审核** → **通过**。  
3. 用户站 **视频列表 / 首页** 可见已发布稿件；详情页 **加载播放器**（本机源为 HTML5 视频，点播源为阿里云播放器）。

### 8.1 Expo / 移动端（`mobile-app`）与 local-beta 对齐

本 compose **不把 API 的容器 `8000` 映射到宿主机**（仅 Docker 内 `nginx → api:8000`）。因此：

- **连本机已起的 local-beta 栈**：请在 `mobile-app/.env`（或环境变量）设置  
  `EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8080/api/v1`  
  （与用户站同源经 Nginx 反代；Android 模拟器常用 `http://10.0.2.2:8080/api/v1`。）
- **连 `backend/docker-compose.yml`（宿主机已映射 `127.0.0.1:8000→api`）**：使用  
  `EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1`。

勿混用：仅起 local-beta 时若仍填 `:8000`，宿主机上通常**没有**监听，会导致 App 无法登录。

详见仓库内 **`mobile-app/.env.example`**。

---

## 9. ngrok / Cloudflare Tunnel 暴露说明

原则：**只把本机 Nginx 的 8080 / 8081 映到公网**，不要把本机映射的 Postgres/Redis 端口（默认 **15432 / 16379**）或 API 的裸 `8000` 直接暴露（本 compose 下 API 也未映射到宿主机）。

前端已使用 **`VITE_API_BASE_URL=/api/v1`** 时，**同一隧道域名**下页面与 API **同源**，隧道 URL 变更后通常**无需重新 build**。

Cloudflare Tunnel 推荐直接使用仓库内专用说明：**[`../cloudflare-tunnel/README.md`](../cloudflare-tunnel/README.md)**。它包含：

- 用户站 `app.example.com` → `127.0.0.1:8080`
- 管理端 `admin.example.com` → `127.0.0.1:8081`
- compose 托管 `cloudflared`
- `API_PUBLIC_BASE_URL=https://app.example.com/api/v1`
- 一键验证脚本 `deploy/cloudflare-tunnel/verify_cloudflare_tunnel.sh`

### Cloudflare Tunnel（quick tunnel）

多数 Linux 发行版 **`apt install cloudflared` 会报找不到包**，请从 [GitHub Releases](https://github.com/cloudflare/cloudflared/releases/latest) 下载 `cloudflared-linux-amd64`（或 `arm64`）到 `~/.local/bin` 或 `/usr/local/bin` 并 `chmod +x`；详见 **`GUIDE_新手一步一步_外测注册登录.md`** 第七节 A1。

```bash
cloudflared tunnel --url http://127.0.0.1:8080
```

终端会打印 `https://....trycloudflare.com`，发给内测用户访问用户站。

管理端另开进程（或配置命名隧道 / 多条 ingress）：

```bash
cloudflared tunnel --url http://127.0.0.1:8081
```

若后端需显式 CORS，在 `backend/.env.local-beta` 设置，例如：

`CORS_ORIGINS=https://你的用户站.trycloudflare.com,https://你的管理端.trycloudflare.com`

（`ENVIRONMENT=local` 时常用 `*` 已足够，按你环境收紧。）

若视频播放链接在浏览器控制台显示 **mixed content** 或 URL 以 `http://` 开头，请设置：

```bash
API_PUBLIC_BASE_URL=https://你的用户站.trycloudflare.com/api/v1
```

然后重启 compose。

### ngrok

安装请用 [ngrok 官方 Linux 文档](https://ngrok.com/download/linux) 的 **apt 源**（勿使用已失效的 `bin.equinox.io` 直链；ARM 包名为 **arm64** 而非 `aarch64`）。配置 `ngrok config add-authtoken` 后：

```bash
ngrok http http://127.0.0.1:8080
ngrok http http://127.0.0.1:8081
```

**隧道模式注意**：若使用 `trycloudflare.com` / ngrok 等域名，须保证浏览器能访问该 HTTPS；后端已可设 `AUTH_TRUST_X_FORWARDED_FOR=true`，由 Nginx 写入 `X-Forwarded-For`。

---

## 10. 部署后验证清单

- [ ] `docker compose --env-file ./backend/.env.local-beta -f docker-compose.local-beta.yml ps` 中 `db`、`redis`、`api`、`nginx` 均为 `running` / `healthy`。
- [ ] `curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/health` 与 `...8081/health` 均为 **200**。
- [ ] Cloudflare Tunnel：`APP_URL=https://你的用户站域名 ADMIN_URL=https://你的管理端域名 bash deploy/cloudflare-tunnel/verify_cloudflare_tunnel.sh` 通过。
- [ ] `curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/api/v1/` 或文档中已知公开路径返回预期（非 502）。
- [ ] 用户站首页与列表无控制台大量 **404** / CORS 错误（若此前 `/users/me/profile-hub` 等 404，多为旧 compose 或走错后端目录；确认 **`om-media-local-beta`** 栈且 **`openapi.json`** 含对应路径）。
- [ ] （可选）**Expo**：`EXPO_PUBLIC_API_BASE_URL` 使用 **8080**（local-beta）或 **8000**（backend compose），勿混用（见上文 §8.1）。
- [ ] 管理端：超级用户可登录；普通用户应无法进入管理后台。
- [ ] 用户站：注册 / 登录、个人中心、视频详情等核心流程无异常。
- [ ] 已发布视频：**播放器加载成功**（阿里云媒资与 AK 权限正确）。
- [ ] 宿主机上 `ss -lntp | grep -E ':15432|:16379'`（或你自定义的映射端口）：**无** `0.0.0.0:` 监听在公网接口（本 compose 仅 `127.0.0.1`）。
- [ ] 对外仅分享 **隧道 HTTPS**，未分享数据库端口或内网 IP 上的裸 DB。

---

## 附录：目录索引

| 路径 | 说明 |
|------|------|
| `/docker-compose.local-beta.yml` | 编排 |
| `/deploy/local-beta/nginx/local-beta.conf` | Nginx |
| `/backend/.env.local-beta.example` | 后端环境示例 |
| `/user-web/.env.production.example` | 用户端生产构建示例 |
| `/admin-web/.env.production.example` | 管理端生产构建示例 |
| `/deploy/local-beta/scripts/register_demo_user.sh` | 演示用户注册 |
| `/deploy/local-beta/scripts/reset_admin_password_in_db.sh` | 同步管理员登录密码到数据库（改 `.env` 后若仍无法登录可执行） |

数据库备份可参考 `backend/README.md` 与 `backend/scripts/backup_postgres.sh`（需本机 `pg_dump` 且能连 `127.0.0.1` 上映射的 PG 端口，本 compose 默认为 **15432**）。

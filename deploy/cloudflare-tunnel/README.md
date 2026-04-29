# Cloudflare Tunnel 部署说明

目标：通过 Cloudflare Tunnel 暴露本机 Beta 栈，同时保证：

- 用户站可访问：`https://app.example.com`
- 管理端可访问：`https://admin.example.com`
- 两端均使用同源 `/api/v1`
- 本机成片播放 URL 为 HTTPS，不再被浏览器 mixed content 拦截
- Postgres / Redis / API 容器不直接暴露公网

## 1. 前置状态

先按 `deploy/local-beta/README.md` 完成本机 Beta：

```bash
cd "$(git rev-parse --show-toplevel)"
cp backend/.env.local-beta.example backend/.env.local-beta
cp user-web/.env.production.example user-web/.env.production
cp admin-web/.env.production.example admin-web/.env.production
./deploy/local-beta/build-and-up.sh
```

确认本机可访问：

- `http://127.0.0.1:8080`
- `http://127.0.0.1:8081`

## 2. 必填后端变量

编辑 `backend/.env.local-beta`：

```bash
AUTH_TRUST_X_FORWARDED_FOR=true

# 推荐显式设置，避免后端签发 http://.../local-stream，HTTPS 页面会被 mixed content 拦截。
# 须含 /api/v1，且不要尾斜杠。
API_PUBLIC_BASE_URL=https://app.example.com/api/v1
```

如果你采用“用户站和管理端两个域名，API 都走各自同源 `/api/v1`”，前端保持：

```bash
VITE_API_BASE_URL=/api/v1
```

即 `user-web/.env.production` 与 `admin-web/.env.production` 均不需要写绝对域名。

## 3. Cloudflare ingress

你需要暴露 **两个 hostname**：

| hostname | 本机服务 |
|---|---|
| `app.example.com` | `http://127.0.0.1:8080` |
| `admin.example.com` | `http://127.0.0.1:8081` |

方式 A：Cloudflare Zero Trust Dashboard 里新增 Public Hostname：

- `app.example.com` → `http://127.0.0.1:8080`
- `admin.example.com` → `http://127.0.0.1:8081`

方式 B：使用本目录 `config.yml.example`：

```bash
cp deploy/cloudflare-tunnel/config.yml.example deploy/cloudflare-tunnel/config.yml
${EDITOR:-nano} deploy/cloudflare-tunnel/config.yml
cloudflared tunnel --config deploy/cloudflare-tunnel/config.yml run <TUNNEL_UUID_OR_NAME>
```

## 4. Compose 管理 cloudflared（可选）

如果你在 Cloudflare Dashboard 拿到 Docker token：

```bash
cp deploy/cloudflare-tunnel/.env.example deploy/cloudflare-tunnel/.env
${EDITOR:-nano} deploy/cloudflare-tunnel/.env

docker compose \
  --env-file ./backend/.env.local-beta \
  --env-file ./deploy/cloudflare-tunnel/.env \
  -f docker-compose.local-beta.yml \
  -f docker-compose.cloudflare-tunnel.yml \
  up -d --build
```

该覆盖文件使用 `network_mode: host`，是为了让 cloudflared 容器访问本机只绑定 `127.0.0.1` 的 Nginx 端口。

## 5. 验证

```bash
APP_URL=https://app.example.com ADMIN_URL=https://admin.example.com \
  bash deploy/cloudflare-tunnel/verify_cloudflare_tunnel.sh
```

验证内容：

- 用户站 SPA 首页
- 管理端 SPA 首页
- `/health`
- `/openapi.json`
- OpenAPI 中是否包含本机播放接口 `/videos/{video_id}/play` 与 `/local-stream`

## 6. 为什么之前 Cloudflare 下视频不能播

Cloudflare Tunnel 到本机 Nginx 是 HTTP。旧 Nginx 配置把 `X-Forwarded-Proto` 覆盖成 `$scheme`，即 `http`。后端生成本机播放链接时可能得到：

```text
http://app.example.com/api/v1/videos/.../local-stream?token=...
```

而你的页面是 HTTPS，浏览器会拦截 HTTP 视频流。现在 `deploy/local-beta/nginx/local-beta.conf` 会优先保留上游传入的 `X-Forwarded-Proto`；同时建议显式设置：

```bash
API_PUBLIC_BASE_URL=https://app.example.com/api/v1
```

这能让播放链接稳定为 HTTPS。

## 7. Cloudflare 上传限制

Cloudflare 代理对单次 HTTP 上传大小有账户级限制（免费/Pro 常见为 100MB，具体以 Cloudflare 当前计划为准）。本仓库 Nginx 与后端已支持大文件，但若视频文件超过 Cloudflare 限制，Tunnel 入口仍可能拒绝。

推荐：

- 内测小视频：走当前 `PUT /api/v1/videos/{id}/local-media-binary`
- 大视频生产：使用阿里云 VOD/OSS 直传，避免大文件穿过 Cloudflare Tunnel
- 或将本机成片上传仅限内网/VPN，公网只播放

## 8. 管理端保护

建议在 Cloudflare Zero Trust 为 `admin.example.com` 增加 Access Policy，只允许你的邮箱/团队访问。应用自身仍有管理员登录鉴权，但公网管理入口建议再加一层 Cloudflare Access。

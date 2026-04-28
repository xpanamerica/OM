# Docker 本机网络与代理（起真实容器前必读）

目标：**dockerd** 能稳定访问镜像仓库，`docker compose up` 可拉取 `db` / `redis` / 构建 `api`。

## 1. 先分清：谁在读 HTTP_PROXY？

| 位置 | 是否影响 `docker pull` |
|------|-------------------------|
| 当前 shell 的 `export HTTP_PROXY=...` | **一般不影响** dockerd（守护进程单独环境） |
| **`/etc/systemd/system/docker.service.d/*.conf`** 里 `Environment=HTTP_PROXY` | **影响**，且占位/错误值会导致 `proxyconnect`、`lookup http` |
| **`~/.docker/config.json`** 的 `proxies` | 可能影响 **客户端** 行为；与 systemd 叠加时需一并检查 |
| **`/etc/docker/daemon.json`** 的 `registry-mirrors` | 影响拉取路径；需 root 编辑 |

结论：在 Linux 上 **`docker compose` / `docker pull` 走 dockerd**，优先查 **systemd drop-in**。

## 2. 推荐修复顺序（本仓库脚本）

1. **自检**（无需 sudo；其中 `docker pull` 默认使用 **DaoCloud** 上的 `hello-world`，避免直连 `registry-1.docker.io` 在国内/弱网下超时）：

   ```bash
   cd backend
   bash scripts/verify_docker_network_ready.sh
   ```

   如需改用其它探测镜像：`export DOCKER_NETWORK_PROBE_IMAGE=你的仓库/镜像:tag` 后再运行脚本。

2. **若第 1 步仍提示 systemd 里存在活动代理行**，或曾出现 `proxyconnect` / `lookup http`：

   ```bash
   sudo bash "$(realpath scripts/one_shot_fix_docker_all.sh)"
   ```

   或分步：`sudo bash "$(realpath scripts/fix_docker_proxy_systemd.sh)"`（见 `docker-registry-pull.md`）。

3. **拉取超时（`context deadline exceeded`）**：

   - 已在本仓库 `Makefile` 的 `up` / `pull` 中设置较长的 **`COMPOSE_HTTP_TIMEOUT`**。
   - `docker-compose.yml` 默认镜像前缀为 **DaoCloud 对 Hub 的公共代理**（可通过环境变量 `MEDIA_*` 改回官方或自建镜像源），见根目录 **`.env.example`**。
   - 复制：`cp .env.example .env`，按需调整 `MEDIA_POSTGRES_IMAGE` / `MEDIA_REDIS_IMAGE` / `MEDIA_PYTHON_IMAGE`。

4. **仍慢或失败**：在 `/etc/docker/daemon.json` 配置 `registry-mirrors`（需管理员），或使用公司内网 registry；详见 Docker 官方文档。

## 3. 验证「本机 Docker 已正常」

```bash
cd backend
bash scripts/verify_docker_network_ready.sh
docker compose up -d --build
bash scripts/verify_docker_endpoints.sh
# 可选：连同默认管理员 OAuth 登录与 GET /users/me
# VERIFY_DOCKER_AUTH=1 bash scripts/verify_docker_endpoints.sh
```

## 4. 与「仅 Registry」文档的关系

- 占位代理、NOPASSWD 一键修复：[`docker-registry-pull.md`](docker-registry-pull.md)
- 本文侧重：**代理 + 超时 + 镜像源** 与 **自检命令** 的总览。

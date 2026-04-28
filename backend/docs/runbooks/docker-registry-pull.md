# Docker Hub 拉镜像失败（代理 / DNS）

## 症状

- `docker pull`、`docker compose up` 报错含 **`proxyconnect`**、**`lookup http`**、**`no such host`** 等。
- 在 shell 里执行 `unset HTTP_PROXY HTTPS_PROXY` **仍无效**。

## 根因

在多数 Linux 安装中，**Docker 守护进程**从 **`/etc/systemd/system/docker.service.d/*.conf`** 读取 `Environment=HTTP_PROXY=...`。占位或错误 URL 会让 daemon 对所有 registry 请求走坏代理。

**总览（代理 + 超时 + 镜像源）**：另见 [`docker-network-proxy.md`](docker-network-proxy.md)。起栈前可运行：`bash scripts/verify_docker_network_ready.sh`。

## 修复步骤

### A. 一条命令（最推荐：一次 sudo 密码）

同时完成 **NOPASSWD sudoers** + **清空无效 systemd 代理并重启 dockerd**：

```bash
cd backend
sudo bash "$(realpath scripts/one_shot_fix_docker_all.sh)"
```

或：`make fix-docker-once`。

**注意**：必须用 `sudo bash …/one_shot_fix_docker_all.sh`，不要用 `sudo -i` 再执行，否则缺少 `SUDO_USER`，NOPASSWD 会写错用户。

完成后可免密：

```bash
sudo -n bash "$(realpath scripts/fix_docker_proxy_systemd.sh)"
```

### B. 分步：仅装 NOPASSWD（一次密码）+ 再免密修代理

```bash
cd backend
bash scripts/install_sudoers_docker_proxy_nopasswd.sh
sudo -n bash "$(realpath scripts/fix_docker_proxy_systemd.sh)"
```

或：`make install-sudoers-docker-nopasswd` → `make fix-docker-proxy`。

### C. 仅临时修复（每次可能提示密码）

1. 诊断（无需 sudo）：

   ```bash
   cd backend
   bash scripts/diagnose_docker_proxy.sh
   ```

2. 修复（需 sudo）：备份并清空无效 drop-in、重启 Docker、试拉 `hello-world`：

   ```bash
   sudo bash "$(realpath scripts/fix_docker_proxy_systemd.sh)"
   ```

3. 若你**确实需要**企业 HTTP 代理，请编辑同一 drop-in 文件，写入**真实** `http://主机:端口/`，并设置合理的 `NO_PROXY`（含 `docker.io`、`.docker.io`、`localhost`、`127.0.0.1`），再：

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart docker
   ```

4. 回到项目：

   ```bash
   docker compose up -d --build
   bash scripts/verify_docker_endpoints.sh
   ```

### D. 可选：镜像加速叠加（仍可能被无效 daemon 代理拖累）

若 Hub 直连慢，可叠加 DaoCloud 代理镜像（**不替代** A/B/C 修复无效 `HTTP_PROXY`）：

```bash
docker compose -f docker-compose.yml -f docker-compose.mirror.yml up -d --build
```

或：`make up-mirror`。

## 仍失败时

- 检查防火墙、公司网络对 `registry-1.docker.io` 的拦截。
- 考虑配置 **registry mirror**（`daemon.json`，需管理员权限），或离线导入镜像。

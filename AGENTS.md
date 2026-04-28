# 本仓库给 AI / Agent 的说明

## 为什么会出现「PhaseAGI 卡住」？

Cursor Agent 执行终端命令时，底层可能启动 **会加载 `~/.bashrc` 的 bash**。若 `bashrc` 里 PhaseAGI 在**任何** shell 里都要求交互密码，非交互的 Agent 管道就会**阻塞**，表现为命令「跑不起来」。

## 本项目约定

1. **工作区**：根目录 `.vscode/settings.json` 已将 **默认终端** 与 **`terminal.integrated.automationProfile.linux`** 设为 **`media_app`**（`bash --noprofile --norc` + `conda activate media_app`），尽量绕开 PhaseAGI。
2. **用户本机**：仍建议在 `~/.bashrc` 里用 **`CURSOR_AGENT` / `CURSOR_SANDBOX`** 跳过 PhaseAGI（见 Cursor 官方 Terminal 文档 Troubleshooting）。可复制片段说明：`backend/scripts/bashrc_phaseagi_guard.snippet.bash`。
3. **跑 Python 命令**：优先使用 **`$HOME/software/anaconda3/envs/media_app/bin/python`**（与 `python.defaultInterpreterPath` 一致）或 **`conda run -n media_app`**，避免裸 `python` 命中错误包装器。

更细的规则见：`.cursor/rules/media-app-conda.mdc`。

## Docker 拉镜像失败

若 `docker compose` 报 `proxyconnect` / `lookup http`：优先在 `backend/` **一条命令**（只输一次 sudo 密码）：

`sudo bash "$(realpath scripts/one_shot_fix_docker_all.sh)"`（或 `make fix-docker-once`）。勿用 `sudo -i` 再执行。  
起栈前自检代理与拉取：`make verify-docker-network` 或 `bash scripts/verify_docker_network_ready.sh`。诊断：`bash scripts/diagnose_docker_proxy.sh`。shell 里 `unset HTTP_PROXY` 对 dockerd **通常无效**。

#起栈验证命令（首次需在 `backend/` 生成 `.env`：`bash scripts/init_local_compose_env.sh`）：
docker compose up -d --build
bash scripts/verify_docker_endpoints.sh
# 可选：连同默认管理员登录烟测（密码由 scripts/read_compose_first_superuser_password.py 从 compose 解析）
# VERIFY_DOCKER_AUTH=1 bash backend/scripts/verify_docker_endpoints.sh
# 仅打印默认引导口令（本地排障）：cd backend && make show-compose-bootstrap-password

# 创建首个超级用户

## Docker Compose 默认行为

`docker-compose.yml` 中 `api` 服务可通过环境变量在启动时创建首个超级用户（若不存在）：

- `FIRST_SUPERUSER_EMAIL`
- `FIRST_SUPERUSER_USERNAME`
- `FIRST_SUPERUSER_PASSWORD`（配置模型中为 **`SecretStr`**，`repr` 与常规日志不会明文输出）

逻辑见 `app/db/init_db.py`。生产/staging 环境下弱口令（如 **`changeme` 整串**、`password`、`admin` 等）会在配置校验阶段直接拒绝，见 `app/core/config.py`。

本地首次起栈请先在 **`backend/`** 执行 **`bash scripts/init_local_compose_env.sh`** 生成 **`.env`**（含随机首管口令）；勿将 **`.env`** 提交到 Git。

### 本地 Docker 登录（OAuth2 表单）

- **用户名**（`username` 字段）：`admin`（或邮箱 `admin@example.com`）
- **密码**：以 **`backend/.env`** 中 `FIRST_SUPERUSER_PASSWORD` 为准；若无 `.env` 则由 `docker-compose.yml` 中 `${FIRST_SUPERUSER_PASSWORD:-…}` 默认段决定。在 **`backend/`** 下执行：  
  `python3 scripts/read_compose_first_superuser_password.py`  
  或 `make show-compose-bootstrap-password`  
  打印**当前**解析出的口令（与 `VERIFY_DOCKER_AUTH` 烟测同源；若需覆盖，可设环境变量 **`DOCKER_FIRST_SUPERUSER_PASSWORD`**）。

示例（宿主机，栈已起、端口 8000）：

```bash
cd backend
PW="$(python3 scripts/read_compose_first_superuser_password.py)"
curl -sS -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'username=admin' \
  --data-urlencode "password=${PW}"
```

一键烟测（含 `/health` 与登录、`/users/me`）：`VERIFY_DOCKER_AUTH=1 bash scripts/verify_docker_endpoints.sh` 或 `make verify-docker-auth`。

## 生产建议

- 使用密钥管理（K8s Secret、云厂商参数中心）注入上述变量，**勿**将密码提交到仓库。
- 创建后立即登录并修改密码；可考虑后续接入「邀请制管理员」流程替代环境变量。

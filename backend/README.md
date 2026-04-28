# 视频知识平台 · 后端 API

面向「视频 + 分类/标签 + 审核流 + 评论 + 互动 + 播放记录 + 管理端统计」的 **FastAPI** 服务。本文档目标：**非原作者也能在本地或 Docker 中跑起来**。

**更多文档**：

| 文档 | 内容 |
|------|------|
| [`docs/API_OVERVIEW.md`](docs/API_OVERVIEW.md) | 各模块 HTTP 路径速览 |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Compose、Postgres/Redis、生产变量、反代/HTTPS/日志/备份 |
| [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md) | 上线前检查清单 |
| [`docs/architecture.md`](docs/architecture.md) | 模块边界与依赖约定 |
| [`docs/runbooks/`](docs/runbooks/) | 镜像拉取、网络代理、迁移、[阿里云 OSS/VOD](docs/runbooks/aliyun-vod-oss.md) 等 Runbook |

---

## 1. 项目简介

提供用户注册登录、视频草稿与审核（提交/通过/驳回/下架）、公开列表与详情、评论、点赞与收藏、播放记录、分类与标签（管理员维护）、管理员视频/用户列表与平台统计等能力。对外统一前缀 **`/api/v1`**（由 `API_V1_PREFIX` 配置，默认即此值）。

---

## 2. 技术栈

| 类别 | 选型 |
|------|------|
| 语言 / 运行时 | Python **3.11** |
| Web | **FastAPI** + Uvicorn |
| ORM | **SQLAlchemy 2.x** |
| 数据库 | **PostgreSQL**（生产）；开发与 CI 亦支持 SQLite |
| 缓存 / 限流 / 幂等 | **Redis**（可选；部分能力可回退进程内） |
| 迁移 | **Alembic** |
| 测试 | **pytest** + `httpx`/`TestClient` |

---

## 3. 目录结构（与仓库一致）

```text
backend/
├── alembic/              # 迁移版本脚本
├── alembic.ini
├── app/
│   ├── api/v1/         # 路由：auth、users、categories、tags、videos、
│   │                   # video_workflow、video_interactions、video_comments、
│   │                   # view_records、admin_management 等
│   ├── core/           # config、security、exceptions、logging、http_middleware
│   ├── db/             # engine、session、init_db
│   ├── models/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   ├── infrastructure/
│   └── main.py         # FastAPI 实例与 lifespan
├── docker-compose.yml
├── docker-compose.mirror.yml      # 可选镜像加速叠加
├── docker-compose.api-loopback.yml  # 可选：API 仅绑定 127.0.0.1:8000
├── Dockerfile
├── docs/               # architecture、runbooks、API_OVERVIEW、DEPLOYMENT、RELEASE_CHECKLIST
├── scripts/            # 校验、排障、bootstrap；含 verify_compose_stack_smoke.sh（CI 烟测）
├── tests/
│   ├── conftest.py     # 见下文「测试」：强制内存 SQLite + DB 依赖覆盖
│   ├── integration/
│   ├── unit/
│   └── test_*.py       # 按业务阶段的回归用例
├── workers/            # 异步任务占位说明（见 workers/README.md）
├── .env.example        # 环境变量模板（Compose + 应用）
├── Makefile
└── requirements.txt
```

---

## 4. 环境变量说明

**权威列表**：`app/core/config.py`（Pydantic `Settings`）与 **`.env.example`**（与下表同一套键名；含 Compose 镜像与超时变量）。

**Compose 与本文件**：**`SECRET_KEY`** 与 **`POSTGRES_PASSWORD`** 不再提供 compose 内联弱默认，须在 **`backend/.env`** 中设置（或导出同名环境变量）。首次起栈推荐执行 **`bash scripts/init_local_compose_env.sh`** 生成随机 **`.env`**（勿提交 Git）；亦可参考 **`.env.example`** 自建。**`DATABASE_URL`** 未显式设置时，`api` 会使用与 **`POSTGRES_*`** 拼接的默认连接串。**`FIRST_SUPERUSER_*`** 仍可用 compose 中的 **`${VAR:-默认}`** 或由 **`.env`** 覆盖。`api` 的 **`ENVIRONMENT` 在 compose 中固定为 `local`**。本机直跑 Uvicorn 时以进程环境与 **`.env`** 为准。

**常见变量**（应用进程；与 `.env.example` 中「App / Database / Redis」段对应）：

| 变量 | 含义 |
|------|------|
| `ENVIRONMENT` | `local` / `development` / `production` / `staging` 等；控制文档暴露、CORS 严格度、`SECRET_KEY` 长度建议等 |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `SECRET_KEY` | JWT 签名密钥；**UTF-8 至少 32 字节**；生产类环境建议 **≥48** 且禁止示例/单测默认串 |
| `DATABASE_URL` | 异步驱动推荐 `postgresql+psycopg://...` |
| `REDIS_URL` | Redis 连接串 |
| `API_V1_PREFIX` | 默认 `/api/v1` |
| `CORS_ORIGINS` | 逗号分隔或 JSON 数组；生产类环境禁止仅 `*` |
| `FIRST_SUPERUSER_*` | 可选；首次建库时创建管理员（见 `app/db/init_db.py`） |

Compose 专用变量（见 `.env.example` 顶部）：`COMPOSE_HTTP_TIMEOUT`、`MEDIA_POSTGRES_IMAGE` 等。

---

## 4.5 启动前检查（约 30 秒）

| 检查项 | Docker 起栈 | 本机 Uvicorn / 跑 pytest |
|--------|-------------|---------------------------|
| **工作目录** | 下文所有 `cd /home/xixiang2025/OM/backend` 中的 **`/home/xixiang2025/OM`** 已填写为本机实际**仓库根目录**（含根 `README.md` 与 `backend/` 子目录的那一层）；进入其中的 **`backend/`** 后再执行 `docker compose` / `make` | 同上 |
| **前置条件** | 已安装 **Docker Engine** 与 **Compose v2** | **Python 3.11**；自备 **PostgreSQL + Redis**（Uvicorn 路线） |
| **配置文件** | 首次推荐 **`bash scripts/init_local_compose_env.sh`** 生成 **`.env`**；镜像源等可再参考 **`.env.example`** 增补；默认 compose 下 **Postgres/Redis 仅监听宿主机 `127.0.0.1`** | 按 §5.2 `export` 或自行加载 `.env` |
| **解释器** | 不依赖宿主 Python | 文档默认 Conda 为 **`$HOME/software/anaconda3/envs/media_app`**（与 `.vscode` 一致）。**若该路径不存在**：先用 §5.2 在 `backend/` 建 **`.venv`** 并 `pip install -r requirements.txt`，测试改用 **`./.venv/bin/python -m pytest tests/ -q`**；或创建同名 Conda 环境后使用 **`conda run -n media_app python -m pytest tests/ -q`**。若 Conda 安装前缀不同，请同步修改 **`.vscode/settings.json`** 里的 **`python.defaultInterpreterPath`**，避免 IDE 与命令行各用一套解释器。 |

**快速自检**（在打算执行 `docker compose` / `pytest` / `alembic` 的终端里）：`test -f docker-compose.yml && test -d app` 应为真；若为假，说明当前不在 **`backend/`** 根目录（常见误操作：停在仓库根 `OM/` 而未进入 `backend/`）。

---

## 5. 本地启动方式

### 5.1 使用 Docker（推荐与生产最接近）

```bash
cd /home/xixiang2025/OM/backend
bash scripts/init_local_compose_env.sh   # 首次：生成随机 SECRET_KEY / 数据库口令 / 首管口令写入 .env
COMPOSE_HTTP_TIMEOUT=300 docker compose up --build
```

默认 **`http://localhost:8000/docs`**（开发态）、**`http://localhost:8000/health`**。默认 compose 中 **Postgres / Redis 仅映射到宿主机 `127.0.0.1`**，`api` 仍为 **`0.0.0.0:8000`**（便于同网段设备调试）；若希望 API 也仅本机访问，可叠加 **`docker-compose.api-loopback.yml`**（见同目录文件头注释）。所有服务带 **`restart: unless-stopped`**。

容器内启动命令等价：`alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000`（见 `Dockerfile`）。

更多：`make up`、`make logs`、`make migrate`；镜像代理、备份、生产变量等见 **[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)**（可独立阅读，无需对照口头说明）。

### 5.2 本机直接跑 Uvicorn（需自备 Postgres + Redis）

```bash
cd /home/xixiang2025/OM/backend
python3 -m venv .venv && source .venv/bin/activate   # 或使用 Conda 环境 media_app
pip install -r requirements.txt

export SECRET_KEY="$(python3 -c "import secrets; print(secrets.token_hex(32))")"
export DATABASE_URL="postgresql+psycopg://USER:PASS@127.0.0.1:5432/videodb"
export REDIS_URL="redis://127.0.0.1:6379/0"
export ENVIRONMENT=local

alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 6. 数据库 migration（Alembic）

**命令速查**（均在 `cd .../backend` 之后执行）：

| 场景 | 命令 |
|------|------|
| 本机已 export `DATABASE_URL`（指向可达 Postgres） | `alembic upgrade head` |
| Compose 已启动、`api` 容器在运行 | `docker compose exec api alembic upgrade head` |
| 与 Makefile 等价 | `make migrate` |

**在开发机（已配置 DATABASE_URL）**：

```bash
cd /home/xixiang2025/OM/backend
alembic upgrade head
```

**在已起的 Compose 栈内**：

```bash
cd /home/xixiang2025/OM/backend
docker compose exec api alembic upgrade head
# 或
make migrate
```

**生成新迁移**（模型变更后）：

```bash
cd /home/xixiang2025/OM/backend
docker compose exec api alembic revision --autogenerate -m "describe_change"
```

**回归**：`pytest tests/test_alembic_sqlite.py -q`（在临时 SQLite 文件上 `upgrade head` / 一步 `downgrade`）。

生产与回滚注意：[`docs/runbooks/migrations.md`](docs/runbooks/migrations.md)。

---

## 7. 测试运行方式

**必须在 `backend/` 目录下执行**，以便 `pytest.ini` 与 `app` 包路径正确：

```bash
cd /home/xixiang2025/OM/backend
```

**命令速查**：

| 方式 | 命令 |
|------|------|
| **推荐：本机 venv + Makefile**（规避系统 Python 的 PEP 668，勿用 `sudo pip`） | 首次：`make venv`；之后：`make test-local`；单测：`make test-local PYTEST_ARGS='tests/test_foo.py::case -q --tb=short'` |
| Conda 解释器直接跑（路径与 `.vscode` 默认一致） | `"$HOME/software/anaconda3/envs/media_app/bin/python" -m pytest tests/ -q` |
| 仅本机 venv（无 Conda；与 §5.2 同一 `.venv`） | `./.venv/bin/python -m pytest tests/ -q` |
| Makefile（内部 `conda run -n media_app`；需已存在环境 `media_app`） | `make test-conda` |
| 已起 Docker 且 `api` 在跑 | `docker compose exec api pytest -q` |

**若出现 `No module named pytest`**：说明当前用的是**系统** `python3`（且未全局安装 pytest）。Ubuntu/Debian 等默认 **PEP 668** 禁止 `pip install` 污染系统解释器。请在本目录执行 **`make venv`** 创建 **`backend/.venv`** 并安装 `requirements.txt`，再用 **`make test-local`** 或 **`./.venv/bin/python -m pytest …`**。

使用 Conda 环境 **`media_app`**（与仓库 `.vscode` 约定一致）：

```bash
cd /home/xixiang2025/OM/backend
"$HOME/software/anaconda3/envs/media_app/bin/python" -m pytest tests/ -q
```

或使用 Makefile（**数据库 URL 会在 `tests/conftest.py` import 时被覆盖为进程内 SQLite 共享内存库**，不碰你的开发 Postgres）：

```bash
cd /home/xixiang2025/OM/backend
make test-conda
```

**说明**：`tests/conftest.py` 在 import 阶段设置 `DATABASE_URL` 为 **SQLite `cache=shared` 内存库**、覆盖 `get_db`，每个用例 `drop_all` + `engine.dispose()`，**不会污染本地开发库**。

**常见失败原因**：在仓库根目录用 `pytest backend/tests/...` 导致收集/根目录错位；请始终在 **`cd backend` 后** 运行 `pytest tests/`。

---

## 8. 常见问题（FAQ）

### Q1：`pytest` 大量失败或 `ImportError`

- 确认当前目录为 **`backend/`**：`cd .../backend && pytest tests/ -q`。
- 确认解释器为 **Python 3.11** 且已安装 `requirements.txt`（优先 **`make venv`** + **`./.venv/bin/python`**，见 §7）。

### Q1b：终端里 `python3 -m pytest` 报 `No module named pytest`

- 原因：系统 Python 未装 pytest，且 **PEP 668** 下不建议 `pip install` 到系统环境。
- 处理：**`cd backend && make venv && make test-local`**；或手动 `python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt`，之后一律用 **`./.venv/bin/python -m pytest`**。

### Q2：Docker 拉镜像 `proxyconnect` / `deadline exceeded`

- 见 [`docs/runbooks/docker-network-proxy.md`](docs/runbooks/docker-network-proxy.md)。
- 一条命令修复（需 sudo）：`sudo bash "$(realpath scripts/one_shot_fix_docker_all.sh)"` 或 `make fix-docker-once`。

### Q3：`SECRET_KEY` 校验失败

- 本地至少 **32 字节 UTF-8**；`ENVIRONMENT=production|prod|staging` 时建议 **≥48** 且不能使用示例/文档占位串（见 `app/core/config.py`）。

### Q4：登录 401 但客户端不弹密码框

- 接口返回带 **`WWW-Authenticate: Bearer`**；需按 OAuth2 Bearer 处理。

### Q5：Cursor Agent 跑命令卡住

- 见仓库根目录 **`AGENTS.md`** 与 **`.cursor/rules/media-app-conda.mdc`**（PhaseAGI / bashrc 等）。

### Q6：改了 `POSTGRES_PASSWORD` 后 API 连不上库 / `DATABASE_URL` 怎么写？

- **Compose 栈**：若未显式设置 `DATABASE_URL`，`api` 会使用与 **`POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB`** 同步拼接的连接串；首次可运行 **`bash scripts/init_local_compose_env.sh`** 生成三者一致的 **`.env`**。
- **口令含 `@`、`:`、`#`、`%` 等**：必须对 **用户名与口令** 分别做 URL 编码后再拼进 `postgresql+psycopg://…`。示例（口令为字面 `p@ss:rd`）：

```bash
python3 -c "from urllib.parse import quote; u=quote('postgres', safe=''); p=quote('p@ss:rd', safe=''); print(f'postgresql+psycopg://{u}:{p}@db:5432/videodb')"
```

将输出写入 `.env` 的 **`DATABASE_URL`**（或与默认拼接一致地只改 `POSTGRES_PASSWORD` 为不含保留字符的强口令）。

### Q7：本机想用宿主机工具连容器里的 Postgres / Redis？

- 默认 **`docker-compose.yml`** 已将 **`5432` / `6379` 绑定到 `127.0.0.1`**，可在本机用 `127.0.0.1` 连接；**非回环网卡上的其他机器默认连不到**（降低误暴露）。若确需远程访问，请用 **SSH 隧道** 或在自建 override 中显式调整映射并评估防火墙。

---

## 9. Cursor / Conda（可选）

工作区建议用仓库根 **`OM`** 打开（界面品牌仍为「恒频OM」），使 `.vscode/settings.json` 生效：集成终端使用 **`media_app`** profile（`bash --noprofile --norc` + `conda activate media_app`），默认 **`cwd` 为 `backend/`**。

若 Conda 不在 `~/software/anaconda3`，请同步修改 `.vscode/settings.json` 中的 `python.defaultInterpreterPath` 与终端 profile，并与 **§4.5**、**§7** 中你实际使用的 `python -m pytest` 命令保持一致。

---

## 10. Makefile 速查

| 目标 | 作用 |
|------|------|
| `make up` | `docker compose up --build`（带较长 `COMPOSE_HTTP_TIMEOUT`） |
| `make down` | `docker compose down -v` |
| `make logs` | `docker compose logs -f api` |
| `make migrate` | 容器内 `alembic upgrade head` |
| `make test-conda` | 用 `media_app` 跑 `pytest` |
| `make verify-docker` | `bash scripts/verify_docker_endpoints.sh` |
| `make verify-docker-auth` | 同上 + 默认管理员 OAuth 烟测 |
| `make verify-docker-network` | 起栈前网络/拉取自检 |
| `make verify-compose-smoke` | 起完整栈并校验 `/health`（含 DB 连通）、`/docs`、`/openapi.json` 后自动 teardown |

完整列表见 `Makefile` 文件顶部 `.PHONY` 行。

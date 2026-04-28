.PHONY: init-env up down logs migrate revision test test-conda test-local venv import-check lint lint-conda diagnose-docker fix-docker-proxy verify-docker verify-docker-auth verify-compose-smoke show-compose-bootstrap-password verify-docker-network install-sudoers-docker-nopasswd up-mirror fix-docker-once

# 本地用 Conda（media_app）跑测试/编译。Cursor 用户优先用工作区默认终端（见 ../.vscode/settings.json）；
# 未加载工作区或需与当前 shell 无关时用本目标。首次：bash scripts/bootstrap_conda_env_media_app.sh
CONDA_BIN ?= /home/xixiang2025/software/anaconda3/bin/conda
CONDA_ENV ?= media_app

init-env:
	bash scripts/init_local_compose_env.sh

up:
	@test -f .env || bash scripts/init_local_compose_env.sh
	COMPOSE_HTTP_TIMEOUT=300 docker compose up --build

pull:
	COMPOSE_HTTP_TIMEOUT=300 docker compose pull

up-mirror:
	@test -f .env || bash scripts/init_local_compose_env.sh
	COMPOSE_HTTP_TIMEOUT=300 docker compose -f docker-compose.yml -f docker-compose.mirror.yml up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f api

migrate:
	docker compose exec api alembic upgrade head

revision:
	docker compose exec api alembic revision --autogenerate -m "$(m)"

test:
	docker compose exec api pytest -q

test-conda:
	SECRET_KEY='unit-test-environment-default-secret-48b-min-ok!!' \
	DATABASE_URL='sqlite+pysqlite:///:memory:' \
	REDIS_URL='redis://127.0.0.1:6379/0' \
	$(CONDA_BIN) run -n $(CONDA_ENV) --no-capture-output python -m pytest -q --tb=short

# 本机 PEP 668 环境：勿用系统 python3 -m pip；在 backend/.venv 安装依赖后跑 pytest（与 README §7 一致）
PYTEST_ARGS ?= tests/ -q --tb=short

venv:
	@test -d .venv || python3 -m venv .venv
	./.venv/bin/pip install -U pip
	./.venv/bin/pip install -r requirements.txt

test-local:
	@test -x .venv/bin/python || (echo "缺少 .venv：请先在本目录执行  make venv  （需网络）" && false)
	./.venv/bin/python -m pytest $(PYTEST_ARGS)

# 用 .venv 验证 FastAPI 应用可导入（勿用系统 python3，见 README §7 / PEP 668）
import-check:
	@test -x .venv/bin/python || (echo "缺少 .venv：请先在本目录执行  make venv  （需网络）" && false)
	./.venv/bin/python -c "from app.main import app; print('ok', app.title)"

lint:
	docker compose exec api python -m compileall app

lint-conda:
	$(CONDA_BIN) run -n $(CONDA_ENV) --no-capture-output python -m compileall -q app

diagnose-docker:
	bash scripts/diagnose_docker_proxy.sh

verify-docker-network:
	bash scripts/verify_docker_network_ready.sh

# 起完整栈并探测 /health、/docs（结束自动 down -v；需 Docker 与网络拉镜像）
verify-compose-smoke:
	bash scripts/verify_compose_stack_smoke.sh

fix-docker-proxy:
	@echo "需要 sudo：将备份并清空 systemd 中无效 Docker 代理，然后重启 docker。"
	sudo bash $$(realpath scripts/fix_docker_proxy_systemd.sh)

install-sudoers-docker-nopasswd:
	bash scripts/install_sudoers_docker_proxy_nopasswd.sh

fix-docker-once:
	@echo "将提示一次 sudo 密码：安装 NOPASSWD + 清空无效 Docker 代理"
	sudo bash $$(realpath scripts/one_shot_fix_docker_all.sh)

verify-docker:
	bash scripts/verify_docker_endpoints.sh

# 在 verify-docker 基础上增加默认管理员 OAuth 登录 + GET /users/me（密码须与 compose 一致或设 DOCKER_FIRST_SUPERUSER_PASSWORD）
verify-docker-auth:
	VERIFY_DOCKER_AUTH=1 bash scripts/verify_docker_endpoints.sh

# 打印 docker-compose.yml 中的 FIRST_SUPERUSER_PASSWORD（勿提交到日志系统；仅本地排障）
show-compose-bootstrap-password:
	@python3 scripts/read_compose_first_superuser_password.py; echo

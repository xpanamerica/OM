# 开发 / 默认 ``docker-compose.yml`` 使用本文件；**生产优化镜像**见同目录 ``Dockerfile.prod`` + ``docker-compose.prod.yml``。
# 可通过 compose build.args.BASE_IMAGE 覆盖为镜像加速地址（见 docker-compose.mirror.yml）
ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE}

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000

# 编排层可覆盖；与 scripts/verify_docker_endpoints 一致探测 /health（不依赖 curl）
HEALTHCHECK --interval=30s --timeout=6s --start-period=120s --retries=5 \
  CMD python3 -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4); c=getattr(r,'status',r.getcode()); r.close(); raise SystemExit(0 if c==200 else 1)"

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

import os

os.environ["SECRET_KEY"] = "unit-test-environment-default-secret-48b-min-ok!!"
# 降低访问日志噪声（阶段 10.4 AccessLogMiddleware）
os.environ["LOG_LEVEL"] = "WARNING"
# 使用共享内存库 + 连接池，避免 StaticPool 单连接在多线程用例中出现 sqlite 游标/连接竞态。
os.environ["DATABASE_URL"] = (
    "sqlite+pysqlite:///file:pytest_media_shared?mode=memory&cache=shared"
)
os.environ["REDIS_URL"] = "redis://127.0.0.1:6379/9"
# 评论发帖限流：全量测试关闭，避免偶发 429；单测可单独 patch。
os.environ["COMMENT_POST_MAX_PER_VIDEO_PER_MINUTE"] = "0"
# 评论限流单测与 HTTP 用例默认走进程内窗口，避免依赖本机 Redis 键态
os.environ["COMMENT_RATE_LIMIT_USE_REDIS"] = "false"
# VOD 刷新凭证 / 附件上传限流：全量测试默认进程内窗口，避免依赖本机 Redis 键态
os.environ["VOD_REFRESH_UPLOAD_RATE_LIMIT_USE_REDIS"] = "false"
os.environ["ATTACHMENT_POST_RATE_LIMIT_USE_REDIS"] = "false"
os.environ["EXPOSE_PROMETHEUS_METRICS"] = "false"
# 全量测试在同一进程内多次登录，关闭登录限流避免偶发 429
os.environ["AUTH_LOGIN_MAX_ATTEMPTS_PER_MINUTE"] = "0"
for k in ("FIRST_SUPERUSER_EMAIL", "FIRST_SUPERUSER_USERNAME", "FIRST_SUPERUSER_PASSWORD"):
    os.environ.pop(k, None)

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool


def _sqlite_enable_foreign_keys(dbapi_connection, _connection_record) -> None:
    """与生产外键语义一致：SQLite 默认不强制 FK，测试库统一打开。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


engine = create_engine(
    "sqlite+pysqlite:///file:pytest_media_shared?mode=memory&cache=shared",
    connect_args={"check_same_thread": False, "uri": True},
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
)
event.listen(engine, "connect", _sqlite_enable_foreign_keys)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

import app.db.session as db_session

db_session.engine = engine
db_session.SessionLocal = TestingSessionLocal

import pytest
from fastapi.testclient import TestClient

from app.core.comment_rate_limit import (
    purge_comment_rate_limit_redis_keys_for_tests,
    reset_comment_rate_limit_state,
)
from app.core.attachment_upload_rate_limit import (
    purge_attachment_upload_rate_limit_redis_keys_for_tests,
    reset_attachment_upload_rate_limit_for_tests,
)
from app.core.vod_refresh_upload_rate_limit import (
    purge_vod_refresh_upload_rate_limit_redis_keys_for_tests,
    reset_vod_refresh_upload_rate_limit_for_tests,
)
from app.core.upload_rate_limit import (
    purge_video_upload_rate_limit_redis_keys_for_tests,
    reset_video_upload_rate_limit_state_for_tests,
)
from app.core.login_rate_limit import reset_login_rate_limit_state
from app.core.search_rate_limit import reset_search_rate_limit_state_for_tests

import app.models  # noqa: F401 — 确保 User 等表注册到 metadata
from app.db.base import Base
from app.db.session import get_db
from app.infrastructure.idempotency_store import clear_idempotency_memory_for_tests
from app.infrastructure.observability.comment_metrics import reset_comment_metrics_for_tests
from app.infrastructure.observability.upload_flow_metrics import reset_upload_flow_metrics_for_tests
from app.infrastructure.observability.view_record_metrics import reset_view_record_metrics_for_tests
from app.main import app


@pytest.fixture(autouse=True)
def _reset_login_rate_limit_between_tests():
    reset_attachment_upload_rate_limit_for_tests()
    purge_attachment_upload_rate_limit_redis_keys_for_tests()
    reset_vod_refresh_upload_rate_limit_for_tests()
    purge_vod_refresh_upload_rate_limit_redis_keys_for_tests()
    reset_login_rate_limit_state()
    reset_search_rate_limit_state_for_tests()
    reset_comment_rate_limit_state()
    purge_comment_rate_limit_redis_keys_for_tests()
    reset_video_upload_rate_limit_state_for_tests()
    purge_video_upload_rate_limit_redis_keys_for_tests()
    reset_comment_metrics_for_tests()
    reset_view_record_metrics_for_tests()
    reset_upload_flow_metrics_for_tests()
    clear_idempotency_memory_for_tests()
    yield
    reset_attachment_upload_rate_limit_for_tests()
    purge_attachment_upload_rate_limit_redis_keys_for_tests()
    reset_vod_refresh_upload_rate_limit_for_tests()
    purge_vod_refresh_upload_rate_limit_redis_keys_for_tests()
    reset_login_rate_limit_state()
    reset_search_rate_limit_state_for_tests()
    reset_comment_rate_limit_state()
    purge_comment_rate_limit_redis_keys_for_tests()
    reset_video_upload_rate_limit_state_for_tests()
    purge_video_upload_rate_limit_redis_keys_for_tests()
    reset_comment_metrics_for_tests()
    reset_view_record_metrics_for_tests()
    reset_upload_flow_metrics_for_tests()
    clear_idempotency_memory_for_tests()


@pytest.fixture
def db_session() -> Session:
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    # 与默认 True 相反：未捕获异常应经 register_exception_handlers 落成 JSON 响应，便于断言 5xx 体
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()

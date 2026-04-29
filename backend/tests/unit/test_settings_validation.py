import pytest
from pydantic import ValidationError

from app.core.config import Settings
from tests.support.docker_bootstrap import default_first_superuser_password

_PROD_LIKE_CORS = ["https://app.example.test"]
# 生产类 Settings 校验禁止 postgres:postgres；单测用非默认口令占位
_PROD_LIKE_DB_URL = "postgresql+psycopg://postgres:prod_ci_nondefault_db_pass_16@localhost:5432/videodb"


def test_secret_key_rejects_under_32_utf8_bytes():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(
            SECRET_KEY="a" * 31,
            DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/videodb",
            REDIS_URL="redis://127.0.0.1:6379/0",
        )


def test_secret_key_rejects_legacy_compose_weak_default():
    with pytest.raises(ValidationError, match="SECRET_KEY|弱默认|常见"):
        Settings(
            SECRET_KEY="dev-insecure-change-me-use-openssl-rand-hex-32-in-prod-env!!",
            DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/videodb",
            REDIS_URL="redis://127.0.0.1:6379/0",
        )


def test_production_rejects_postgres_postgres_in_database_url():
    with pytest.raises(ValidationError, match="默认数据库口令"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 48,
            CORS_ORIGINS=_PROD_LIKE_CORS,
            DATABASE_URL="postgresql+psycopg://postgres:postgres@db.internal:5432/videodb",
            REDIS_URL="redis://127.0.0.1:6379/0",
        )


def test_production_environment_requires_48_byte_secret():
    with pytest.raises(ValidationError, match="48"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 40,
            CORS_ORIGINS=_PROD_LIKE_CORS,
            DATABASE_URL=_PROD_LIKE_DB_URL,
            REDIS_URL="redis://127.0.0.1:6379/0",
        )


def test_production_rejects_documents_example_secret_key():
    with pytest.raises(ValidationError, match="示例或默认"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            CORS_ORIGINS=_PROD_LIKE_CORS,
            DATABASE_URL=_PROD_LIKE_DB_URL,
            REDIS_URL="redis://127.0.0.1:6379/0",
        )


def test_production_rejects_unit_test_default_secret_key():
    with pytest.raises(ValidationError, match="示例或默认"):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY="unit-test-environment-default-secret-48b-min-ok!!",
            CORS_ORIGINS=_PROD_LIKE_CORS,
            DATABASE_URL=_PROD_LIKE_DB_URL,
            REDIS_URL="redis://127.0.0.1:6379/0",
        )


def test_production_accepts_48_byte_secret():
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a" * 48,
        CORS_ORIGINS=_PROD_LIKE_CORS,
        DATABASE_URL=_PROD_LIKE_DB_URL,
        REDIS_URL="redis://127.0.0.1:6379/0",
    )
    assert len(s.SECRET_KEY.get_secret_value().encode()) == 48


def test_secret_key_secretstr_repr_redacts():
    s = Settings(
        SECRET_KEY="b" * 48,
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/videodb",
        REDIS_URL="redis://127.0.0.1:6379/0",
    )
    r = repr(s.SECRET_KEY)
    assert "b" * 8 not in r
    assert "**********" in r or "SecretStr" in r


def test_access_token_expire_bounds():
    with pytest.raises(ValidationError):
        Settings(
            SECRET_KEY="a" * 32,
            ACCESS_TOKEN_EXPIRE_MINUTES=0,
            DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/videodb",
            REDIS_URL="redis://127.0.0.1:6379/0",
        )


def test_superuser_password_rejects_over_72_utf8_bytes():
    with pytest.raises(ValidationError, match="72"):
        Settings(
            SECRET_KEY="a" * 32,
            FIRST_SUPERUSER_PASSWORD="x" * 73,
            DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/videodb",
            REDIS_URL="redis://127.0.0.1:6379/0",
        )


def test_superuser_password_too_short():
    with pytest.raises(ValidationError, match="FIRST_SUPERUSER_PASSWORD"):
        Settings(
            SECRET_KEY="a" * 32,
            FIRST_SUPERUSER_PASSWORD="short",
            DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/videodb",
            REDIS_URL="redis://127.0.0.1:6379/0",
        )


def test_superuser_password_changeme_rejected_in_production():
    with pytest.raises(ValidationError, match="强密码"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 48,
            CORS_ORIGINS=_PROD_LIKE_CORS,
            FIRST_SUPERUSER_PASSWORD="changeme",
            DATABASE_URL=_PROD_LIKE_DB_URL,
            REDIS_URL="redis://127.0.0.1:6379/0",
        )


def test_docker_compose_default_superuser_password_ok_for_local():
    """与 docker-compose / .env.example 默认一致：local 下可用较长非弱口令。"""
    pw = default_first_superuser_password()
    s = Settings(
        ENVIRONMENT="local",
        SECRET_KEY="a" * 32,
        FIRST_SUPERUSER_PASSWORD=pw,
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/videodb",
        REDIS_URL="redis://127.0.0.1:6379/0",
    )
    assert s.FIRST_SUPERUSER_PASSWORD is not None
    assert s.FIRST_SUPERUSER_PASSWORD.get_secret_value() == pw


def test_superuser_password_secretstr_repr():
    s = Settings(
        SECRET_KEY="a" * 32,
        FIRST_SUPERUSER_PASSWORD="my-bootstrap-secret-8chars-min",
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/videodb",
        REDIS_URL="redis://127.0.0.1:6379/0",
    )
    assert s.FIRST_SUPERUSER_PASSWORD is not None
    r = repr(s.FIRST_SUPERUSER_PASSWORD)
    assert "my-bootstrap" not in r


def test_expose_internal_error_details_defaults_false():
    s = Settings(
        SECRET_KEY="a" * 32,
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/videodb",
        REDIS_URL="redis://127.0.0.1:6379/0",
    )
    assert s.EXPOSE_INTERNAL_ERROR_DETAILS is False


@pytest.mark.parametrize(
    "env,expected",
    [
        ("local", True),
        ("development", True),
        ("production", False),
        ("prod", False),
        ("staging", False),
        ("  Staging  ", False),
    ],
)
def test_expose_openapi_docs_by_environment(env: str, expected: bool):
    prod_like = env.strip().lower() in ("production", "prod", "staging")
    s = Settings(
        ENVIRONMENT=env,
        SECRET_KEY="a" * 48 if prod_like else "a" * 32,
        CORS_ORIGINS=_PROD_LIKE_CORS if prod_like else None,
        DATABASE_URL=_PROD_LIKE_DB_URL if prod_like else "postgresql+psycopg://postgres:postgres@localhost:5432/videodb",
        REDIS_URL="redis://127.0.0.1:6379/0",
    )
    assert s.expose_openapi_docs is expected


def test_expose_openapi_docs_explicit_override_staging_on():
    s = Settings(
        ENVIRONMENT="staging",
        EXPOSE_OPENAPI_DOCS=True,
        SECRET_KEY="a" * 48,
        CORS_ORIGINS=_PROD_LIKE_CORS,
        DATABASE_URL=_PROD_LIKE_DB_URL,
        REDIS_URL="redis://127.0.0.1:6379/0",
    )
    assert s.expose_openapi_docs is True


def test_expose_openapi_docs_explicit_override_local_off():
    s = Settings(
        ENVIRONMENT="local",
        EXPOSE_OPENAPI_DOCS=False,
        SECRET_KEY="a" * 32,
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/videodb",
        REDIS_URL="redis://127.0.0.1:6379/0",
    )
    assert s.expose_openapi_docs is False


def test_production_rejects_cors_wildcard():
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 48,
            CORS_ORIGINS=["*"],
            DATABASE_URL=_PROD_LIKE_DB_URL,
            REDIS_URL="redis://127.0.0.1:6379/0",
        )


def test_cors_origins_comma_string_parsed():
    s = Settings(
        SECRET_KEY="a" * 32,
        CORS_ORIGINS="http://a.example, http://b.example",
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/videodb",
        REDIS_URL="redis://127.0.0.1:6379/0",
    )
    assert s.CORS_ORIGINS == ["http://a.example", "http://b.example"]


def test_trending_weights_sum_must_be_positive():
    with pytest.raises(ValidationError, match="须大于 0"):
        Settings(
            SECRET_KEY="a" * 32,
            DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/videodb",
            REDIS_URL="redis://127.0.0.1:6379/0",
            VIDEO_TRENDING_WEIGHT_VIEWS=0,
            VIDEO_TRENDING_WEIGHT_LIKES=0,
            VIDEO_TRENDING_WEIGHT_FAVORITES=0,
        )


def test_turnstile_bypass_requires_node_env_test():
    with pytest.raises(ValidationError, match="TURNSTILE_BYPASS"):
        Settings(
            SECRET_KEY="a" * 32,
            DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/videodb",
            REDIS_URL="redis://127.0.0.1:6379/0",
            TURNSTILE_BYPASS=True,
            NODE_ENV="development",
        )


def test_turnstile_bypass_allowed_in_node_env_test():
    s = Settings(
        SECRET_KEY="a" * 32,
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/videodb",
        REDIS_URL="redis://127.0.0.1:6379/0",
        TURNSTILE_BYPASS=True,
        NODE_ENV="test",
    )
    assert s.TURNSTILE_BYPASS is True
    assert s.NODE_ENV == "test"


def test_turnstile_allowed_hostnames_comma_string_parsed():
    s = Settings(
        SECRET_KEY="a" * 32,
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/videodb",
        REDIS_URL="redis://127.0.0.1:6379/0",
        TURNSTILE_ALLOWED_HOSTNAMES="App.Example.com, admin.example.com ",
    )
    assert s.TURNSTILE_ALLOWED_HOSTNAMES == ["app.example.com", "admin.example.com"]


def test_security_hsts_max_age_default_zero():
    s = Settings(
        SECRET_KEY="a" * 32,
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/videodb",
        REDIS_URL="redis://127.0.0.1:6379/0",
    )
    assert s.SECURITY_HSTS_MAX_AGE == 0


def test_security_hsts_max_age_rejects_over_one_year():
    with pytest.raises(ValidationError):
        Settings(
            SECRET_KEY="a" * 32,
            DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/videodb",
            REDIS_URL="redis://127.0.0.1:6379/0",
            SECURITY_HSTS_MAX_AGE=366 * 24 * 3600,
        )

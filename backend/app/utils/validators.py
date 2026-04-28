import re
import uuid


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w\s-]", "", value)
    value = re.sub(r"[-\s]+", "-", value).strip("-")
    return value or str(uuid.uuid4())


def ensure_unique_slug(base: str, exists_checker) -> str:
    slug = slugify(base)[:200]
    candidate = slug
    n = 1
    while exists_checker(candidate):
        suffix = f"-{n}"
        candidate = (slug[: 200 - len(suffix)] + suffix) if len(slug) + len(suffix) > 200 else slug + suffix
        n += 1
    return candidate

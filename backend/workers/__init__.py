"""Background workers module using ARQ (async Redis queue)."""

from arq import create_pool
from arq.connections import RedisSettings

from app.config import get_settings

settings = get_settings()


def get_redis_settings() -> RedisSettings:
    """Get Redis connection settings from config."""
    # Parse redis URL (redis://localhost:6379)
    redis_url = settings.redis_url
    if redis_url.startswith("redis://"):
        redis_url = redis_url[8:]

    host_port = redis_url.split(":")
    host = host_port[0] if host_port else "localhost"
    port = int(host_port[1]) if len(host_port) > 1 else 6379

    return RedisSettings(host=host, port=port)


async def get_redis_pool():
    """Create and return an ARQ Redis pool."""
    return await create_pool(get_redis_settings())

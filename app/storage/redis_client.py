"""Redis客户端 — 可选依赖，连接失败自动降级"""

import redis.asyncio as redis
from typing import Optional

from config import settings


class RedisClient:
    _instance = None
    _client = None
    _available: bool = False  # 仅当成功连接后才为 True

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def available(self) -> bool:
        return self._available

    async def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            self._client = redis.Redis(
                host=settings.redis_host, port=settings.redis_port,
                db=settings.redis_db, decode_responses=True, socket_timeout=5
            )
            await self._client.ping()
            self._available = True
        except Exception as e:
            self._client = None
            self._available = False
            print(f"  Redis 连接失败 ({e})，会话持久化已降级")
        return self._client

    async def get(self, key: str) -> Optional[str]:
        if not self._available:
            return None
        try:
            client = await self._get_client()
            return await client.get(key) if client else None
        except Exception:
            return None

    async def set(self, key: str, value: str, ttl: int = None):
        if not self._available:
            return
        try:
            client = await self._get_client()
            if not client:
                return
            if ttl:
                await client.setex(key, ttl, value)
            else:
                await client.set(key, value)
        except Exception:
            pass

    async def delete(self, key: str):
        if not self._available:
            return
        try:
            client = await self._get_client()
            if client:
                await client.delete(key)
        except Exception:
            pass

    async def exists(self, key: str) -> bool:
        if not self._available:
            return False
        try:
            client = await self._get_client()
            return await client.exists(key) > 0 if client else False
        except Exception:
            return False

    async def keys(self, pattern: str) -> list:
        if not self._available:
            return []
        try:
            client = await self._get_client()
            return await client.keys(pattern) if client else []
        except Exception:
            return []

    async def close(self):
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None
        self._available = False


redis_client = RedisClient()

"""Rate limiting, backed by the same Redis as the cache.

Why Redis and not the in-memory backend: in-memory counters live inside one
process. Run four uvicorn workers and the effective limit becomes 4x whatever
you configured, because each worker counts on its own. Redis keeps one counter
for all of them.
"""

from __future__ import annotations

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def client_key(request: Request) -> str:
    """Limit per authenticated user when we know who they are, per IP otherwise.

    Keying purely on IP punishes everyone behind one NAT and does nothing
    against a logged-in client rotating addresses.

    Note: behind a reverse proxy get_remote_address returns the proxy's IP,
    so every anonymous caller shares one bucket. Fix that at deploy time by
    running uvicorn with --proxy-headers and a trusted proxy list, not by
    reading X-Forwarded-For here (it is trivially spoofable).
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return get_remote_address(request)


limiter = Limiter(
    key_func=client_key,
    storage_uri=REDIS_URL,
    default_limits=["200/minute"],
)

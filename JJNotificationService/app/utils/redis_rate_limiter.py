# app/utils/redis_rate_limiter.py
import redis
import logging

logger = logging.getLogger(__name__)

# Redis client (adjust host/port/password as needed)
redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

# Cooldowns in seconds
RATE_LIMITS = {
    "CLIENT_UP": 300,    # 5 minutes
    "ADMIN_DOWN": 600,   # 10 minutes
    "ISP_UP": 600,       # 10 minutes
}


def allow_send(client_id: int, event_key: str) -> bool:
    """
    Returns True if notification is allowed based on Redis TTL.
    Uses SET NX to atomically enforce cooldown.
    """
    key = f"notify:{client_id}:{event_key}"
    ttl = RATE_LIMITS.get(event_key, 300)

    # SET NX with TTL; returns True if key did not exist
    allowed = redis_client.set(key, "1", nx=True, ex=ttl)
    if not allowed:
        logger.debug(f"Rate-limited: client_id={client_id} event={event_key}")
    return allowed is not None

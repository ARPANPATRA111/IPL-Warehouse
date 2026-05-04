from collections import OrderedDict
from collections.abc import Callable
from functools import wraps
from threading import Lock
from time import monotonic
from typing import Any, TypeVar

from config.settings import get_settings

ReturnType = TypeVar("ReturnType")


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze(item) for item in value))
    return value


def ttl_cache(
    max_entries: int = 128,
) -> Callable[[Callable[..., ReturnType]], Callable[..., ReturnType]]:

    def decorator(func: Callable[..., ReturnType]) -> Callable[..., ReturnType]:
        cache: "OrderedDict[Any, tuple[float, ReturnType]]" = OrderedDict()
        lock = Lock()

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> ReturnType:
            ttl_seconds = max(get_settings().api_cache_ttl_seconds, 0)
            if ttl_seconds == 0:
                return func(*args, **kwargs)

            key = (_freeze(args), _freeze(kwargs))
            now = monotonic()

            with lock:
                cached = cache.get(key)
                if cached is not None:
                    expires_at, value = cached
                    if expires_at > now:
                        cache.move_to_end(key)
                        return value
                    cache.pop(key, None)

            value = func(*args, **kwargs)

            with lock:
                cache[key] = (now + ttl_seconds, value)
                cache.move_to_end(key)
                while len(cache) > max_entries:
                    cache.popitem(last=False)

            return value

        def cache_clear() -> None:
            with lock:
                cache.clear()

        wrapper.cache_clear = cache_clear

        return wrapper

    return decorator

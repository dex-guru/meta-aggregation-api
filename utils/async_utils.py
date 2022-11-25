import asyncio
from functools import wraps, partial
from typing import Awaitable, Union, Callable


def async_from_sync(func) -> Union[Awaitable, Callable]:
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)

    return run

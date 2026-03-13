"""Bridge asyncio coroutines into gevent/synchronous context.

Runs a single asyncio event loop on a real OS thread (via gevent's
threadpool, which is NOT monkey-patched). Locust greenlets submit
coroutines to this loop and block until the result is ready.
"""

import asyncio
import threading

_loop = None
_started = False
_lock = threading.Lock()


def _run_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


def _ensure_loop():
    global _loop, _started
    if _started:
        return _loop
    with _lock:
        if _started:
            return _loop
        _loop = asyncio.new_event_loop()
        try:
            import gevent.threadpool
            pool = gevent.threadpool.ThreadPool(1)
            pool.spawn(_run_loop, _loop)
        except ImportError:
            # Not running under gevent — use a regular thread
            t = threading.Thread(target=_run_loop, args=(_loop,), daemon=True)
            t.start()
        _started = True
    return _loop


def run_async(coro):
    """Schedule a coroutine on the background asyncio loop and block until done."""
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


def create_on_loop(factory, *args, **kwargs):
    """Create an object on the asyncio loop thread.

    Use this for grpclib Channels which bind to the event loop on creation.
    """
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(
        _create_async(factory, *args, **kwargs), loop
    )
    return future.result()


async def _create_async(factory, *args, **kwargs):
    return factory(*args, **kwargs)

"""
Async runtime bridge for the Flask backend.

The agents are async (LangGraph + MCP over streamable HTTP) while Flask is
synchronous. Instead of spinning up a fresh event loop per request - which
would tear down the MCP sessions every time - we keep one long-lived event
loop on a background thread and submit coroutines to it.
"""

from __future__ import annotations

import asyncio
import queue
import threading
from typing import Any, AsyncIterator, Callable, Coroutine, Iterator, TypeVar

T = TypeVar("T")

_SENTINEL = object()


class AsyncRuntime:
    """Owns a background event loop shared by every request."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="agent-event-loop",
            daemon=True,
        )
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return self._loop

    def run(self, coro: Coroutine[Any, Any, T], timeout: float | None = None) -> T:
        """Run a coroutine on the background loop and wait for its result."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise

    def iterate(
        self,
        make_agen: Callable[[], AsyncIterator[Any]],
        timeout: float | None = None,
    ) -> Iterator[Any]:
        """
        Drain an async generator from synchronous code.

        The generator runs on the background loop and pushes items into a
        thread-safe queue that the calling (Flask) thread consumes, which is
        what lets us stream agent updates straight into an SSE response.
        """
        items: queue.Queue[Any] = queue.Queue(maxsize=64)

        async def pump() -> None:
            try:
                async for item in make_agen():
                    await asyncio.to_thread(items.put, item)
            except Exception as exc:  # surfaced to the consumer below
                await asyncio.to_thread(items.put, exc)
            finally:
                await asyncio.to_thread(items.put, _SENTINEL)

        future = asyncio.run_coroutine_threadsafe(pump(), self._loop)
        try:
            while True:
                item = items.get(timeout=timeout)
                if item is _SENTINEL:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item
        finally:
            if not future.done():
                future.cancel()

    def shutdown(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)

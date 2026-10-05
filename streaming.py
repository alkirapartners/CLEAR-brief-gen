"""Run a blocking job in a thread and report it as a server-sent-event stream.

The job owns its own side effects (it saves the brief itself), so a client
that disconnects mid-stream changes nothing: the thread runs to completion.
"""

import asyncio
import json
import logging
import threading
from typing import AsyncIterator, Callable

from errors import GENERIC_ERROR, UserFacingError

logger = logging.getLogger(__name__)

PhaseCallback = Callable[[str], None]
Work = Callable[[PhaseCallback], dict]

HEARTBEAT = ": ping\n\n"
# generate.py reports "done" itself; the stream's own done event carries the id.
_INTERNAL_PHASES = frozenset({"done"})
_TERMINAL_TYPES = frozenset({"done", "error"})


def _frame(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


async def stream_job(work: Work, heartbeat_seconds: float = 15.0) -> AsyncIterator[str]:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict] = asyncio.Queue()

    def emit(event: dict) -> None:
        try:
            loop.call_soon_threadsafe(queue.put_nowait, event)
        except RuntimeError:
            # The loop is gone (client left and the server is shutting down).
            # The job's own work is already done or still running; nothing to tell.
            pass

    def on_phase(phase: str) -> None:
        if phase not in _INTERNAL_PHASES:
            emit({"type": "phase", "phase": phase})

    def runner() -> None:
        try:
            emit(work(on_phase))
        except UserFacingError as exc:
            emit({"type": "error", "message": str(exc)})
        except Exception:
            logger.exception("Brief job failed")
            emit({"type": "error", "message": GENERIC_ERROR})

    threading.Thread(target=runner, name="brief-job", daemon=True).start()

    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
        except asyncio.TimeoutError:
            yield HEARTBEAT
            continue
        yield _frame(event)
        if event.get("type") in _TERMINAL_TYPES:
            return

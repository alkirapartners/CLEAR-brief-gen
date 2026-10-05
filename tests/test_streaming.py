import asyncio
import json
import threading
import time

from errors import GENERIC_ERROR, UserFacingError
from streaming import stream_job


def _collect(work, heartbeat_seconds=5.0):
    async def run():
        return [chunk async for chunk in stream_job(work, heartbeat_seconds)]
    return asyncio.run(run())


def _data(chunks):
    return [json.loads(c[len("data: "):]) for c in chunks if c.startswith("data: ")]


def test_phases_then_done_and_the_done_phase_is_not_forwarded():
    def work(on_phase):
        for phase in ("init", "research", "done"):
            on_phase(phase)
        return {"type": "done", "briefId": "b1", "reusedFrom": None}

    assert _data(_collect(work)) == [
        {"type": "phase", "phase": "init"},
        {"type": "phase", "phase": "research"},
        {"type": "done", "briefId": "b1", "reusedFrom": None},
    ]


def test_every_chunk_is_a_complete_sse_frame():
    chunks = _collect(lambda on_phase: {"type": "done", "briefId": "b1", "reusedFrom": None})
    assert all(chunk.endswith("\n\n") for chunk in chunks)


def test_user_facing_errors_keep_their_message():
    def work(on_phase):
        raise UserFacingError("Shown to the partner")

    assert _data(_collect(work)) == [{"type": "error", "message": "Shown to the partner"}]


def test_unexpected_errors_are_replaced_with_the_generic_message():
    def work(on_phase):
        raise RuntimeError("secret internals at /var/www")

    assert _data(_collect(work)) == [{"type": "error", "message": GENERIC_ERROR}]


def test_heartbeats_fill_the_silence():
    def work(on_phase):
        time.sleep(0.25)
        return {"type": "done", "briefId": "b1", "reusedFrom": None}

    chunks = _collect(work, heartbeat_seconds=0.05)
    assert ": ping\n\n" in chunks
    assert _data(chunks)[-1]["type"] == "done"


def test_work_finishes_after_consumer_stops():
    release = threading.Event()
    finished = threading.Event()

    def work(on_phase):
        on_phase("init")
        release.wait(2)
        finished.set()
        return {"type": "done", "briefId": "b1", "reusedFrom": None}

    async def scenario():
        stream = stream_job(work, heartbeat_seconds=5)
        first = await stream.__anext__()
        assert '"init"' in first
        await stream.aclose()

    asyncio.run(scenario())
    release.set()
    assert finished.wait(2), "the job must run to completion after the client leaves"


def test_work_runs_even_if_the_stream_is_never_read():
    """A client that drops before the first byte must not leave the job unstarted.

    The job releases the per-user in-flight guard when it finishes, so a job
    that never starts would lock that user out until the process restarts.
    """
    finished = threading.Event()

    def work(on_phase):
        finished.set()
        return {"type": "done", "briefId": "b1", "reusedFrom": None}

    async def scenario():
        stream_job(work, heartbeat_seconds=5)  # created, never iterated
        await asyncio.sleep(0)

    asyncio.run(scenario())
    assert finished.wait(2), "the job must start when the stream is created"

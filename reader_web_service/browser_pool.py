"""Persistent Camoufox browser pool: a bounded queue feeds dedicated worker threads.

Each worker thread owns one Camoufox browser for its whole life and reuses it
across jobs; every job gets a fresh page via ``read_with_browser``. Job
results are bridged back to the event loop with futures, so async callers
await results while the synchronous browser stays pinned to its owning
thread (Camoufox is synchronous and must not cross threads).
"""

import asyncio
import os
import queue
import threading

import sentry_sdk
from camoufox.sync_api import Camoufox
from loguru import logger as _log

from reader_web_service.read_by_firefox import (
    _OPERATIONAL_EXCEPTIONS,
    MAX_ATTEMPTS,
    _build_camoufox_kwargs,
    read_with_browser,
)

BROWSER_QUEUE_SIZE = 3
BROWSER_QUEUE_TIMEOUT_SECONDS = 30
RECYCLE_AFTER_JOBS = 200


class BrowserBusy(Exception):
    """The pool is saturated: the waiting queue is full or timed out."""


def _validated_size(size):
    """Resolve the worker count: explicit int or ``BROWSER_POOL_SIZE`` (default 3).

    Non-integer, zero, and negative sizes are rejected with a clear ValueError.
    """
    if size is None:
        raw = os.getenv('BROWSER_POOL_SIZE', '3')
        try:
            size = int(raw)
        except ValueError:
            raise ValueError(f'BROWSER_POOL_SIZE must be an integer, got {raw!r}') from None
    if not isinstance(size, int) or size < 1:
        raise ValueError(f'BrowserPool size must be a positive integer, got {size!r}')
    return size


class _Job:
    """One page operation, bridged between a worker thread and the event loop.

    ``_state`` moves queued -> started -> done under ``_lock``, or queued ->
    abandoned when the caller gives up first. That lock makes the queue
    timeout exact: a job can only be abandoned while no worker owns it, and
    once started it runs to completion on the worker.
    """

    def __init__(self, url, reader, loop):
        self.url = url
        self.reader = reader
        self._loop = loop
        self._lock = threading.Lock()
        self._state = 'queued'
        self.started = loop.create_future()  # resolved once a worker owns the job
        self.done = loop.create_future()  # the operation's result or error

    def try_start(self):
        """Worker claims the job; False if the caller abandoned it while queued."""
        with self._lock:
            if self._state != 'queued':
                return False
            self._state = 'started'
        self._settle(self.started, None)
        return True

    def abandon(self):
        """Caller stops waiting; True when the job will be skipped."""
        with self._lock:
            if self._state == 'queued':
                self._state = 'abandoned'
                return True
            return False

    def resolve(self, value):
        self._settle(self.done, value)

    def reject(self, error):
        self._settle(self.done, error, as_error=True)

    def _settle(self, future, value, as_error=False):
        def apply():
            if not future.done():  # the caller may have been cancelled meanwhile
                if as_error:
                    future.set_exception(value)
                else:
                    future.set_result(value)

        try:
            self._loop.call_soon_threadsafe(apply)
        except RuntimeError:
            pass  # event loop already closed (shutdown race); nobody is waiting


class BrowserPool:
    """Bounded pool of persistent Camoufox browsers, one per dedicated worker thread."""

    def __init__(self, size=None):
        self.size = _validated_size(size)
        # Workers take a job out of the queue the moment they start it, so
        # maxsize bounds only waiting (not-yet-started) jobs.
        self._queue = queue.Queue(maxsize=BROWSER_QUEUE_SIZE)
        self._workers = []
        self._enqueue_lock = threading.Lock()  # makes "pool closed" atomic with enqueue
        self._closed = False
        self._local = threading.local()  # browser state, private to each worker thread

    async def start(self):
        if self._workers:
            return
        for _ in range(self.size):
            worker = threading.Thread(target=self._worker_loop, daemon=True)
            worker.start()
            self._workers.append(worker)

    async def run(self, url, reader=True):
        loop = asyncio.get_running_loop()
        job = _Job(url, reader, loop)
        with self._enqueue_lock:
            if self._closed:
                raise RuntimeError('BrowserPool is shut down')
            try:
                self._queue.put_nowait(job)
            except queue.Full:
                raise BrowserBusy('browser pool queue is full') from None
        try:
            await asyncio.wait_for(job.started, BROWSER_QUEUE_TIMEOUT_SECONDS)
        except TimeoutError:
            # Only a job no worker started may time out. abandon() loses the
            # race exactly when a worker already owns the job — then we still
            # wait for its result: processing time is not covered here.
            if job.abandon():
                raise BrowserBusy(f'no worker started the job within {BROWSER_QUEUE_TIMEOUT_SECONDS}s') from None
        except asyncio.CancelledError:
            job.abandon()  # skipped if still queued; a started job keeps running
            raise
        return await job.done

    async def shutdown(self):
        """Stop accepting work, drain accepted jobs, close each browser on its
        owning worker thread, and join all workers."""
        with self._enqueue_lock:
            if self._closed:
                return
            self._closed = True
            # Sentinels sit behind every accepted job (FIFO), so each worker
            # drains the queue, then closes its own browser and exits.
            for _ in self._workers:
                self._queue.put(None)
        if self._workers:
            await asyncio.to_thread(self._join_workers)

    def _join_workers(self):
        for worker in self._workers:
            worker.join()

    def _worker_loop(self):
        local = self._local
        local.cm = None
        local.browser = None
        local.jobs = 0
        while True:
            job = self._queue.get()
            if job is None:  # shutdown sentinel: close this thread's browser
                self._discard_browser()
                return
            if job.try_start():
                self._handle(job)

    def _handle(self, job):
        try:
            result = self._execute(job)
            local = self._local
            local.jobs += 1
            if local.jobs >= RECYCLE_AFTER_JOBS:
                self._discard_browser()  # limit long-lived browser state
            job.resolve(result)
        except BaseException as e:  # deliver anything unexpected; keep this worker alive
            job.reject(e)

    def _execute(self, job):
        local = self._local
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                if local.browser is None:
                    # The proxy is chosen here and stays fixed for this
                    # browser's whole life (ruling: rotation per launch, not
                    # per request).
                    local.cm = Camoufox(**_build_camoufox_kwargs())
                    local.browser = local.cm.__enter__()
                return read_with_browser(local.browser, job.url, reader=job.reader)
            except _OPERATIONAL_EXCEPTIONS as e:
                _log.debug(f'operational browser failure (attempt {attempt}/{MAX_ATTEMPTS}): {e}')
                self._discard_browser()  # close and replace before the retry
            except Exception as e:
                sentry_sdk.capture_exception(e)
                self._discard_browser()
                return None
        return None

    def _discard_browser(self):
        """Close this thread's browser (if any) and reset its per-browser state."""
        local = self._local
        local.browser = None
        local.jobs = 0
        cm = local.cm
        local.cm = None
        if cm is not None:
            try:
                cm.__exit__(None, None, None)
            except Exception as e:
                _log.debug(f'browser close failed: {e}')

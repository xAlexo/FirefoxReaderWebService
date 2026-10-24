"""Tests for the persistent browser pool — fake browsers only, no real launch or network.

Fake-Camoufox tests run the REAL read_with_browser against mock browsers:
R1: one worker browser is reused across three requests.
R2: every request gets its own fresh page, closed after use.
R3: an operational failure retries on a replacement browser (old one closed).
R4: exhausted operational retries return None with no Sentry capture.
R5: an unexpected exception is captured once, returns None, discards the browser.
R6: a browser is recycled after 200 completed jobs (None results count).

Fake-worker tests patch read_with_browser for controlled blocking:
W1: the queue holds three waiting jobs; a fourth raises BrowserBusy immediately.
W2: two concurrent jobs run on distinct worker browsers on distinct threads.
W3: a queued job no worker starts within the timeout raises BrowserBusy and
    is then skipped.
W4: time spent processing a started job is not covered by the queue timeout.
W5: a queued job cancelled before start is skipped.
W6: cancelling an active job leaves the worker and its browser intact.
W7: shutdown drains accepted jobs and closes browsers on their owner threads.
W8: after shutdown the pool accepts no new work; shutdown is idempotent.
W9: shutdown keeps the event loop responsive while the queue is full, then
    still drains accepted jobs and closes browsers on owner threads.

S: pool size validation — explicit size, BROWSER_POOL_SIZE override, clear
   ValueError for non-integer, zero, and negative sizes; constants pinned.
"""

import asyncio
import os
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from playwright.sync_api import Error as PlaywrightError

from reader_web_service import browser_pool
from reader_web_service.browser_pool import BrowserBusy, BrowserPool


def make_page(title, content='<p>body</p>', url='https://example.com'):
    """A mock page the real read_with_browser can drive without network."""
    page = MagicMock()
    page.url = url
    page.title.return_value = title
    page.inner_html.return_value = content
    return page


def _page_with_goto_error(error, index):
    page = make_page(f'Page {index}')
    page.goto.side_effect = error
    return page


class FakeBrowser:
    """Hands out a fresh scripted mock page per new_page() call."""

    def __init__(self, page_factory=None):
        self.page_factory = page_factory or (lambda i: make_page(f'Page {i}'))
        self.pages = []

    def new_page(self):
        page = self.page_factory(len(self.pages))
        self.pages.append(page)
        return page


class FakeLaunch:
    """One Camoufox() context manager; records which thread entered/exited it."""

    def __init__(self, browser):
        self.browser = browser
        self.enter_count = 0
        self.exit_count = 0
        self.enter_thread = None
        self.exit_thread = None

    def __enter__(self):
        self.enter_count += 1
        self.enter_thread = threading.get_ident()
        return self.browser

    def __exit__(self, *exc):
        self.exit_count += 1
        self.exit_thread = threading.get_ident()
        return False

    @property
    def exited(self):
        return self.exit_count > 0


class FakeCamoufoxFactory:
    """Patch target for browser_pool.Camoufox; enters scripted browsers in order."""

    def __init__(self):
        self.browsers = []  # scripted per launch; a fresh FakeBrowser when empty
        self.launches = []
        self.kwargs = []

    def __call__(self, **kwargs):
        self.kwargs.append(kwargs)
        browser = self.browsers.pop(0) if self.browsers else FakeBrowser()
        launch = FakeLaunch(browser)
        self.launches.append(launch)
        return launch


class PoolTestCase(unittest.IsolatedAsyncioTestCase):
    """Shared setup: fake Camoufox, stubbed Sentry, a pool that always shuts down."""

    async def asyncSetUp(self):
        self.camoufox = FakeCamoufoxFactory()
        self.enterContext(patch.object(browser_pool, 'Camoufox', self.camoufox))
        self.sentry = self.enterContext(patch.object(browser_pool, 'sentry_sdk'))
        self.pool = None

    async def asyncTearDown(self):
        if self.pool is not None:
            await self.pool.shutdown()

    async def started_pool(self, size=1):
        self.pool = BrowserPool(size=size)
        await self.pool.start()
        return self.pool

    def install_op(self, op):
        """Replace read_with_browser inside the pool with a controlled fake."""
        self.enterContext(patch.object(browser_pool, 'read_with_browser', op))


class FakeCamoufoxPoolTests(PoolTestCase):
    """Real read_with_browser against fake browsers: reuse, pages, retry, Sentry, recycle."""

    async def test_one_browser_reused_across_requests(self):
        pool = await self.started_pool(size=1)

        results = [await pool.run('https://example.com', reader=False) for _ in range(3)]

        self.assertEqual([r['title'] for r in results], ['Page 0', 'Page 1', 'Page 2'])
        self.assertEqual(len(self.camoufox.launches), 1, 'three requests must reuse one browser')
        launch = self.camoufox.launches[0]
        self.assertEqual(len(launch.browser.pages), 3)
        self.assertFalse(launch.exited, 'a healthy browser must stay open for the next request')
        # launch kwargs still flow through the existing Camoufox kwargs helper
        self.assertTrue(self.camoufox.kwargs[0].get('headless'))
        self.assertFalse(self.sentry.capture_exception.called)

    async def test_every_request_gets_a_fresh_closed_page(self):
        pool = await self.started_pool(size=1)

        await pool.run('https://example.com', reader=False)
        await pool.run('https://example.com', reader=False)

        pages = self.camoufox.launches[0].browser.pages
        self.assertEqual(len(pages), 2)
        self.assertIsNot(pages[0], pages[1], 'each request must use its own page')
        for page in pages:
            page.close.assert_called_once()

    async def test_operational_failure_retries_on_replacement_browser(self):
        bad = FakeBrowser(page_factory=lambda i: _page_with_goto_error(PlaywrightError('Target closed'), i))
        good = FakeBrowser()
        self.camoufox.browsers += [bad, good]
        pool = await self.started_pool(size=1)

        result = await pool.run('https://example.com', reader=False)

        self.assertEqual(result['title'], 'Page 0')
        self.assertEqual(len(self.camoufox.launches), 2, 'the retry must launch a replacement browser')
        self.assertTrue(self.camoufox.launches[0].exited, 'the failed browser must be closed before the retry')
        self.assertFalse(self.camoufox.launches[1].exited)
        bad.pages[0].close.assert_called_once()
        self.assertFalse(self.sentry.capture_exception.called, 'operational failures must not hit Sentry')

    async def test_exhausted_operational_retries_return_none_and_pool_stays_healthy(self):
        for _ in range(3):
            self.camoufox.browsers.append(
                FakeBrowser(page_factory=lambda i: _page_with_goto_error(PlaywrightError('Target closed'), i))
            )
        pool = await self.started_pool(size=1)

        self.assertIsNone(await pool.run('https://example.com', reader=False))

        self.assertEqual(len(self.camoufox.launches), 3, 'one fresh browser per attempt')
        for launch in self.camoufox.launches:
            self.assertTrue(launch.exited, 'every failed attempt must close its browser')
            self.assertEqual(launch.enter_thread, launch.exit_thread)
            for page in launch.browser.pages:
                page.close.assert_called_once()
        self.assertFalse(self.sentry.capture_exception.called)

        result = await pool.run('https://example.com', reader=False)
        self.assertEqual(result['title'], 'Page 0', 'the worker must stay healthy after exhausted retries')
        self.assertEqual(len(self.camoufox.launches), 4)

    async def test_unexpected_exception_captured_once_and_browser_discarded(self):
        bad = FakeBrowser(page_factory=lambda i: _page_with_goto_error(RuntimeError('genuinely unexpected'), i))
        good = FakeBrowser()
        self.camoufox.browsers += [bad, good]
        pool = await self.started_pool(size=1)

        self.assertIsNone(await pool.run('https://example.com', reader=False))

        self.assertEqual(self.sentry.capture_exception.call_count, 1, 'unexpected errors are captured exactly once')
        self.assertTrue(self.camoufox.launches[0].exited, 'the poisoned browser must be discarded')

        result = await pool.run('https://example.com', reader=False)
        self.assertEqual(result['title'], 'Page 0', 'the next job must get a fresh browser')
        self.assertEqual(len(self.camoufox.launches), 2)
        self.assertEqual(self.sentry.capture_exception.call_count, 1, 'no retry for unexpected errors')

    async def test_browser_recycled_after_200_completed_jobs(self):
        def page_for(i):
            if i == 36:  # job 37 parses no article -> returns None, still a completed job
                page = make_page(f'Page {i}')
                page.evaluate.return_value = None
                return page
            return make_page(f'Page {i}')

        self.camoufox.browsers.append(FakeBrowser(page_factory=page_for))
        pool = await self.started_pool(size=1)

        for i in range(200):
            if i == 36:
                self.assertIsNone(await pool.run('https://example.com', reader=True))
            else:
                self.assertIsNotNone(await pool.run('https://example.com', reader=False))

        first = self.camoufox.launches[0]
        self.assertTrue(first.exited, 'the browser must be recycled after its 200th completed job')
        self.assertEqual(len(first.browser.pages), 200)
        self.assertEqual(len(self.camoufox.launches), 1, 'the replacement launches lazily on the next job')

        result = await pool.run('https://example.com', reader=False)
        self.assertEqual(result['title'], 'Page 0')
        self.assertEqual(len(self.camoufox.launches), 2, 'a recycled browser is replaced on the next job')


class WorkerPoolTests(PoolTestCase):
    """Patched read_with_browser: queue bounds, timeout, cancellation, shutdown."""

    async def test_queue_holds_three_waiting_jobs_then_busy(self):
        calls = []
        started = threading.Event()
        release = threading.Event()

        def op(browser, url, reader=True):
            calls.append(url)
            started.set()
            release.wait(2)
            return {'title': url, 'content': 'x'}

        self.install_op(op)
        pool = await self.started_pool(size=1)
        first = asyncio.create_task(pool.run('first'))
        self.assertTrue(await asyncio.to_thread(started.wait, 2), 'the worker must pick up the first job')

        queued = [asyncio.create_task(pool.run(f'q{i}')) for i in range(3)]
        await asyncio.sleep(0.05)  # let the queued jobs park on the start signal

        with self.assertRaises(BrowserBusy):
            await asyncio.wait_for(pool.run('overflow'), timeout=5)

        release.set()
        results = await asyncio.wait_for(asyncio.gather(first, *queued), timeout=5)
        self.assertEqual([r['title'] for r in results], ['first', 'q0', 'q1', 'q2'])
        self.assertEqual(calls, ['first', 'q0', 'q1', 'q2'])
        self.assertEqual(len(self.camoufox.launches), 1, 'all four jobs share one worker browser')

    async def test_concurrent_jobs_run_on_distinct_worker_browsers(self):
        calls = []
        both_inside = threading.Event()

        def op(browser, url, reader=True):
            calls.append((url, browser))
            if len(calls) == 2:
                both_inside.set()
            both_inside.wait(2)
            return {'title': url, 'content': 'x'}

        self.install_op(op)
        pool = await self.started_pool(size=2)
        tasks = [asyncio.create_task(pool.run(u)) for u in ('u1', 'u2')]

        self.assertTrue(await asyncio.to_thread(both_inside.wait, 2), 'both workers must be inside their jobs')

        results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=5)
        self.assertEqual([r['title'] for r in results], ['u1', 'u2'])
        self.assertEqual(len(self.camoufox.launches), 2, 'each worker must own its own browser')
        self.assertEqual(
            {b for _, b in calls},
            {launch.browser for launch in self.camoufox.launches},
            'each job must run on its owning worker browser',
        )
        threads = {launch.enter_thread for launch in self.camoufox.launches}
        self.assertEqual(len(threads), 2, 'each browser must be entered on its own worker thread')
        self.assertNotIn(threading.get_ident(), threads)

    async def test_queued_job_times_out_and_is_skipped(self):
        self.enterContext(patch.object(browser_pool, 'BROWSER_QUEUE_TIMEOUT_SECONDS', 0.1))
        calls = []
        started = threading.Event()
        release = threading.Event()

        def op(browser, url, reader=True):
            calls.append(url)
            started.set()
            release.wait(2)
            return {'title': url, 'content': 'x'}

        self.install_op(op)
        pool = await self.started_pool(size=1)
        first = asyncio.create_task(pool.run('first'))
        self.assertTrue(await asyncio.to_thread(started.wait, 2))

        late = asyncio.create_task(pool.run('late'))
        with self.assertRaises(BrowserBusy):
            await late

        release.set()
        await first
        result = await pool.run('after')
        self.assertEqual(result['title'], 'after')
        self.assertEqual(calls, ['first', 'after'], 'the timed-out job must be skipped, not run')

    async def test_queue_timeout_does_not_cover_processing_time(self):
        self.enterContext(patch.object(browser_pool, 'BROWSER_QUEUE_TIMEOUT_SECONDS', 0.3))
        entered = threading.Event()
        release = threading.Event()

        def op(browser, url, reader=True):
            entered.set()
            release.wait(2)
            return {'title': url, 'content': 'x'}

        self.install_op(op)
        pool = await self.started_pool(size=1)
        task = asyncio.create_task(pool.run('slow'))
        self.assertTrue(await asyncio.to_thread(entered.wait, 2), 'the job must start first')

        await asyncio.sleep(0.5)  # processing longer than the patched queue timeout
        self.assertFalse(task.done(), 'a started job is not subject to the queue timeout')

        release.set()
        result = await asyncio.wait_for(task, timeout=5)
        self.assertEqual(result['title'], 'slow')

    async def test_cancelled_queued_job_is_skipped(self):
        calls = []
        started = threading.Event()
        release = threading.Event()

        def op(browser, url, reader=True):
            calls.append(url)
            started.set()
            release.wait(2)
            return {'title': url, 'content': 'x'}

        self.install_op(op)
        pool = await self.started_pool(size=1)
        first = asyncio.create_task(pool.run('first'))
        self.assertTrue(await asyncio.to_thread(started.wait, 2))

        late = asyncio.create_task(pool.run('late'))
        await asyncio.sleep(0.05)  # 'late' is parked waiting for a worker
        late.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await late

        release.set()
        await first
        result = await pool.run('after')
        self.assertEqual(result['title'], 'after')
        self.assertEqual(calls, ['first', 'after'], 'the cancelled job must be skipped, not run')

    async def test_cancelling_active_job_leaves_worker_and_browser_intact(self):
        calls = []
        entered = threading.Event()
        release = threading.Event()
        finished = threading.Event()

        def op(browser, url, reader=True):
            calls.append(url)
            entered.set()
            release.wait(2)
            finished.set()  # proves the worker ran the operation to its end
            return {'title': url, 'content': 'x'}

        self.install_op(op)
        pool = await self.started_pool(size=1)
        active = asyncio.create_task(pool.run('active'))
        self.assertTrue(await asyncio.to_thread(entered.wait, 2), 'the job must have started on the worker')

        active.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await active
        self.assertFalse(finished.is_set(), 'cancellation must not interrupt the synchronous operation')

        release.set()
        self.assertTrue(await asyncio.to_thread(finished.wait, 2), 'the worker must finish the operation and cleanup')
        self.assertFalse(self.sentry.capture_exception.called)

        result = await pool.run('next')
        self.assertEqual(result['title'], 'next')
        self.assertEqual(len(self.camoufox.launches), 1, 'a cancelled active job must not discard its browser')
        self.assertEqual(calls, ['active', 'next'])

    async def test_shutdown_drains_jobs_and_closes_browsers_on_owner_threads(self):
        calls = []
        two_inside = threading.Event()
        release = threading.Event()

        def op(browser, url, reader=True):
            calls.append(url)
            if len(calls) == 2:
                two_inside.set()
            release.wait(2)
            return {'title': url, 'content': 'x'}

        self.install_op(op)
        pool = await self.started_pool(size=2)
        tasks = [asyncio.create_task(pool.run(f'j{i}')) for i in range(3)]  # 2 running, 1 queued
        self.assertTrue(await asyncio.to_thread(two_inside.wait, 2))

        stopping = asyncio.create_task(pool.shutdown())
        await asyncio.sleep(0.05)  # the gate is closed; workers still hold their jobs
        self.assertFalse(stopping.done(), 'shutdown must wait for accepted work')

        release.set()
        await asyncio.wait_for(stopping, timeout=5)
        results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=5)
        self.assertEqual(
            [r['title'] for r in results], ['j0', 'j1', 'j2'], 'accepted jobs must be drained, not dropped'
        )

        self.assertEqual(len(self.camoufox.launches), 2)
        for launch in self.camoufox.launches:
            self.assertEqual((launch.enter_count, launch.exit_count), (1, 1))
            self.assertEqual(
                launch.enter_thread, launch.exit_thread, 'browsers must close on their owning worker thread'
            )
            self.assertNotEqual(launch.enter_thread, threading.get_ident())

    async def test_after_shutdown_rejects_new_work(self):
        pool = await self.started_pool(size=1)

        result = await pool.run('https://example.com', reader=False)
        self.assertEqual(result['title'], 'Page 0')

        await pool.shutdown()
        await pool.shutdown()  # idempotent

        with self.assertRaises(RuntimeError):
            await pool.run('https://example.com', reader=False)

    async def test_shutdown_keeps_event_loop_responsive_while_queue_is_full(self):
        calls = []
        started = threading.Event()
        release = threading.Event()

        def op(browser, url, reader=True):
            calls.append(url)
            started.set()
            release.wait(2)
            return {'title': url, 'content': 'x'}

        self.install_op(op)
        pool = await self.started_pool(size=1)
        first = asyncio.create_task(pool.run('first'))
        self.assertTrue(await asyncio.to_thread(started.wait, 2), 'the worker must be busy')

        queued = [asyncio.create_task(pool.run(f'q{i}')) for i in range(3)]
        await asyncio.sleep(0.05)  # three jobs parked: the queue is full

        canary = asyncio.create_task(asyncio.sleep(0.05))
        stopping = asyncio.create_task(pool.shutdown())
        began = time.monotonic()
        await asyncio.wait_for(canary, timeout=0.5)
        self.assertLess(
            time.monotonic() - began,
            0.5,
            'shutdown must not freeze the event loop while the queue is full',
        )
        self.assertFalse(stopping.done(), 'shutdown must still be draining accepted work')

        release.set()
        await asyncio.wait_for(stopping, timeout=5)
        results = await asyncio.wait_for(asyncio.gather(first, *queued), timeout=5)
        self.assertEqual(
            [r['title'] for r in results],
            ['first', 'q0', 'q1', 'q2'],
            'accepted jobs must still drain after the freeze-free shutdown',
        )
        self.assertEqual(calls, ['first', 'q0', 'q1', 'q2'])
        self.assertEqual(len(self.camoufox.launches), 1)
        launch = self.camoufox.launches[0]
        self.assertEqual((launch.enter_count, launch.exit_count), (1, 1))
        self.assertEqual(launch.enter_thread, launch.exit_thread, 'browsers must close on their owning worker thread')


class PoolSizeTests(unittest.TestCase):
    """Size validation: explicit size, BROWSER_POOL_SIZE override, clear errors."""

    def test_operational_constants_pinned(self):
        self.assertEqual(browser_pool.BROWSER_QUEUE_SIZE, 3)
        self.assertEqual(browser_pool.BROWSER_QUEUE_TIMEOUT_SECONDS, 30)
        self.assertEqual(browser_pool.RECYCLE_AFTER_JOBS, 200)
        self.assertEqual(browser_pool.MAX_ATTEMPTS, 3)

    def test_default_size_is_three(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(BrowserPool().size, 3)

    def test_env_size_used_when_explicit_absent(self):
        with patch.dict(os.environ, {'BROWSER_POOL_SIZE': '2'}):
            self.assertEqual(BrowserPool().size, 2)

    def test_explicit_size_wins_over_env(self):
        with patch.dict(os.environ, {'BROWSER_POOL_SIZE': '2'}):
            self.assertEqual(BrowserPool(size=5).size, 5)

    def test_explicit_invalid_sizes_rejected(self):
        for bad in (0, -1, -7, 1.5, '2', [3]):
            with self.assertRaises(ValueError):
                BrowserPool(size=bad)

    def test_env_invalid_sizes_rejected(self):
        for bad in ('0', '-2', 'abc', '1.5', ''):
            with patch.dict(os.environ, {'BROWSER_POOL_SIZE': bad}):
                with self.assertRaises(ValueError):
                    BrowserPool()


if __name__ == '__main__':
    unittest.main()

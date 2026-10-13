import asyncio
import threading
import unittest
from unittest.mock import patch

from reader_web_service.browser_capacity import BrowserBusy, BrowserCapacity


class BrowserCapacityTests(unittest.IsolatedAsyncioTestCase):
    async def test_allows_three_active_and_three_waiting_requests(self):
        capacity = BrowserCapacity()
        for _ in range(3):
            await capacity.acquire()

        waiters = [asyncio.create_task(capacity.acquire()) for _ in range(3)]
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        with self.assertRaises(BrowserBusy):
            await asyncio.wait_for(capacity.acquire(), timeout=0.1)

        for _ in range(3):
            await capacity.release()
        await asyncio.gather(*waiters)
        for _ in range(3):
            await capacity.release()

    async def test_waiting_request_times_out(self):
        with patch("reader_web_service.browser_capacity.BROWSER_QUEUE_TIMEOUT_SECONDS", 0.01):
            capacity = BrowserCapacity()
            for _ in range(3):
                await capacity.acquire()

            with self.assertRaises(BrowserBusy):
                await capacity.acquire()

            self.assertEqual(capacity._waiting, 0)
            for _ in range(3):
                await capacity.release()

    async def test_cancelled_request_holds_slot_until_worker_finishes(self):
        capacity = BrowserCapacity()
        started = threading.Event()
        finish = threading.Event()

        def blocked_browser_call():
            started.set()
            finish.wait(timeout=2)

        task = asyncio.create_task(capacity.run(blocked_browser_call))
        try:
            for _ in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(0.01)
            self.assertTrue(started.is_set())

            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

            await capacity.acquire()
            await capacity.acquire()
            queued = asyncio.create_task(capacity.acquire())
            await asyncio.sleep(0)
            self.assertFalse(queued.done())

            finish.set()
            await asyncio.wait_for(queued, timeout=1)
            for _ in range(3):
                await capacity.release()
        finally:
            finish.set()

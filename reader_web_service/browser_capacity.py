import asyncio

ACTIVE_BROWSER_SLOTS = 3
BROWSER_QUEUE_SIZE = 3
BROWSER_QUEUE_TIMEOUT_SECONDS = 30


class BrowserBusy(Exception):
    pass


class BrowserCapacity:
    def __init__(self):
        self._active = 0
        self._waiting = 0
        self._condition = asyncio.Condition()

    async def acquire(self):
        async with self._condition:
            if self._active < ACTIVE_BROWSER_SLOTS and self._waiting == 0:
                self._active += 1
                return
            if self._waiting >= BROWSER_QUEUE_SIZE:
                raise BrowserBusy

            self._waiting += 1
            try:
                try:
                    await asyncio.wait_for(
                        self._condition.wait_for(lambda: self._active < ACTIVE_BROWSER_SLOTS),
                        timeout=BROWSER_QUEUE_TIMEOUT_SECONDS,
                    )
                except TimeoutError as error:
                    raise BrowserBusy from error
                self._active += 1
            finally:
                self._waiting -= 1

    async def release(self):
        async with self._condition:
            self._active -= 1
            self._condition.notify(1)

    async def run(self, function, *args):
        await self.acquire()
        loop = asyncio.get_running_loop()
        try:
            future = loop.run_in_executor(None, function, *args)
        except BaseException:
            await self.release()
            raise

        release_here = True
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            release_here = False
            future.add_done_callback(lambda _: asyncio.create_task(self.release()))
            raise
        finally:
            if release_here:
                await self.release()

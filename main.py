import asyncio
import queue
import threading
import time
import typing
from concurrent.futures import ThreadPoolExecutor
import nest_asyncio
import sys

sys.setrecursionlimit(1000000)

# Save originals
_original_run_until_complete = asyncio.BaseEventLoop.run_until_complete
_original_asyncio_run = asyncio.run

# Main thread / loop snapshot
_main_thread = threading.main_thread()
_main_loop = asyncio.get_event_loop()

executor = ThreadPoolExecutor(max_workers=4)
from greenlet import getcurrent

from greenlet import greenlet


class MainGreenlet(greenlet):

    def __init__(self):
        self.greenlets = []

    def run(self):

        print("hello1")

class SubGreenlet(greenlet):

    def __init__(self, to_run):
        self.result = None
        self.to_run = to_run
        self.result_fut = to_run

    def is_done(self):
        if self.result_fut.done():
            self.result = self.result_fut.result()
            return True
        return False

    def run(self):
        return self.result


main_greenlet =  MainGreenlet()

def patched_run_until_complete(self, future):
    # Main thread and already running = offload
    current_thread = threading.current_thread()
    print(current_thread)
    if current_thread.name == threading.main_thread().name:
        print("Running main thread!")
        f = await_sync(future, main_greenlet)
        print(f"Found {f}")
        return f
    print("Running original!")
    return _original_run_until_complete(self, future)


def patched_asyncio_run(awaitable, *, debug=False):
    try:
        thread = threading.current_thread()
        print(thread)
        if thread.name == threading.main_thread().name:
            print("Running curr")
            return await_sync(awaitable, main_greenlet)
    except RuntimeError:
        print('err')
    print("Running original")
    return _original_asyncio_run(awaitable)


def patch_asyncio_safely():
    asyncio.BaseEventLoop.run_until_complete = patched_run_until_complete
    asyncio.run = patched_asyncio_run

import asyncio

def await_sync(awaitable, main_greenlet: MainGreenlet):
    """
    Suspend sync function and await the awaitable inside the main event loop.
    """
    loop = asyncio.get_event_loop()
    result_box = {}

    def coroutine_runner():
        async def inner():
            result_box["result"] = await awaitable
            runner_greenlet.switch()

        fut = asyncio.ensure_future(inner())

        fut.add_done_callback(lambda s: print("hello is done"))

        # yield to the main loop until inner completes
        print("Switching!")
        handle = loop.call_soon(runner_greenlet.switch, None)

        while 'result' not in result_box.keys():
            print("result not found")
            main_greenlet.switch()

        print("result found!")

        return result_box["result"]

    runner_greenlet = SubGreenlet(coroutine_runner)
    main_greenlet.switch()
    return runner_greenlet.switch()


# Apply patch
# patch_asyncio_safely()
# nest_asyncio.apply()
sys.setrecursionlimit(1000000)
patch_asyncio_safely()

async def ok():
    await asyncio.sleep(1)
    return "hello"

def hello():
    return asyncio.get_event_loop().run_until_complete(ok())

async def again():
    await asyncio.sleep(1)
    return hello()

def to():
    return asyncio.get_event_loop().run_until_complete(again())

def whatever():
    print(f'TO: ' + to())

async def call_whatever():
    whatever()

asyncio.get_event_loop().run_until_complete(call_whatever())

q = asyncio.Queue()

async def add_to_queue():
    time.sleep(2)
    print("Adding")
    await q.put(100)
    print("Added")

for i in range(4):
    time.sleep(1)
    threading.Thread(target=lambda: asyncio.new_event_loop().run_until_complete(add_to_queue())).start()
    print("Found")

async def get_from_queue():
    return await q.get()

async def run_all():
    all = []
    for i in range(1000):
        queue = await get_from_queue()
        print(f"Gotten {queue}")
        all.append(queue)

    await asyncio.gather(*all)

print("Starting")
gathered = asyncio.get_event_loop().run_until_complete(run_all())


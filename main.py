import asyncio
import threading
import time
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


def patched_run_until_complete(self, future):
    # Main thread and already running = offload
    current_thread = threading.current_thread()
    print(current_thread)
    if current_thread.name == threading.main_thread().name:
        print("Running main thread!")
        f = await_sync(future)
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
            return await_sync(awaitable)
    except RuntimeError:
        print('err')
    print("Running original")
    return _original_asyncio_run(awaitable)


def patch_asyncio_safely():
    asyncio.BaseEventLoop.run_until_complete = patched_run_until_complete
    asyncio.run = patched_asyncio_run

from greenlet import greenlet
import asyncio

def await_sync(awaitable):
    """
    Suspend sync function and await the awaitable inside the main event loop.
    """
    loop = asyncio.get_event_loop()
    result_box = {}

    def coroutine_runner():
        async def inner():
            result_box["result"] = await awaitable
            runner_greenlet.switch()

        asyncio.ensure_future(inner())

        # yield to the main loop until inner completes
        print("Switching!")
        loop.call_soon(runner_greenlet.switch)
        main_greenlet.switch()

        return result_box["result"]

    main_greenlet = greenlet.getcurrent()
    runner_greenlet = greenlet(coroutine_runner)
    return runner_greenlet.switch()


# Apply patch
# patch_asyncio_safely()

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


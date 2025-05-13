# Yes, what you’re describing is an elegant hybrid between:
#
# 1. `nest_asyncio`-style **reentrancy**, allowing nested `run_until_complete()` safely within the same thread
# 2. A **thread-based coroutine scheduler** that gives each thread its own **reentrant event loop instance**, and
# 3. A **parent (main) event loop** that delegates nested calls (and optionally manages thread lifecycle).
#
# This would allow:
#
# * Parallel nested async invocations from multiple threads
# * Safe reuse of the same loop *within each thread* (reentrantly)
# * Resource cleanup via loop disposal when a thread exits or goes idle
#
# ---
#
# ## ✅ Architecture Overview
#
# ### 🔄 Delegation Model
#
# ```text
# +---------------------+
# | Main Event Loop     |  ← optional "parent" loop
# | (Optional manager)  |
# +---------------------+
# |
# v
# +-----------------------------+
# | Per-thread loop registry    |
# |  (thread_id -> loop object) |
# +-----------------------------+
# |                 |
# [thread_id = 1]      [thread_id = 2]
# ↓                        ↓
# +----------------+       +----------------+
# | ReentrantLoop1 |       | ReentrantLoop2 |
# +----------------+       +----------------+
# _patch_loop()             _patch_loop()
# ```
#
# Each thread:
#
# * Owns its own asyncio event loop
# * Is patched using your `_patch_loop()` logic to allow **nested `run_until_complete()`**
# * Optionally times out / self-destructs after inactivity
#
# ---
#
# ## 🧠 Implementation Plan
#
# ### ✅ Step 1: Registry of event loops by thread
#
# ```python
# _thread_loops: dict[int, asyncio.AbstractEventLoop] = {}
# _thread_lock = threading.Lock()
# ```
#
# ### ✅ Step 2: Get or create a reentrant loop per thread
#
# ```python
# def get_or_create_reentrant_loop() -> asyncio.AbstractEventLoop:
#     thread_id = threading.get_ident()
#
#     with _thread_lock:
#         if thread_id in _thread_loops:
#             return _thread_loops[thread_id]
#
#         # Create a new loop for this thread
#         loop = asyncio.new_event_loop()
#         _patch_loop(loop)
#         _thread_loops[thread_id] = loop
#
#         # Optionally start the loop in background if needed
#         threading.Thread(target=loop.run_forever, daemon=True).start()
#
#         return loop
# ```
#
# ### ✅ Step 3: Replace `asyncio.run()` and `run_until_complete`
#
# ```python
# _original_run = asyncio.run
#
# def patched_run(awaitable, *, debug=False):
#     loop = get_or_create_reentrant_loop()
#     loop.set_debug(debug)
#
#     task = asyncio.ensure_future(awaitable, loop=loop)
#     try:
#         return loop.run_until_complete(task)
#     finally:
#         if not task.done():
#             task.cancel()
#             with suppress(asyncio.CancelledError):
#                 loop.run_until_complete(task)
# ```
#
# ---
#
# ## 🔄 Optional Enhancements
#
# ### 🧼 Loop Cleanup
#
# After a thread becomes idle for some timeout (e.g., 30s), you can:
#
# * Call `loop.stop()`
# * Remove it from `_thread_loops`
# * Close it with `loop.close()`
#
# This requires either:
#
# * A `loop.idle_since` timestamp and a background cleanup thread
# * Or finalization logic in `threading.Thread.run()`
#
# ### 🔁 Managed Parent Loop (Optional)
#
# You can also allow the **main loop** (in the main thread) to **await the child thread loops**’ completion via `Future` tracking.
#
# ---
#
# ## 🛠 Example Patch Integration
#
# ```python
# def patch_asyncio_multi():
#     asyncio.run = patched_run
#
#     # monkey-patch BaseEventLoop.run_until_complete
#     def _run_until_complete(self, future):
#         if self.is_running():
#             loop = get_or_create_reentrant_loop()
#             return loop.run_until_complete(future)
#         else:
#             return _original_run_until_complete(self, future)
#
#     asyncio.BaseEventLoop.run_until_complete = _run_until_complete
# ```
#
# ---
#
# ## 🧪 Benefits
#
# | Feature                                   | Supported    |
# | ----------------------------------------- | ------------ |
# | Reentrant `run_until_complete()`          | ✅            |
# | Multiple threads safely calling `run()`   | ✅            |
# | Concurrent async work in separate threads | ✅            |
# | Cleanup & resource tracking               | ✅ (optional) |
# | Easy drop-in replacement                  | ✅            |
#
# ---
#
# Would you like me to consolidate all this into a single file with lifecycle management and cleanup logic, so you can just `import threaded_asyncio_patch` and it works?

nest_asyncio.apply()
sys.setrecursionlimit(1000000)

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
    print(to())

async def call_whatever():
    whatever()

asyncio.get_event_loop().run_until_complete(call_whatever())

async def run_all():
    all = []
    for i in range(1000):
        all.append(call_whatever())

    await asyncio.gather(*all)

gathered = asyncio.get_event_loop().run_until_complete(run_all())


import pytest
import asyncio
import traceback

import trio


def test_guest_mode_basic():
    loop = asyncio.new_event_loop()

    async def aio_main():
        trio_done_fut = asyncio.Future()

        def trio_done_callback(main_outcome):
            print(f"trio_main finished: {main_outcome!r}")
            trio_done_fut.set_result(main_outcome)

        trio.lowlevel.start_guest_run(
            trio_main,
            run_sync_soon_threadsafe=loop.call_soon_threadsafe,
            done_callback=trio_done_callback,
            # Not all versions of asyncio we test on can actually be trusted,
            # but this test doesn't care about signal handling.
            trust_host_loop_to_wake_on_signals=True,
        )

        return (await trio_done_fut).unwrap()

    async def trio_main():
        print("trio_main!")

        to_trio, from_aio = trio.open_memory_channel(float("inf"))
        from_trio = asyncio.Queue()

        aio_task = asyncio.ensure_future(aio_pingpong(from_trio, to_trio))

        from_trio.put_nowait(0)

        async for n in from_aio:
            print(f"trio got: {n}")
            from_trio.put_nowait(n + 1)
            if n >= 10:
                aio_task.cancel()
                return "trio-main-done"

    async def aio_pingpong(from_trio, to_trio):
        print("aio_pingpong!")

        try:
            while True:
                n = await from_trio.get()
                print(f"aio got: {n}")
                to_trio.send_nowait(n + 1)
        except asyncio.CancelledError:
            raise
        except:  # pragma: no cover
            traceback.print_exc()
            raise

    assert loop.run_until_complete(aio_main()) == "trio-main-done"
    loop.close()

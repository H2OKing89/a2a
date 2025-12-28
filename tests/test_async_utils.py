"""
Tests for async CLI utilities.
"""

import asyncio

import pytest

from src.cli.async_utils import (
    AsyncBatchProcessor,
    async_command,
    gather_with_progress,
    run_async,
    stream_with_progress,
)


class TestRunAsync:
    """Tests for run_async function."""

    def test_runs_simple_coroutine(self):
        async def simple_coro():
            return 42

        result = run_async(simple_coro())
        assert result == 42

    def test_runs_coroutine_with_await(self):
        async def coro_with_await():
            await asyncio.sleep(0.001)
            return "done"

        result = run_async(coro_with_await())
        assert result == "done"

    def test_propagates_exceptions(self):
        async def failing_coro():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            run_async(failing_coro())


class TestAsyncCommand:
    """Tests for async_command decorator."""

    def test_wraps_async_function(self):
        @async_command(show_spinner=False)
        async def test_func(x: int) -> int:
            return x * 2

        result = test_func(21)
        assert result == 42

    def test_preserves_function_name(self):
        @async_command(show_spinner=False)
        async def my_named_func() -> str:
            return "test"

        assert my_named_func.__name__ == "my_named_func"

    def test_handles_exceptions(self):
        @async_command(show_spinner=False)
        async def raising_func():
            raise RuntimeError("command failed")

        with pytest.raises(RuntimeError, match="command failed"):
            raising_func()

    def test_with_keyword_args(self):
        @async_command(show_spinner=False)
        async def func_with_kwargs(a: int, b: int = 10) -> int:
            return a + b

        assert func_with_kwargs(5) == 15
        assert func_with_kwargs(5, b=20) == 25


class TestGatherWithProgress:
    """Tests for gather_with_progress function."""

    @pytest.mark.asyncio
    async def test_gathers_results(self):
        async def task(n: int) -> int:
            await asyncio.sleep(0.001)
            return n * 2

        tasks = [task(1), task(2), task(3)]
        results = await gather_with_progress(tasks)
        # Verify results maintain input order
        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_maintains_input_order(self):
        """Verify results are in input order even when tasks complete in different order."""

        async def task_with_delay(n: int, delay: float) -> int:
            await asyncio.sleep(delay)
            return n

        # Create tasks that will complete in reverse order (3, 2, 1)
        # but should be returned in input order (1, 2, 3)
        tasks = [
            task_with_delay(1, 0.03),  # Slowest
            task_with_delay(2, 0.02),  # Medium
            task_with_delay(3, 0.01),  # Fastest
        ]
        results = await gather_with_progress(tasks)
        # Results should be in input order, not completion order
        assert results == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_empty_tasks(self):
        results = await gather_with_progress([])
        assert results == []

    @pytest.mark.asyncio
    async def test_single_task(self):
        async def task() -> str:
            return "result"

        results = await gather_with_progress([task()])
        assert results == ["result"]


class TestStreamWithProgress:
    """Tests for stream_with_progress function."""

    @pytest.mark.asyncio
    async def test_streams_items(self):
        async def async_gen():
            for i in range(5):
                yield i

        results = await stream_with_progress(async_gen())
        assert results == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_empty_stream(self):
        async def empty_gen():
            return
            yield  # Makes it a generator

        results = await stream_with_progress(empty_gen())
        assert results == []


class TestAsyncBatchProcessor:
    """Tests for AsyncBatchProcessor class."""

    @pytest.mark.asyncio
    async def test_processes_items_in_batches(self):
        processor = AsyncBatchProcessor(batch_size=2, delay_between_batches=0.001)

        async def double(x: int) -> int:
            return x * 2

        items = [1, 2, 3, 4, 5]
        results = await processor.process(items, double)
        assert sorted(results) == [2, 4, 6, 8, 10]

    @pytest.mark.asyncio
    async def test_handles_empty_list(self):
        processor = AsyncBatchProcessor(batch_size=2)

        async def noop(x: int) -> int:
            return x

        results = await processor.process([], noop)
        assert results == []

    @pytest.mark.asyncio
    async def test_handles_single_item(self):
        processor = AsyncBatchProcessor(batch_size=10)

        async def identity(x: str) -> str:
            return x

        results = await processor.process(["single"], identity)
        assert results == ["single"]

    @pytest.mark.asyncio
    async def test_handles_exceptions_gracefully(self):
        processor = AsyncBatchProcessor(batch_size=2, delay_between_batches=0.001)

        async def maybe_fail(x: int) -> int:
            if x == 3:
                raise ValueError("Item 3 failed")
            return x * 2

        items = [1, 2, 3, 4, 5]
        # Should complete with warnings but not raise
        results = await processor.process(items, maybe_fail)
        # Item 3 should be skipped due to error
        assert sorted(results) == [2, 4, 8, 10]

    @pytest.mark.asyncio
    async def test_custom_batch_size(self):
        call_count = 0
        batches_processed = []

        processor = AsyncBatchProcessor(batch_size=3, delay_between_batches=0.001)

        async def track_calls(x: int) -> int:
            nonlocal call_count
            call_count += 1
            batches_processed.append(x)
            return x

        items = list(range(7))  # 7 items with batch_size=3 = 3 batches
        await processor.process(items, track_calls)
        assert call_count == 7

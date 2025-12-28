"""
Async CLI utilities.

Provides helpers for running async operations in Typer CLI commands
with proper progress indication and error handling.
"""

import asyncio
import functools
from collections.abc import AsyncIterable, Awaitable, Callable, Coroutine
from concurrent.futures import ThreadPoolExecutor
from typing import Any, ParamSpec, TypeVar, cast

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

P = ParamSpec("P")
T = TypeVar("T")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """
    Run an async coroutine from synchronous code.

    Handles event loop lifecycle properly for CLI commands.

    Args:
        coro: Async coroutine to run

    Returns:
        Result of the coroutine
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        # Already in async context - run in executor
        with ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        # No running loop - create one
        return asyncio.run(coro)


def async_command(
    console: Console | None = None,
    show_spinner: bool = True,
    spinner_text: str = "Processing...",
) -> Callable[[Callable[P, Coroutine[Any, Any, T]]], Callable[P, T]]:
    """
    Decorator to make async functions work as Typer commands.

    Wraps an async function to run it with asyncio.run() and
    optionally shows a spinner during execution.

    Usage:
        @app.command()
        @async_command(show_spinner=True, spinner_text="Loading...")
        async def my_command(arg: str):
            result = await some_async_operation(arg)
            return result

    Args:
        console: Rich console instance
        show_spinner: Whether to show a spinner during execution
        spinner_text: Text to display with spinner

    Returns:
        Decorator function
    """
    _console = console or Console()

    def decorator(func: Callable[P, Coroutine[Any, Any, T]]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            async def run_with_spinner() -> T:
                if show_spinner:
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        console=_console,
                        transient=True,
                    ) as progress:
                        progress.add_task(description=spinner_text, total=None)
                        return await func(*args, **kwargs)
                else:
                    return await func(*args, **kwargs)

            return run_async(run_with_spinner())

        return wrapper

    return decorator


async def gather_with_progress(
    tasks: list[Awaitable[T]],
    console: Console | None = None,
    description: str = "Processing...",
) -> list[T]:
    """
    Run multiple async tasks concurrently with a progress indicator.

    Args:
        tasks: List of awaitable tasks
        console: Rich console instance
        description: Progress description text

    Returns:
        List of results in same order as input tasks
    """
    _console = console or Console()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TextColumn("({task.completed}/{task.total})"),
        console=_console,
        transient=True,
    ) as progress:
        task_id = progress.add_task(description, total=len(tasks))

        # Wrap each task to update progress when it completes
        async def track_progress(coro: Awaitable[T]) -> T:
            result = await coro
            progress.advance(task_id)
            return result

        # Use gather to maintain input order
        return await asyncio.gather(*[track_progress(t) for t in tasks])


async def stream_with_progress(
    items: AsyncIterable[T],
    total: int | None = None,
    console: Console | None = None,
    description: str = "Processing...",
) -> list[T]:
    """
    Stream async items with progress indication.

    Args:
        items: Async iterable of items
        total: Total expected items (for progress bar)
        console: Rich console instance
        description: Progress description text

    Returns:
        List of collected items
    """
    _console = console or Console()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=_console,
        transient=True,
    ) as progress:
        task_id = progress.add_task(description, total=total)
        results: list[T] = []

        async for item in items:
            results.append(item)
            progress.advance(task_id)

        return results


class AsyncBatchProcessor:
    """
    Process items in batches with async operations.

    Useful for processing large numbers of items with rate limiting.
    """

    def __init__(
        self,
        batch_size: int = 10,
        delay_between_batches: float = 0.1,
    ) -> None:
        """
        Initialize batch processor.

        Args:
            batch_size: Number of items to process per batch
            delay_between_batches: Delay in seconds between batches
        """
        self.batch_size = batch_size
        self.delay = delay_between_batches

    async def process(
        self,
        items: list[Any],
        processor: Callable[[Any], Awaitable[T]],
        console: Console | None = None,
        description: str = "Processing items...",
    ) -> list[T]:
        """
        Process items in batches.

        Args:
            items: List of items to process
            processor: Async function to apply to each item
            console: Rich console instance
            description: Progress description

        Returns:
            List of processed results (failed items are logged and skipped,
            so the returned list may be shorter than the input list)
        """
        _console = console or Console()
        results: list[T] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TextColumn("({task.completed}/{task.total})"),
            console=_console,
            transient=True,
        ) as progress:
            task_id = progress.add_task(description, total=len(items))

            for i in range(0, len(items), self.batch_size):
                batch = items[i : i + self.batch_size]
                batch_tasks = [processor(item) for item in batch]
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

                for result in batch_results:
                    if isinstance(result, Exception):
                        # Log error but continue
                        _console.print(f"[yellow]Warning: {result}[/yellow]")
                    else:
                        results.append(cast(T, result))
                    progress.advance(task_id)

                # Rate limit between batches
                if i + self.batch_size < len(items):
                    await asyncio.sleep(self.delay)

        return results

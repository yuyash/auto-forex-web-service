"""Unit tests for TaskExecutor collaborators."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from apps.trading.tasks.execution_collaborators import (
    ExecutionStateRepository,
    ExecutionTickLoop,
)


class TestExecutionStateRepository:
    """Tests for state persistence delegation."""

    def test_save_uses_executor_state_store(self):
        state = SimpleNamespace(
            task_id="task-1",
            ticks_processed=3,
            last_tick_timestamp=None,
            current_balance="1000",
        )
        executor = SimpleNamespace(
            logger=MagicMock(),
            state_store=SimpleNamespace(save=MagicMock()),
        )

        ExecutionStateRepository(executor).save(state)

        executor.state_store.save.assert_called_once_with(state)


class TestExecutionTickLoop:
    """Tests for batch-loop orchestration delegation."""

    def test_run_processes_batch_and_persists_progress(self):
        state = SimpleNamespace(ticks_processed=1)
        loop = SimpleNamespace(
            state=state,
            no_tick_batches=0,
            batch_count=0,
            stopped_early=False,
        )
        tick_batch = [object()]
        executor = SimpleNamespace(
            logger=MagicMock(),
            task=SimpleNamespace(pk="task-1"),
            data_source=[tick_batch],
            _flush_task_logs=MagicMock(),
            _should_stop_before_batch=MagicMock(return_value=False),
            _handle_empty_batch=MagicMock(return_value=False),
            _process_tick_batch=MagicMock(),
            _persist_batch_progress=MagicMock(),
            _after_batch_processed=MagicMock(),
        )

        ExecutionTickLoop(executor).run(loop)

        executor._process_tick_batch.assert_called_once_with(loop, tick_batch)
        executor._persist_batch_progress.assert_called_once_with(loop)
        executor._after_batch_processed.assert_called_once_with(loop)
        assert loop.batch_count == 1

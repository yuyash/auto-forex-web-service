"""Unit tests for trading logging module."""

import logging
from unittest.mock import MagicMock

from apps.trading.logging import (
    DEFAULT_TASK_LOGGER_NAMES,
    JSONLoggingHandler,
    TaskLoggingSession,
    get_task_logger,
)


class TestJSONLoggingHandler:
    """Test JSONLoggingHandler."""

    def test_init_stores_task(self):
        task = MagicMock()
        handler = JSONLoggingHandler(task)
        assert handler.task is task

    def test_emit_handles_exception_gracefully(self):
        """emit() should not raise even if DB write fails."""
        task = MagicMock()
        task.pk = 1
        handler = JSONLoggingHandler(task)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        # Should not raise even though TaskLog is not available
        handler.emit(record)


class TestGetTaskLogger:
    """Test get_task_logger factory function."""

    def test_returns_logger(self):
        task = MagicMock()
        task.pk = 42
        logger = get_task_logger(task, logger_name="test.unique.gettasklogger1")
        assert isinstance(logger, logging.Logger)
        # Cleanup
        for h in list(logger.handlers):
            if isinstance(h, JSONLoggingHandler):
                logger.removeHandler(h)

    def test_does_not_add_duplicate_handlers(self):
        task = MagicMock()
        task.pk = 99
        name = "test.unique.gettasklogger2"
        _logger1 = get_task_logger(task, logger_name=name)
        logger2 = get_task_logger(task, logger_name=name)
        json_handlers = [h for h in logger2.handlers if isinstance(h, JSONLoggingHandler)]
        assert len(json_handlers) == 1
        # Cleanup
        for h in list(logger2.handlers):
            if isinstance(h, JSONLoggingHandler):
                logger2.removeHandler(h)


class TestTaskLoggingSession:
    """Test TaskLoggingSession context manager."""

    def test_start_attaches_handler(self):
        task = MagicMock()
        task.pk = 10
        session = TaskLoggingSession(task, logger_names=["test.session.tls1"])
        session.start()
        logger_obj = logging.getLogger("test.session.tls1")
        assert session.handler in logger_obj.handlers
        session.stop()

    def test_stop_detaches_handler(self):
        task = MagicMock()
        task.pk = 11
        session = TaskLoggingSession(task, logger_names=["test.session.tls2"])
        session.start()
        session.stop()
        logger_obj = logging.getLogger("test.session.tls2")
        assert session.handler not in logger_obj.handlers

    def test_context_manager(self):
        task = MagicMock()
        task.pk = 12
        name = "test.session.tls3"
        with TaskLoggingSession(task, logger_names=[name]) as session:
            logger_obj = logging.getLogger(name)
            assert session.handler in logger_obj.handlers
        assert session.handler not in logger_obj.handlers

    def test_exit_returns_false(self):
        task = MagicMock()
        task.pk = 13
        session = TaskLoggingSession(task, logger_names=["test.session.tls4"])
        result = session.__exit__(None, None, None)
        assert result is False

    def test_default_logger_names(self):
        assert DEFAULT_TASK_LOGGER_NAMES == ("apps.trading",)

"""
System health monitoring module.

This module provides system health monitoring functionality including:
- CPU and memory usage monitoring
- Database connection health checks
- Redis connection health checks
- OANDA API connection health checks
- Active stream and task monitoring
- Uptime tracking for host, container, and Celery process

Requirements: 19.1, 19.2, 19.3, 19.4
"""

import logging
import os
import time
from datetime import datetime, timezone as dt_timezone
from typing import Any, Dict, Optional

from django.conf import settings
from django.db import connection
from django.utils import timezone

import psutil
import redis

logger = logging.getLogger(__name__)

# Track when this module was first imported (approximate process start time)
# Use stdlib timezone to avoid Django settings requirement at import time
_PROCESS_START_TIME: Optional[datetime] = datetime.now(dt_timezone.utc)


class SystemHealthMonitor:
    """
    Monitor system health metrics and service connections.

    This class provides methods to check the health of various system
    components including CPU, memory, database, Redis, and external APIs.

    Requirements: 19.1, 19.2, 19.3, 19.4
    """

    def __init__(self) -> None:
        """Initialize the system health monitor."""
        self.redis_client = None
        try:
            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                self.redis_client = redis.from_url(
                    redis_url,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")

    def get_cpu_usage(self) -> Dict[str, Any]:
        """
        Get current CPU usage metrics.

        Returns:
            Dictionary containing CPU usage information
        """
        try:
            # Use interval=0 for non-blocking call (uses cached value from previous call)
            # This is acceptable for frequent dashboard updates
            cpu_percent = psutil.cpu_percent(interval=0)
            cpu_count = psutil.cpu_count()
            load_avg = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0, 0, 0)

            return {
                "status": "healthy" if cpu_percent < 80 else "warning",
                "cpu_percent": cpu_percent,
                "cpu_count": cpu_count,
                "load_average": {
                    "1min": load_avg[0],
                    "5min": load_avg[1],
                    "15min": load_avg[2],
                },
            }
        except Exception as e:
            logger.error(f"Failed to get CPU usage: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    def get_memory_usage(self) -> Dict[str, Any]:
        """
        Get current memory usage metrics.

        Returns:
            Dictionary containing memory usage information
        """
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            return {
                "status": "healthy" if memory.percent < 80 else "warning",
                "total_mb": memory.total / (1024 * 1024),
                "available_mb": memory.available / (1024 * 1024),
                "used_mb": memory.used / (1024 * 1024),
                "percent": memory.percent,
                "swap_total_mb": swap.total / (1024 * 1024),
                "swap_used_mb": swap.used / (1024 * 1024),
                "swap_percent": swap.percent,
            }
        except Exception as e:
            logger.error(f"Failed to get memory usage: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    def check_database_connection(self) -> Dict[str, Any]:
        """
        Check PostgreSQL database connection health.

        Returns:
            Dictionary containing database connection status
        """
        try:
            start_time = time.time()
            connection.ensure_connection()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            response_time = (time.time() - start_time) * 1000  # Convert to ms

            return {
                "status": "healthy",
                "connected": True,
                "response_time_ms": round(response_time, 2),
                "database": settings.DATABASES["default"]["NAME"],
                "host": settings.DATABASES["default"]["HOST"],
            }
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return {
                "status": "error",
                "connected": False,
                "error": str(e),
            }

    def check_redis_connection(self) -> Dict[str, Any]:
        """
        Check Redis connection health.

        Returns:
            Dictionary containing Redis connection status
        """
        if not self.redis_client:
            return {
                "status": "error",
                "connected": False,
                "error": "Redis client not initialized",
            }

        try:
            start_time = time.time()
            self.redis_client.ping()
            response_time = (time.time() - start_time) * 1000  # Convert to ms

            info = self.redis_client.info()
            return {
                "status": "healthy",
                "connected": True,
                "response_time_ms": round(response_time, 2),
                "version": info.get("redis_version", "unknown"),
                "used_memory_mb": info.get("used_memory", 0) / (1024 * 1024),
                "connected_clients": info.get("connected_clients", 0),
            }
        except Exception as e:
            logger.error(f"Redis connection check failed: {e}")
            return {
                "status": "error",
                "connected": False,
                "error": str(e),
            }

    def check_oanda_api_connection(self) -> Dict[str, Any]:
        """
        Check OANDA API connection health.

        This checks if the OANDA API endpoints are reachable.
        Note: This does not validate specific account credentials.

        Returns:
            Dictionary containing OANDA API connection status
        """
        try:
            import requests

            practice_url = f"{settings.OANDA_PRACTICE_API}/v3/accounts"
            live_url = f"{settings.OANDA_LIVE_API}/v3/accounts"

            practice_status = "unknown"
            live_status = "unknown"

            # Check practice API (without auth, just to see if endpoint is reachable)
            # Use short timeout (1s) since this runs frequently for dashboard updates
            try:
                response = requests.get(practice_url, timeout=1)
                # 401 is expected without auth, but means endpoint is reachable
                practice_status = "reachable" if response.status_code in [401, 403] else "error"
            except Exception as e:
                logger.warning(f"Practice API check failed: {e}")
                practice_status = "unreachable"

            # Check live API
            # Use short timeout (1s) since this runs frequently for dashboard updates
            try:
                response = requests.get(live_url, timeout=1)
                live_status = "reachable" if response.status_code in [401, 403] else "error"
            except Exception as e:
                logger.warning(f"Live API check failed: {e}")
                live_status = "unreachable"

            overall_status = (
                "healthy"
                if practice_status == "reachable" or live_status == "reachable"
                else "error"
            )

            return {
                "status": overall_status,
                "practice_api": {
                    "status": practice_status,
                    "url": settings.OANDA_PRACTICE_API,
                },
                "live_api": {
                    "status": live_status,
                    "url": settings.OANDA_LIVE_API,
                },
            }
        except Exception as e:
            logger.error(f"OANDA API connection check failed: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    def get_active_streams_count(self) -> int:
        """
        Get count of active v20 streaming connections.

        Returns:
            Number of active streaming connections
        """
        try:
            from celery import current_app

            # Count active market data stream tasks
            inspect = current_app.control.inspect(timeout=2.0)
            if inspect is None:
                logger.warning("Celery inspect returned None for streams count")
                return 0

            active_tasks = inspect.active() or {}

            # Count tasks with name containing 'market_data_stream'
            stream_count = 0
            for worker_tasks in active_tasks.values():
                if worker_tasks:
                    for task in worker_tasks:
                        task_name = task.get("name", "")
                        if "start_market_data_stream" in task_name:
                            stream_count += 1

            if stream_count > 0:
                logger.debug("Found %d active market data streams", stream_count)

            return stream_count
        except Exception as e:
            logger.error(f"Failed to get active streams count: {e}", exc_info=True)
            return 0

    def get_celery_tasks_count(self) -> Dict[str, int]:
        """
        Get count of Celery worker tasks.

        Returns:
            Dictionary with counts of active, scheduled, and reserved tasks
        """
        try:
            from celery import current_app

            active_tasks: dict[str, list] = {}
            scheduled_tasks: dict[str, list] = {}
            reserved_tasks: dict[str, list] = {}

            # Use shorter timeout and single attempt for frequent dashboard updates
            # Retry logic can be added for less frequent checks if needed
            try:
                inspect = current_app.control.inspect(timeout=0.5)
                if inspect is None:
                    raise RuntimeError("Celery inspect returned None")

                active_tasks = inspect.active() or {}
                scheduled_tasks = inspect.scheduled() or {}
                reserved_tasks = inspect.reserved() or {}

                # Log for debugging
                if active_tasks or scheduled_tasks or reserved_tasks:
                    logger.debug(
                        "Celery tasks: active=%d, scheduled=%d, reserved=%d",
                        sum(len(t) for t in active_tasks.values() if t),
                        sum(len(t) for t in scheduled_tasks.values() if t),
                        sum(len(t) for t in reserved_tasks.values() if t),
                    )
            except Exception as inner_error:  # pragma: no cover - network timing
                logger.warning("Celery inspect failed: %s", inner_error)
                # Return empty results instead of raising - dashboard should still work
                active_tasks = {}
                scheduled_tasks = {}
                reserved_tasks = {}

            active_count = sum(len(tasks) for tasks in active_tasks.values() if tasks)
            scheduled_count = sum(len(tasks) for tasks in scheduled_tasks.values() if tasks)
            reserved_count = sum(len(tasks) for tasks in reserved_tasks.values() if tasks)

            return {
                "active": active_count,
                "scheduled": scheduled_count,
                "reserved": reserved_count,
                "total": active_count + scheduled_count + reserved_count,
            }
        except Exception as e:
            logger.error(f"Failed to get Celery tasks count: {e}", exc_info=True)
            return {
                "active": 0,
                "scheduled": 0,
                "reserved": 0,
                "total": 0,
            }

    def get_uptime_info(self) -> Dict[str, Any]:
        """
        Get uptime information for host, container, and process.

        Returns:
            Dictionary containing:
            - host: Host system uptime (since last reboot)
            - container: Docker container uptime (from /proc/1/stat)
            - process: Current Python process uptime
            - celery_workers: Celery worker process info
        """
        now = timezone.now()

        result: Dict[str, Any] = {
            "timestamp": now.isoformat(),
            "host": self._get_host_uptime(),
            "container": self._get_container_uptime(),
            "process": self._get_process_uptime(now),
            "celery_workers": self._get_celery_worker_uptime(),
        }

        return result

    def _get_host_uptime(self) -> Dict[str, Any]:
        """Get host system uptime since last boot."""
        try:
            boot_time = datetime.fromtimestamp(
                psutil.boot_time(), tz=timezone.get_current_timezone()
            )
            uptime_seconds = (timezone.now() - boot_time).total_seconds()

            return {
                "boot_time": boot_time.isoformat(),
                "uptime_seconds": int(uptime_seconds),
                "uptime_human": self._format_uptime(uptime_seconds),
                "status": "healthy",
            }
        except Exception as e:
            logger.error(f"Failed to get host uptime: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    def _get_container_uptime(self) -> Dict[str, Any]:
        """
        Get Docker container uptime by checking PID 1 start time.

        In Docker, PID 1 is the main container process (entrypoint).
        """
        try:
            # Check if we're in a container (PID 1 is not init/systemd)
            proc1 = psutil.Process(1)
            proc1_name = proc1.name()

            # In Docker, PID 1 is typically the entrypoint (e.g., python, bash, etc.)
            # On a host system, PID 1 is init/systemd
            is_container = proc1_name not in ("init", "systemd", "launchd")

            if not is_container:
                return {
                    "is_container": False,
                    "status": "not_applicable",
                    "message": "Not running in a container",
                }

            create_time = datetime.fromtimestamp(
                proc1.create_time(), tz=timezone.get_current_timezone()
            )
            uptime_seconds = (timezone.now() - create_time).total_seconds()

            return {
                "is_container": True,
                "container_start_time": create_time.isoformat(),
                "uptime_seconds": int(uptime_seconds),
                "uptime_human": self._format_uptime(uptime_seconds),
                "entrypoint": proc1_name,
                "status": "healthy",
            }
        except Exception as e:
            logger.error(f"Failed to get container uptime: {e}")
            return {
                "is_container": None,
                "status": "error",
                "error": str(e),
            }

    def _get_process_uptime(self, now: datetime) -> Dict[str, Any]:
        """Get current Python process uptime."""
        try:
            # Get the actual process start time from psutil
            current_proc = psutil.Process()
            proc_start = datetime.fromtimestamp(
                current_proc.create_time(), tz=timezone.get_current_timezone()
            )
            uptime_seconds = (now - proc_start).total_seconds()

            return {
                "pid": current_proc.pid,
                "process_name": current_proc.name(),
                "start_time": proc_start.isoformat(),
                "uptime_seconds": int(uptime_seconds),
                "uptime_human": self._format_uptime(uptime_seconds),
                "module_load_time": (
                    _PROCESS_START_TIME.isoformat() if _PROCESS_START_TIME else None
                ),
                "status": "healthy",
            }
        except Exception as e:
            logger.error(f"Failed to get process uptime: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    def _get_celery_worker_uptime(self) -> Dict[str, Any]:
        """
        Get Celery worker process information.

        Uses Celery's inspect API to get worker stats including uptime.
        """
        try:
            from celery import current_app

            # Get worker stats with a short timeout
            inspect = current_app.control.inspect(timeout=1.0)
            if inspect is None:
                return {
                    "status": "error",
                    "error": "Celery inspect returned None",
                }

            stats = inspect.stats() or {}
            workers: Dict[str, Any] = {}

            for worker_name, worker_stats in stats.items():
                # Extract relevant uptime info
                pool_info = worker_stats.get("pool", {})

                # Calculate uptime from broker connection time if available
                broker_info = worker_stats.get("broker", {})

                workers[worker_name] = {
                    "pid": worker_stats.get("pid"),
                    "pool": pool_info.get("implementation", "unknown"),
                    "concurrency": pool_info.get("max-concurrency", 0),
                    "processes": pool_info.get("processes", []),
                    "prefetch_count": worker_stats.get("prefetch_count", 0),
                    "broker_connected": (
                        broker_info.get("connected", False) if broker_info else None
                    ),
                    "status": "healthy",
                }

            if not workers:
                return {
                    "status": "warning",
                    "message": "No Celery workers found",
                    "workers": {},
                }

            return {
                "status": "healthy",
                "worker_count": len(workers),
                "workers": workers,
            }
        except Exception as e:
            logger.error(f"Failed to get Celery worker uptime: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    @staticmethod
    def _format_uptime(seconds: float) -> str:
        """Format uptime seconds into human-readable string."""
        days, remainder = divmod(int(seconds), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, secs = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")

        return " ".join(parts)

    def get_health_summary(self, include_external_apis: bool = False) -> Dict[str, Any]:
        """
        Get comprehensive system health summary.

        Args:
            include_external_apis: Whether to include external API checks (default: False)
                                   Set to False for frequent dashboard updates to avoid
                                   slow external API timeouts.

        Returns:
            Dictionary containing all health metrics
        """
        health_data = {
            "timestamp": timezone.now().isoformat(),
            "cpu": self.get_cpu_usage(),
            "memory": self.get_memory_usage(),
            "database": self.check_database_connection(),
            "redis": self.check_redis_connection(),
            "active_streams": self.get_active_streams_count(),
            "celery_tasks": self.get_celery_tasks_count(),
            "uptime": self.get_uptime_info(),
            "overall_status": self._calculate_overall_status(),
        }

        # Only include external API checks if explicitly requested
        if include_external_apis:
            health_data["oanda_api"] = self.check_oanda_api_connection()

        return health_data

    def _calculate_overall_status(self) -> str:
        """
        Calculate overall system health status.

        Returns:
            Overall status: 'healthy', 'warning', or 'error'
        """
        cpu = self.get_cpu_usage()
        memory = self.get_memory_usage()
        database = self.check_database_connection()
        redis = self.check_redis_connection()

        # Critical services must be healthy
        if database["status"] == "error" or redis["status"] == "error":
            return "error"

        # Warning if CPU or memory is high
        if cpu["status"] == "warning" or memory["status"] == "warning":
            return "warning"

        return "healthy"

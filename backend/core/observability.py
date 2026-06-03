import time
import json
import logging
from logging.handlers import RotatingFileHandler
from functools import wraps
import os

# All metrics/alert output goes through named loggers.
# In production (container) the root handler writes to stdout; set LOG_FILE_DIR
# in the environment to also mirror logs to rotating files.
_LOG_DIR = os.getenv("LOG_FILE_DIR", "")


def _file_handler(filename: str) -> logging.Handler:
    """Return a 10 MB rotating file handler when LOG_FILE_DIR is set, else NullHandler."""
    if not _LOG_DIR:
        return logging.NullHandler()
    os.makedirs(_LOG_DIR, exist_ok=True)
    h = RotatingFileHandler(
        os.path.join(_LOG_DIR, filename),
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
    )
    h.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    return h


_metrics_logger = logging.getLogger("rag_observability")
if not _metrics_logger.handlers:
    _metrics_logger.addHandler(_file_handler("metrics.log"))

_alert_logger = logging.getLogger("rag_alerts")
_alert_logger.setLevel(logging.WARNING)
if not _alert_logger.handlers:
    _alert_logger.addHandler(_file_handler("alerts.log"))


def setup_langsmith():
    if os.getenv("LANGCHAIN_API_KEY"):
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = "Enterprise-RAG-Platform"
        logging.getLogger(__name__).info("LangSmith tracing enabled.")


class MetricsLogger:
    @staticmethod
    def log_request(endpoint: str, user: str, latency_ms: float, success: bool, metadata: dict = None):
        event = {
            "timestamp": time.time(),
            "endpoint": endpoint,
            "user": user,
            "latency_ms": round(latency_ms, 2),
            "success": success,
            "metadata": metadata or {},
        }
        _metrics_logger.info(json.dumps(event))
        AlertManager.check_metrics(latency_ms, success)


def time_execution(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            AlertManager.trigger("CRITICAL_FAILURE", f"Exception in {func.__name__}: {e}")
            raise
        finally:
            _ = (time.time() - start) * 1000  # latency available if needed
    return wrapper


class AlertManager:
    @staticmethod
    def trigger(alert_type: str, message: str):
        _alert_logger.warning("%s: %s", alert_type, message)

    @staticmethod
    def check_metrics(latency_ms: float, success: bool):
        if not success:
            AlertManager.trigger("API_FAILURE", "Request failed.")
        if latency_ms > 5000:
            AlertManager.trigger("HIGH_LATENCY", f"Latency {latency_ms:.0f}ms exceeded 5 s threshold.")
import os
import time
import json
import logging
from functools import wraps
from backend.core.config import settings

# Setup basic logging
logger = logging.getLogger("rag_observability")
logger.setLevel(logging.INFO)
handler = logging.FileHandler("metrics.log")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def setup_langsmith():
    """
    Configures LangSmith tracing if API key is present.
    """
    if os.getenv("LANGCHAIN_API_KEY"):
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = "Enterprise-RAG-Platform"
        logger.info("LangSmith tracing enabled.")
    else:
        # User confirmed no key is fine; suppressing warning to keep logs clean
        pass

class MetricsLogger:
    @staticmethod
    def log_request(endpoint: str, user: str, latency_ms: float, success: bool, metadata: dict = None):
        """
        Logs a structured JSON event for custom metrics analysis.
        """
        event = {
            "timestamp": time.time(),
            "endpoint": endpoint,
            "user": user,
            "latency_ms": latency_ms,
            "success": success,
            "metadata": metadata or {}
        }
        logger.info(json.dumps(event))
        
        # Check for alerts
        AlertManager.check_metrics(latency_ms, success)

# Decorator for timing
def time_execution(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            # Log success handled by caller if needed, or we can move it here.
            # For now, the endpoint handles logging because it has user context.
            return result
        except Exception as e:
            # Alert on critical failures
            AlertManager.trigger("CRITICAL_FAILURE", f"Exception in {func.__name__}: {str(e)}")
            raise e
        finally:
            pass
    return wrapper

class AlertManager:
    logger = logging.getLogger("rag_alerts")
    logger.setLevel(logging.WARNING)
    handler = logging.FileHandler("alerts.log")
    formatter = logging.Formatter('%(asctime)s - [ALERT] - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    @staticmethod
    def trigger(alert_type: str, message: str):
        """
        Triggers an alert. In production, this would send a Slack/Email notification.
        """
        AlertManager.logger.warning(f"{alert_type}: {message}")
        print(f"!!! ALERT [{alert_type}]: {message}") # Visual feedback in console

    @staticmethod
    def check_metrics(latency_ms: float, success: bool):
        if not success:
            AlertManager.trigger("API_FAILURE", "Request failed.")
        if latency_ms > 5000:
            AlertManager.trigger("HIGH_LATENCY", f"Latency {latency_ms:.2f}ms exceeded threshold.")


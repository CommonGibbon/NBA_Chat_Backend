from contextvars import ContextVar
import datetime
from tenacity import RetryCallState

# 1. The magic context variable
# Defaults to None so code runs fine even without the orchestrator
active_log_path: ContextVar[str] = ContextVar("active_log_path", default=None)

def log_to_active_node(message: str):
    """Writes to the log file currently set in context, if any."""
    path = active_log_path.get()
    if path:
        timestamp = datetime.datetime.now().isoformat()
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")

def log_retry_attempt(retry_state: RetryCallState):
    """
    Tenacity 'before_sleep' callback.
    Logs the exception that caused the retry and the wait time.
    """
    if retry_state.outcome.failed:
        exception = retry_state.outcome.exception()
        verb = "Retrying"
        # Calculate wait time
        wait = retry_state.next_action.sleep
        
        msg = (
            f"[RETRY] Attempt {retry_state.attempt_number} failed.\n"
            f"   Error: {type(exception).__name__}: {exception}\n"
            f"   Action: Creating backoff. Sleeping for {wait:.2f}s..."
        )
        log_to_active_node(msg)
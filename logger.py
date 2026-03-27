"""
Central event logger for EasyAuth.
Captures auth events (login, signup, token ops, data access) per service
and stores them in the owner's MongoDB collection for debugging and analytics.
"""

from datetime import datetime, timezone
import database

# ── Event type constants ─────────────────────────────────────────────────────

SIGNUP_SUCCESS    = "signup_success"
SIGNUP_FAIL       = "signup_fail"
LOGIN_SUCCESS     = "login_success"
LOGIN_FAIL        = "login_fail"
TOKEN_ISSUED      = "token_issued"
TOKEN_VERIFIED    = "token_verified"
TOKEN_VERIFY_FAIL = "token_verify_fail"
DATA_READ         = "data_read"
DATA_WRITE        = "data_write"
ERROR             = "error"


def log_event(db, owner, service_name, event, status,
              user_id=None, ip=None, error_message=None, metadata=None):
    """
    Record an auth event for a service.

    Args:
        db           : pymongo database instance
        owner        : Service owner's username (determines which collection stores the log)
        service_name : Name of the service this event belongs to
        event        : Event type constant (e.g. LOGIN_SUCCESS, TOKEN_ISSUED)
        status       : "success" or "failure"
        user_id      : Username of the service user involved (if applicable)
        ip           : Client IP address
        error_message: Human-readable error description (on failure)
        metadata     : Extra context dict (e.g. {"method": "password"})
    """
    entry = {
        "timestamp":     datetime.now(timezone.utc),
        "event":         event,
        "status":        status,
        "user_id":       user_id,
        "ip":            ip,
        "error_message": error_message,
        "metadata":      metadata or {},
    }
    database.insert_log(db, owner, service_name, entry)

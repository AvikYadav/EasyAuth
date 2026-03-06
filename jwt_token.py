import jwt
import uuid
from datetime import datetime, timezone, timedelta

# ── Config ─────────────────────────────────────────────────────────────────────
JWT_SECRET_KEY  = "your-secret-key-change-this-in-production"
JWT_ALGORITHM   = "HS256"
JWT_EXPIRY_HOURS = 5


def generate_token(username: str) -> str:
    """
    Generate a signed JWT token for the given username.

    Args:
        username : The authenticated user's username

    Returns:
        token : Signed JWT string
    """
    payload = {
        "sub": username,                                                    # subject — who the token belongs to
        "jti": str(uuid.uuid4()),                                           # unique token ID
        "iat": datetime.now(timezone.utc),                                  # issued at
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),  # expiry
    }

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    return token

def verify_token(token: str) -> dict | None:
    """
    Decode and verify a JWT token.

    Returns:
        payload : dict with sub, jti, iat, exp  — if valid
        None    : if expired or invalid
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload

    except jwt.ExpiredSignatureError:
        # Token is valid but has expired — client needs to log in again
        return None

    except jwt.InvalidTokenError:
        # Token is tampered with or malformed
        return None

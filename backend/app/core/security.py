"""
Security — Secret redaction, encryption helpers, and JWT utilities.

PRD §15: Encrypt broker tokens and secrets at rest. Never expose secrets to frontend/logs.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

# ────────────────────────── Secret Redaction ──────────────────────────

# Patterns to redact from logs
_SENSITIVE_PATTERNS = [
    re.compile(r'(api[_-]?key\s*[=:]\s*)["\']?[\w\-]+["\']?', re.IGNORECASE),
    re.compile(r'(secret\s*[=:]\s*)["\']?[\w\-]+["\']?', re.IGNORECASE),
    re.compile(r'(password\s*[=:]\s*)["\']?[\w\-]+["\']?', re.IGNORECASE),
    re.compile(r'(token\s*[=:]\s*)["\']?[\w\-]+["\']?', re.IGNORECASE),
    re.compile(r'(authorization\s*[=:]\s*)["\']?Bearer\s+[\w\-\.]+["\']?', re.IGNORECASE),
]

_SENSITIVE_KEYS = {
    "api_key", "api_secret", "secret_key", "password", "access_token",
    "refresh_token", "groq_api_key", "upstox_api_key", "upstox_api_secret",
    "upstox_access_token", "authorization",
}


def redact_sensitive(data: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively redact sensitive values in a dictionary.
    Returns a new dict with secrets replaced by '***REDACTED***'.
    """
    redacted = {}
    for key, value in data.items():
        if key.lower() in _SENSITIVE_KEYS:
            redacted[key] = "***REDACTED***"
        elif isinstance(value, dict):
            redacted[key] = redact_sensitive(value)
        elif isinstance(value, str):
            redacted_value = value
            for pattern in _SENSITIVE_PATTERNS:
                redacted_value = pattern.sub(r"\1***REDACTED***", redacted_value)
            redacted[key] = redacted_value
        else:
            redacted[key] = value
    return redacted


def redact_string(text: str) -> str:
    """Redact sensitive patterns from a string."""
    result = text
    for pattern in _SENSITIVE_PATTERNS:
        result = pattern.sub(r"\1***REDACTED***", result)
    return result


# ────────────────────────── JWT Tokens ──────────────────────────


def create_access_token(
    data: dict[str, Any],
    secret_key: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, secret_key, algorithm="HS256")


def decode_access_token(token: str, secret_key: str) -> dict[str, Any]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}") from e


# ────────────────────────── Encryption Helpers ──────────────────────────


def generate_secret_key(length: int = 32) -> str:
    """Generate a cryptographic random secret key."""
    return secrets.token_hex(length)


def hash_value(value: str) -> str:
    """Create a SHA-256 hash of a value."""
    return hashlib.sha256(value.encode()).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    return hmac.compare_digest(a.encode(), b.encode())


# ────────────────────────── Envelope Encryption Interface ──────────────────────────


class SecretManager:
    """
    KMS-ready secret management interface.

    Phase 1: Uses environment variables.
    Phase 3: Pluggable KMS backend (AWS, GCP, Vault).
    """

    def __init__(self, master_key: str | None = None):
        self._master_key = master_key or os.environ.get("SECRET_KEY", "")

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a secret value. Phase 1: returns hashed placeholder."""
        # Phase 1: Simple HMAC-based wrapping. Replace with AES-256 in Phase 3.
        return hmac.new(
            self._master_key.encode(),
            plaintext.encode(),
            hashlib.sha256,
        ).hexdigest()

    def is_configured(self) -> bool:
        """Check if secret manager has a valid master key."""
        return bool(self._master_key) and self._master_key != "change-me-in-production"

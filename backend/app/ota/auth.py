"""
Authentication, hashing, JWT token handling, and cryptographic signature services.
"""

from datetime import datetime, timedelta
import hashlib
import hmac
import os
import secrets
from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from app.logging.logger import get_logger

logger = get_logger(__name__)

# Security keys (can be overridden via environment)
JWT_SECRET_KEY = os.environ.get("OTA_JWT_SECRET", "ota-admin-jwt-secret-teleprompter-secure-key-2026")
LICENSE_SIGNING_KEY = os.environ.get("OTA_LICENSE_SIGNING_KEY", "teleprompter-license-signing-secret-key-diwakar-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

security_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with random salt."""
    salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    ).hex()
    return f"{salt}:{pw_hash}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Verify password against stored salt:hash."""
    try:
        salt, pw_hash = stored_hash.split(":", 1)
        calc_hash = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            100000,
        ).hex()
        return hmac.compare_digest(pw_hash, calc_hash)
    except Exception as e:
        logger.error("Error verifying password", error=str(e))
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=JWT_EXPIRATION_HOURS))
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except (jwt.PyJWTError, Exception) as e:
        logger.warning("Invalid or expired JWT token", error=str(e))
        return None


def generate_device_token() -> str:
    """Generate a secure cryptographic device token."""
    return secrets.token_urlsafe(32)


def sign_license_payload(payload_dict: Dict[str, Any]) -> str:
    """
    Generate an authoritative HMAC-SHA256 signature for a license response.
    Protects against client-side tampering of usage limits or status.
    """
    message = f"{payload_dict.get('device_id')}:{payload_dict.get('status')}:{payload_dict.get('usage_limit')}:{payload_dict.get('usage_consumed')}"
    sig = hmac.new(
        LICENSE_SIGNING_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return sig


def verify_license_signature(payload_dict: Dict[str, Any], signature: str) -> bool:
    """Verify license response HMAC signature."""
    expected_sig = sign_license_payload(payload_dict)
    return hmac.compare_digest(expected_sig, signature)


async def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> Dict[str, Any]:
    """Dependency: authenticate admin user from Bearer JWT token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload or payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized or invalid admin privileges",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload

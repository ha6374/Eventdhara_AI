import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet
from app.core.config import settings


def get_fernet_cipher() -> Fernet:
    """
    Initializes a Fernet cipher using GOOGLE_TOKEN_ENCRYPTION_KEY or derives
    a deterministic 32-byte url-safe base64 key from SECRET_KEY.
    """
    raw_key = getattr(settings, "GOOGLE_TOKEN_ENCRYPTION_KEY", None)
    if raw_key and len(raw_key.strip()) == 44:
        try:
            return Fernet(raw_key.strip().encode("utf-8"))
        except Exception:
            pass

    # Derive 32-byte key via SHA-256 from SECRET_KEY
    secret = (getattr(settings, "SECRET_KEY", "eventdhara-enterprise-secure-key-2026") or "eventdhara").encode("utf-8")
    derived = hashlib.sha256(secret).digest()
    b64_key = base64.urlsafe_b64encode(derived)
    return Fernet(b64_key)


def encrypt_token(token: Optional[str]) -> Optional[str]:
    """Encrypts sensitive OAuth tokens before storing in database."""
    if not token:
        return None
    cipher = get_fernet_cipher()
    return cipher.encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted: Optional[str]) -> Optional[str]:
    """Decrypts sensitive OAuth tokens for API calls."""
    if not encrypted:
        return None
    cipher = get_fernet_cipher()
    try:
        return cipher.decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except Exception:
        # If decryption fails (e.g. unencrypted legacy token), return original
        return encrypted

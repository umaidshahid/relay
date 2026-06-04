"""
proxy/crypto.py

Fernet-based encryption for provider credentials.

Rules (Constitution §II):
- encrypt_credential / decrypt_credential operate on plaintext strings.
- The key comes from the RELAY_ENCRYPT_KEY environment variable — never from DB.
- decrypt_credential is called only inside the proxy request path; the result
  must not be assigned to any variable that outlives the single request.
- No function here logs the key or the plaintext value.
"""

from __future__ import annotations

from cryptography.fernet import Fernet


def encrypt_credential(plaintext: str, key: bytes) -> str:
    """Encrypt a provider API key with Fernet; return URL-safe base64 ciphertext."""
    f = Fernet(key)
    return f.encrypt(plaintext.encode()).decode()


def decrypt_credential(ciphertext: str, key: bytes) -> str:
    """Decrypt a Fernet ciphertext; raises InvalidToken on tampering."""
    f = Fernet(key)
    return f.decrypt(ciphertext.encode()).decode()


def mask_credential(plaintext: str) -> str:
    """Return ****{last4} masked form; never log or return the full value."""
    if not plaintext:
        return "****"
    suffix = plaintext[-4:] if len(plaintext) >= 4 else plaintext
    return f"****{suffix}"

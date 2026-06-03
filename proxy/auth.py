"""
proxy/auth.py

API key validation for Relay.

authenticate_key() is a pure function — it performs no I/O and has no
database access.  It receives the raw Authorization header value and the
list of configured ApiKey objects, and returns the matching ApiKey or None.
"""

from __future__ import annotations

from proxy.config import ApiKey


def authenticate_key(
    authorization_header: str | None,
    api_keys: list[ApiKey],
) -> ApiKey | None:
    """Validate a Bearer token against the configured API key list.

    Returns the matching ApiKey if found, or None if the header is missing,
    malformed, or the key is not recognised.

    The lookup is O(n) over the key list.  For a weekend-scoped project with
    a handful of keys this is fine; a dict lookup can replace it if needed.
    """
    if not authorization_header:
        return None

    parts = authorization_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    token = parts[1].strip()
    for api_key in api_keys:
        if api_key.key == token:
            return api_key

    return None

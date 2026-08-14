from __future__ import annotations

from urllib.parse import urlparse


_PLACEHOLDER_HOSTS = {"server", "host", "hostname"}


def validate_server_url(value: str) -> str:
    """Validate a Dispatch base URL before starting a retrying client."""
    try:
        parsed = urlparse(value)
        hostname = parsed.hostname
        # Accessing port also validates malformed/non-numeric port values.
        parsed.port
    except ValueError as error:
        raise ValueError(f"invalid Dispatch server URL: {value!r}") from error
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise ValueError(
            "Dispatch server URL must include http:// or https:// and a hostname"
        )
    if hostname.lower() in _PLACEHOLDER_HOSTS:
        raise ValueError(
            f"replace the placeholder host {hostname!r} with 127.0.0.1 "
            "or the actual Dispatch server hostname"
        )
    return value.rstrip("/")

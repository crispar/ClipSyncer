"""TLS bootstrap: integrate the OS trust store via ``truststore``.

Corporate Windows machines typically have the corporate root CA installed
in the Windows certificate store (managed by IT via group policy). Python's
``ssl`` module however defaults to certifi's bundled Mozilla CA list, so
HTTPS to GitHub through a corporate MITM proxy fails with
``CERTIFICATE_VERIFY_FAILED`` even though Edge/Chrome on the same machine
work fine.

``truststore.inject_into_ssl()`` patches Python's ``ssl`` module to use the
OS trust store instead. After injection, every library that builds its
``SSLContext`` from defaults (PyGithub, requests, urllib3, ...) automatically
picks up the corporate CA.

This module provides a single idempotent ``activate()`` call. It is safe on
non-Windows platforms (truststore also supports macOS keychain and Linux
system stores) and on Python builds without truststore installed (logs and
moves on).
"""

import logging
import sys
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level state so other modules can introspect what happened at startup
# without re-running the import. Tests use the same flag.
_active: bool = False
_error: Optional[str] = None


def activate() -> bool:
    """Inject truststore into ssl. Idempotent. Returns True on success.

    Must be called before any HTTPS connection is established - otherwise
    libraries that already cached an SSLContext (or that built one from
    certifi explicitly) will keep using the old store.
    """
    global _active, _error
    if _active:
        return True

    if sys.version_info < (3, 10):
        # truststore officially supports 3.10+. Bail without raising so the
        # app still works on older interpreters with the certifi fallback.
        _error = f"truststore requires Python 3.10+, found {sys.version_info[:2]}"
        return False

    try:
        import truststore  # type: ignore[import-not-found]
    except ImportError as e:
        _error = f"truststore not installed: {e}"
        return False

    try:
        truststore.inject_into_ssl()
    except Exception as e:  # pragma: no cover - defensive
        _error = f"truststore.inject_into_ssl() failed: {e}"
        return False

    _active = True
    return True


def is_active() -> bool:
    """Whether truststore has been successfully injected into ssl."""
    return _active


def last_error() -> Optional[str]:
    """Reason activate() declined to inject (None if it succeeded or wasn't
    called)."""
    return _error

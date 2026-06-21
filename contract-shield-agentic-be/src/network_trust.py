"""TLS trust helpers for corporate Windows environments."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def configure_system_trust() -> None:
    """Inject the OS trust store into Python's SSL stack when available."""
    try:
        import truststore

        truststore.inject_into_ssl()
        logger.debug("Injected system trust store via truststore")
    except ImportError:
        logger.debug("truststore not installed; using default Python SSL trust configuration")

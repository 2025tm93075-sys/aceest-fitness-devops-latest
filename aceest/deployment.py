"""
Runtime deployment metadata.

Kubernetes injects these values through environment variables so every
response can say which version, track and pod served it. This is what makes
rolling, blue-green, canary, A/B and shadow deployments observable from the
outside (curl the endpoint and read the X-* headers or /api/version).
"""

from __future__ import annotations

import os
import socket

from aceest import __version__

VALID_VARIANTS = ("A", "B")
FAULT_MODES = ("", "none", "health")


def deployment_info() -> dict:
    """Snapshot of how this instance was deployed."""
    variant = os.environ.get("UI_VARIANT", "A").upper()
    return {
        "version": __version__,
        "track": os.environ.get("DEPLOYMENT_TRACK", "local"),
        "variant": variant if variant in VALID_VARIANTS else "A",
        "pod": os.environ.get("POD_NAME") or socket.gethostname(),
    }


def fault_mode() -> str:
    """
    Fault injection for rollback drills.

    FAULT_INJECTION=health makes /health and /ready return 503, so Kubernetes
    readiness probes fail, the rollout stalls and the pipeline rolls back.
    """
    mode = os.environ.get("FAULT_INJECTION", "").strip().lower()
    return mode if mode in FAULT_MODES else ""

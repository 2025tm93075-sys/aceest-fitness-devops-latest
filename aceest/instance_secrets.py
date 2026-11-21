"""
Per-installation secrets.

When SECRET_KEY or ADMIN_PASSWORD are not supplied through the environment
(Kubernetes injects them from the aceest-secrets Secret), a random value is
generated once and stored with 0600 permissions in the instance directory.
Every Gunicorn worker in the same container then shares the same value, and
no credential is ever hard-coded in the source.
"""

from __future__ import annotations

import os
import secrets
import tempfile


def load_or_create(directory: str, name: str, nbytes: int = 32) -> tuple[str, bool]:
    """Return (value, created) for the secret file ``directory/name``."""
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, name)
    if not os.path.exists(path):
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=f".{name}.")
        try:
            with os.fdopen(fd, "w") as handle:
                handle.write(secrets.token_urlsafe(nbytes))
            os.chmod(tmp, 0o600)
            try:
                os.link(tmp, path)          # atomic: only one worker wins
                created = True
            except FileExistsError:
                created = False
        finally:
            os.unlink(tmp)
    else:
        created = False
    with open(path, encoding="utf-8") as handle:
        return handle.read().strip(), created

"""
Shared resolver for the canonical resources/ directory.

Why this exists: every module that hardcoded `Path(__file__).resolve().
parents[N]` to find resources/ has been wrong at least once, in
opposite directions, because the directory depth from any given
backend-python/app/... file to resources/ is DIFFERENT depending on
where the code runs:

- Locally: backend-python/app/backend/X.py -> resources/ is 3 parents
  up (...backend-python/app/backend -> app -> backend-python -> repo
  root, where resources/ lives as backend-python's sibling).
- Inside the Docker container: /app/backend/X.py -> resources/ is only
  1 parent up (/app/resources/), because the Dockerfile's
  `COPY backend-python/ /app/` flattens the backend-python/ directory
  away entirely, and a separate `COPY resources/ /app/resources/`
  places the real (root) resources/ directly under /app/.

A fixed parents[N] is correct in exactly one of those two layouts and
silently wrong (often resolving to a path outside the project, or
beyond the root and raising IndexError) in the other - confirmed live:
parents[2] resolves to a nonexistent root-level path, and parents[3]
raises IndexError, when actually run inside the container.

resolve_resources_dir() instead searches upward from the calling
file for a directory containing a resources/product_catalog/
_registry.json - the file that's only ever lived in the true root
resources/, not any backend-python/resources/ duplicate - so it finds
the right directory regardless of which layout is currently running in.
"""

from pathlib import Path
from typing import Optional

_MARKER = Path("resources") / "product_catalog" / "_registry.json"


def resolve_resources_dir(start: Path, max_levels: int = 8) -> Path:
    """Walk up from `start` (a file or directory) until a `resources/`
    directory containing the canonical product catalog is found.
    Falls back to `<start's 3rd ancestor>/resources` (the local-dev
    layout) if no marker is found anywhere, so callers always get a
    Path back rather than an exception - some resources/ subdirectories
    (e.g. a brand new one being created for the first time) won't have
    the marker file yet.
    """
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for _ in range(max_levels):
        if (current / _MARKER).exists():
            return current / "resources"
        if current.parent == current:
            break
        current = current.parent
    # Fallback: best-effort guess matching the local-dev layout.
    fallback = start.resolve()
    if fallback.is_file():
        fallback = fallback.parent
    levels_up = min(3, len(fallback.parts) - 1)
    for _ in range(levels_up):
        fallback = fallback.parent
    return fallback / "resources"

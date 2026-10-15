"""Compatibility façade for app.domains.activities.satellite.

Prefer the domain package for new backend features. Existing imports,
including internal helper names, are retained during this transition.
"""

from app.domains.activities.satellite import *  # noqa: F401,F403
from app.domains.activities import satellite as _implementation

# Preserve pre-existing private helper imports used by tests and integrations.
globals().update({
    key: value for key, value in vars(_implementation).items()
    if key.startswith("_") and not key.startswith("__")
})
del _implementation

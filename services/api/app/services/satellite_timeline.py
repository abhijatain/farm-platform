"""Compatibility façade for app.domains.satellite.timeline.

Prefer the domain package for new backend features. Existing imports,
including internal helper names, are retained during this transition.
"""

from app.domains.satellite.timeline import *  # noqa: F401,F403
from app.domains.satellite import timeline as _implementation

# Preserve pre-existing private helper imports used by tests and integrations.
globals().update({
    key: value for key, value in vars(_implementation).items()
    if key.startswith("_") and not key.startswith("__")
})
del _implementation

from __future__ import annotations

import __main__


def _resolve_version() -> int:
    value = getattr(__main__, "version", 1)
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return 1


version = _resolve_version()
__version__ = str(version)


__all__ = ["version", "__version__"]
